from __future__ import annotations

import argparse
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


EXPECTED_COLUMN_COUNT = 84
EXPECTED_FIRST_COLUMN = "Flow ID"
FAMILY_ORDER = [
    "Benign",
    "BruteForce",
    "DDoS",
    "DoS",
    "Mirai",
    "Recon",
    "Spoofing",
    "Web-Based",
]
LEAKAGE_COLUMNS = ["Flow ID", "Src IP", "Dst IP", "Timestamp", "Label"]
METADATA_COLUMNS = [
    "source_file",
    "attack_family",
    "attack_scenario",
    "derived_label_binary",
    "derived_label_family",
    "split",
]
OOD_FAMILIES = {"BruteForce", "Recon"}
QUARANTINE_SUBPATH = Path("DoS") / "DoS-TCP_Flood"


@dataclass(frozen=True)
class DatasetFile:
    path: Path
    source_file: str
    attack_family: str
    attack_scenario: str
    derived_label_binary: str
    derived_label_family: str


class SplitWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.writer: pq.ParquetWriter | None = None
        self.rows_written = 0

    def write_df(self, df: pd.DataFrame) -> None:
        if df.empty:
            return
        table = pa.Table.from_pandas(df, preserve_index=False)
        if self.writer is None:
            self.writer = pq.ParquetWriter(self.path, table.schema, compression="snappy")
        self.writer.write_table(table)
        self.rows_written += len(df)

    def close(self) -> None:
        if self.writer is not None:
            self.writer.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess CIC IoT-DIAD 2024 flow-based CSVs into binary IDS parquet splits."
    )
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--task", required=True, choices=["binary"])
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--chunk-size", type=int, default=100_000)
    parser.add_argument("--hash-buckets", type=int, default=256)
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def discover_files(input_root: Path) -> list[DatasetFile]:
    files: list[DatasetFile] = []
    for path in sorted(input_root.rglob("*.csv")):
        rel = path.relative_to(input_root)
        if not rel.parts:
            continue
        family = rel.parts[0]
        if family not in FAMILY_ORDER:
            continue
        scenario_parts = rel.parts[1:-1]
        attack_scenario = "/".join(scenario_parts) if scenario_parts else family
        source_file = rel.as_posix()
        files.append(
            DatasetFile(
                path=path,
                source_file=source_file,
                attack_family=family,
                attack_scenario=attack_scenario,
                derived_label_binary="Benign" if family == "Benign" else "Attack",
                derived_label_family=family,
            )
        )
    return files


def is_known_bad_file(dataset_file: DatasetFile) -> bool:
    rel = Path(dataset_file.source_file)
    return rel.parent == QUARANTINE_SUBPATH


def validate_file(dataset_file: DatasetFile) -> tuple[bool, list[str], list[str] | None]:
    reasons: list[str] = []
    if is_known_bad_file(dataset_file):
        reasons.append("known_bad_file")
    try:
        header = pd.read_csv(dataset_file.path, nrows=0)
        columns = list(header.columns)
    except Exception as exc:  # pragma: no cover - best effort validation
        return False, [f"read_header_failed:{type(exc).__name__}"], None
    if len(columns) != EXPECTED_COLUMN_COUNT:
        reasons.append(f"unexpected_column_count:{len(columns)}")
    if not columns or columns[0] != EXPECTED_FIRST_COLUMN:
        reasons.append(f"unexpected_first_column:{columns[0] if columns else 'missing'}")
    return len(reasons) == 0, reasons, columns


def file_key(source_file: str) -> str:
    return source_file.replace("/", "__").replace("\\", "__").replace(":", "_")


def sanitize_numeric(chunk: pd.DataFrame, feature_columns: list[str]) -> tuple[pd.DataFrame, int]:
    numeric = chunk.loc[:, feature_columns].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.replace([np.inf, -np.inf], np.nan)
    valid = numeric.notna().all(axis=1)
    dropped = int((~valid).sum())
    cleaned = numeric.loc[valid].copy()
    return cleaned, dropped


