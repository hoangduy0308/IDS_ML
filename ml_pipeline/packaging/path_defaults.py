from __future__ import annotations

from ids.core.path_defaults import (
    DEFAULT_REPO_ROOT,
    DEFAULT_REPO_ROOT_ENV_VAR,
    resolve_repo_path,
    resolve_repo_root,
)


DEFAULT_PACKAGING_SOURCE_ROOT = resolve_repo_path(
    "artifacts",
    "kaggle",
    "outputs",
    "catboost_full_data_attempt",
    "catboost_full_data_attempt_results",
)
DEFAULT_PACKAGING_MODEL_PATH = DEFAULT_PACKAGING_SOURCE_ROOT / "catboost_full_data_attempt.cbm"
DEFAULT_PACKAGING_FEATURE_COLUMNS_PATH = resolve_repo_path(
    "artifacts",
    "cic_iot_diad_2024_binary",
    "manifests",
    "feature_columns.json",
)
DEFAULT_PACKAGING_SUMMARY_PATH = DEFAULT_PACKAGING_SOURCE_ROOT / "reports" / "summary.csv"
DEFAULT_PACKAGING_TRAINING_SUMMARY_PATH = (
    DEFAULT_PACKAGING_SOURCE_ROOT / "reports" / "training_summary.json"
)
DEFAULT_PACKAGING_THRESHOLD_SELECTION_PATH = resolve_repo_path(
    "artifacts",
    "posttrain_analysis",
    "scaling_finalists",
    "reports",
    "catboost_full_threshold_selection.json",
)
DEFAULT_PACKAGING_BUNDLE_ROOT = resolve_repo_path(
    "artifacts",
    "final_model",
    "catboost_full_data_v1",
)


__all__ = [
    "DEFAULT_REPO_ROOT",
    "DEFAULT_REPO_ROOT_ENV_VAR",
    "DEFAULT_PACKAGING_BUNDLE_ROOT",
    "DEFAULT_PACKAGING_FEATURE_COLUMNS_PATH",
    "DEFAULT_PACKAGING_MODEL_PATH",
    "DEFAULT_PACKAGING_SOURCE_ROOT",
    "DEFAULT_PACKAGING_SUMMARY_PATH",
    "DEFAULT_PACKAGING_THRESHOLD_SELECTION_PATH",
    "DEFAULT_PACKAGING_TRAINING_SUMMARY_PATH",
    "resolve_repo_path",
    "resolve_repo_root",
]
