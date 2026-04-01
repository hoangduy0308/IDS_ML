from __future__ import annotations

from pathlib import Path
import subprocess
import sys


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
