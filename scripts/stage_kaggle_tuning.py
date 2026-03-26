from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


DEFAULT_OUTPUT_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\kaggle_tuning")
DEFAULT_DATASET_ID = "hdiiii/cic-iot-diad-2024"

MODEL_SPECS = {
    "catboost": {
        "title": "IDS Binary CatBoost",
        "kernel_slug": "ids-binary-catboost",
        "enable_gpu": True,
        "trials": 16,
        "promote": 2,
    },
    "random_forest": {
        "title": "IDS Binary Random Forest",
        "kernel_slug": "ids-binary-random-forest",
        "enable_gpu": False,
        "trials": 10,
        "promote": 1,
    },
    "hist_gb": {
        "title": "IDS Binary Hist Gradient Boosting",
        "kernel_slug": "ids-binary-hist-gradient-boosting",
        "enable_gpu": False,
        "trials": 12,
        "promote": 1,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage Kaggle kernels for top-model hyperparameter tuning.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--dataset-id", type=str, default=DEFAULT_DATASET_ID)
    parser.add_argument("--profile", choices=["quick", "full"], default="quick")
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--eval-max-rows", type=int, default=100_000)
    parser.add_argument("--ood-max-rows", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--checkpoint-every", type=int, default=1)
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


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


def kernel_readme(model_key: str, spec: dict[str, object], dataset_id: str, profile: str) -> str:
    accelerator = "GPU" if spec["enable_gpu"] else "CPU"
    return f"""# {spec['title']}

Kernel tuning riêng cho `{model_key}` trên dataset Kaggle `{dataset_id}`.

- profile: `{profile}`
- accelerator: `{accelerator}`
- trials: `{spec['trials']}`
- output: `/kaggle/working/{model_key}_tuning_results`

Artifacts chính:

- `trial_results.csv`
- `trial_results_ranked.csv`
- `best_configs.json`
- `progress.json`
"""


def stage_kernel_bundles(args: argparse.Namespace) -> list[Path]:
    kernels_root = args.output_root / "kernels"
    ensure_clean_dir(kernels_root)
    template_path = Path(r"F:\Work\IDS_ML_New\kaggle\kernel_template\tune_top_models_template.py")
    dataset_slug = args.dataset_id.split("/", 1)[1]
    kernel_dirs: list[Path] = []

    for model_key, spec in MODEL_SPECS.items():
        kernel_dir = kernels_root / model_key
        kernel_dir.mkdir(parents=True, exist_ok=True)

        notebook_name = f"{model_key}_tuning.ipynb"
        rendered = render_template(
            template_path,
            {
                "%%MODEL_KEY%%": model_key,
                "%%MODEL_TITLE%%": str(spec["title"]),
                "%%DATASET_SLUG%%": dataset_slug,
                "%%TRIALS%%": str(spec["trials"]),
                "%%PROMOTE%%": str(spec["promote"]),
                "%%PROFILE%%": args.profile,
                "%%BATCH_SIZE%%": str(args.batch_size),
                "%%EVAL_MAX_ROWS%%": str(args.eval_max_rows),
                "%%OOD_MAX_ROWS%%": str(args.ood_max_rows),
                "%%SEED%%": str(args.seed),
                "%%CHECKPOINT_EVERY%%": str(args.checkpoint_every),
            },
        )
        write_json(kernel_dir / notebook_name, notebook_payload(rendered))

        write_json(
            kernel_dir / "kernel-metadata.json",
            {
                "id": f"hdiiii/{spec['kernel_slug']}",
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
        (kernel_dir / "README.md").write_text(kernel_readme(model_key, spec, args.dataset_id, args.profile), encoding="utf-8")
        kernel_dirs.append(kernel_dir)
    return kernel_dirs


def write_helper_scripts(output_root: Path, kernel_dirs: list[Path]) -> None:
    push_lines = [f'kaggle kernels push -p "{kernel_dir}"' for kernel_dir in kernel_dirs]
    status_lines = [f'kaggle kernels status "hdiiii/{MODEL_SPECS[kernel_dir.name]["kernel_slug"]}"' for kernel_dir in kernel_dirs]
    output_lines = [
        f'kaggle kernels output "hdiiii/{MODEL_SPECS[kernel_dir.name]["kernel_slug"]}" -p "{output_root / "outputs" / kernel_dir.name}"'
        for kernel_dir in kernel_dirs
    ]

    (output_root / "push_tuning_kernels.ps1").write_text("\n".join(push_lines) + "\n", encoding="utf-8")
    (output_root / "tuning_kernel_status.ps1").write_text("\n".join(status_lines) + "\n", encoding="utf-8")
    (output_root / "download_tuning_outputs.ps1").write_text("\n".join(output_lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    log("Staging Kaggle tuning kernels")
    kernel_dirs = stage_kernel_bundles(args)
    write_helper_scripts(output_root, kernel_dirs)
    log(f"Tuning kernel bundles ready under {output_root / 'kernels'}")


if __name__ == "__main__":
    main()
