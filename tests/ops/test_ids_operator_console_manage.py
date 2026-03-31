from __future__ import annotations

from wrapper_smoke_support import assert_help_smoke, run_python_module_help, run_python_script_help


def test_script_wrapper_help_runs_through_module_entrypoint() -> None:
    help_run = run_python_module_help("scripts.ids_operator_console_manage")
    assert_help_smoke(help_run, "scripts.ids_operator_console_manage")
    assert "usage:" in help_run.stdout.lower()


def test_script_wrapper_help_runs_through_direct_file_entrypoint() -> None:
    help_run = run_python_script_help("scripts/ids_operator_console_manage.py")
    assert_help_smoke(help_run, "scripts/ids_operator_console_manage.py")
    assert "usage:" in help_run.stdout.lower()
