from __future__ import annotations

from pathlib import Path
import sys

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from ml_pipeline.benchmark.stage_kaggle_benchmark import (  # noqa: F401
    DEFAULT_DATASET_ID,
    DEFAULT_DATASET_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DATA_FILES,
    MANIFEST_FILES,
    MODEL_SPECS,
    dataset_readme,
    ensure_clean_dir,
    kernel_readme,
    link_or_copy,
    log,
    main,
    parse_args,
    read_json,
    render_template,
    stage_dataset_bundle,
    stage_kernel_bundles,
    validate_inputs,
    write_helper_scripts,
    write_json,
)


if __name__ == "__main__":
    main()
