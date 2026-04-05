from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import pyarrow.parquet as pq

from ml_pipeline.data_prep.preprocess_iot_diad import FAMILY_ORDER, METADATA_COLUMNS, OOD_FAMILIES, SplitWriter


SOURCE_SPLITS = ["train", "val", "test", "ood_attack_holdout"]
KNOWN_ATTACK_FAMILIES = [family for family in FAMILY_ORDER if family not in {"Benign", *OOD_FAMILIES}]
DIRECT_MULTICLASS_LABELS = ["Benign", *KNOWN_ATTACK_FAMILIES]
REPO_ROOT = Path(__file__).resolve().parents[2]
APPROVED_OUTPUT_ROOTS = (REPO_ROOT / "artifacts", Path(tempfile.gettempdir()).resolve())


@dataclass(frozen=True)
class ViewSpec:
    name: str
    description: str
    label_space: list[str]
    row_filter: Callable[[pd.DataFrame, str], pd.DataFrame]
    split_semantics: dict[str, str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive family-view parquet artifacts from the frozen CIC IoT-DIAD binary output."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path(r"F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary"),
        help="Frozen binary artifact root to read from.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_family_views"),
        help="Destination root for derived family-view artifacts.",
    )
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def assert_safe_output_root(path: Path, *, approved_roots: tuple[Path, ...] = APPROVED_OUTPUT_ROOTS) -> Path:
    resolved = path.resolve()
    normalized_roots = tuple(root.resolve() for root in approved_roots)
    for root in normalized_roots:
        if resolved == root:
            raise ValueError(f"Refusing to operate on approved root directly: {resolved}")
        if _is_relative_to(resolved, root):
            return resolved
    approved = ", ".join(str(root) for root in normalized_roots)
    raise ValueError(f"Output root must stay inside an approved artifact root. Got {resolved}. Approved roots: {approved}")


def ensure_clean_dir(path: Path) -> None:
    resolved = assert_safe_output_root(path)
    if path.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def resolve_dataset_file(dataset_root: Path, *candidates: str) -> Path:
    searched = [str(dataset_root / candidate) for candidate in candidates]
    for candidate in candidates:
        path = dataset_root / candidate
        if path.exists():
            return path
    candidate_names = {Path(candidate).name for candidate in candidates}
    recursive_hits = [path for path in dataset_root.rglob("*") if path.is_file() and path.name in candidate_names]
    if recursive_hits:
        recursive_hits.sort(key=lambda path: (len(path.parts), str(path)))
        return recursive_hits[0]
    raise FileNotFoundError(f"Unable to locate dataset file. Tried: {searched}")


def load_feature_columns(dataset_root: Path) -> list[str]:
    payload = read_json(resolve_dataset_file(dataset_root, "manifests/feature_columns.json", "feature_columns.json"))
    return list(payload["feature_columns"])


def resolve_split_path(dataset_root: Path, split_name: str) -> Path:
    return resolve_dataset_file(dataset_root, f"clean/{split_name}.parquet", f"clean/{split_name}")


def count_values(values: pd.Series) -> dict[str, int]:
    counts = Counter(str(value) for value in values.tolist())
    return dict(sorted(counts.items()))


def attack_only_filter(frame: pd.DataFrame, split_name: str) -> pd.DataFrame:
    if split_name == "ood_attack_holdout":
        return frame[frame["derived_label_family"].isin(sorted(OOD_FAMILIES))].copy()
    return frame[frame["derived_label_family"].isin(KNOWN_ATTACK_FAMILIES)].copy()


def direct_multiclass_filter(frame: pd.DataFrame, split_name: str) -> pd.DataFrame:
    if split_name == "ood_attack_holdout":
        return frame[frame["derived_label_family"].isin(sorted(OOD_FAMILIES))].copy()
    return frame[frame["derived_label_family"].isin(DIRECT_MULTICLASS_LABELS)].copy()


def build_view_specs() -> list[ViewSpec]:
    attack_split_semantics = {
        "train": "Rows from source train with Benign removed; only known attack families remain.",
        "val": "Rows from source val with Benign removed; only known attack families remain.",
        "test": "Rows from source test with Benign removed; only known attack families remain.",
        "ood_attack_holdout": "Rows from source ood_attack_holdout restricted to BruteForce and Recon.",
    }
    direct_split_semantics = {
        "train": "Rows from source train with OOD families removed; Benign retained as a class.",
        "val": "Rows from source val with OOD families removed; Benign retained as a class.",
        "test": "Rows from source test with OOD families removed; Benign retained as a class.",
        "ood_attack_holdout": "Rows from source ood_attack_holdout restricted to BruteForce and Recon.",
    }
    return [
        ViewSpec(
            name="attack_only",
            description="Attack-only family view for stage-2 family training and oracle evaluation.",
            label_space=list(KNOWN_ATTACK_FAMILIES),
            row_filter=attack_only_filter,
            split_semantics=attack_split_semantics,
        ),
        ViewSpec(
            name="direct_multiclass",
            description="Direct multiclass family view for offline comparison against the two-stage lane.",
            label_space=list(DIRECT_MULTICLASS_LABELS),
            row_filter=direct_multiclass_filter,
            split_semantics=direct_split_semantics,
        ),
    ]


