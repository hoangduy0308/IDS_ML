from __future__ import annotations

import importlib
from pathlib import Path

from ids.core import path_defaults


REPO_ROOT = Path(__file__).resolve().parents[2]


def _reload_path_defaults(monkeypatch, repo_root: Path | None) -> None:
    env_var = path_defaults.DEFAULT_REPO_ROOT_ENV_VAR
    if repo_root is None:
        monkeypatch.delenv(env_var, raising=False)
    else:
        monkeypatch.setenv(env_var, str(repo_root))

    importlib.reload(path_defaults)


def test_resolve_repo_root_prefers_env_override(monkeypatch, tmp_path: Path) -> None:
    overridden_root = tmp_path / "env-root"
    overridden_root.mkdir()
    monkeypatch.setenv(path_defaults.DEFAULT_REPO_ROOT_ENV_VAR, str(overridden_root))

    assert path_defaults.resolve_repo_root() == overridden_root.resolve()


def test_resolve_repo_root_ignores_existing_default_linux_root(monkeypatch, tmp_path: Path) -> None:
    linux_root = tmp_path / "opt" / "ids_ml_new"
    linux_root.mkdir(parents=True)
    monkeypatch.delenv(path_defaults.DEFAULT_REPO_ROOT_ENV_VAR, raising=False)
    monkeypatch.setattr(path_defaults, "DEFAULT_REPO_ROOT", linux_root)

    assert path_defaults.resolve_repo_root() == REPO_ROOT


def test_resolve_repo_root_falls_back_to_checkout_when_default_root_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(path_defaults.DEFAULT_REPO_ROOT_ENV_VAR, raising=False)
    monkeypatch.setattr(path_defaults, "DEFAULT_REPO_ROOT", tmp_path / "missing-linux-root")

    resolved = path_defaults.resolve_repo_root()

    assert resolved == REPO_ROOT


def test_resolve_repo_path_uses_explicit_repo_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo-root"
    repo_root.mkdir()

    resolved = path_defaults.resolve_repo_path("artifacts", "final_model", repo_root=repo_root)

    assert resolved == (repo_root / "artifacts" / "final_model").resolve()


def test_runtime_compat_bundle_root_follows_repo_root_override(monkeypatch, tmp_path: Path) -> None:
    repo_root = (tmp_path / "override-root").resolve()

    _reload_path_defaults(monkeypatch, repo_root)

    expected_bundle_root = repo_root / "artifacts" / "final_model" / "catboost_full_data_v1"
    assert path_defaults.DEFAULT_RUNTIME_COMPAT_BUNDLE_ROOT == expected_bundle_root
    assert path_defaults.DEFAULT_RUNTIME_COMPAT_MODEL_PATH == expected_bundle_root / "model.cbm"
    assert (
        path_defaults.DEFAULT_RUNTIME_COMPAT_FEATURE_COLUMNS_PATH
        == expected_bundle_root / "feature_columns.json"
    )


def test_runtime_compat_bundle_root_falls_back_to_checkout_when_env_is_unset(monkeypatch) -> None:
    _reload_path_defaults(monkeypatch, None)

    checkout_root = REPO_ROOT
    expected_bundle_root = checkout_root / "artifacts" / "final_model" / "catboost_full_data_v1"
    assert path_defaults.DEFAULT_RUNTIME_COMPAT_BUNDLE_ROOT == expected_bundle_root
    assert path_defaults.DEFAULT_RUNTIME_COMPAT_MODEL_PATH == expected_bundle_root / "model.cbm"
    assert (
        path_defaults.DEFAULT_RUNTIME_COMPAT_FEATURE_COLUMNS_PATH
        == expected_bundle_root / "feature_columns.json"
    )
