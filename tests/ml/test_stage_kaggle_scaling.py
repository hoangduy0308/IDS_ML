from __future__ import annotations

import json
from pathlib import Path

from ml_pipeline.benchmark.stage_kaggle_scaling import RUN_MATRIX, main


def test_stage_scaling_generates_all_notebooks(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "artifacts"
    upload_root = tmp_path / "upload"
    monkeypatch.setattr(
        "sys.argv",
        [
            "stage_kaggle_scaling.py",
            "--output-root",
            str(output_root),
            "--upload-root",
            str(upload_root),
        ],
    )

    main()

    notebooks = sorted(upload_root.glob("*.ipynb"))
    assert len(notebooks) == len(RUN_MATRIX)
    assert notebooks[0].name == "01_catboost_2m_scaling.ipynb"
    assert notebooks[-1].name == "10_catboost_full_data_attempt.ipynb"


def test_rendered_scaling_notebook_compiles_and_contains_target_rows(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "artifacts"
    upload_root = tmp_path / "upload"
    monkeypatch.setattr(
        "sys.argv",
        [
            "stage_kaggle_scaling.py",
            "--output-root",
            str(output_root),
            "--upload-root",
            str(upload_root),
        ],
    )

    main()

    notebook_path = upload_root / "05_hist_gb_4m_scaling.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    code = "".join(notebook["cells"][0]["source"])

    assert 'RUN_KEY = "hist_gb_4m_scaling"' in code
    assert 'TRAIN_TARGET_ROWS = 4000000' in code
    assert 'EXPECTED_DATASET_SUBDIR = "cic-iot-diad-2024-binary-ids"' in code
    compile(code, str(notebook_path), "exec")


def test_full_data_attempt_renders_none_target_rows(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "artifacts"
    upload_root = tmp_path / "upload"
    monkeypatch.setattr(
        "sys.argv",
        [
            "stage_kaggle_scaling.py",
            "--output-root",
            str(output_root),
            "--upload-root",
            str(upload_root),
        ],
    )

    main()

    notebook_path = upload_root / "10_catboost_full_data_attempt.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    code = "".join(notebook["cells"][0]["source"])

    assert 'RUN_KEY = "catboost_full_data_attempt"' in code
    assert "TRAIN_TARGET_ROWS = None" in code
    compile(code, str(notebook_path), "exec")
