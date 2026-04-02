from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ids.ops import module_validation
from ids.ops.module_validation import _build_import_env, resolve_importable_module


def test_build_import_env_scrubs_python_contamination_vars(monkeypatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "C:/hostile/pythonpath")
    monkeypatch.setenv("PYTHONSTARTUP", "C:/hostile/startup.py")
    monkeypatch.setenv("PYTHONOPTIMIZE", "2")
    monkeypatch.setenv("IDS_TEST_SENTINEL", "kept")

    env = _build_import_env()

    assert all(not key.startswith("PYTHON") for key in env)
    assert env["IDS_TEST_SENTINEL"] == "kept"


def test_build_import_env_returns_copy_of_process_environment(monkeypatch) -> None:
    monkeypatch.setenv("IDS_TEST_COPY_CHECK", "original")

    env = _build_import_env()
    env["IDS_TEST_COPY_CHECK"] = "mutated"

    assert os.environ["IDS_TEST_COPY_CHECK"] == "original"


def test_build_import_env_preserves_non_python_vars(monkeypatch) -> None:
    monkeypatch.setenv("PATH", "original:path")
    monkeypatch.setenv("PYTHONWARNINGS", "default")

    env = _build_import_env()

    assert env["PATH"] == "original:path"
    assert "PYTHONWARNINGS" not in env


