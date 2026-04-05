from __future__ import annotations

import argparse
import ast
import json
import shutil
import tempfile
import textwrap
from pathlib import Path


DEFAULT_OUTPUT_ROOT = Path(r"F:\Work\IDS_ML_New\artifacts\kaggle")
DEFAULT_BUNDLE_ROOT = DEFAULT_OUTPUT_ROOT / "kernels" / "direct_multiclass"
DEFAULT_DATASET_ID = "hdiiii/cic-iot-diad-2024"
DEFAULT_KERNEL_ID = "hdiiii/ids-multiclass-direct-baseline"
DEFAULT_KERNEL_TITLE = "IDS Direct Multiclass Baseline"
DEFAULT_DIRECT_SCRIPT = Path(r"F:\Work\IDS_ML_New\ml_pipeline\training\train_iot_diad_direct_multiclass.py")
DEFAULT_HELPER_SCRIPT = Path(r"F:\Work\IDS_ML_New\ml_pipeline\training\train_iot_diad_family_classifier.py")
DEFAULT_GPU_DEVICES = "0:1"
DEFAULT_REPORT_CONTRACT = Path(
    r"F:\Work\IDS_ML_New\artifacts\modeling\cic_iot_diad_2024_family_views\direct_multiclass\reports\direct_multiclass_eval.json"
)
REPO_ROOT = Path(__file__).resolve().parents[2]
APPROVED_OUTPUT_ROOTS = (REPO_ROOT / "artifacts", Path(tempfile.gettempdir()).resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage a Kaggle kernel bundle for the direct multiclass baseline.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--dataset-id", type=str, default=DEFAULT_DATASET_ID)
    parser.add_argument("--kernel-id", type=str, default=DEFAULT_KERNEL_ID)
    parser.add_argument("--title", type=str, default=DEFAULT_KERNEL_TITLE)
    parser.add_argument("--direct-script-path", type=Path, default=DEFAULT_DIRECT_SCRIPT)
    parser.add_argument("--helper-script-path", type=Path, default=DEFAULT_HELPER_SCRIPT)
    parser.add_argument("--gpu-devices", type=str, default=DEFAULT_GPU_DEVICES)
    parser.add_argument("--report-contract-path", type=Path, default=DEFAULT_REPORT_CONTRACT)
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


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


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_readme(title: str, dataset_id: str, report_contract_path: Path, gpu_devices: str) -> str:
    output_dir = "/kaggle/working/direct_multiclass_results"
    report_path = f"{output_dir}/reports/direct_multiclass_eval.json"
    dataset_name = dataset_id.split("/", 1)[1]
    kaggle_dataset_root = f"/kaggle/input/{dataset_name}/{dataset_name}-binary-ids"
    return f"""# {title}

Kaggle bundle for the direct multiclass baseline.

Dataset source:

- `{dataset_id}`
- Expected Kaggle path in this bundle: `{kaggle_dataset_root}`
- Preferred accelerator: `GPU`
- GPU devices default in this bundle: `{gpu_devices}` (intended for dual T4)
- The notebook in this bundle can bootstrap `family_views` automatically if the attached dataset only contains the frozen binary artifact.

Runtime outputs:

- `{output_dir}/models/catboost_direct_multiclass.cbm`
- `{report_path}`

How to bring the report back into this repo:

1. Run the Kaggle kernel against `{dataset_id}`.
2. Download `{report_path}` from Kaggle.
3. Place that JSON at `{report_contract_path.as_posix()}` in the repo.
4. Keep the report schema unchanged so Story 3 can compare it against the stage-2 family classifier output.

Bundle contents:

- `kernel-metadata.json`
- `README.md`
- `train_direct_multiclass.py` (self-contained Kaggle entrypoint)
- `train_direct_multiclass.ipynb` (self-contained Kaggle notebook with family-view bootstrap fallback)
- `train_iot_diad_family_classifier.py` (reference helper source)
"""


def strip_future_import(source_text: str) -> str:
    return source_text.replace("from __future__ import annotations\n\n", "", 1)


def strip_helper_main(source_text: str) -> str:
    marker = '\n\nif __name__ == "__main__":\n    main()\n'
    if marker in source_text:
        return source_text.replace(marker, "\n", 1)
    return source_text


def strip_helper_import_block(source_text: str) -> str:
    target = """from ml_pipeline.training.train_iot_diad_family_classifier import (
    build_label_index,
    ensure_output_dirs,
    evaluate_known_split,
    evaluate_ood_split,
    load_family_view_index,
    load_feature_columns,
    resolve_dataset_file,
    resolve_view_split_path,
    sample_train_split,
    train_model,
)

"""
    return source_text.replace(target, "", 1)


def render_helper_source(source_text: str) -> str:
    rendered = strip_helper_main(strip_future_import(source_text))
    return rendered


def render_direct_script(direct_source_text: str, helper_source_text: str, dataset_id: str, gpu_devices: str) -> str:
    rendered = strip_helper_import_block(strip_future_import(direct_source_text))
    rendered = rendered.replace(
        'Path(r"F:\\Work\\IDS_ML_New\\artifacts\\cic_iot_diad_2024_family_views")',
        f'Path("/kaggle/input/{dataset_id.split("/", 1)[1]}")',
    )
    rendered = rendered.replace(
        'Path(r"F:\\Work\\IDS_ML_New\\artifacts\\modeling\\cic_iot_diad_2024_family_views\\direct_multiclass")',
        'Path("/kaggle/working/direct_multiclass_results")',
    )
    rendered = rendered.replace(
        'DEFAULT_TASK_TYPE = "CPU"',
        'DEFAULT_TASK_TYPE = "GPU"',
    )
    rendered = rendered.replace(
        'DEFAULT_DEVICES = ""',
        f'DEFAULT_DEVICES = "{gpu_devices}"',
    )
    helper_rendered = render_helper_source(helper_source_text)
    return "from __future__ import annotations\n\n" + helper_rendered + "\n\n" + rendered


def strip_cli_for_notebook(source_text: str) -> str:
    module = ast.parse(source_text)
    filtered_body = []
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name in {"parse_args", "main"}:
            continue
        if isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "__main__"
            ):
                continue
        if isinstance(node, ast.Import):
            remaining_names = [alias for alias in node.names if alias.name != "argparse"]
            if remaining_names:
                filtered_body.append(ast.Import(names=remaining_names))
            continue
        filtered_body.append(node)

    module.body = filtered_body
    return ast.unparse(module) + "\n"