def assign_family_splits(
    manifest_df: pd.DataFrame, seed: int
) -> tuple[dict[str, str], dict[str, dict[str, int]]]:
    rng = np.random.default_rng(seed)
    split_map: dict[str, str] = {}
    family_targets: dict[str, dict[str, int]] = {}
    ratios = {"train": 0.70, "val": 0.15, "test": 0.15}

    for family in FAMILY_ORDER:
        family_df = manifest_df[manifest_df["attack_family"] == family].copy()
        if family_df.empty:
            continue
        if family in OOD_FAMILIES or len(family_df) < 3:
            for source_file in family_df["source_file"]:
                split_map[source_file] = "ood_attack_holdout"
            family_targets[family] = {"ood_attack_holdout": int(family_df["clean_rows_pre_dedupe"].sum())}
            continue

        family_df["shuffle"] = rng.random(len(family_df))
        family_df = family_df.sort_values(
            by=["clean_rows_pre_dedupe", "shuffle", "source_file"],
            ascending=[False, True, True],
        )
        total_rows = int(family_df["clean_rows_pre_dedupe"].sum())
        targets = {split: int(round(total_rows * ratio)) for split, ratio in ratios.items()}
        targets["train"] = total_rows - targets["val"] - targets["test"]
        family_targets[family] = targets

        assigned_rows = {"train": 0, "val": 0, "test": 0}
        ordered_records = family_df.to_dict("records")
        seed_splits = ["train", "val", "test"]
        for split_name, record in zip(seed_splits, ordered_records[:3]):
            split_map[record["source_file"]] = split_name
            assigned_rows[split_name] += int(record["clean_rows_pre_dedupe"])

        for record in ordered_records[3:]:
            row_count = int(record["clean_rows_pre_dedupe"])
            candidate_scores: list[tuple[float, str]] = []
            for split_name in seed_splits:
                current = assigned_rows[split_name]
                target = targets[split_name]
                ratio = current / target if target else math.inf
                projected_gap = abs((current + row_count) - target)
                candidate_scores.append((ratio, projected_gap, split_name))
            _, _, chosen_split = min(candidate_scores)
            split_map[record["source_file"]] = chosen_split
            assigned_rows[chosen_split] += row_count

    return split_map, family_targets


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_progress(
    path: Path,
    phase: str,
    processed_files: int,
    total_files: int,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "phase": phase,
        "processed_files": processed_files,
        "total_files": total_files,
    }
    if extra:
        payload.update(extra)
    write_json(path, payload)


def read_stage_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    table = pq.read_table(path, columns=columns)
    return table.to_pandas()


def compute_zero_variance_columns(train_stage_path: Path, feature_columns: list[str]) -> list[str]:
    parquet_file = pq.ParquetFile(train_stage_path)
    minima = {column: None for column in feature_columns}
    maxima = {column: None for column in feature_columns}

    for batch in parquet_file.iter_batches(batch_size=100_000, columns=feature_columns):
        frame = batch.to_pandas()
        for column in feature_columns:
            values = frame[column].to_numpy()
            if values.size == 0:
                continue
            current_min = values.min()
            current_max = values.max()
            minima[column] = current_min if minima[column] is None else min(minima[column], current_min)
            maxima[column] = current_max if maxima[column] is None else max(maxima[column], current_max)

    return [column for column in feature_columns if minima[column] == maxima[column]]


def summarize_label_distribution_from_parquet(path: Path) -> dict[str, int]:
    parquet_file = pq.ParquetFile(path)
    counts: dict[str, int] = {}
    for batch in parquet_file.iter_batches(batch_size=200_000, columns=["derived_label_binary"]):
        values = batch.column(0).to_pylist()
        for value in values:
            key = str(value)
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def validate_no_nan_or_inf(path: Path, feature_columns: list[str]) -> None:
    parquet_file = pq.ParquetFile(path)
    for batch in parquet_file.iter_batches(batch_size=100_000, columns=feature_columns):
        frame = batch.to_pandas()
        values = frame.to_numpy()
        if np.isnan(values).any():
            raise RuntimeError(f"NaN values remain in {path}")
        if not np.isfinite(values).all():
            raise RuntimeError(f"Non-finite values remain in {path}")


