from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

_MODULE_ORIGIN_SCRIPT = """
from __future__ import annotations

import json
from pathlib import Path
import sys

def _find_spec_without_import(fullname: str, search_path: list[str] | None):
    for finder in sys.meta_path:
        method = getattr(finder, "find_spec", None)
        if method is None:
            continue
        try:
            spec = method(fullname, search_path)
        except TypeError:
            spec = method(fullname, search_path, None)
        if spec is not None:
            return spec
    return None

name = sys.argv[1]
parts = name.split(".")
qualified_name = ""
search_path = None
spec = None
for index, part in enumerate(parts):
    qualified_name = part if not qualified_name else f"{qualified_name}.{part}"
    spec = _find_spec_without_import(qualified_name, search_path)
    assert spec is not None, f"{name} is not importable"
    if index < len(parts) - 1:
        search_path = list(spec.submodule_search_locations or [])
        assert search_path, f"{name} parent package is not importable"
origin = getattr(spec, "origin", None)
assert origin and origin not in {"built-in", "frozen"}, f"{name} has no module origin"
print(json.dumps({"origin": str(Path(origin).resolve())}))
"""

_MODULE_IMPORT_PROOF_SCRIPT = """
from __future__ import annotations

import importlib
import sys

importlib.import_module(sys.argv[1])
"""


def clean_module_name(value: str | None, *, name: str, allow_blank: bool = True) -> str | None:
    normalized = None if value is None else str(value).strip()
    if not normalized:
        if allow_blank:
            return None
        raise ValueError(f"{name} must not be blank")
    if any(part.strip() == "" for part in normalized.split(".")):
        raise ValueError(f"{name} must be a dotted Python module path")
    return normalized


def _build_import_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONSAFEPATH", None)
    return env


def _run_module_check(
    python_binary: Path,
    script: str,
    module_name: str,
) -> subprocess.CompletedProcess[str]:
    resolved_python = Path(python_binary).resolve()
    return subprocess.run(
        [
            str(resolved_python),
            "-I",
            "-c",
            script,
            module_name,
        ],
        cwd=resolved_python.parent,
        env=_build_import_env(),
        capture_output=True,
        check=False,
        text=True,
    )


def resolve_importable_module(
    python_binary: Path,
    module_name: str,
    *,
    name: str,
    trusted_root: Path | None = None,
    trusted_root_label: str = "trusted_root",
) -> tuple[str, Path]:
    normalized = clean_module_name(module_name, name=name, allow_blank=True)
    if normalized is None:
        raise ValueError(f"{name} must not be blank")
    completed = _run_module_check(python_binary, _MODULE_ORIGIN_SCRIPT, normalized)
    if completed.returncode != 0:
        raise ValueError(f"{name} is not importable by python_binary: {normalized}")
    try:
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} import check produced invalid output: {normalized}") from exc
    origin = payload.get("origin")
    if not origin:
        raise ValueError(f"{name} import did not expose a module file: {normalized}")
    origin_path = Path(origin).resolve()
    if not origin_path.exists():
        raise ValueError(f"{name} import resolved to a missing module file: {normalized}")
    if trusted_root is not None:
        trusted_root_path = Path(trusted_root).resolve()
        try:
            origin_path.relative_to(trusted_root_path)
        except ValueError as exc:
            raise ValueError(f"{name} resolved outside {trusted_root_label}: {origin_path}") from exc
    proof = _run_module_check(python_binary, _MODULE_IMPORT_PROOF_SCRIPT, normalized)
    if proof.returncode != 0:
        raise ValueError(f"{name} failed to import in python_binary: {normalized}")
    return normalized, origin_path


def require_importable_module(
    python_binary: Path,
    module_name: str,
    *,
    name: str,
    trusted_root: Path | None = None,
    trusted_root_label: str = "trusted_root",
) -> str:
    normalized, _origin = resolve_importable_module(
        python_binary,
        module_name,
        name=name,
        trusted_root=trusted_root,
        trusted_root_label=trusted_root_label,
    )
    return normalized
