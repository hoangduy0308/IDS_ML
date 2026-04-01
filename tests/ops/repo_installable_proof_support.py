from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_command(
    argv: list[str],
    *,
    cwd: Path = REPO_ROOT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def venv_python(tmp_path: Path) -> Path:
    venv_dir = tmp_path / "venv"
    completed = run_command([sys.executable, "-m", "venv", str(venv_dir)], cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr

    pyvenv_cfg = (venv_dir / "pyvenv.cfg").read_text(encoding="utf-8")
    assert "include-system-site-packages = false" in pyvenv_cfg

    windows_python = venv_dir / "Scripts" / "python.exe"
    posix_python = venv_dir / "bin" / "python"
    python_path = windows_python if windows_python.exists() else posix_python
    assert python_path.exists(), f"venv python not found under {venv_dir}"
    return python_path.resolve()


def _editable_install_cache_identity() -> str:
    payload = "\n".join(
        [
            str(REPO_ROOT.resolve()),
            str(Path(sys.executable).resolve()),
            ".".join(str(part) for part in sys.version_info[:3]),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _editable_install_signature() -> str:
    pyproject = REPO_ROOT / "pyproject.toml"
    payload = "\n".join(
        [
            hashlib.sha256(pyproject.read_bytes()).hexdigest(),
            str(REPO_ROOT.resolve()),
            str(Path(sys.executable).resolve()),
            ".".join(str(part) for part in sys.version_info[:3]),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _probe_editable_install(python_path: Path) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            str(python_path),
            "-I",
            "-c",
            "import ids.console.server, ids.ops.operator_console_manage; print('ok')",
        ],
        cwd=python_path.parent,
    )


def shared_editable_repo_python(cache_key: str) -> Path:
    cache_root = Path(tempfile.gettempdir()) / (
        f"ids_ml_new_{cache_key}_{_editable_install_cache_identity()}"
    )
    cache_root.mkdir(parents=True, exist_ok=True)

    signature = _editable_install_signature()
    stamp_path = cache_root / ".editable-install.stamp"

    windows_python = cache_root / "venv" / "Scripts" / "python.exe"
    posix_python = cache_root / "venv" / "bin" / "python"
    python_path = windows_python if windows_python.exists() else posix_python
    if not python_path.exists():
        python_path = venv_python(cache_root)

    if not stamp_path.exists() or stamp_path.read_text(encoding="utf-8").strip() != signature:
        completed = run_command(
            [str(python_path), "-m", "pip", "install", "-e", str(REPO_ROOT)],
            cwd=cache_root,
        )
        assert completed.returncode == 0, completed.stderr
        stamp_path.write_text(signature + "\n", encoding="utf-8")

    probe = _probe_editable_install(python_path)
    if probe.returncode != 0:
        if stamp_path.exists():
            stamp_path.unlink()
        completed = run_command(
            [str(python_path), "-m", "pip", "install", "-e", str(REPO_ROOT)],
            cwd=cache_root,
        )
        assert completed.returncode == 0, completed.stderr
        stamp_path.write_text(signature + "\n", encoding="utf-8")
        probe = _probe_editable_install(python_path)
        assert probe.returncode == 0, probe.stderr

    stale_shadow_path = site_packages_dir(python_path) / "zz_shadow_import.pth"
    if stale_shadow_path.exists():
        stale_shadow_path.unlink()

    return python_path.resolve()


def site_packages_dir(python_binary: Path) -> Path:
    completed = run_command(
        [str(python_binary), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
    )
    assert completed.returncode == 0, completed.stderr
    return Path(completed.stdout.strip()).resolve()


def write_shadow_sitecustomize(site_packages_dir_path: Path) -> Path:
    site_packages_dir_path.mkdir(parents=True, exist_ok=True)
    path = site_packages_dir_path / "sitecustomize.py"
    path.write_text(
        "\n".join(
            [
                "import importlib.util",
                "import os",
                "import sys",
                "from pathlib import Path",
                "shadow_module = os.environ.get('IDS_TEST_SHADOW_IMPORT_MODULE')",
                "shadow_root = os.environ.get('IDS_TEST_SHADOW_IMPORT_ROOT')",
                "if shadow_module and shadow_root:",
                "    class _ShadowFinder:",
                "        def find_spec(self, fullname, path=None, target=None):",
                "            if fullname != shadow_module:",
                "                return None",
                "            shadow_path = Path(shadow_root).joinpath(*fullname.split('.')).with_suffix('.py')",
                "            if not shadow_path.is_file():",
                "                return None",
                "            return importlib.util.spec_from_file_location(fullname, shadow_path)",
                "    sys.meta_path.insert(0, _ShadowFinder())",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def scripts_dir(venv_python_path: Path) -> Path:
    completed = run_command(
        [str(venv_python_path), "-c", "import sysconfig; print(sysconfig.get_path('scripts'))"],
    )
    assert completed.returncode == 0, completed.stderr
    return Path(completed.stdout.strip()).resolve()


def resolve_console_script(scripts_dir_path: Path, command_name: str) -> Path:
    for suffix in ("", ".exe", ".cmd", ".bat"):
        candidate = scripts_dir_path / f"{command_name}{suffix}"
        if candidate.exists():
            return candidate.resolve()
    raise AssertionError(f"console script not found for {command_name} under {scripts_dir_path}")