def run_pipeline(args: argparse.Namespace) -> None:
    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()

    clean_dir = output_root / "clean"
    manifest_dir = output_root / "manifests"
    temp_dir = output_root / "_temp"
    cleaned_shards_dir = temp_dir / "cleaned_shards"
    bucket_dir = temp_dir / "hash_buckets"
    stage_dir = temp_dir / "stage"

    ensure_clean_dir(output_root)
    clean_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    cleaned_shards_dir.mkdir(parents=True, exist_ok=True)
    bucket_dir.mkdir(parents=True, exist_ok=True)
    stage_dir.mkdir(parents=True, exist_ok=True)

    files = discover_files(input_root)
    if not files:
        raise FileNotFoundError(f"No CSV files found under {input_root}")

    file_records: list[dict[str, Any]] = []
    quarantine_columns = [
        "source_file",
        "attack_family",
        "attack_scenario",
        "quarantine_reason",
    ]
    quarantine_records: list[dict[str, Any]] = []
    feature_columns: list[str] | None = None

    log(f"Discovered {len(files)} CSV files")
    write_progress(manifest_dir / "progress.json", "cleaning", 0, len(files))

    for file_index, dataset_file in enumerate(files, start=1):
        valid, reasons, columns = validate_file(dataset_file)
        if not valid:
            quarantine_records.append(
                {
                    "source_file": dataset_file.source_file,
                    "attack_family": dataset_file.attack_family,
                    "attack_scenario": dataset_file.attack_scenario,
                    "quarantine_reason": "|".join(reasons),
                }
            )
            log(f"[{file_index}/{len(files)}] Quarantine {dataset_file.source_file}: {';'.join(reasons)}")
            pd.DataFrame(quarantine_records, columns=quarantine_columns).to_csv(
                manifest_dir / "quarantine_manifest.partial.csv",
                index=False,
            )
            write_progress(
                manifest_dir / "progress.json",
                "cleaning",
                file_index,
                len(files),
                {"last_source_file": dataset_file.source_file, "status": "quarantined"},
            )
            continue

        assert columns is not None
        if feature_columns is None:
            feature_columns = [column for column in columns if column not in LEAKAGE_COLUMNS]
        elif [column for column in columns if column not in LEAKAGE_COLUMNS] != feature_columns:
            quarantine_records.append(
                {
                    "source_file": dataset_file.source_file,
                    "attack_family": dataset_file.attack_family,
                    "attack_scenario": dataset_file.attack_scenario,
                    "quarantine_reason": "feature_schema_mismatch",
                }
            )
            log(f"[{file_index}/{len(files)}] Quarantine {dataset_file.source_file}: feature_schema_mismatch")
            continue

        raw_rows = 0
        clean_rows = 0
        dropped_rows = 0
        shard_index = 0
        file_temp_dir = cleaned_shards_dir / file_key(dataset_file.source_file)
        file_temp_dir.mkdir(parents=True, exist_ok=True)

        log(f"[{file_index}/{len(files)}] Cleaning {dataset_file.source_file}")
        for chunk in pd.read_csv(dataset_file.path, chunksize=args.chunk_size, low_memory=False):
            raw_rows += len(chunk)
            cleaned_numeric, dropped = sanitize_numeric(chunk, feature_columns)
            dropped_rows += dropped
            if cleaned_numeric.empty:
                continue

            cleaned_numeric["source_file"] = dataset_file.source_file
            cleaned_numeric["attack_family"] = dataset_file.attack_family
            cleaned_numeric["attack_scenario"] = dataset_file.attack_scenario
            cleaned_numeric["derived_label_binary"] = dataset_file.derived_label_binary
            cleaned_numeric["derived_label_family"] = dataset_file.derived_label_family
            clean_rows += len(cleaned_numeric)

            shard_path = file_temp_dir / f"chunk-{shard_index:05d}.parquet"
            cleaned_numeric.to_parquet(shard_path, index=False)
            shard_index += 1

        file_records.append(
            {
                "source_file": dataset_file.source_file,
                "attack_family": dataset_file.attack_family,
                "attack_scenario": dataset_file.attack_scenario,
                "derived_label_binary": dataset_file.derived_label_binary,
                "derived_label_family": dataset_file.derived_label_family,
                "raw_rows": raw_rows,
                "clean_rows_pre_dedupe": clean_rows,
                "dropped_rows_nan_inf": dropped_rows,
                "temp_dir": str(file_temp_dir),
            }
        )
        pd.DataFrame(file_records).drop(columns=["temp_dir"], errors="ignore").to_csv(
            manifest_dir / "file_manifest.partial.csv",
            index=False,
        )
        pd.DataFrame(quarantine_records, columns=quarantine_columns).to_csv(
            manifest_dir / "quarantine_manifest.partial.csv",
            index=False,
        )
        write_progress(
            manifest_dir / "progress.json",
            "cleaning",
            file_index,
            len(files),
            {"last_source_file": dataset_file.source_file, "status": "cleaned"},
        )

    if feature_columns is None:
        raise RuntimeError("No valid input files were found")

    file_manifest_df = pd.DataFrame(file_records)
    quarantine_df = pd.DataFrame(quarantine_records, columns=quarantine_columns)

    split_map, family_targets = assign_family_splits(file_manifest_df, seed=args.seed)
    file_manifest_df["split"] = file_manifest_df["source_file"].map(split_map)

    log("Writing hash bucket shards")
    write_progress(manifest_dir / "progress.json", "hash_bucket_writing", 0, len(file_manifest_df))
    for bucket_input_index, record in enumerate(file_manifest_df.to_dict("records"), start=1):
        source_file = record["source_file"]
        split_name = split_map[source_file]
        temp_dir_for_file = Path(record["temp_dir"])
        for shard_path in sorted(temp_dir_for_file.glob("*.parquet")):
            frame = pd.read_parquet(shard_path)
            frame["split"] = split_name
            dedupe_columns = [column for column in frame.columns if column != "source_file"]
            hash_values = pd.util.hash_pandas_object(frame[dedupe_columns], index=False).to_numpy(dtype=np.uint64)
            frame["__hash_bucket__"] = hash_values % args.hash_buckets
            frame["__hash_value__"] = hash_values

            for bucket_id, bucket_frame in frame.groupby("__hash_bucket__", sort=False):
                bucket_path = bucket_dir / f"bucket-{int(bucket_id):03d}"
                bucket_path.mkdir(parents=True, exist_ok=True)
                shard_name = f"{file_key(source_file)}-{shard_path.stem}.parquet"
                bucket_frame.to_parquet(bucket_path / shard_name, index=False)
        write_progress(
            manifest_dir / "progress.json",
            "hash_bucket_writing",
            bucket_input_index,
            len(file_manifest_df),
            {"last_source_file": source_file},
        )

    stage_paths = {
        "train": stage_dir / "train_stage.parquet",
        "val": stage_dir / "val_stage.parquet",
        "test": stage_dir / "test_stage.parquet",
        "ood_attack_holdout": stage_dir / "ood_attack_holdout_stage.parquet",
    }
    stage_writers = {name: SplitWriter(path) for name, path in stage_paths.items()}
    dedupe_columns = feature_columns + [
        "attack_family",
        "attack_scenario",
        "derived_label_binary",
        "derived_label_family",
    ]
    total_rows_post_dedupe = 0

    log("Deduping hash buckets and writing stage parquet files")
    for bucket_index in range(args.hash_buckets):
        bucket_path = bucket_dir / f"bucket-{bucket_index:03d}"
        shard_paths = sorted(bucket_path.glob("*.parquet"))
        if not shard_paths:
            continue
        bucket_frames = [pd.read_parquet(path) for path in shard_paths]
        bucket_df = pd.concat(bucket_frames, ignore_index=True)
        bucket_df = bucket_df.drop_duplicates(subset=dedupe_columns, keep="first").drop(
            columns=["__hash_bucket__", "__hash_value__"]
        )

        for split_name, writer in stage_writers.items():
            split_df = bucket_df[bucket_df["split"] == split_name]
            writer.write_df(split_df)
            total_rows_post_dedupe += len(split_df)
        write_progress(
            manifest_dir / "progress.json",
            "deduping_and_stage_writing",
            bucket_index + 1,
            args.hash_buckets,
            {"last_bucket": bucket_index},
        )

    for writer in stage_writers.values():
        writer.close()

    zero_variance_columns = compute_zero_variance_columns(stage_paths["train"], feature_columns)
    final_feature_columns = [column for column in feature_columns if column not in zero_variance_columns]

    final_paths = {
        "train": clean_dir / "train.parquet",
        "val": clean_dir / "val.parquet",
        "test": clean_dir / "test.parquet",
        "ood_attack_holdout": clean_dir / "ood_attack_holdout.parquet",
    }
    final_writers = {name: SplitWriter(path) for name, path in final_paths.items()}

    distribution_by_split: dict[str, dict[str, int]] = {}
    row_count_by_split: dict[str, int] = {}
    verify_no_duplicates = {
        "train": 0,
        "val": 0,
        "test": 0,
        "ood_attack_holdout": 0,
    }

    final_columns = final_feature_columns + METADATA_COLUMNS
    log("Writing final parquet outputs")
    for split_index, (split_name, stage_path) in enumerate(stage_paths.items(), start=1):
        stage_parquet = pq.ParquetFile(stage_path)
        for batch in stage_parquet.iter_batches(batch_size=100_000):
            frame = batch.to_pandas()
            trimmed = frame[final_columns].copy()
            final_writers[split_name].write_df(trimmed)
        final_writers[split_name].close()

        parquet_file = pq.ParquetFile(final_paths[split_name])
        final_schema_names = parquet_file.schema.names
        missing_forbidden = [column for column in LEAKAGE_COLUMNS if column in final_schema_names]
        if missing_forbidden:
            raise RuntimeError(f"Forbidden columns still present in output: {missing_forbidden}")
        row_count_by_split[split_name] = int(parquet_file.metadata.num_rows)
        distribution_by_split[split_name] = summarize_label_distribution_from_parquet(final_paths[split_name])
        validate_no_nan_or_inf(final_paths[split_name], final_feature_columns)
        write_progress(
            manifest_dir / "progress.json",
            "final_writing",
            split_index,
            len(stage_paths),
            {"last_split": split_name},
        )

    all_source_files = {
        split_name: set(file_manifest_df.loc[file_manifest_df["split"] == split_name, "source_file"].tolist())
        for split_name in ["train", "val", "test"]
    }
    if all_source_files["train"] & all_source_files["val"]:
        raise RuntimeError("train/val share source_file values")
    if all_source_files["train"] & all_source_files["test"]:
        raise RuntimeError("train/test share source_file values")
    if all_source_files["val"] & all_source_files["test"]:
        raise RuntimeError("val/test share source_file values")

    file_manifest_df = file_manifest_df.drop(columns=["temp_dir"])
    file_manifest_df.to_csv(manifest_dir / "file_manifest.csv", index=False)
    quarantine_df.to_csv(manifest_dir / "quarantine_manifest.csv", index=False)
    write_json(manifest_dir / "feature_columns.json", {"feature_columns": final_feature_columns})

    cleaning_report = {
        "input_root": str(input_root),
        "output_root": str(output_root),
        "task": args.task,
        "seed": args.seed,
        "hash_buckets": args.hash_buckets,
        "valid_file_count": int(len(file_manifest_df)),
        "quarantine_file_count": int(len(quarantine_df)),
        "rows_before_clean": int(file_manifest_df["raw_rows"].sum()),
        "rows_after_clean_before_dedupe": int(file_manifest_df["clean_rows_pre_dedupe"].sum()),
        "rows_dropped_nan_inf": int(file_manifest_df["dropped_rows_nan_inf"].sum()),
        "rows_removed_duplicates": int(file_manifest_df["clean_rows_pre_dedupe"].sum() - total_rows_post_dedupe),
        "rows_after_dedupe": int(total_rows_post_dedupe),
        "rows_by_split": row_count_by_split,
        "label_distribution_by_split": distribution_by_split,
        "family_targets": family_targets,
        "zero_variance_columns": zero_variance_columns,
        "duplicate_rows_remaining_by_split": verify_no_duplicates,
        "ood_families": sorted(OOD_FAMILIES),
    }
    write_json(manifest_dir / "cleaning_report.json", cleaning_report)
    write_progress(manifest_dir / "progress.json", "completed", len(files), len(files))
    try:
        shutil.rmtree(temp_dir)
    except PermissionError as exc:
        log(f"Warning: unable to delete temp directory {temp_dir}: {exc}")


def main() -> None:
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
