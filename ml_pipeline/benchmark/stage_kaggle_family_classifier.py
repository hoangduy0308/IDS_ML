from __future__ import annotations

import argparse
import json
import shutil
import textwrap
from pathlib import Path


DEFAULT_OUTPUT_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\kaggle")
DEFAULT_BUNDLE_ROOT = DEFAULT_OUTPUT_ROOT / "kernels" / "family_classifier"
DEFAULT_DATASET_ID = "hdiiii/cic-iot-diad-2024"
DEFAULT_KERNEL_ID = "hdiiii/ids-stage2-family-classifier-full-data"
DEFAULT_KERNEL_TITLE = "Ids Stage2 Family Classifier Full Data"
DEFAULT_TRAINING_SCRIPT = Path(r"F:\Work\IDS_ML_New\ml_pipeline\training\train_iot_diad_family_classifier.py")
DEFAULT_GPU_DEVICES = "0"
DEFAULT_MAX_TRAIN_ROWS = 25_000_000
DEFAULT_ITERATIONS = 500
DEFAULT_CLASS_WEIGHT_EXPONENT = 0.5
DEFAULT_REPORT_CONTRACT = Path(
    r"F:\Work\IDS_ML_New\artifacts\modeling\cic_iot_diad_2024_family_views\family_classifier\reports\oracle_family_eval.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage a Kaggle kernel bundle for the full-data stage-2 family classifier.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--dataset-id", type=str, default=DEFAULT_DATASET_ID)
    parser.add_argument("--kernel-id", type=str, default=DEFAULT_KERNEL_ID)
    parser.add_argument("--title", type=str, default=DEFAULT_KERNEL_TITLE)
    parser.add_argument("--training-script-path", type=Path, default=DEFAULT_TRAINING_SCRIPT)
    parser.add_argument("--gpu-devices", type=str, default=DEFAULT_GPU_DEVICES)
    parser.add_argument("--max-train-rows", type=int, default=DEFAULT_MAX_TRAIN_ROWS)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--class-weight-exponent", type=float, default=DEFAULT_CLASS_WEIGHT_EXPONENT)
    parser.add_argument("--report-contract-path", type=Path, default=DEFAULT_REPORT_CONTRACT)
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_readme(
    title: str,
    dataset_id: str,
    report_contract_path: Path,
    gpu_devices: str,
    max_train_rows: int,
    iterations: int,
    class_weight_exponent: float,
) -> str:
    dataset_name = dataset_id.split("/", 1)[1]
    kaggle_dataset_root = f"/kaggle/input/{dataset_name}/{dataset_name}-binary-ids"
    output_dir = "/kaggle/working/family_classifier_results"
    report_path = f"{output_dir}/reports/oracle_family_eval.json"
    return f"""# {title}

Kaggle script kernel bundle for the full-data stage-2 family classifier.

Dataset source:

- `{dataset_id}`
- Expected Kaggle path in this bundle: `{kaggle_dataset_root}`
- Preferred accelerator: `GPU`
- GPU devices default in this bundle: `{gpu_devices}`
- This kernel bootstraps `family_views` automatically if the attached dataset only contains the frozen binary artifact.
- `max_train_rows` default in this bundle: `{max_train_rows}`
- `iterations` default in this bundle: `{iterations}`
- `class_weight_exponent` default in this bundle: `{class_weight_exponent}`

Runtime outputs:

- `{output_dir}/models/catboost_family_classifier.cbm`
- `{report_path}`

How to bring the report back into this repo:

1. Run the Kaggle kernel against `{dataset_id}`.
2. Download `{report_path}` from Kaggle.
3. Place that JSON at `{report_contract_path.as_posix()}` in the repo.
4. Use the imported report to calibrate stage-2 abstention thresholds before runtime wiring.

Bundle contents:

- `kernel-metadata.json`
- `README.md`
- `train_family_classifier.py`
"""


def strip_training_main(source_text: str) -> str:
    marker = '\n\nif __name__ == "__main__":\n    main()\n'
    if marker in source_text:
        return source_text.replace(marker, "\n", 1)
    return source_text


