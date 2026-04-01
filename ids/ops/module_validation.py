from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


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
    pythonpath_entries: list[str] = []
    seen: set[str] = set()

    existing_pythonpath = os.environ.get("PYTHONPATH")
    if existing_pythonpath:
        for entry in existing_pythonpath.split(os.pathsep):
            candidate = entry.strip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                pythonpath_entries.append(candidate)

    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in seen:
        seen.add(repo_root)
        pythonpath_entries.append(repo_root)

    for entry in sys.path:
        candidate = str(Path(entry).resolve()) if entry else ""
        if not candidate or candidate in seen or not Path(candidate).exists():
            continue
        seen.add(candidate)
        pythonpath_entries.append(candidate)

    env = dict(os.environ)
    if pythonpath_entries:
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    return env


def resolve_importable_module(
    python_binary: Path,
    module_name: str,
    *,
    name: str,
) -> tuple[str, Path]:
    normalized = clean_module_name(module_name, name=name, allow_blank=True)
    if normalized is None:
        raise ValueError(f"{name} must not be blank")
    import_cwd = None if os.environ.get("PYTHONPATH") else Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            str(Path(python_binary).resolve()),
            "-c",
            (
                "import importlib, json, pathlib; "
                f"name={normalized!r}; "
                "module = importlib.import_module(name); "
                "origin = getattr(module, '__file__', None); "
                "assert origin is not None, f'{name} has no module file'; "
                "print(json.dumps({'origin': str(pathlib.Path(origin).resolve())}))"
            ),
        ],
        cwd=import_cwd,
        env=_build_import_env(),
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(f"{name} is not importable by python_binary: {normalized}")
    try:
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} import check produced invalid output: {normalized}") from exc
    origin = payload.get("origin")
    if not origin:
        raise ValueError(f"{name} import did not expose a module file: {normalized}")
    return normalized, Path(origin).resolve()


def require_importable_module(
    python_binary: Path,
    module_name: str,
    *,
    name: str,
) -> str:
    normalized, _origin = resolve_importable_module(python_binary, module_name, name=name)
    return normalized
