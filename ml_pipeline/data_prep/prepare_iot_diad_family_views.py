from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ids.core.model_bundle import build_feature_schema_metadata
from ids.core.path_defaults import resolve_repo_path


SOURCE_SPLITS = ("train", "val", "test", "ood_attack_holdout")
KNOWN_ATTACK_FAMILIES = ("DDoS", "DoS", "Mirai", "Spoofing", "Web-Based")
OOD_PROBE_FAMILIES = ("BruteForce", "Recon")
TARGET_LABEL_COLUMN = "derived_label_family"
GATE_LABEL_COLUMN = "derived_label_binary"

DEFAULT_SOURCE_ROOT = resolve_repo_path("artifacts", "cic_iot_diad_2024_binary")
DEFAULT_OUTPUT_ROOT = resolve_repo_path("artifacts", "cic_iot_diad_2024_family_views")
DEFAULT_BATCH_SIZE = 100_000


@dataclass(frozen=True)
class ViewSpec:
    name: str
    description: str
    output_subdir: str
    include_benign: bool
    closed_set_labels: tuple[str, ...]


VIEW_SPECS = (
    ViewSpec(
        name="attack_only_family",
        description="Attack-only family view for the stage-2 family classifier.",
        output_subdir="attack_only_family",
        include_benign=False,
        closed_set_labels=KNOWN_ATTACK_FAMILIES,
    ),
    ViewSpec(
        name="direct_multiclass",
        description="Direct multiclass view for offline comparison against Benign plus attack families.",
        output_subdir="direct_multiclass",
        include_benign=True,
        closed_set_labels=("Benign",) + KNOWN_ATTACK_FAMILIES,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Derive attack-only family and direct multiclass views from the frozen "
            "CIC IoT-DIAD binary parquet artifact."
        )
    )
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def load_feature_columns(source_root: Path) -> list[str]:
    feature_columns_path = source_root / "manifests" / "feature_columns.json"
    if not feature_columns_path.is_file():
        raise FileNotFoundError(f"Missing feature schema manifest: {feature_columns_path}")
    payload = read_json(feature_columns_path)
    feature_columns = payload.get("feature_columns")
    if not isinstance(feature_columns, list) or not all(isinstance(name, str) for name in feature_columns):
        raise ValueError(f"Invalid feature_columns payload: {feature_columns_path}")
    return list(feature_columns)


def source_split_path(source_root: Path, split_name: str) -> Path:
    return source_root / "clean" / f"{split_name}.parquet"


def load_source_schema(source_root: Path) -> pa.Schema:
    train_path = source_split_path(source_root, "train")
    if not train_path.is_file():
        raise FileNotFoundError(f"Missing source parquet: {train_path}")
    return pq.ParquetFile(train_path).schema_arrow


def empty_table(schema: pa.Schema) -> pa.Table:
    arrays = [pa.array([], type=field.type) for field in schema]
    return pa.Table.from_arrays(arrays, schema=schema)


def iter_source_frames(path: Path, batch_size: int) -> pd.DataFrame:
    parquet_file = pq.ParquetFile(path)
    for batch in parquet_file.iter_batches(batch_size=batch_size):
        yield batch.to_pandas()