def build_bootstrap_main(dataset_id: str) -> str:
    dataset_name = dataset_id.split("/", 1)[1]
    kaggle_dataset_root = f"/kaggle/input/{dataset_name}/{dataset_name}-binary-ids"
    return textwrap.dedent(
        f"""
        SOURCE_SPLITS = ("train", "val", "test", "ood_attack_holdout")
        OOD_FAMILIES = {{"BruteForce", "Recon"}}
        KNOWN_ATTACK_FAMILIES = ["DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"]
        METADATA_COLUMNS = [
            "source_file",
            "attack_family",
            "attack_scenario",
            "derived_label_binary",
            "derived_label_family",
            "split",
        ]


        class BootstrapSplitWriter:
            def __init__(self, path: Path) -> None:
                self.path = path
                self.writer = None

            def write_df(self, frame: pd.DataFrame) -> None:
                if frame.empty:
                    return
                table = pa.Table.from_pandas(frame, preserve_index=False)
                if self.writer is None:
                    self.writer = pq.ParquetWriter(self.path, table.schema, compression="snappy")
                self.writer.write_table(table)

            def close(self) -> None:
                if self.writer is not None:
                    self.writer.close()


        def candidate_roots(preferred_root: Path) -> list[Path]:
            roots: list[Path] = []
            seen: set[str] = set()

            def add(path: Path) -> None:
                candidate = Path(path)
                key = str(candidate)
                if key not in seen:
                    seen.add(key)
                    roots.append(candidate)

            add(preferred_root)
            add(Path("/kaggle/input"))
            kaggle_input = Path("/kaggle/input")
            if kaggle_input.exists():
                for child in sorted(kaggle_input.iterdir()):
                    if child.is_dir():
                        add(child)
            return roots


        def discover_family_view_root(preferred_root: Path) -> Path | None:
            for base in candidate_roots(preferred_root):
                if not base.exists():
                    continue
                direct_manifest = base / "manifests" / "family_view_index.json"
                if direct_manifest.exists():
                    return base
                flat_manifest = base / "family_view_index.json"
                if flat_manifest.exists():
                    return base
                for hit in sorted(base.rglob("family_view_index.json")):
                    if hit.parent.name == "manifests":
                        return hit.parent.parent
                    return hit.parent
            return None


        def discover_binary_root(preferred_root: Path) -> Path | None:
            def is_binary_root(candidate: Path) -> bool:
                has_cleaning_report = (candidate / "manifests" / "cleaning_report.json").exists() or (candidate / "cleaning_report.json").exists()
                has_train_split = (candidate / "clean" / "train.parquet").exists() or (candidate / "train.parquet").exists()
                return has_cleaning_report and has_train_split

            for base in candidate_roots(preferred_root):
                if not base.exists():
                    continue
                if is_binary_root(base):
                    return base
                manifest_hits = sorted(base.rglob("cleaning_report.json"))
                for hit in manifest_hits:
                    candidate = hit.parent.parent if hit.parent.name == "manifests" else hit.parent
                    if is_binary_root(candidate):
                        return candidate
            return None


        def ensure_bootstrap_clean_dir(path: Path) -> None:
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)


        def filter_attack_only(frame: pd.DataFrame, split_name: str) -> pd.DataFrame:
            if split_name == "ood_attack_holdout":
                return frame[frame["derived_label_family"].isin(sorted(OOD_FAMILIES))].copy()
            return frame[frame["derived_label_family"].isin(KNOWN_ATTACK_FAMILIES)].copy()


        def derive_family_views_from_binary(source_root: Path, output_root: Path) -> Path:
            ensure_bootstrap_clean_dir(output_root)
            manifests_dir = output_root / "manifests"
            manifests_dir.mkdir(parents=True, exist_ok=True)

            feature_columns_payload = read_json(resolve_dataset_file(source_root, "manifests/feature_columns.json", "feature_columns.json"))
            feature_columns = list(feature_columns_payload["feature_columns"])
            write_json(manifests_dir / "feature_columns.json", feature_columns_payload)

            clean_dir = output_root / "attack_only" / "clean"
            manifest_dir = output_root / "attack_only" / "manifests"
            clean_dir.mkdir(parents=True, exist_ok=True)
            manifest_dir.mkdir(parents=True, exist_ok=True)

            rows_by_split: dict[str, int] = {{}}
            label_distribution_by_split: dict[str, dict[str, int]] = {{}}
            for split_name in SOURCE_SPLITS:
                writer = BootstrapSplitWriter(clean_dir / f"{{split_name}}.parquet")
                label_counts: dict[str, int] = {{}}
                try:
                    source_split_path = resolve_dataset_file(
                        source_root,
                        f"clean/{{split_name}}.parquet",
                        f"{{split_name}}.parquet",
                        f"clean/{{split_name}}",
                        f"{{split_name}}",
                    )
                    parquet_file = pq.ParquetFile(source_split_path)
                    row_count = 0
                    for batch in parquet_file.iter_batches(batch_size=100_000, columns=feature_columns + METADATA_COLUMNS):
                        frame = batch.to_pandas()
                        filtered = filter_attack_only(frame, split_name)
                        if filtered.empty:
                            continue
                        writer.write_df(filtered)
                        row_count += len(filtered)
                        counts = filtered["derived_label_family"].astype(str).value_counts().to_dict()
                        for label, count in counts.items():
                            label_counts[label] = label_counts.get(label, 0) + int(count)
                    rows_by_split[split_name] = row_count
                    label_distribution_by_split[split_name] = dict(sorted(label_counts.items()))
                finally:
                    writer.close()

            report_payload = {{
                "view_name": "attack_only",
                "description": "Attack-only family view for stage-2 family training and oracle evaluation.",
                "source_root": str(source_root),
                "output_root": str(output_root / "attack_only"),
                "feature_schema_path": "manifests/feature_columns.json",
                "label_column": "derived_label_family",
                "label_space": list(KNOWN_ATTACK_FAMILIES),
                "closed_set_families": list(KNOWN_ATTACK_FAMILIES),
                "ood_families": sorted(OOD_FAMILIES),
                "split_paths": {{split_name: f"attack_only/clean/{{split_name}}.parquet" for split_name in SOURCE_SPLITS}},
                "rows_by_split": rows_by_split,
                "label_distribution_by_split": label_distribution_by_split,
            }}
            write_json(manifest_dir / "family_view_report.json", report_payload)
            index_payload = {{
                "schema_version": "1.0",
                "source_root": str(source_root),
                "output_root": str(output_root),
                "feature_schema_path": "manifests/feature_columns.json",
                "source_artifact": {{
                    "clean_root": str(source_root / "clean"),
                    "cleaning_report_path": str(resolve_dataset_file(source_root, "manifests/cleaning_report.json", "cleaning_report.json")),
                    "feature_columns_path": str(resolve_dataset_file(source_root, "manifests/feature_columns.json", "feature_columns.json")),
                }},
                "ood_probe_families": sorted(OOD_FAMILIES),
                "views": {{
                    "attack_only": {{
                        "description": "Attack-only family view for stage-2 family training and oracle evaluation.",
                        "label_column": "derived_label_family",
                        "label_space": list(KNOWN_ATTACK_FAMILIES),
                        "closed_set_families": list(KNOWN_ATTACK_FAMILIES),
                        "ood_probe_families": sorted(OOD_FAMILIES),
                        "split_paths": {{split_name: f"attack_only/clean/{{split_name}}.parquet" for split_name in SOURCE_SPLITS}},
                        "report_path": "attack_only/manifests/family_view_report.json",
                    }}
                }},
            }}
            write_json(manifests_dir / "family_view_index.json", index_payload)
            write_json(manifests_dir / "family_view_reports.json", {{"attack_only": report_payload}})
            return output_root


        def ensure_family_view_root(preferred_root: Path, derived_root: Path) -> Path:
            existing = discover_family_view_root(preferred_root)
            if existing is not None:
                return existing
            if (derived_root / "manifests" / "family_view_index.json").exists():
                return derived_root
            binary_root = discover_binary_root(preferred_root)
            if binary_root is None:
                searched = [str(path) for path in candidate_roots(preferred_root)]
                raise FileNotFoundError(
                    "Unable to locate either family_view_index.json or a binary source artifact with "
                    f"clean splits under: {{searched}}"
                )
            log(f"Deriving family views from binary artifact at {{binary_root}}")
            return derive_family_views_from_binary(binary_root, derived_root)


        def main() -> None:
            args = parse_args()
            args.dataset_root = ensure_family_view_root(
                Path(args.dataset_root),
                Path("/kaggle/working/cic_iot_diad_2024_family_views_runtime"),
            )
            args.output_root = Path("/kaggle/working/family_classifier_results")
            log(f"Using dataset root: {{args.dataset_root}}")
            log(f"Using output root: {{args.output_root}}")
            run_training(args)


        if __name__ == "__main__":
            main()
        """
    ).strip() + "\n"


