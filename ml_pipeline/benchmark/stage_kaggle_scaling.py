from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


DEFAULT_OUTPUT_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\kaggle_scaling")
DEFAULT_UPLOAD_ROOT = Path(r"F:\Work\IDS_ML_New\kaggle\scaling_notebooks")
DEFAULT_DATASET_ID = "hdiiii/cic-iot-diad-2024"

MODEL_BASE_CONFIGS = {
    "catboost": {
        "title": "IDS Scaling CatBoost",
        "enable_gpu": True,
        "fit_val_caps": {
            "2m": {"attack": 300_000, "benign": None},
            "4m": {"attack": 500_000, "benign": None},
            "8m": {"attack": 800_000, "benign": None},
            "full": {"attack": 1_000_000, "benign": None},
        },
        "model_params": {
            "depth": 10,
            "learning_rate": 0.09698,
            "iterations": 500,
            "l2_leaf_reg": 5,
            "random_strength": 0.0,
            "bagging_temperature": 0.5,
            "border_count": 64,
            "attack_weight_multiplier": 1.3,
        },
    },
    "hist_gb": {
        "title": "IDS Scaling HistGB",
        "enable_gpu": False,
        "fit_val_caps": {
            "2m": {"attack": None, "benign": None},
            "4m": {"attack": None, "benign": None},
            "8m": {"attack": None, "benign": None},
        },
        "model_params": {
            "learning_rate": 0.02,
            "max_iter": 600,
            "max_leaf_nodes": 127,
            "min_samples_leaf": 200,
            "l2_regularization": 1.0,
            "max_bins": 255,
        },
    },
    "random_forest": {
        "title": "IDS Scaling Random Forest",
        "enable_gpu": False,
        "fit_val_caps": {
            "2m": {"attack": None, "benign": None},
            "4m": {"attack": None, "benign": None},
            "8m": {"attack": None, "benign": None},
        },
        "model_params": {
            "n_estimators": 400,
            "max_depth": 24,
            "min_samples_leaf": 4,
            "min_samples_split": 10,
            "max_features": "sqrt",
            "max_samples": 0.35,
        },
    },
}

RUN_MATRIX = [
    {"run_key": "catboost_2m_scaling", "model_key": "catboost", "size_label": "2m", "train_target_rows": 2_000_000},
    {"run_key": "catboost_4m_scaling", "model_key": "catboost", "size_label": "4m", "train_target_rows": 4_000_000},
    {"run_key": "catboost_8m_scaling", "model_key": "catboost", "size_label": "8m", "train_target_rows": 8_000_000},
    {"run_key": "hist_gb_2m_scaling", "model_key": "hist_gb", "size_label": "2m", "train_target_rows": 2_000_000},
    {"run_key": "hist_gb_4m_scaling", "model_key": "hist_gb", "size_label": "4m", "train_target_rows": 4_000_000},
    {"run_key": "hist_gb_8m_scaling", "model_key": "hist_gb", "size_label": "8m", "train_target_rows": 8_000_000},
    {"run_key": "random_forest_2m_scaling", "model_key": "random_forest", "size_label": "2m", "train_target_rows": 2_000_000},
    {"run_key": "random_forest_4m_scaling", "model_key": "random_forest", "size_label": "4m", "train_target_rows": 4_000_000},
    {"run_key": "random_forest_8m_scaling", "model_key": "random_forest", "size_label": "8m", "train_target_rows": 8_000_000},
    {"run_key": "catboost_full_data_attempt", "model_key": "catboost", "size_label": "full", "train_target_rows": None},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage Kaggle scaling-experiment notebooks for IDS models.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--upload-root", type=Path, default=DEFAULT_UPLOAD_ROOT)
    parser.add_argument("--dataset-id", type=str, default=DEFAULT_DATASET_ID)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=131_072)
    return parser.parse_args()


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def render_template(template_path: Path, replacements: dict[str, str]) -> str:
    text = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


