from __future__ import annotations

import sys

from wrapper_smoke_support import (
    assert_command_smoke,
    assert_help_smoke,
    run_command,
    run_python_module_help,
    run_python_script_help,
)


WRAPPER_MODULES = [
    "scripts.ids_inference",
    "scripts.ids_live_capture",
    "scripts.ids_realtime_pipeline",
    "scripts.ids_live_sensor",
    "scripts.ids_live_sensor_health",
    "scripts.ids_live_sensor_sinks",
]

DIRECT_FILE_WRAPPERS = [
    "scripts/ids_realtime_pipeline.py",
]


def test_phase1_runtime_wrapper_help_smoke() -> None:
    for module_name in WRAPPER_MODULES:
        completed = run_python_module_help(module_name)
        assert_help_smoke(completed, module_name)


def test_phase1_runtime_wrapper_direct_file_help_smoke() -> None:
    for script_relative_path in DIRECT_FILE_WRAPPERS:
        completed = run_python_script_help(script_relative_path)
        assert_help_smoke(completed, script_relative_path)


def test_phase1_runtime_wrapper_module_alias_smoke() -> None:
    completed = run_command(
        [
            sys.executable,
            "-c",
            "import scripts.ids_live_flow_bridge as bridge; "
            "print(hasattr(bridge, 'BridgeWindowResult'))",
        ]
    )

    assert_command_smoke(completed, "scripts.ids_live_flow_bridge")
    assert "True" in completed.stdout