def render_training_script(
    training_source_text: str,
    dataset_id: str,
    gpu_devices: str,
    max_train_rows: int,
    iterations: int,
    class_weight_exponent: float,
) -> str:
    dataset_name = dataset_id.split("/", 1)[1]
    kaggle_dataset_root = f"/kaggle/input/{dataset_name}/{dataset_name}-binary-ids"
    rendered = strip_training_main(training_source_text)
    rendered = rendered.replace(
        'Path(r"F:\\Work\\IDS_ML_New\\artifacts\\cic_iot_diad_2024_family_views")',
        f'Path("{kaggle_dataset_root}")',
    )
    rendered = rendered.replace(
        'Path(r"F:\\Work\\IDS_ML_New\\artifacts\\modeling\\cic_iot_diad_2024_family_views\\family_classifier")',
        'Path("/kaggle/working/family_classifier_results")',
    )
    rendered = rendered.replace('DEFAULT_TASK_TYPE = "CPU"', 'DEFAULT_TASK_TYPE = "GPU"')
    rendered = rendered.replace('DEFAULT_DEVICES = ""', f'DEFAULT_DEVICES = "{gpu_devices}"')
    rendered = rendered.replace('DEFAULT_MAX_TRAIN_ROWS = 1_000_000', f'DEFAULT_MAX_TRAIN_ROWS = {max_train_rows:_}')
    rendered = rendered.replace('DEFAULT_ITERATIONS = 300', f'DEFAULT_ITERATIONS = {iterations}')
    rendered = rendered.replace(
        'DEFAULT_CLASS_WEIGHT_EXPONENT = 1.0',
        f'DEFAULT_CLASS_WEIGHT_EXPONENT = {class_weight_exponent}',
    )
    rendered = rendered.replace("import pyarrow.parquet as pq", "import pyarrow.parquet as pq\nimport pyarrow as pa")
    return rendered.rstrip() + "\n\n" + build_bootstrap_main(dataset_id)