def notebook_payload(code: str) -> dict:
    return {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": code.splitlines(keepends=True),
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def upload_name(index: int, run_key: str) -> str:
    return f"{index:02d}_{run_key}.ipynb"


def build_readme(dataset_id: str) -> str:
    return f"""# Kaggle Scaling Notebooks

Bộ notebook này dùng để chạy `data-scaling experiment` cho 3 mô hình chính:

- `CatBoost`
- `HistGradientBoosting`
- `RandomForest`

Dataset cần attach:

- `{dataset_id}`

Các mốc dữ liệu:

- `2M`
- `4M`
- `8M`

Ngoài ra có thêm:

- `CatBoost full-data attempt`

Tổng cộng có 10 notebook, mỗi notebook đại diện cho một cặp:

- `model x train_size`

Mỗi notebook sẽ:

- dùng đúng một cấu hình hyperparameter finalist theo model
- train với `train_target_rows` cố định
- evaluate full `val`, `test`, `ood_attack_holdout`
- ghi output vào `/kaggle/working/<run_key>_results`

Ghi chú:

- đây là thí nghiệm công bằng theo `train size`
- `CatBoost` sẽ bật GPU nếu Kaggle cấp GPU
- `HistGB` và `RandomForest` vẫn là CPU-only
- notebook `CatBoost full-data attempt` là nhánh triển khai, không dùng để so sánh công bằng theo train size
"""


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    upload_root = args.upload_root.resolve()
    kernels_root = output_root / "kernels"
    ensure_clean_dir(kernels_root)
    ensure_clean_dir(upload_root)

    template_path = Path(r"F:\Work\IDS_ML_New\kaggle\kernel_template\scaling_experiment_template.py")
    dataset_slug = args.dataset_id.split("/", 1)[1]

    for index, run_spec in enumerate(RUN_MATRIX, start=1):
        model_spec = MODEL_BASE_CONFIGS[run_spec["model_key"]]
        caps = model_spec["fit_val_caps"][run_spec["size_label"]]
        kernel_dir = kernels_root / run_spec["run_key"]
        kernel_dir.mkdir(parents=True, exist_ok=True)
        notebook_name = upload_name(index, run_spec["run_key"])

        rendered = render_template(
            template_path,
            {
                "%%RUN_KEY%%": run_spec["run_key"],
                "%%MODEL_KEY%%": run_spec["model_key"],
                "%%MODEL_TITLE%%": f"{model_spec['title']} {run_spec['size_label']}",
                "%%DATASET_SLUG%%": dataset_slug,
                "%%SEED%%": str(args.seed),
                "%%BATCH_SIZE%%": str(args.batch_size),
                "%%TRAIN_TARGET_ROWS%%": str(run_spec["train_target_rows"]),
                "%%FIT_VAL_ATTACK_CAP%%": "None" if caps["attack"] is None else str(caps["attack"]),
                "%%FIT_VAL_BENIGN_CAP%%": "None" if caps["benign"] is None else str(caps["benign"]),
                "%%MODEL_PARAMS_JSON%%": json.dumps(model_spec["model_params"], ensure_ascii=False),
            },
        )
        write_json(kernel_dir / notebook_name, notebook_payload(rendered))
        write_json(
            kernel_dir / "kernel-metadata.json",
            {
                "id": f"hdiiii/{run_spec['run_key']}",
                "title": f"{model_spec['title']} {run_spec['size_label']}",
                "code_file": notebook_name,
                "language": "python",
                "kernel_type": "notebook",
                "is_private": "true",
                "enable_gpu": "true" if model_spec["enable_gpu"] else "false",
                "enable_tpu": "false",
                "enable_internet": "false",
                "dataset_sources": [args.dataset_id],
                "competition_sources": [],
                "kernel_sources": [],
                "model_sources": [],
            },
        )
        (kernel_dir / "README.md").write_text(
            f"# {model_spec['title']} {run_spec['size_label']}\n\nUpload notebook `{notebook_name}` lên Kaggle và attach dataset `{args.dataset_id}`.\n",
            encoding="utf-8",
        )
        shutil.copy2(kernel_dir / notebook_name, upload_root / notebook_name)

    (upload_root / "README.md").write_text(build_readme(args.dataset_id), encoding="utf-8")


if __name__ == "__main__":
    main()
