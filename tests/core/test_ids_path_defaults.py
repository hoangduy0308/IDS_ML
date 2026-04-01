from __future__ import annotations

from pathlib import Path

from ids.core import path_defaults


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

    assert path_defaults.resolve_repo_root() == Path(path_defaults.__file__).resolve().parents[2]


def test_resolve_repo_root_falls_back_to_checkout_when_default_root_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(path_defaults.DEFAULT_REPO_ROOT_ENV_VAR, raising=False)
    monkeypatch.setattr(path_defaults, "DEFAULT_REPO_ROOT", tmp_path / "missing-linux-root")

    resolved = path_defaults.resolve_repo_root()

    assert resolved == Path(path_defaults.__file__).resolve().parents[2]


def test_resolve_repo_path_uses_explicit_repo_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo-root"
    repo_root.mkdir()

    resolved = path_defaults.resolve_repo_path("artifacts", "final_model", repo_root=repo_root)

    assert resolved == (repo_root / "artifacts" / "final_model").resolve()
