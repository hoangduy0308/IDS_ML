from __future__ import annotations

from pathlib import Path
import sys

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from ml_pipeline.benchmark.stage_kaggle_tuning import *  # noqa: F401,F403
from ml_pipeline.benchmark.stage_kaggle_tuning import main


if __name__ == "__main__":
    main()