def _make_completed(
    stdout: str,
    *,
    returncode: int = 0,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_resolve_importable_module_blank_name_raises() -> None:
    python_binary = Path(sys.executable)
    with pytest.raises(ValueError, match="must not be blank"):
        resolve_importable_module(python_binary, "", name="module")


def test_resolve_importable_module_process_failure(monkeypatch) -> None:
    stderr_message = "missing dependency"
    monkeypatch.setattr(
        module_validation,
        "_run_module_check",
        lambda *args, **kwargs: _make_completed("", returncode=1, stderr=stderr_message),
    )
    with pytest.raises(ValueError) as excinfo:
        resolve_importable_module(Path(sys.executable), "ids.module", name="module")
    message = str(excinfo.value)
    assert "is not importable" in message
    assert f"diagnostic: stderr={stderr_message}" in message


def test_resolve_importable_module_process_failure_truncates_stderr(monkeypatch) -> None:
    long_stderr = "X" * 600
    monkeypatch.setattr(
        module_validation,
        "_run_module_check",
        lambda *args, **kwargs: _make_completed("", returncode=1, stderr=long_stderr),
    )
    with pytest.raises(ValueError) as excinfo:
        resolve_importable_module(Path(sys.executable), "ids.module", name="module")
    message = str(excinfo.value)
    assert "diagnostic: stderr=" in message
    limit = 500 - len("...")
    expected = f"{long_stderr[:limit]}..."
    assert expected in message


def test_resolve_importable_module_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(
        module_validation,
        "_run_module_check",
        lambda *args, **kwargs: _make_completed("not-json"),
    )
    with pytest.raises(ValueError, match="produced invalid output"):
        resolve_importable_module(Path(sys.executable), "ids.module", name="module")


def test_resolve_importable_module_missing_origin(monkeypatch) -> None:
    monkeypatch.setattr(
        module_validation,
        "_run_module_check",
        lambda *args, **kwargs: _make_completed(json.dumps({"ok": True})),
    )
    with pytest.raises(ValueError, match="did not expose a module file"):
        resolve_importable_module(Path(sys.executable), "ids.module", name="module")


def test_resolve_importable_module_outside_trusted_root(tmp_path, monkeypatch) -> None:
    payload = {"error": "outside_trusted_root", "origin": str(tmp_path / "outside.py")}
    monkeypatch.setattr(
        module_validation,
        "_run_module_check",
        lambda *args, **kwargs: _make_completed(json.dumps(payload)),
    )
    with pytest.raises(ValueError, match="resolved outside"):
        resolve_importable_module(
            Path(sys.executable),
            "ids.module",
            name="module",
            trusted_root=tmp_path,
        )


def test_resolve_importable_module_import_failed(monkeypatch, tmp_path) -> None:
    payload = {"error": "import_failed", "origin": str(tmp_path / "mod.py")}
    monkeypatch.setattr(
        module_validation,
        "_run_module_check",
        lambda *args, **kwargs: _make_completed(json.dumps(payload)),
    )
    with pytest.raises(ValueError, match="failed to import"):
        resolve_importable_module(Path(sys.executable), "ids.module", name="module")


def test_resolve_importable_module_missing_file(tmp_path, monkeypatch) -> None:
    payload = {"ok": True, "origins": [str(tmp_path / "missing.py")]}
    monkeypatch.setattr(
        module_validation,
        "_run_module_check",
        lambda *args, **kwargs: _make_completed(json.dumps(payload)),
    )
    with pytest.raises(ValueError, match="missing module file"):
        resolve_importable_module(Path(sys.executable), "ids.module", name="module")


def test_resolve_importable_module_rejects_hostile_intermediate(monkeypatch, tmp_path) -> None:
    payload = {
        "error": "outside_trusted_root",
        "origin": str(tmp_path / "hostile" / "__init__.py"),
    }
    monkeypatch.setattr(
        module_validation,
        "_run_module_check",
        lambda *args, **kwargs: _make_completed(json.dumps(payload)),
    )
    with pytest.raises(ValueError) as excinfo:
        resolve_importable_module(
            Path(sys.executable),
            "ids.console.server",
            name="module",
            trusted_root=tmp_path / "trusted",
            trusted_root_label="repo_root",
        )
    message = str(excinfo.value)
    assert "resolved outside repo_root" in message
    assert "diagnostic: origin=" in message
    assert payload["origin"] in message


def test_find_spec_skips_faulty_meta_path(monkeypatch):
    class BadFinder:
        def find_spec(self, fullname, search_path):
            raise ImportError("fail")

    class GoodFinder:
        def find_spec(self, fullname, search_path):
            spec = type("Spec", (), {"origin": str(Path(__file__).resolve())})
            return spec

    original_meta_path = list(sys.meta_path)
    monkeypatch.setattr(sys, "meta_path", [BadFinder(), GoodFinder()])
    spec = module_validation._find_spec_without_import("ids.module", None)
    assert spec is not None
    monkeypatch.setattr(sys, "meta_path", original_meta_path)


def test_find_spec_handles_type_error_retry(monkeypatch):
    class TypeErrorFinder:
        def __init__(self):
            self.called = 0

        def find_spec(self, fullname, search_path, maybe=None):
            self.called += 1
            if self.called == 1:
                raise TypeError("needs three args")
            spec = type("Spec", (), {"origin": str(Path(__file__).resolve())})
            return spec

    finder = TypeErrorFinder()
    original_meta_path = list(sys.meta_path)
    monkeypatch.setattr(sys, "meta_path", [finder])
    spec = module_validation._find_spec_without_import("ids.module", None)
    assert spec is not None
    assert finder.called == 2
    monkeypatch.setattr(sys, "meta_path", original_meta_path)

def test_clean_module_name_rejects_non_identifier_segments() -> None:
    with pytest.raises(ValueError, match="must be a dotted Python module path"):
        module_validation.clean_module_name("ids..console", name="module", allow_blank=False)
    with pytest.raises(ValueError, match="must be a dotted Python module path"):
        module_validation.clean_module_name("ids.console-evil", name="module", allow_blank=False)
    with pytest.raises(ValueError, match="must be a dotted Python module path"):
        module_validation.clean_module_name("ids.console.", name="module", allow_blank=False)


def test_clean_module_name_allows_valid_segments() -> None:
    name = module_validation.clean_module_name("ids.console.server", name="module", allow_blank=False)
    assert name == "ids.console.server"
