from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


DEFAULT_DATASET_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary")
DEFAULT_OUTPUT_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\kaggle")
DEFAULT_DATASET_ID = "hdiiii/cic-iot-diad-2024"

DATA_FILES = [
    "train.parquet",
    "val.parquet",
    "test.parquet",
    "ood_attack_holdout.parquet",
]
MANIFEST_FILES = [
    "file_manifest.csv",
    "quarantine_manifest.csv",
    "cleaning_report.json",
    "feature_columns.json",
]
MODEL_SPECS = {
    "logreg": {
        "title": "IDS Binary Logistic Regression",
        "kernel_slug": "ids-binary-logistic-regression",
        "enable_gpu": False,
    },
    "random_forest": {
        "title": "IDS Binary Random Forest",
        "kernel_slug": "ids-binary-random-forest",
        "enable_gpu": False,
    },
    "hist_gb": {
        "title": "IDS Binary Hist Gradient Boosting",
        "kernel_slug": "ids-binary-hist-gradient-boosting",
        "enable_gpu": False,
    },
    "catboost": {
        "title": "IDS Binary CatBoost",
        "kernel_slug": "ids-binary-catboost",
        "enable_gpu": True,
    },
    "mlp": {
        "title": "IDS Binary MLP",
        "kernel_slug": "ids-binary-mlp",
        "enable_gpu": True,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage frozen IDS dataset and Kaggle kernels for parallel benchmark runs.")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--dataset-id", type=str, default=DEFAULT_DATASET_ID)
    parser.add_argument("--license-name", type=str, default="CC0-1.0")
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def link_or_copy(src: Path, dst: Path) -> None:
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def dataset_readme(cleaning_report: dict, dataset_id: str) -> str:
    rows_by_split = cleaning_report["rows_by_split"]
    label_distribution = cleaning_report["label_distribution_by_split"]
    return f"""# CIC IoT-DIAD 2024 Binary IDS Benchmark

Frozen preprocessing output for Kaggle benchmark runs.

Dataset ID target: `{dataset_id}`

## Contents

- `train.parquet`
- `val.parquet`
- `test.parquet`
- `ood_attack_holdout.parquet`
- `file_manifest.csv`
- `quarantine_manifest.csv`
- `cleaning_report.json`
- `feature_columns.json`

## Split Summary

- train: {rows_by_split['train']:,} rows
- val: {rows_by_split['val']:,} rows
- test: {rows_by_split['test']:,} rows
- ood_attack_holdout: {rows_by_split['ood_attack_holdout']:,} rows

## Label Distribution

- train: Attack={label_distribution['train']['Attack']:,}, Benign={label_distribution['train']['Benign']:,}
- val: Attack={label_distribution['val']['Attack']:,}, Benign={label_distribution['val']['Benign']:,}
- test: Attack={label_distribution['test']['Attack']:,}, Benign={label_distribution['test']['Benign']:,}
- ood_attack_holdout: Attack={label_distribution['ood_attack_holdout']['Attack']:,}

## Notes

- Split is frozen by `source_file`, not by row.
- `BruteForce` and `Recon` are excluded from train/val/test and kept in `ood_attack_holdout.parquet`.
- Leakage columns were removed before export: `Flow ID`, `Src IP`, `Dst IP`, `Timestamp`, `Label`.
- `feature_columns.json` is the final train-time feature list after zero-variance filtering.
"""


def kernel_readme(model_key: str, title: str, dataset_id: str) -> str:
    accelerator = "GPU" if MODEL_SPECS[model_key]["enable_gpu"] else "CPU"
    return f"""# {title}

Kaggle kernel bundle for `{model_key}` on the frozen binary IDS split.

Dataset source:

- `{dataset_id}`
- Preferred accelerator: `{accelerator}`

Outputs written to `/kaggle/working/{model_key}_results`:

- `metrics.json`
- `summary.csv`
- `training_summary.json`
- model artifact (`.joblib` or `.cbm`)
"""


def render_template(template_path: Path, replacements: dict[str, str]) -> str:
    text = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def stage_dataset_bundle(
    dataset_root: Path,
    output_root: Path,
    dataset_id: str,
    license_name: str,
) -> Path:
    bundle_dir = output_root / "datasets" / dataset_id.split("/", 1)[1]
    ensure_clean_dir(bundle_dir)

    clean_dir = dataset_root / "clean"
    manifest_dir = dataset_root / "manifests"
    cleaning_report = read_json(manifest_dir / "cleaning_report.json")

    for file_name in DATA_FILES:
        link_or_copy(clean_dir / file_name, bundle_dir / file_name)
    for file_name in MANIFEST_FILES:
        link_or_copy(manifest_dir / file_name, bundle_dir / file_name)

    write_json(
        bundle_dir / "dataset-metadata.json",
        {
            "title": "CIC IoT-DIAD 2024 Binary IDS Benchmark",
            "id": dataset_id,
            "licenses": [{"name": license_name}],
        },
    )
    (bundle_dir / "README.md").write_text(
        dataset_readme(cleaning_report, dataset_id),
        encoding="utf-8",
    )
    return bundle_dir


def stage_kernel_bundles(output_root: Path, dataset_id: str) -> list[Path]:
    kernels_root = output_root / "kernels"
    ensure_clean_dir(kernels_root)
    template_path = Path(r"F:\Work\IDS_ML_New\kaggle\kernel_template\train_binary_ids_template.py")
    dataset_slug = dataset_id.split("/", 1)[1]
    kernel_dirs: list[Path] = []

    for model_key, spec in MODEL_SPECS.items():
        kernel_dir = kernels_root / model_key
        kernel_dir.mkdir(parents=True, exist_ok=True)

        script_name = f"train_{model_key}.py"
        rendered = render_template(
            template_path,
            {
                "%%MODEL_KEY%%": model_key,
                "%%MODEL_TITLE%%": spec["title"],
                "%%DATASET_SLUG%%": dataset_slug,
            },
        )
        (kernel_dir / script_name).write_text(rendered, encoding="utf-8")
        write_json(
            kernel_dir / "kernel-metadata.json",
            {
                "id": f"hdiiii/{spec['kernel_slug']}",
                "title": spec["title"],
                "code_file": script_name,
                "language": "python",
                "kernel_type": "script",
                "is_private": "true",
                "enable_gpu": "true" if spec["enable_gpu"] else "false",
                "enable_tpu": "false",
                "enable_internet": "true",
                "dataset_sources": [dataset_id],
                "competition_sources": [],
                "kernel_sources": [],
                "model_sources": [],
            },
        )
        (kernel_dir / "README.md").write_text(
            kernel_readme(model_key, spec["title"], dataset_id),
            encoding="utf-8",
        )
        kernel_dirs.append(kernel_dir)
    return kernel_dirs


def write_helper_scripts(output_root: Path, dataset_bundle_dir: Path, kernel_dirs: list[Path]) -> None:
    create_lines = [
        f'kaggle datasets create -p "{dataset_bundle_dir}" -q',
        "",
    ]
    version_lines = [
        f'kaggle datasets version -p "{dataset_bundle_dir}" -m "Refresh frozen binary IDS split" -q',
        "",
    ]
    push_lines = [f'kaggle kernels push -p "{kernel_dir}"' for kernel_dir in kernel_dirs]
    status_lines = [
        f'kaggle kernels status "hdiiii/{MODEL_SPECS[kernel_dir.name]["kernel_slug"]}"'
        for kernel_dir in kernel_dirs
    ]

    (output_root / "create_dataset_private.ps1").write_text("\n".join(create_lines), encoding="utf-8")
    (output_root / "version_dataset.ps1").write_text("\n".join(version_lines), encoding="utf-8")
    (output_root / "push_kernels.ps1").write_text("\n".join(push_lines) + "\n", encoding="utf-8")
    (output_root / "kernel_status.ps1").write_text("\n".join(status_lines) + "\n", encoding="utf-8")


def validate_inputs(dataset_root: Path) -> None:
    clean_dir = dataset_root / "clean"
    manifest_dir = dataset_root / "manifests"
    for file_name in DATA_FILES:
        path = clean_dir / file_name
        if not path.exists():
            raise FileNotFoundError(f"Missing required dataset split: {path}")
    for file_name in MANIFEST_FILES:
        path = manifest_dir / file_name
        if not path.exists():
            raise FileNotFoundError(f"Missing required manifest file: {path}")


def main() -> None:
    args = parse_args()
    dataset_root = args.dataset_root.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    validate_inputs(dataset_root)

    log("Staging Kaggle dataset bundle")
    dataset_bundle_dir = stage_dataset_bundle(
        dataset_root=dataset_root,
        output_root=output_root,
        dataset_id=args.dataset_id,
        license_name=args.license_name,
    )
    log("Staging Kaggle kernel bundles")
    kernel_dirs = stage_kernel_bundles(output_root=output_root, dataset_id=args.dataset_id)
    write_helper_scripts(output_root=output_root, dataset_bundle_dir=dataset_bundle_dir, kernel_dirs=kernel_dirs)
    log(f"Dataset bundle ready at {dataset_bundle_dir}")
    log(f"Kernel bundles ready under {output_root / 'kernels'}")


if __name__ == "__main__":
    main()
