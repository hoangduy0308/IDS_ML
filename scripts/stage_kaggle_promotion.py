from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


DEFAULT_OUTPUT_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\kaggle_promotion")
DEFAULT_UPLOAD_ROOT = Path(r"F:\Work\IDS_ML_New\kaggle\promotion_notebooks")
DEFAULT_DATASET_ID = "hdiiii/cic-iot-diad-2024"

FINALISTS = {
    "catboost_trial_008": {
        "title": "IDS Promotion CatBoost Trial 008",
        "model_key": "catboost",
        "enable_gpu": True,
        "train_attack_cap": 1_500_000,
        "train_benign_cap": None,
        "fit_val_attack_cap": 250_000,
        "fit_val_benign_cap": None,
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
    "catboost_trial_012": {
        "title": "IDS Promotion CatBoost Trial 012",
        "model_key": "catboost",
        "enable_gpu": True,
        "train_attack_cap": 1_500_000,
        "train_benign_cap": None,
        "fit_val_attack_cap": 250_000,
        "fit_val_benign_cap": None,
        "model_params": {
            "depth": 8,
            "learning_rate": 0.10681,
            "iterations": 500,
            "l2_leaf_reg": 5,
            "random_strength": 2.0,
            "bagging_temperature": 1.0,
            "border_count": 254,
            "attack_weight_multiplier": 1.15,
        },
    },
    "hist_gb_trial_003": {
        "title": "IDS Promotion HistGB Trial 003",
        "model_key": "hist_gb",
        "enable_gpu": False,
        "train_attack_cap": 1_000_000,
        "train_benign_cap": None,
        "fit_val_attack_cap": None,
        "fit_val_benign_cap": None,
        "model_params": {
            "learning_rate": 0.02,
            "max_iter": 600,
            "max_leaf_nodes": 127,
            "min_samples_leaf": 200,
            "l2_regularization": 1.0,
            "max_bins": 255,
        },
    },
    "random_forest_trial_010": {
        "title": "IDS Promotion Random Forest Trial 010",
        "model_key": "random_forest",
        "enable_gpu": False,
        "train_attack_cap": 600_000,
        "train_benign_cap": None,
        "fit_val_attack_cap": None,
        "fit_val_benign_cap": None,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage Kaggle promotion-run notebooks for finalist IDS models.")
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


def upload_name(index: int, finalist_key: str) -> str:
    return f"{index:02d}_{finalist_key}_promotion.ipynb"


def build_readme(dataset_id: str) -> str:
    return f"""# Kaggle Promotion Notebooks

Bo notebook này dùng để chạy `promotion run` cho 4 cấu hình finalist sau vòng coarse tuning.

Dataset cần attach:

- `{dataset_id}`

Các notebook:

- `01_catboost_trial_008_promotion.ipynb`
- `02_catboost_trial_012_promotion.ipynb`
- `03_hist_gb_trial_003_promotion.ipynb`
- `04_random_forest_trial_010_promotion.ipynb`

Mỗi notebook sẽ:

- gắn sẵn hyperparameter finalist
- train trên tập train mở rộng hơn vòng coarse
- evaluate full `val`, `test`, `ood_attack_holdout`
- ghi output vào `/kaggle/working/<run_key>_promotion_results`

Lưu ý:

- Đây là `promotion run`, không còn random search
- `CatBoost` sẽ bật GPU nếu Kaggle cấp GPU
- `Random Forest` và `HistGB` vẫn là CPU-only
- Các notebook train trên train sample mở rộng có cap để phù hợp RAM/CPU/GPU của Kaggle, không ép nạp toàn bộ 18M+ dòng vào memory
"""


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    upload_root = args.upload_root.resolve()
    kernels_root = output_root / "kernels"
    ensure_clean_dir(kernels_root)
    ensure_clean_dir(upload_root)

    template_path = Path(r"F:\Work\IDS_ML_New\kaggle\kernel_template\promotion_run_template.py")
    dataset_slug = args.dataset_id.split("/", 1)[1]

    for index, (finalist_key, spec) in enumerate(FINALISTS.items(), start=1):
        kernel_dir = kernels_root / finalist_key
        kernel_dir.mkdir(parents=True, exist_ok=True)
        notebook_name = upload_name(index, finalist_key)
        rendered = render_template(
            template_path,
            {
                "%%RUN_KEY%%": finalist_key,
                "%%MODEL_KEY%%": str(spec["model_key"]),
                "%%MODEL_TITLE%%": str(spec["title"]),
                "%%DATASET_SLUG%%": dataset_slug,
                "%%SEED%%": str(args.seed),
                "%%BATCH_SIZE%%": str(args.batch_size),
                "%%TRAIN_ATTACK_CAP%%": "None" if spec["train_attack_cap"] is None else str(spec["train_attack_cap"]),
                "%%TRAIN_BENIGN_CAP%%": "None" if spec["train_benign_cap"] is None else str(spec["train_benign_cap"]),
                "%%FIT_VAL_ATTACK_CAP%%": "None" if spec["fit_val_attack_cap"] is None else str(spec["fit_val_attack_cap"]),
                "%%FIT_VAL_BENIGN_CAP%%": "None" if spec["fit_val_benign_cap"] is None else str(spec["fit_val_benign_cap"]),
                "%%MODEL_PARAMS_JSON%%": json.dumps(spec["model_params"], ensure_ascii=False),
            },
        )
        write_json(kernel_dir / notebook_name, notebook_payload(rendered))
        write_json(
            kernel_dir / "kernel-metadata.json",
            {
                "id": f"hdiiii/{finalist_key}",
                "title": spec["title"],
                "code_file": notebook_name,
                "language": "python",
                "kernel_type": "notebook",
                "is_private": "true",
                "enable_gpu": "true" if spec["enable_gpu"] else "false",
                "enable_tpu": "false",
                "enable_internet": "false",
                "dataset_sources": [args.dataset_id],
                "competition_sources": [],
                "kernel_sources": [],
                "model_sources": [],
            },
        )
        (kernel_dir / "README.md").write_text(
            f"# {spec['title']}\n\nUpload notebook `{notebook_name}` lên Kaggle và attach dataset `{args.dataset_id}`.\n",
            encoding="utf-8",
        )
        shutil.copy2(kernel_dir / notebook_name, upload_root / notebook_name)

    (upload_root / "README.md").write_text(build_readme(args.dataset_id), encoding="utf-8")


if __name__ == "__main__":
    main()