def materialize_split(
    *,
    source_path: Path,
    destination_path: Path,
    schema: pa.Schema,
    include_benign: bool,
    batch_size: int,
) -> dict[str, Any]:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        destination_path.unlink()

    writer: pq.ParquetWriter | None = None
    source_rows = 0
    written_rows = 0
    filtered_rows = 0
    source_label_counts: Counter[str] = Counter()
    written_label_counts: Counter[str] = Counter()

    for frame in iter_source_frames(source_path, batch_size):
        source_rows += len(frame)
        source_label_counts.update(frame[TARGET_LABEL_COLUMN].astype(str).tolist())

        if include_benign:
            kept = frame
        else:
            kept = frame[frame[GATE_LABEL_COLUMN] == "Attack"].copy()

        filtered_rows += len(frame) - len(kept)
        if not kept.empty:
            kept = kept.loc[:, schema.names].copy()
            written_label_counts.update(kept[TARGET_LABEL_COLUMN].astype(str).tolist())
            table = pa.Table.from_pandas(kept, schema=schema, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(destination_path, schema, compression="snappy")
            writer.write_table(table)
            written_rows += len(kept)

    if writer is None:
        pq.write_table(empty_table(schema), destination_path, compression="snappy")
    else:
        writer.close()

    return {
        "source_rows": source_rows,
        "written_rows": written_rows,
        "filtered_rows": filtered_rows,
        "source_label_counts": dict(sorted(source_label_counts.items())),
        "written_label_counts": dict(sorted(written_label_counts.items())),
    }


def materialize_view(
    *,
    source_root: Path,
    output_root: Path,
    feature_columns: list[str],
    view_spec: ViewSpec,
    batch_size: int,
) -> dict[str, Any]:
    source_schema = load_source_schema(source_root)
    expected_columns = set(feature_columns) | {TARGET_LABEL_COLUMN, GATE_LABEL_COLUMN, "attack_family", "attack_scenario", "split"}
    missing_columns = sorted(expected_columns.difference(source_schema.names))
    if missing_columns:
        raise ValueError(f"Source parquet schema is missing required columns: {missing_columns}")

    view_root = output_root / "clean" / view_spec.output_subdir
    manifest_root = output_root / "manifests"
    report_root = output_root / "reports"
    view_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    split_manifest_rows: list[dict[str, Any]] = []
    split_summaries: dict[str, Any] = {}
    for split_name in SOURCE_SPLITS:
        source_path = source_split_path(source_root, split_name)
        if not source_path.is_file():
            raise FileNotFoundError(f"Missing source parquet: {source_path}")
        destination_path = view_root / f"{split_name}.parquet"
        split_summary = materialize_split(
            source_path=source_path,
            destination_path=destination_path,
            schema=source_schema,
            include_benign=view_spec.include_benign,
            batch_size=batch_size,
        )
        split_summaries[split_name] = {
            **split_summary,
            "parquet_path": str(destination_path.resolve()),
        }
        split_manifest_rows.append(
            {
                "split": split_name,
                "parquet_path": str(destination_path.resolve()),
                "source_rows": split_summary["source_rows"],
                "written_rows": split_summary["written_rows"],
                "filtered_rows": split_summary["filtered_rows"],
                "label_column": TARGET_LABEL_COLUMN,
                "gate_column": GATE_LABEL_COLUMN,
                "includes_benign": str(view_spec.include_benign).lower(),
                "closed_set_labels_json": json.dumps(list(view_spec.closed_set_labels), ensure_ascii=False),
                "ood_probe_labels_json": json.dumps(list(OOD_PROBE_FAMILIES), ensure_ascii=False),
            }
        )

    manifest_path = manifest_root / f"{view_spec.output_subdir}_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "split",
            "parquet_path",
            "source_rows",
            "written_rows",
            "filtered_rows",
            "label_column",
            "gate_column",
            "includes_benign",
            "closed_set_labels_json",
            "ood_probe_labels_json",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(split_manifest_rows)

    report_path = report_root / f"{view_spec.output_subdir}_counts.json"
    report_payload = {
        "view_name": view_spec.name,
        "description": view_spec.description,
        "label_column": TARGET_LABEL_COLUMN,
        "gate_column": GATE_LABEL_COLUMN,
        "includes_benign": view_spec.include_benign,
        "closed_set_labels": list(view_spec.closed_set_labels),
        "ood_probe_labels": list(OOD_PROBE_FAMILIES),
        "split_summaries": split_summaries,
    }
    write_json(report_path, report_payload)

    return {
        "view_name": view_spec.name,
        "description": view_spec.description,
        "output_subdir": view_spec.output_subdir,
        "manifest_path": str(manifest_path.resolve()),
        "report_path": str(report_path.resolve()),
        "split_summaries": split_summaries,
    }


def run_pipeline(*, source_root: Path, output_root: Path, batch_size: int) -> dict[str, Any]:
    source_root = source_root.resolve()
    output_root = output_root.resolve()

    if not source_root.is_dir():
        raise FileNotFoundError(f"Source artifact root not found: {source_root}")

    ensure_clean_dir(output_root)
    feature_columns = load_feature_columns(source_root)

    copied_feature_columns_path = output_root / "manifests" / "feature_columns.json"
    copied_feature_columns_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_root / "manifests" / "feature_columns.json", copied_feature_columns_path)

    source_cleaning_report_path = source_root / "manifests" / "cleaning_report.json"
    source_cleaning_report = read_json(source_cleaning_report_path) if source_cleaning_report_path.is_file() else None

    view_results = [
        materialize_view(
            source_root=source_root,
            output_root=output_root,
            feature_columns=feature_columns,
            view_spec=view_spec,
            batch_size=batch_size,
        )
        for view_spec in VIEW_SPECS
    ]

    feature_schema_metadata = build_feature_schema_metadata(copied_feature_columns_path)
    index_payload = {
        "schema_version": "1.0",
        "source_artifact_root": str(source_root),
        "source_clean_parquet_root": str((source_root / "clean").resolve()),
        "source_feature_columns_path": str((source_root / "manifests" / "feature_columns.json").resolve()),
        "source_cleaning_report_path": str(source_cleaning_report_path.resolve()) if source_cleaning_report is not None else None,
        "output_root": str(output_root),
        "feature_schema": feature_schema_metadata,
        "target_label_column": TARGET_LABEL_COLUMN,
        "gate_label_column": GATE_LABEL_COLUMN,
        "known_attack_families": list(KNOWN_ATTACK_FAMILIES),
        "ood_probe_families": list(OOD_PROBE_FAMILIES),
        "views": {},
    }

    for view_result in view_results:
        view_spec = next(spec for spec in VIEW_SPECS if spec.name == view_result["view_name"])
        index_payload["views"][view_result["view_name"]] = {
            "description": view_result["description"],
            "output_subdir": view_result["output_subdir"],
            "manifest_path": view_result["manifest_path"],
            "report_path": view_result["report_path"],
            "label_column": TARGET_LABEL_COLUMN,
            "gate_column": GATE_LABEL_COLUMN,
            "includes_benign": view_spec.include_benign,
            "closed_set_labels": list(view_spec.closed_set_labels),
            "ood_probe_labels": list(OOD_PROBE_FAMILIES),
            "split_parquet_paths": {
                split_name: split_data["parquet_path"] for split_name, split_data in view_result["split_summaries"].items()
            },
            "split_row_counts": {
                split_name: split_data["written_rows"] for split_name, split_data in view_result["split_summaries"].items()
            },
        }

    index_path = output_root / "manifests" / "family_view_index.json"
    write_json(index_path, index_payload)

    summary = {
        "source_root": str(source_root),
        "output_root": str(output_root),
        "feature_schema_path": str(copied_feature_columns_path.resolve()),
        "family_view_index": str(index_path.resolve()),
        "views": view_results,
    }
    log(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main() -> None:
    args = parse_args()
    run_pipeline(source_root=args.source_root, output_root=args.output_root, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