def filter_for_view(frame: pd.DataFrame, spec: ViewSpec, split_name: str) -> pd.DataFrame:
    label_column = "derived_label_family"
    observed_labels = {str(value) for value in frame[label_column].astype(str).tolist()}
    if split_name == "ood_attack_holdout":
        allowed_source_labels = set(OOD_FAMILIES)
    else:
        allowed_source_labels = set(DIRECT_MULTICLASS_LABELS)
    unexpected_labels = sorted(observed_labels.difference(allowed_source_labels))
    if unexpected_labels:
        raise ValueError(
            f"{spec.name} view saw unexpected labels in split {split_name}: {unexpected_labels}. "
            f"Allowed labels: {sorted(allowed_source_labels)}"
        )
    return spec.row_filter(frame, split_name)


def derive_view(
    source_root: Path,
    output_root: Path,
    spec: ViewSpec,
    feature_columns: list[str],
) -> dict[str, Any]:
    view_root = output_root / spec.name
    clean_dir = view_root / "clean"
    manifest_dir = view_root / "manifests"
    clean_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    split_paths = {split_name: clean_dir / f"{split_name}.parquet" for split_name in SOURCE_SPLITS}
    writers = {split_name: SplitWriter(path) for split_name, path in split_paths.items()}
    rows_by_split: dict[str, int] = {split_name: 0 for split_name in SOURCE_SPLITS}
    label_distribution_by_split: dict[str, dict[str, int]] = {split_name: {} for split_name in SOURCE_SPLITS}

    columns = feature_columns + METADATA_COLUMNS
    for split_name in SOURCE_SPLITS:
        source_split_path = resolve_split_path(source_root, split_name)
        parquet_file = pq.ParquetFile(source_split_path)
        label_counter = Counter()
        for batch in parquet_file.iter_batches(batch_size=100_000, columns=columns):
            frame = batch.to_pandas()
            filtered = filter_for_view(frame, spec, split_name)
            if filtered.empty:
                continue
            writers[split_name].write_df(filtered)
            rows_by_split[split_name] += len(filtered)
            label_counter.update(str(value) for value in filtered["derived_label_family"].tolist())
        label_distribution_by_split[split_name] = dict(sorted(label_counter.items()))
        if split_name != "ood_attack_holdout" and rows_by_split[split_name] == 0:
            raise ValueError(f"{spec.name} view produced no rows for split {split_name}")

    for writer in writers.values():
        writer.close()

    report_payload = {
        "view_name": spec.name,
        "description": spec.description,
        "source_root": str(source_root),
        "output_root": str(view_root),
        "feature_schema_path": str(output_root / "manifests" / "feature_columns.json"),
        "label_column": "derived_label_family",
        "label_space": spec.label_space,
        "closed_set_families": list(KNOWN_ATTACK_FAMILIES),
        "ood_families": sorted(OOD_FAMILIES),
        "split_paths": {split_name: str(path.relative_to(output_root)) for split_name, path in split_paths.items()},
        "rows_by_split": rows_by_split,
        "label_distribution_by_split": label_distribution_by_split,
        "split_semantics": spec.split_semantics,
        "source_artifact": {
            "clean_root": str(source_root / "clean"),
            "file_manifest_path": str(source_root / "manifests" / "file_manifest.csv"),
            "cleaning_report_path": str(source_root / "manifests" / "cleaning_report.json"),
            "feature_columns_path": str(source_root / "manifests" / "feature_columns.json"),
        },
    }
    write_json(manifest_dir / "family_view_report.json", report_payload)
    return report_payload


def run_pipeline(args: argparse.Namespace) -> None:
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()

    feature_columns = load_feature_columns(source_root)
    source_feature_columns_path = resolve_dataset_file(source_root, "manifests/feature_columns.json", "feature_columns.json")
    source_cleaning_report_path = resolve_dataset_file(source_root, "manifests/cleaning_report.json", "cleaning_report.json")
    source_file_manifest_path = resolve_dataset_file(source_root, "manifests/file_manifest.csv", "file_manifest.csv")

    ensure_clean_dir(output_root)
    (output_root / "manifests").mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_feature_columns_path, output_root / "manifests" / "feature_columns.json")

    view_reports: dict[str, dict[str, Any]] = {}
    for spec in build_view_specs():
        log(f"Deriving {spec.name} view")
        view_reports[spec.name] = derive_view(source_root, output_root, spec, feature_columns)

    index_payload = {
        "schema_version": "1.0",
        "source_root": str(source_root),
        "output_root": str(output_root),
        "feature_schema_path": "manifests/feature_columns.json",
        "source_artifact": {
            "clean_root": str(source_root / "clean"),
            "file_manifest_path": str(source_file_manifest_path),
            "cleaning_report_path": str(source_cleaning_report_path),
            "feature_columns_path": str(source_feature_columns_path),
        },
        "ood_probe_families": sorted(OOD_FAMILIES),
        "views": {
            spec.name: {
                "description": spec.description,
                "label_column": "derived_label_family",
                "label_space": spec.label_space,
                "closed_set_families": list(KNOWN_ATTACK_FAMILIES),
                "ood_probe_families": sorted(OOD_FAMILIES),
                "split_semantics": spec.split_semantics,
                "split_paths": {split_name: f"{spec.name}/clean/{split_name}.parquet" for split_name in SOURCE_SPLITS},
                "report_path": f"{spec.name}/manifests/family_view_report.json",
            }
            for spec in build_view_specs()
        },
    }
    write_json(output_root / "manifests" / "family_view_index.json", index_payload)

    # Keep the root index grounded in the generated reports for quick inspection.
    write_json(output_root / "manifests" / "family_view_reports.json", view_reports)


def main() -> None:
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
