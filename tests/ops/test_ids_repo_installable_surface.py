from __future__ import annotations

import json
import tomllib
from pathlib import Path

from repo_installable_proof_support import (
    REPO_ROOT,
    resolve_console_script,
    run_command,
    scripts_dir,
    venv_python,
)


def test_pyproject_console_scripts_map_to_canonical_modules() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["ids-stack"] == "ids.ops.same_host_stack_manage:main"
    assert scripts["ids-model-bundle-manage"] == "ids.ops.model_bundle_manage:main"
    assert scripts["ids-live-sensor"] == "ids.runtime.live_sensor:main"
    assert scripts["ids-operator-console-server"] == "ids.console.server:main"
    assert scripts["ids-package-final-model"] == "ml_pipeline.packaging.package_final_model:main"
    assert all(not target.startswith("scripts.") for target in scripts.values())


def test_editable_install_surface_exposes_entrypoints_and_console_assets(tmp_path: Path) -> None:
    venv_python_path = venv_python(tmp_path)
    install = run_command(
        [str(venv_python_path), "-m", "pip", "install", "-e", str(REPO_ROOT)],
        cwd=tmp_path,
    )
    assert install.returncode == 0, install.stderr

    scripts_dir_path = scripts_dir(venv_python_path)
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected_scripts: dict[str, str] = pyproject["project"]["scripts"]
    resolved_scripts = {
        command_name: resolve_console_script(scripts_dir_path, command_name)
        for command_name in expected_scripts
    }
    assert all(path.exists() for path in resolved_scripts.values())

    for command_name, script_path in resolved_scripts.items():
        help_run = run_command([str(script_path), "--help"], cwd=tmp_path)
        assert help_run.returncode == 0, f"{command_name}: {help_run.stderr}"
        assert "usage:" in help_run.stdout.lower(), command_name

    inspect = run_command(
        [
            str(venv_python_path),
            "-c",
            (
                "import json, importlib.metadata as md; "
                "from importlib.resources import files; "
                "dist=md.distribution('ids-ml-new'); "
                "eps={ep.name: ep.value for ep in dist.entry_points if ep.group=='console_scripts'}; "
                "print(json.dumps({"
                "'entry_points': eps, "
                "'templates_dir': files('ids.console').joinpath('templates').is_dir(), "
                "'static_dir': files('ids.console').joinpath('static').is_dir()"
                "}))"
            ),
        ],
        cwd=tmp_path,
    )
    assert inspect.returncode == 0, inspect.stderr
    payload = json.loads(inspect.stdout)

    assert payload["entry_points"] == expected_scripts
    assert payload["templates_dir"] is True
    assert payload["static_dir"] is True
