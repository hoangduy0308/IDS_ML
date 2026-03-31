from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(argv: list[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _venv_python(tmp_path: Path) -> Path:
    venv_dir = tmp_path / "venv"
    create = _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=tmp_path)
    assert create.returncode == 0, create.stderr

    windows_python = venv_dir / "Scripts" / "python.exe"
    posix_python = venv_dir / "bin" / "python"
    python_path = windows_python if windows_python.exists() else posix_python
    assert python_path.exists(), f"venv python not found under: {venv_dir}"
    return python_path


def _scripts_dir(venv_python: Path) -> Path:
    result = _run(
        [str(venv_python), "-c", "import sysconfig; print(sysconfig.get_path('scripts'))"],
    )
    assert result.returncode == 0, result.stderr
    return Path(result.stdout.strip()).resolve()


def _resolve_console_script(scripts_dir: Path, command_name: str) -> Path:
    for suffix in ("", ".exe", ".cmd", ".bat"):
        candidate = scripts_dir / f"{command_name}{suffix}"
        if candidate.exists():
            return candidate
    raise AssertionError(f"console script not found for {command_name} under {scripts_dir}")


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
    venv_python = _venv_python(tmp_path)
    install = _run(
        [str(venv_python), "-m", "pip", "install", "--no-deps", "-e", str(REPO_ROOT)],
        cwd=tmp_path,
    )
    assert install.returncode == 0, install.stderr

    scripts_dir = _scripts_dir(venv_python)
    ids_stack = _resolve_console_script(scripts_dir, "ids-stack")
    ids_bundle_manage = _resolve_console_script(scripts_dir, "ids-model-bundle-manage")
    assert ids_stack.exists()
    assert ids_bundle_manage.exists()

    inspect = _run(
        [
            str(venv_python),
            "-c",
            (
                "import json, importlib.metadata as md; "
                "from importlib.resources import files; "
                "dist=md.distribution('ids-ml-new'); "
                "eps={ep.name: ep.value for ep in dist.entry_points if ep.group=='console_scripts'}; "
                "print(json.dumps({"
                "'ids-stack': eps.get('ids-stack'), "
                "'ids-model-bundle-manage': eps.get('ids-model-bundle-manage'), "
                "'ids-live-sensor': eps.get('ids-live-sensor'), "
                "'templates_dir': files('ids.console').joinpath('templates').is_dir(), "
                "'static_dir': files('ids.console').joinpath('static').is_dir()"
                "}))"
            ),
        ],
        cwd=tmp_path,
    )
    assert inspect.returncode == 0, inspect.stderr
    payload = json.loads(inspect.stdout)

    assert payload["ids-stack"] == "ids.ops.same_host_stack_manage:main"
    assert payload["ids-model-bundle-manage"] == "ids.ops.model_bundle_manage:main"
    assert payload["ids-live-sensor"] == "ids.runtime.live_sensor:main"
    assert payload["templates_dir"] is True
    assert payload["static_dir"] is True
