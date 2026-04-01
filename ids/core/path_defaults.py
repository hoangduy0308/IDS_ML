from __future__ import annotations

import os
from pathlib import Path


DEFAULT_REPO_ROOT_ENV_VAR = "IDS_REPO_ROOT"
DEFAULT_REPO_ROOT = Path("/opt/ids_ml_new")
DEFAULT_RUNTIME_ACTIVATION_PATH = Path("/var/lib/ids-live-sensor/active_bundle.json")


def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def resolve_repo_root(*, env_var: str = DEFAULT_REPO_ROOT_ENV_VAR) -> Path:
    env_value = _clean_env(os.environ.get(env_var))
    if env_value is not None:
        return Path(env_value).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def resolve_repo_path(*parts: str, repo_root: Path | None = None) -> Path:
    root = repo_root or resolve_repo_root()
    return root.joinpath(*parts).resolve()


DEFAULT_RUNTIME_COMPAT_BUNDLE_ROOT = resolve_repo_path(
    "artifacts",
    "final_model",
    "catboost_full_data_v1",
)
DEFAULT_RUNTIME_COMPAT_MODEL_PATH = DEFAULT_RUNTIME_COMPAT_BUNDLE_ROOT / "model.cbm"
DEFAULT_RUNTIME_COMPAT_FEATURE_COLUMNS_PATH = (
    DEFAULT_RUNTIME_COMPAT_BUNDLE_ROOT / "feature_columns.json"
)


__all__ = [
    "DEFAULT_REPO_ROOT",
    "DEFAULT_REPO_ROOT_ENV_VAR",
    "DEFAULT_RUNTIME_ACTIVATION_PATH",
    "DEFAULT_RUNTIME_COMPAT_BUNDLE_ROOT",
    "DEFAULT_RUNTIME_COMPAT_FEATURE_COLUMNS_PATH",
    "DEFAULT_RUNTIME_COMPAT_MODEL_PATH",
    "resolve_repo_path",
    "resolve_repo_root",
]
