from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
import subprocess


_DIAGNOSTIC_LIMIT = 500
_DIAGNOSTIC_SUFFIX = "..."


def _truncate_diagnostic(value: str | None, *, max_chars: int = _DIAGNOSTIC_LIMIT, suffix: str = _DIAGNOSTIC_SUFFIX) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    allowed = max(max_chars - len(suffix), 0)
    return f"{text[:allowed].rstrip()}{suffix}"


def _diagnostic_suffix(*entries: tuple[str, str | None]) -> str:
    fragments = []
    for label, value in entries:
        trimmed = _truncate_diagnostic(value)
        if trimmed:
            fragments.append(f"{label}={trimmed}")
    if not fragments:
        return ""
    return f" (diagnostic: {'; '.join(fragments)})"


def _module_validation_error(summary: str, *, stderr: str | None = None, origin: str | None = None) -> ValueError:
    return ValueError(f"{summary}{_diagnostic_suffix(('stderr', stderr), ('origin', origin))}")


_MODULE_VALIDATION_SCRIPT = """
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys

def _call_finder(method, fullname, search_path):
    try:
        return method(fullname, search_path)
    except TypeError:
        try:
            return method(fullname, search_path, None)
        except Exception:
            return None
    except Exception:
        return None

def _find_spec_without_import(fullname: str, search_path: list[str] | None):
    for finder in sys.meta_path:
        method = getattr(finder, "find_spec", None)
        if method is None:
            continue
        spec = _call_finder(method, fullname, search_path)
        if spec is not None:
            return spec
    return None

def _fail(kind: str, *, origin: str | None = None):
    payload = {"ok": False, "error": kind}
    if origin is not None:
        payload["origin"] = origin
    print(json.dumps(payload))
    raise SystemExit(0)

name = sys.argv[1]
trusted_root_arg = sys.argv[2] or None
parts = name.split(".")
qualified_name = ""
search_path = None
origins = []

trusted_root = Path(trusted_root_arg).resolve() if trusted_root_arg is not None else None

spec = None
for index, part in enumerate(parts):
    qualified_name = part if not qualified_name else f"{qualified_name}.{part}"
    spec = _find_spec_without_import(qualified_name, search_path)
    if spec is None:
        _fail("not_importable")
    origin = getattr(spec, "origin", None)
    if not origin or origin in {"built-in", "frozen"}:
        _fail("no_origin")
    origin_path = Path(origin).resolve()
    origins.append(str(origin_path))
    if trusted_root is not None:
        try:
            origin_path.relative_to(trusted_root)
        except ValueError:
            _fail("outside_trusted_root", origin=str(origin_path))
    if index < len(parts) - 1:
        search_path = list(spec.submodule_search_locations or [])
        if not search_path:
            _fail("not_importable")
try:
    importlib.import_module(name)
except Exception:
    _fail("import_failed", origin=str(origin_path))
print(json.dumps({"ok": True, "origins": origins, "origin": origins[-1]}))
"""


def _call_finder(method, fullname, search_path):
    try:
        return method(fullname, search_path)
    except TypeError:
        try:
            return method(fullname, search_path, None)
        except Exception:
            return None
    except Exception:
        return None


def _find_spec_without_import(fullname: str, search_path: list[str] | None):
    for finder in sys.meta_path:
        method = getattr(finder, "find_spec", None)
        if method is None:
            continue
        spec = _call_finder(method, fullname, search_path)
        if spec is not None:
            return spec
    return None


_MODULE_NAME_SEGMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def clean_module_name(value: str | None, *, name: str, allow_blank: bool = True) -> str | None:
    normalized = None if value is None else str(value).strip()
    if not normalized:
        if allow_blank:
            return None
        raise ValueError(f"{name} must not be blank")
    if any(part.strip() == "" for part in normalized.split(".")):
        raise ValueError(f"{name} must be a dotted Python module path")
    for part in normalized.split("."):
        if not _MODULE_NAME_SEGMENT.fullmatch(part):
            raise ValueError(f"{name} must be a dotted Python module path")
    return normalized


def _build_import_env() -> dict[str, str]:
    # defense-in-depth: drop every PYTHON*-prefixed variable from the environment
    return {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}


def _run_module_check(
    python_binary: Path,
    script: str,
    *script_args: str,
) -> subprocess.CompletedProcess[str]:
    resolved_python = Path(python_binary).resolve()
    return subprocess.run(
        [
            str(resolved_python),
            "-I",
            "-c",
            script,
            *script_args,
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
    trusted_root_arg = ""
    if trusted_root is not None:
        trusted_root_arg = str(Path(trusted_root).resolve())
    completed = _run_module_check(
        python_binary,
        _MODULE_VALIDATION_SCRIPT,
        normalized,
        trusted_root_arg,
    )
    if completed.returncode != 0:
        raise _module_validation_error(
            f"{name} is not importable by python_binary: {normalized}",
            stderr=completed.stderr,
        )
    try:
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise _module_validation_error(
            f"{name} import check produced invalid output: {normalized}",
            stderr=completed.stderr,
        ) from exc
    error = payload.get("error")
    if error == "not_importable":
        raise _module_validation_error(
            f"{name} is not importable by python_binary: {normalized}",
            stderr=completed.stderr,
        )
    if error == "no_origin":
        raise _module_validation_error(
            f"{name} import did not expose a module file: {normalized}",
            stderr=completed.stderr,
        )
    if error == "outside_trusted_root":
        origin = payload.get("origin")
        if not origin:
            raise _module_validation_error(
                f"{name} import did not expose a module file: {normalized}",
                stderr=completed.stderr,
            )
        raise _module_validation_error(
            f"{name} resolved outside {trusted_root_label}: {normalized}",
            stderr=completed.stderr,
            origin=origin,
        )
    if error == "import_failed":
        raise _module_validation_error(
            f"{name} failed to import in python_binary: {normalized}",
            stderr=completed.stderr,
            origin=payload.get("origin"),
        )
    origins = payload.get("origins") or []
    if not isinstance(origins, list):
        if payload.get("origin"):
            origins = [payload["origin"]]
    if not origins:
        raise _module_validation_error(
            f"{name} import did not expose a module file: {normalized}",
            stderr=completed.stderr,
        )
    resolved_origins = []
    for origin_value in origins:
        if not origin_value:
            raise _module_validation_error(
                f"{name} import did not expose a module file: {normalized}",
                stderr=completed.stderr,
            )
        origin_path = Path(origin_value).resolve()
        if not origin_path.exists():
            raise _module_validation_error(
                f"{name} import resolved to a missing module file: {normalized}",
                stderr=completed.stderr,
                origin=str(origin_path),
            )
        resolved_origins.append(origin_path)
    return normalized, resolved_origins[-1]
