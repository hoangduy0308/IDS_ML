from __future__ import annotations

from pathlib import Path
import subprocess


def clean_module_name(value: str | None, *, name: str, allow_blank: bool = True) -> str | None:
    normalized = None if value is None else str(value).strip()
    if not normalized:
        if allow_blank:
            return None
        raise ValueError(f"{name} must not be blank")
    if any(part.strip() == "" for part in normalized.split(".")):
        raise ValueError(f"{name} must be a dotted Python module path")
    return normalized


def require_importable_module(
    python_binary: Path,
    module_name: str,
    *,
    name: str,
) -> str:
    normalized = clean_module_name(module_name, name=name, allow_blank=True)
    if normalized is None:
        raise ValueError(f"{name} must not be blank")
    completed = subprocess.run(
        [
            str(Path(python_binary).resolve()),
            "-c",
            (
                "import importlib.util, sys; "
                f"name={normalized!r}; "
                "sys.exit(0 if importlib.util.find_spec(name) is not None else 1)"
            ),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(f"{name} is not importable by python_binary: {normalized}")
    return normalized
