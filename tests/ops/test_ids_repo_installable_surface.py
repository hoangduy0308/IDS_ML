from __future__ import annotations

import json
import tomllib
from pathlib import Path
import subprocess

import repo_installable_proof_support as proof_support
import pytest
from repo_installable_proof_support import (
    REPO_ROOT,
    resolve_console_script,
    run_command,
    scripts_dir,
    venv_python,
)
from tests_editable_install_cache import SHARED_EDITABLE_INSTALL_CACHE_KEY


def _cache_root_from_python(python_path: Path) -> Path:
    return python_path.parent.parent


def _patch_shared_editable_install(
    monkeypatch,
    tmp_path: Path,
    *,
    repo_root: Path,
    executable: Path,
    version_info: tuple[int, int, int],
) -> list[tuple[list[str], Path]]:
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "pyproject.toml").write_text(
        "[project]\nname = 'ids-ml-new'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )

    install_calls: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(proof_support, "REPO_ROOT", repo_root)
    monkeypatch.setattr(proof_support.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(proof_support.sys, "executable", str(executable))
    monkeypatch.setattr(proof_support.sys, "version_info", version_info)

    def fake_venv_python(cache_root: Path) -> Path:
        python_path = cache_root / "venv" / "bin" / "python"
        python_path.parent.mkdir(parents=True, exist_ok=True)
        python_path.write_text("#!/bin/sh\n", encoding="utf-8", newline="\n")
        return python_path.resolve()

    def fake_run_command(
        argv: list[str],
        *,
        cwd: Path = proof_support.REPO_ROOT,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del env
        if "-m" in argv and "pip" in argv and "install" in argv and "-e" in argv:
            install_calls.append((argv, cwd))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def fake_site_packages_dir(python_binary: Path) -> Path:
        site_dir = python_binary.parent.parent / "site-packages"
        site_dir.mkdir(parents=True, exist_ok=True)
        return site_dir

    monkeypatch.setattr(proof_support, "venv_python", fake_venv_python)
    monkeypatch.setattr(proof_support, "run_command", fake_run_command)
    monkeypatch.setattr(proof_support, "site_packages_dir", fake_site_packages_dir)

    return install_calls


def _patch_shared_editable_install_with_probe_results(
    monkeypatch,
    tmp_path: Path,
    *,
    repo_root: Path,
    executable: Path,
    version_info: tuple[int, int, int],
    probe_returncodes: list[int],
) -> tuple[list[tuple[list[str], Path]], list[list[str]], Path]:
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "pyproject.toml").write_text(
        "[project]\nname = 'ids-ml-new'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )

    install_calls: list[tuple[list[str], Path]] = []
    probe_calls: list[list[str]] = []

    monkeypatch.setattr(proof_support, "REPO_ROOT", repo_root)
    monkeypatch.setattr(proof_support.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(proof_support.sys, "executable", str(executable))
    monkeypatch.setattr(proof_support.sys, "version_info", version_info)

    def fake_venv_python(cache_root: Path) -> Path:
        python_path = cache_root / "venv" / "bin" / "python"
        python_path.parent.mkdir(parents=True, exist_ok=True)
        python_path.write_text("#!/bin/sh\n", encoding="utf-8", newline="\n")
        return python_path.resolve()

    def fake_run_command(
        argv: list[str],
        *,
        cwd: Path = proof_support.REPO_ROOT,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del env
        if "-m" in argv and "pip" in argv and "install" in argv and "-e" in argv:
            install_calls.append((argv, cwd))
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if (
            len(argv) >= 4
            and argv[1] == "-I"
            and argv[2] == "-c"
            and argv[3] == "import ids.console.server, ids.ops.operator_console_manage; print('ok')"
        ):
            probe_calls.append(argv)
            index = len(probe_calls) - 1
            returncode = probe_returncodes[index] if index < len(probe_returncodes) else probe_returncodes[-1]
            stdout = "ok\n" if returncode == 0 else ""
            stderr = "" if returncode == 0 else f"probe failed on attempt {index + 1}"
            return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def fake_site_packages_dir(python_binary: Path) -> Path:
        site_dir = python_binary.parent.parent / "site-packages"
        site_dir.mkdir(parents=True, exist_ok=True)
        return site_dir

    monkeypatch.setattr(proof_support, "venv_python", fake_venv_python)
    monkeypatch.setattr(proof_support, "run_command", fake_run_command)
    monkeypatch.setattr(proof_support, "site_packages_dir", fake_site_packages_dir)

    cache_root = (
        Path(tmp_path)
        / f"ids_ml_new_{SHARED_EDITABLE_INSTALL_CACHE_KEY}_{proof_support._editable_install_cache_identity()}"
    )
    return install_calls, probe_calls, cache_root


def test_pyproject_console_scripts_map_to_canonical_modules() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["ids-stack"] == "ids.ops.same_host_stack_manage:main"
    assert scripts["ids-model-bundle-manage"] == "ids.ops.model_bundle_manage:main"
    assert scripts["ids-live-sensor"] == "ids.runtime.live_sensor:main"
    assert scripts["ids-operator-console-server"] == "ids.console.server:main"
    assert scripts["ids-package-final-model"] == "ml_pipeline.packaging.package_final_model:main"
    assert all(not target.startswith("scripts.") for target in scripts.values())


def test_editable_install_surface_exposes_entrypoints_and_console_assets(tmp_path: Path) -> None:
    venv_python_path = venv_python(tmp_path)
    install = run_command(
        [str(venv_python_path), "-m", "pip", "install", "-e", str(REPO_ROOT)],
        cwd=tmp_path,
    )
    assert install.returncode == 0, install.stderr

    scripts_dir_path = scripts_dir(venv_python_path)
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected_scripts: dict[str, str] = pyproject["project"]["scripts"]
    resolved_scripts = {
        command_name: resolve_console_script(scripts_dir_path, command_name)
        for command_name in expected_scripts
    }
    assert all(path.exists() for path in resolved_scripts.values())

    for command_name, script_path in resolved_scripts.items():
        help_run = run_command([str(script_path), "--help"], cwd=tmp_path)
        assert help_run.returncode == 0, f"{command_name}: {help_run.stderr}"
        assert "usage:" in help_run.stdout.lower(), command_name

    inspect = run_command(
        [
            str(venv_python_path),
            "-c",
            (
                "import json, importlib.metadata as md; "
                "from importlib.resources import files; "
                "dist=md.distribution('ids-ml-new'); "
                "eps={ep.name: ep.value for ep in dist.entry_points if ep.group=='console_scripts'}; "
                "print(json.dumps({"
                "'entry_points': eps, "
                "'templates_dir': files('ids.console').joinpath('templates').is_dir(), "
                "'static_dir': files('ids.console').joinpath('static').is_dir()"
                "}))"
            ),
        ],
        cwd=tmp_path,
    )
    assert inspect.returncode == 0, inspect.stderr
    payload = json.loads(inspect.stdout)

    assert payload["entry_points"] == expected_scripts
    assert payload["templates_dir"] is True
    assert payload["static_dir"] is True


def test_shared_editable_repo_python_rekeys_cache_for_checkout_root(monkeypatch, tmp_path: Path) -> None:
    install_calls = _patch_shared_editable_install(
        monkeypatch,
        tmp_path,
        repo_root=tmp_path / "checkout-a",
        executable=tmp_path / "python-a",
        version_info=(3, 11, 9),
    )

    first_python = proof_support.shared_editable_repo_python(SHARED_EDITABLE_INSTALL_CACHE_KEY)

    second_repo_root = tmp_path / "checkout-b"
    second_repo_root.mkdir(parents=True, exist_ok=True)
    (second_repo_root / "pyproject.toml").write_text(
        "[project]\nname = 'ids-ml-new'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(proof_support, "REPO_ROOT", second_repo_root)

    second_python = proof_support.shared_editable_repo_python(SHARED_EDITABLE_INSTALL_CACHE_KEY)

    assert _cache_root_from_python(first_python) != _cache_root_from_python(second_python)
    assert len(install_calls) == 2


def test_shared_editable_repo_python_rekeys_cache_for_interpreter_identity(
    monkeypatch, tmp_path: Path
) -> None:
    install_calls = _patch_shared_editable_install(
        monkeypatch,
        tmp_path,
        repo_root=tmp_path / "checkout",
        executable=tmp_path / "python-a",
        version_info=(3, 11, 9),
    )

    first_python = proof_support.shared_editable_repo_python(SHARED_EDITABLE_INSTALL_CACHE_KEY)

    monkeypatch.setattr(proof_support.sys, "executable", str(tmp_path / "python-b"))
    monkeypatch.setattr(proof_support.sys, "version_info", (3, 12, 1))

    second_python = proof_support.shared_editable_repo_python(SHARED_EDITABLE_INSTALL_CACHE_KEY)

    assert _cache_root_from_python(first_python) != _cache_root_from_python(second_python)
    assert len(install_calls) == 2


def test_shared_editable_repo_python_cleans_stale_shadow_path_without_reinstall(
    monkeypatch, tmp_path: Path
) -> None:
    install_calls = _patch_shared_editable_install(
        monkeypatch,
        tmp_path,
        repo_root=tmp_path / "checkout",
        executable=tmp_path / "python-a",
        version_info=(3, 11, 9),
    )

    python_path = proof_support.shared_editable_repo_python(SHARED_EDITABLE_INSTALL_CACHE_KEY)
    stale_shadow_path = proof_support.site_packages_dir(python_path) / "zz_shadow_import.pth"
    stale_shadow_path.write_text("shadow\n", encoding="utf-8")

    reused_python = proof_support.shared_editable_repo_python(SHARED_EDITABLE_INSTALL_CACHE_KEY)

    assert reused_python == python_path
    assert len(install_calls) == 1
    assert not stale_shadow_path.exists()


def test_shared_editable_repo_python_repairs_after_probe_failure(
    monkeypatch, tmp_path: Path
) -> None:
    install_calls, probe_calls, cache_root = _patch_shared_editable_install_with_probe_results(
        monkeypatch,
        tmp_path,
        repo_root=tmp_path / "checkout",
        executable=tmp_path / "python-a",
        version_info=(3, 11, 9),
        probe_returncodes=[1, 0],
    )

    python_path = proof_support.shared_editable_repo_python(SHARED_EDITABLE_INSTALL_CACHE_KEY)
    stamp_path = cache_root / ".editable-install.stamp"

    assert python_path == (cache_root / "venv" / "bin" / "python").resolve()
    assert len(install_calls) == 2
    assert len(probe_calls) == 2
    assert stamp_path.read_text(encoding="utf-8").strip() == proof_support._editable_install_signature()


def test_shared_editable_repo_python_raises_when_repair_probe_still_fails(
    monkeypatch, tmp_path: Path
) -> None:
    install_calls, probe_calls, cache_root = _patch_shared_editable_install_with_probe_results(
        monkeypatch,
        tmp_path,
        repo_root=tmp_path / "checkout",
        executable=tmp_path / "python-a",
        version_info=(3, 11, 9),
        probe_returncodes=[1, 1],
    )

    with pytest.raises(AssertionError, match="probe failed on attempt 2"):
        proof_support.shared_editable_repo_python(SHARED_EDITABLE_INSTALL_CACHE_KEY)

    stamp_path = cache_root / ".editable-install.stamp"

    assert len(install_calls) == 2
    assert len(probe_calls) == 2
    assert stamp_path.read_text(encoding="utf-8").strip() == proof_support._editable_install_signature()