def build_notebook_markdown(title: str) -> list[str]:
    return [
        f"# {title}\n",
        "\n",
        "Standalone Kaggle notebook for the direct multiclass CatBoost baseline.\n",
        "\n",
        "- Self-contained: no repo script imports required at runtime\n",
        "- Notebook-safe: no CLI arg parsing or `main()` auto-execution\n",
        "- Auto-bootstrap: derives `family_views` from the binary artifact if the attached dataset only contains the binary splits\n",
        "- Default GPU mode: `task_type=\"GPU\"`\n",
        "- Default devices: `0:1` for dual T4\n",
        "- Output report: `/kaggle/working/direct_multiclass_results/reports/direct_multiclass_eval.json`\n",
    ]


def build_notebook_run_cell(dataset_id: str, gpu_devices: str) -> str:
    dataset_name = dataset_id.split("/", 1)[1]
    kaggle_dataset_root = f"/kaggle/input/{dataset_name}/{dataset_name}-binary-ids"
    return textwrap.dedent(
        f"""
        from types import SimpleNamespace
        import shutil
        import pyarrow as pa

        SOURCE_SPLITS = ("train", "val", "test", "ood_attack_holdout")
        OOD_FAMILIES = {{"BruteForce", "Recon"}}
        KNOWN_ATTACK_FAMILIES = ["DDoS", "DoS", "Mirai", "Spoofing", "Web-Based"]
        DIRECT_MULTICLASS_LABELS = ["Benign", *KNOWN_ATTACK_FAMILIES]
        METADATA_COLUMNS = [
            "source_file",
            "attack_family",
            "attack_scenario",
            "derived_label_binary",
            "derived_label_family",
            "split",
        ]


        class NotebookSplitWriter:
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


        def ensure_clean_dir(path: Path) -> None:
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)


        def filter_for_view(frame: pd.DataFrame, view_name: str, split_name: str) -> pd.DataFrame:
            if split_name == "ood_attack_holdout":
                return frame[frame["derived_label_family"].isin(sorted(OOD_FAMILIES))].copy()
            if view_name == "attack_only":
                return frame[frame["derived_label_family"].isin(KNOWN_ATTACK_FAMILIES)].copy()
            if view_name == "direct_multiclass":
                return frame[frame["derived_label_family"].isin(DIRECT_MULTICLASS_LABELS)].copy()
            raise ValueError(f"Unknown view {{view_name}}")


        def derive_family_views_from_binary(source_root: Path, output_root: Path) -> Path:
            ensure_clean_dir(output_root)
            manifests_dir = output_root / "manifests"
            manifests_dir.mkdir(parents=True, exist_ok=True)

            feature_columns_payload = read_json(resolve_dataset_file(source_root, "manifests/feature_columns.json", "feature_columns.json"))
            feature_columns = list(feature_columns_payload["feature_columns"])
            write_json(manifests_dir / "feature_columns.json", feature_columns_payload)

            view_specs = {{
                "attack_only": {{
                    "description": "Attack-only family view for stage-2 family training and oracle evaluation.",
                    "label_space": list(KNOWN_ATTACK_FAMILIES),
                }},
                "direct_multiclass": {{
                    "description": "Direct multiclass family view for offline comparison against the two-stage lane.",
                    "label_space": list(DIRECT_MULTICLASS_LABELS),
                }},
            }}

            view_reports: dict[str, dict[str, object]] = {{}}
            for view_name, spec in view_specs.items():
                clean_dir = output_root / view_name / "clean"
                manifest_dir = output_root / view_name / "manifests"
                clean_dir.mkdir(parents=True, exist_ok=True)
                manifest_dir.mkdir(parents=True, exist_ok=True)

                split_paths = {{split_name: clean_dir / f"{{split_name}}.parquet" for split_name in SOURCE_SPLITS}}
                rows_by_split: dict[str, int] = {{}}
                label_distribution_by_split: dict[str, dict[str, int]] = {{}}

                for split_name in SOURCE_SPLITS:
                    writer = NotebookSplitWriter(split_paths[split_name])
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
                            filtered = filter_for_view(frame, view_name, split_name)
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
                    "view_name": view_name,
                    "description": spec["description"],
                    "source_root": str(source_root),
                    "output_root": str(output_root / view_name),
                    "feature_schema_path": "manifests/feature_columns.json",
                    "label_column": "derived_label_family",
                    "label_space": spec["label_space"],
                    "closed_set_families": list(KNOWN_ATTACK_FAMILIES),
                    "ood_families": sorted(OOD_FAMILIES),
                    "split_paths": {{split_name: f"{{view_name}}/clean/{{split_name}}.parquet" for split_name in SOURCE_SPLITS}},
                    "rows_by_split": rows_by_split,
                    "label_distribution_by_split": label_distribution_by_split,
                }}
                write_json(manifest_dir / "family_view_report.json", report_payload)
                view_reports[view_name] = report_payload

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
                    view_name: {{
                        "description": spec["description"],
                        "label_column": "derived_label_family",
                        "label_space": spec["label_space"],
                        "closed_set_families": list(KNOWN_ATTACK_FAMILIES),
                        "ood_probe_families": sorted(OOD_FAMILIES),
                        "split_paths": {{split_name: f"{{view_name}}/clean/{{split_name}}.parquet" for split_name in SOURCE_SPLITS}},
                        "report_path": f"{{view_name}}/manifests/family_view_report.json",
                    }}
                    for view_name, spec in view_specs.items()
                }},
            }}
            write_json(manifests_dir / "family_view_index.json", index_payload)
            write_json(manifests_dir / "family_view_reports.json", view_reports)
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
            print("Deriving family views from binary artifact at", binary_root)
            return derive_family_views_from_binary(binary_root, derived_root)


        CONFIG = {{
            "dataset_root": Path("{kaggle_dataset_root}"),
            "output_root": Path("/kaggle/working/direct_multiclass_results"),
            "view_name": "direct_multiclass",
            "seed": 42,
            "batch_size": 100_000,
            "max_train_rows": 1_000_000,
            "iterations": 300,
            "learning_rate": 0.06,
            "depth": 8,
            "l2_leaf_reg": 3.0,
            "thread_count": 1,
            "task_type": "GPU",
            "devices": "{gpu_devices}",
        }}

        resolved_config = dict(CONFIG)
        resolved_config["dataset_root"] = ensure_family_view_root(
            Path(resolved_config["dataset_root"]),
            Path("/kaggle/working/cic_iot_diad_2024_family_views_runtime"),
        )
        print("Using dataset root:", resolved_config["dataset_root"])
        print("Using output root:", resolved_config["output_root"])
        report = run_training(SimpleNamespace(**resolved_config))
        report_path = Path(report["output_root"]) / "reports" / "direct_multiclass_eval.json"
        print("Run complete")
        print("Report:", report_path)
        print("Model:", report["model"]["artifact_path"])
        """
    ).strip() + "\n"


