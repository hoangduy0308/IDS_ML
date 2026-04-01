from __future__ import annotations

import re
import sys
from pathlib import Path

from wrapper_smoke_support import assert_command_smoke, run_command


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
PYTEST_COMMAND = [
    sys.executable,
    "-m",
    "pytest",
    "tests/runtime/test_ids_inference.py",
    "tests/runtime/test_ids_realtime_pipeline.py",
    "tests/runtime/test_ids_record_adapter.py",
    "-q",
]


def _top_level_docs_stubs() -> list[Path]:
    return sorted(path for path in DOCS_ROOT.glob("*.md") if path.name != "README.md")


def _stub_target_path(doc_path: Path) -> Path:
    text = doc_path.read_text(encoding="utf-8")
    assert "compatibility stub" in text, doc_path
    match = re.search(r"\[(?P<label>[^\]]+)\]\((?P<target>[^)]+)\)", text)
    assert match is not None, doc_path
    return Path(match.group("target"))


def test_top_level_docs_stubs_point_to_current_or_archive_targets() -> None:
    for doc_path in _top_level_docs_stubs():
        target_path = _stub_target_path(doc_path)
        assert target_path.exists(), doc_path
        resolved_target = target_path.resolve()
        assert (
            resolved_target.is_relative_to(DOCS_ROOT / "current")
            or resolved_target.is_relative_to(DOCS_ROOT / "archive")
        ), doc_path


def test_documented_mirrored_pytest_commands_are_live() -> None:
    documented_pages = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "current" / "operations" / "e2e_demo_runbook.md",
        REPO_ROOT / "docs" / "current" / "ml" / "system_evaluation.md",
    ]

    expected_command = (
        "python -m pytest tests/runtime/test_ids_inference.py "
        "tests/runtime/test_ids_realtime_pipeline.py "
        "tests/runtime/test_ids_record_adapter.py -q"
    )
    for doc_path in documented_pages:
        assert expected_command in doc_path.read_text(encoding="utf-8"), doc_path

    completed = run_command(PYTEST_COMMAND)
    assert_command_smoke(completed, "documented mirrored pytest command")


def test_packaged_operator_docs_keep_canonical_command_surface() -> None:
    stack_doc = (REPO_ROOT / "docs" / "current" / "operations" / "ids_same_host_stack_operations.md").read_text(
        encoding="utf-8"
    )
    live_sensor_doc = (REPO_ROOT / "docs" / "current" / "runtime" / "ids_live_sensor_operations.md").read_text(
        encoding="utf-8"
    )
    bundle_doc = (REPO_ROOT / "docs" / "current" / "runtime" / "final_model_bundle.md").read_text(
        encoding="utf-8"
    )

    assert "ids-stack" in stack_doc
    assert "compatibility entrypoint" in stack_doc
    assert "scripts/ids_same_host_stack_manage.py" in stack_doc
    assert "/opt/ids_ml_new/.venv/bin/python" in stack_doc

    assert "ids-live-sensor-preflight" in live_sensor_doc
    assert "ids-model-bundle-manage" in live_sensor_doc
    assert "ids-inference" in live_sensor_doc

    assert "ids-package-final-model" in bundle_doc
    assert "ids-model-bundle-manage" in bundle_doc
    assert "F:\\Work\\IDS_ML_New" not in bundle_doc


def test_console_docs_index_links_are_portable() -> None:
    console_readme = (REPO_ROOT / "docs" / "current" / "console" / "README.md").read_text(encoding="utf-8")

    for target in [
        "ids_operator_console_architecture.md",
        "ids_operator_console_ui_prd.md",
        "ids_operator_console_ui_surface_spec.md",
        "ids_operator_console_operations.md",
    ]:
        assert f"[{target}]({target})" in console_readme

    assert "F:/Work/IDS_ML_New" not in console_readme
    assert "F:\\Work\\IDS_ML_New" not in console_readme