def stage_kernel_bundle(
    *,
    bundle_root: Path,
    dataset_id: str,
    kernel_id: str,
    title: str,
    training_script_path: Path,
    gpu_devices: str,
    max_train_rows: int,
    iterations: int,
    class_weight_exponent: float,
    report_contract_path: Path,
) -> Path:
    ensure_clean_dir(bundle_root)
    training_source = training_script_path.read_text(encoding="utf-8")
    rendered_training = render_training_script(
        training_source,
        dataset_id,
        gpu_devices,
        max_train_rows,
        iterations,
        class_weight_exponent,
    )

    (bundle_root / "train_family_classifier.py").write_text(rendered_training, encoding="utf-8")
    write_json(
        bundle_root / "kernel-metadata.json",
        {
            "id": kernel_id,
            "title": title,
            "code_file": "train_family_classifier.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": "true",
            "enable_gpu": "true",
            "enable_tpu": "false",
            "enable_internet": "true",
            "dataset_sources": [dataset_id],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": [],
        },
    )
    (bundle_root / "README.md").write_text(
        build_readme(
            title,
            dataset_id,
            report_contract_path,
            gpu_devices,
            max_train_rows,
            iterations,
            class_weight_exponent,
        ),
        encoding="utf-8",
    )
    return bundle_root


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    bundle_root = args.bundle_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    staged_root = stage_kernel_bundle(
        bundle_root=bundle_root,
        dataset_id=args.dataset_id,
        kernel_id=args.kernel_id,
        title=args.title,
        training_script_path=args.training_script_path.resolve(),
        gpu_devices=args.gpu_devices,
        max_train_rows=int(args.max_train_rows),
        iterations=int(args.iterations),
        class_weight_exponent=float(args.class_weight_exponent),
        report_contract_path=args.report_contract_path.resolve(),
    )
    log(f"Staged family classifier Kaggle kernel at {staged_root}")


if __name__ == "__main__":
    main()