def write_notebook_bundle(bundle_root: Path, title: str, rendered_direct: str, dataset_id: str, gpu_devices: str) -> None:
    notebook_code = strip_cli_for_notebook(rendered_direct)
    notebook_payload = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": build_notebook_markdown(title),
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": notebook_code.splitlines(keepends=True),
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": build_notebook_run_cell(dataset_id, gpu_devices).splitlines(keepends=True),
            },
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    write_json(bundle_root / "train_direct_multiclass.ipynb", notebook_payload)


def stage_kernel_bundle(
    *,
    bundle_root: Path,
    dataset_id: str,
    kernel_id: str,
    title: str,
    direct_script_path: Path,
    helper_script_path: Path,
    gpu_devices: str,
    report_contract_path: Path,
) -> Path:
    ensure_clean_dir(bundle_root)

    direct_source = direct_script_path.read_text(encoding="utf-8")
    helper_source = helper_script_path.read_text(encoding="utf-8")
    rendered_direct = render_direct_script(direct_source, helper_source, dataset_id, gpu_devices)

    (bundle_root / "train_direct_multiclass.py").write_text(rendered_direct, encoding="utf-8")
    shutil.copy2(helper_script_path, bundle_root / "train_iot_diad_family_classifier.py")
    write_notebook_bundle(bundle_root, title, rendered_direct, dataset_id, gpu_devices)

    write_json(
        bundle_root / "kernel-metadata.json",
        {
            "id": kernel_id,
            "title": title,
            "code_file": "train_direct_multiclass.py",
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
    (bundle_root / "README.md").write_text(build_readme(title, dataset_id, report_contract_path, gpu_devices), encoding="utf-8")
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
        direct_script_path=args.direct_script_path.resolve(),
        helper_script_path=args.helper_script_path.resolve(),
        gpu_devices=args.gpu_devices,
        report_contract_path=args.report_contract_path.resolve(),
    )
    log(f"Staged direct multiclass Kaggle kernel at {staged_root}")


if __name__ == "__main__":
    main()
