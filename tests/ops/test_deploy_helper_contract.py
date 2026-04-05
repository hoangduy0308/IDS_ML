from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXED_RELEASE_TIMESTAMP = "20260405T181500Z"


def _to_bash_path(path: Path | str) -> str:
    resolved = Path(path).resolve()
    text = str(resolved).replace("\\", "/")
    if os.name == "nt" and len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        return f"/mnt/{text[0].lower()}{text[2:]}"
    return text


def _write_release_bundle_contract(bundle_root: Path, *, valid: bool) -> Path:
    bundle_root.mkdir(parents=True, exist_ok=True)
    feature_columns_path = bundle_root / "feature_columns.json"
    feature_columns_payload = {"feature_columns": ["f1", "f2"]}
    feature_columns_path.write_text(json.dumps(feature_columns_payload), encoding="utf-8")
    (bundle_root / "model.cbm").write_text("model", encoding="utf-8")

    schema_sha256 = hashlib.sha256(feature_columns_path.read_bytes()).hexdigest()
    if not valid:
        schema_sha256 = "0" * 64

    manifest = {
        "manifest_version": 2,
        "bundle_name": "bundle-proof",
        "created_at": "2026-04-05T00:00:00+07:00",
        "model_key": "catboost_full_data",
        "model_family": "CatBoostClassifier",
        "model_artifact": "model.cbm",
        "feature_columns_file": "feature_columns.json",
        "threshold": 0.5,
        "positive_label": "Attack",
        "negative_label": "Benign",
        "feature_count": 2,
        "train_rows": 123,
        "metrics_file": "metrics.json",
        "training_summary_file": "training_summary.json",
        "compatibility": {
            "feature_schema": {
                "kind": "feature_columns_json.v1",
                "path": "feature_columns.json",
                "feature_count": 2,
                "sha256": schema_sha256,
            },
            "inference_contract": {
                "version": "ids_binary_classifier.v1",
                "prediction_type": "binary_classifier",
                "score_field": "attack_score",
                "alert_field": "is_alert",
                "threshold_source": "bundle",
                "threshold": 0.5,
                "positive_label": "Attack",
                "negative_label": "Benign",
                "allows_external_model_path": False,
                "allows_external_feature_columns_path": False,
                "allows_external_threshold_override": False,
            },
        },
    }
    (bundle_root / "model_bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
    return bundle_root


def _git(repo_root: Path, *args: str) -> None:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Codex",
            "GIT_AUTHOR_EMAIL": "codex@example.com",
            "GIT_COMMITTER_NAME": "Codex",
            "GIT_COMMITTER_EMAIL": "codex@example.com",
        }
    )
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def _make_release_fixture_repo(tmp_path: Path, *, valid_bundle: bool) -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "fixture-repo"
    bundle_root = repo_root / "artifacts" / "final_model" / "catboost_full_data_v1"
    output_dir = tmp_path / "release-output"
    fake_python = tmp_path / "fake-python.sh"
    real_python = _to_bash_path(sys.executable)

    _write_release_bundle_contract(bundle_root, valid=valid_bundle)
    (repo_root / "pyproject.toml").parent.mkdir(parents=True, exist_ok=True)
    (repo_root / "pyproject.toml").write_text(
        "[project]\nname = 'ids-ml-new'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (repo_root / "requirements.txt").write_text("", encoding="utf-8")

    _git(repo_root, "init")
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-m", "seed release fixture")

    fake_python.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'real_python="{real_python}"',
                f'fixed_timestamp="{FIXED_RELEASE_TIMESTAMP}"',
                "to_windows_path() {",
                "  case \"$1\" in",
                "    /mnt/[a-z]/*)",
                "      local drive rest",
                "      drive=${1#/mnt/}",
                "      drive=${drive%%/*}",
                "      rest=${1#\"/mnt/${drive}\"}",
                "      printf '%s:%s\\n' \"$(printf '%s' \"${drive}\" | tr '[:lower:]' '[:upper:]')\" \"${rest}\"",
                "      ;;",
                "    *)",
                "      printf '%s\\n' \"$1\"",
                "      ;;",
                "  esac",
                "}",
                'case "${1-}" in',
                "  -c)",
                '    code="${2-}"',
                '    if [[ "${code}" == *"datetime.now(timezone.utc).strftime(\'%Y%m%dT%H%M%SZ\')"* ]]; then',
                '      printf "%s\\n" "${fixed_timestamp}"',
                "      exit 0",
                "    fi",
                '    if [[ "${code}" == *"load_model_bundle_manifest"* ]]; then',
                '      bundle_root="$(to_windows_path "${4-}")"',
                '      exec "${real_python}" - "${bundle_root}" <<\'PY\'',
                "import hashlib",
                "import json",
                "import sys",
                "from pathlib import Path",
                "",
                "bundle_root = Path(sys.argv[1])",
                "manifest_path = bundle_root / 'model_bundle.json'",
                "if not manifest_path.is_file():",
                "    raise SystemExit(f'Bundle manifest not found: {manifest_path}')",
                "manifest = json.loads(manifest_path.read_text(encoding='utf-8'))",
                "feature_schema = manifest.get('compatibility', {}).get('feature_schema', {})",
                "feature_columns_file = str(manifest.get('feature_columns_file', 'feature_columns.json'))",
                "feature_columns_path = bundle_root / feature_columns_file",
                "if not feature_columns_path.is_file():",
                "    raise SystemExit(f'Bundle feature schema missing: {feature_columns_path}')",
                "if int(manifest.get('manifest_version', 0)) != 2:",
                "    raise SystemExit('Unsupported model bundle manifest version')",
                "actual_digest = hashlib.sha256(feature_columns_path.read_bytes()).hexdigest()",
                "if str(feature_schema.get('sha256', '')).strip() != actual_digest:",
                "    raise SystemExit(f'Bundle feature schema digest mismatch for {feature_columns_path}')",
                "PY",
                "    fi",
                '    exec "${real_python}" "$@"',
                "    ;;",
                "  -m)",
                '    if [[ "${2-}" == "pip" && "${3-}" == "wheel" ]]; then',
                "      exit 0",
                "    fi",
                '    exec "${real_python}" "$@"',
                "    ;;",
                "  *)",
                '    exec "${real_python}" "$@"',
                "    ;;",
                "esac",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    fake_python.chmod(fake_python.stat().st_mode | 0o111)

    return repo_root, output_dir, fake_python


def _run_build_release(repo_root: Path, output_dir: Path, python_bin: Path) -> subprocess.CompletedProcess[str]:
    build_release_script = _to_bash_path(REPO_ROOT / "ops" / "build_release.sh")
    return subprocess.run(
        [
            "bash",
            build_release_script,
            "--repo-root",
            _to_bash_path(repo_root),
            "--output-dir",
            _to_bash_path(output_dir),
            "--python-bin",
            _to_bash_path(python_bin),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _rewrite_working_tree_bundle_contract(repo_root: Path, *, valid: bool) -> None:
    bundle_root = repo_root / "artifacts" / "final_model" / "catboost_full_data_v1"
    _write_release_bundle_contract(bundle_root, valid=valid)


def _write_executable(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def _copy_install_surface(repo_root: Path) -> None:
    for relative_path in [
        Path("ops/install.sh"),
        Path("ops/ids-operator-console.env.example"),
        Path("ops/ids-live-sensor.env.example"),
        Path("deploy/systemd/ids-live-sensor.service"),
        Path("deploy/systemd/ids-operator-console.service"),
        Path("deploy/systemd/ids-operator-console-notify.service"),
        Path("pyproject.toml"),
        Path("requirements.txt"),
    ]:
        source = REPO_ROOT / relative_path
        target = repo_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    ids_dir = repo_root / "ids"
    ids_dir.mkdir(parents=True, exist_ok=True)
    (ids_dir / "__init__.py").write_text("", encoding="utf-8")


def _write_install_fakes(fake_bin: Path, *, log_path: Path) -> Path:
    _write_executable(
        fake_bin / "python3.11",
        f"""#!/usr/bin/env bash
set -euo pipefail
log_file="{_to_bash_path(log_path)}"
if [[ "${{1-}}" == "-c" ]]; then
  if [[ "${{2-}}" == *"sys.version_info"* ]]; then
    printf '3.11\\n'
  fi
  exit 0
fi
if [[ "${{1-}}" == "-m" && "${{2-}}" == "venv" ]]; then
  target="${{@: -1}}"
  mkdir -p "${{target}}/bin"
  cat > "${{target}}/bin/python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'venv-python %s\\n' "$*" >> "${{IDS_TEST_INSTALL_LOG}}"
if [[ "${{1-}}" == "-c" && "${{2-}}" == *"sysconfig.get_path('scripts')"* ]]; then
  printf '%s\\n' "$(cd -- "$(dirname -- "$0")" && pwd)"
fi
exit 0
EOF
  chmod +x "${{target}}/bin/python"
  cat > "${{target}}/bin/ids-stack" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'ids-stack %s\\n' "$*" >> "${{IDS_TEST_INSTALL_LOG}}"
exit 0
EOF
  chmod +x "${{target}}/bin/ids-stack"
  cat > "${{target}}/bin/ids-offline-window-extractor" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "${{target}}/bin/ids-offline-window-extractor"
  exit 0
fi
if [[ "${{1-}}" == "-" ]]; then
  printf 'generated-value\\n'
  exit 0
fi
printf 'root-python %s\\n' "$*" >> "${{log_file}}"
exit 0
""",
    )
    _write_executable(
        fake_bin / "systemctl",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'systemctl %s\n' "$*" >> "${IDS_TEST_INSTALL_LOG}"
exit 0
""",
    )
    _write_executable(
        fake_bin / "id",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1-}" == "-u" ]]; then
  exit 1
fi
exit 0
""",
    )
    _write_executable(
        fake_bin / "useradd",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'useradd %s\n' "$*" >> "${IDS_TEST_INSTALL_LOG}"
exit 0
""",
    )
    _write_executable(
        fake_bin / "install",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1-}" == "-d" ]]; then
  mkdir -p "${@: -1}"
  exit 0
fi
src="${@: -2:1}"
dest="${@: -1}"
mkdir -p "$(dirname -- "${dest}")"
cp "${src}" "${dest}"
""",
    )
    _write_executable(fake_bin / "chmod", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(fake_bin / "chown", "#!/usr/bin/env bash\nexit 0\n")
    return fake_bin


def _write_install_shell_overrides(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """id() {
  if [[ "${1-}" == "-u" ]]; then
    return 1
  fi
  return 0
}

useradd() {
  printf 'useradd %s\n' "$*" >> "${IDS_TEST_INSTALL_LOG}"
}

systemctl() {
  printf 'systemctl %s\n' "$*" >> "${IDS_TEST_INSTALL_LOG}"
}

install() {
  if [[ "${1-}" == "-d" ]]; then
    mkdir -p "${@: -1}"
    return 0
  fi
  local src="${@: -2:1}"
  local dest="${@: -1}"
  mkdir -p "$(dirname -- "${dest}")"
  cp "${src}" "${dest}"
}

chmod() {
  return 0
}

chown() {
  return 0
}
""",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _write_operator_env_template(
    path: Path,
    *,
    database_path: Path,
    alerts_output_path: Path,
    quarantine_output_path: Path,
    summary_output_path: Path,
    secret_key_file: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "IDS_OPERATOR_CONSOLE_ENVIRONMENT=production",
                "IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL=https://console.example",
                f"IDS_OPERATOR_CONSOLE_DATABASE_PATH={database_path}",
                f"IDS_OPERATOR_CONSOLE_ALERTS_INPUT_PATH={alerts_output_path}",
                f"IDS_OPERATOR_CONSOLE_QUARANTINE_INPUT_PATH={quarantine_output_path}",
                f"IDS_OPERATOR_CONSOLE_SUMMARY_INPUT_PATH={summary_output_path}",
                f"IDS_OPERATOR_CONSOLE_SECRET_KEY_FILE={secret_key_file}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _install_helper_env(repo_root: Path, fake_bin: Path, paths: dict[str, Path], log_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{_to_bash_path(fake_bin)}:/usr/bin:/bin"
    env["IDS_TEST_INSTALL_LOG"] = str(log_path)
    env["IDS_INSTALL_TEST_MODE"] = "1"
    env["BASH_ENV"] = str(_write_install_shell_overrides(log_path.parent / "install-shell-overrides.sh"))
    return env


def _run_install_helper(
    repo_root: Path,
    *,
    env: dict[str, str],
    paths: dict[str, Path],
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    exports = {
        "IDS_INSTALL_SKIP_ROOT_CHECK": "1",
        "IDS_INSTALL_SKIP_SYSTEM_USER_SETUP": "1",
        "IDS_INSTALL_TEST_MODE": "1",
        "IDS_TEST_INSTALL_LOG": _to_bash_path(env["IDS_TEST_INSTALL_LOG"]),
        "IDS_INSTALL_EXPECTED_ROOT": _to_bash_path(repo_root),
        "IDS_INSTALL_SERVICE_DIR": _to_bash_path(paths["service_dir"]),
        "IDS_INSTALL_OPS_CONFIG_DIR": _to_bash_path(paths["ops_config_dir"]),
        "IDS_INSTALL_LIVE_SENSOR_CONFIG_DIR": _to_bash_path(paths["live_sensor_config_dir"]),
        "IDS_INSTALL_SENSOR_STATE_DIR": _to_bash_path(paths["sensor_state_dir"]),
        "IDS_INSTALL_SENSOR_LOG_DIR": _to_bash_path(paths["sensor_log_dir"]),
        "IDS_INSTALL_OPERATOR_STATE_DIR": _to_bash_path(paths["operator_state_dir"]),
        "IDS_INSTALL_OPERATOR_BACKUP_DIR": _to_bash_path(paths["operator_backup_dir"]),
    }
    export_prefix = " ".join(f'{key}="{value}"' for key, value in exports.items())
    arg_string = " ".join(f'"{arg}"' for arg in args)
    script_path = _to_bash_path(repo_root / "ops" / "install.sh")
    return subprocess.run(
        ["bash", "-c", f"{export_prefix} bash \"{script_path}\" {arg_string}"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_install_helper_keeps_in_place_editable_checkout_contract() -> None:
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    assert "--install-root" not in install_script
    assert "--source-root" not in install_script
    assert "copy_repo_tree" not in install_script
    assert "--mode MODE" in install_script
    assert "console-only" in install_script
    assert "full-stack-same-host" in install_script
    assert "--live-sensor-env PATH" not in install_script
    assert "ids-offline-window-extractor" in install_script
    assert 'INSTALL_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)' in install_script
    assert 'INSTALL_TEST_MODE="${IDS_INSTALL_TEST_MODE:-0}"' in install_script
    assert 'EXPECTED_INSTALL_ROOT="/opt/ids_ml_new"' in install_script
    assert 'if [[ "${INSTALL_TEST_MODE}" == "1" ]]; then' in install_script
    assert 'EXPECTED_INSTALL_ROOT="${IDS_INSTALL_EXPECTED_ROOT:-${EXPECTED_INSTALL_ROOT}}"' in install_script
    assert 'if [[ "${INSTALL_ROOT}" != "${EXPECTED_INSTALL_ROOT}" ]]' in install_script
    assert '"${PYTHON_BIN}" -m venv --clear "${INSTALL_ROOT}/.venv"' in install_script
    assert '"${INSTALL_ROOT}/.venv/bin/python" -m pip install --no-deps -e "${INSTALL_ROOT}"' in install_script
    assert 'Missing required --mode. Use console-only or full-stack-same-host.' in install_script
    assert 'console-only mode does not accept bootstrap or bundle inputs.' in install_script
    assert 'console-only mode requires --create-secrets or --admin-password-file.' in install_script
    assert 'full-stack-same-host mode requires --bootstrap.' in install_script
    assert 'full-stack-same-host does not support --skip-service-enable because bootstrap verifies the started packaged services.' in install_script
    assert 'DEFAULT_BUNDLED_BUNDLE_ROOT="${INSTALL_ROOT}/artifacts/final_model/catboost_full_data_v1"' in install_script
    assert 'DEFAULT_CONSOLE_ADMIN_PASSWORD_FILE="${OPS_CONFIG_DIR}/admin.password"' in install_script
    assert 'LIVE_SENSOR_ENV_SRC="${INSTALL_ROOT}/ops/ids-live-sensor.env.example"' in install_script
    assert 'LIVE_SENSOR_ENV_DEST="${LIVE_SENSOR_CONFIG_DIR}/ids-live-sensor.env"' in install_script
    assert 'seed_live_sensor_env()' in install_script
    assert 'operator_env_value()' in install_script
    assert 'seed_console_admin_password()' in install_script
    assert '--extractor-command-prefix P' in install_script
    assert 'single-token extractor helper path written into the live-sensor env before bootstrap/runtime' in install_script
    assert '--extractor-command-prefix "${live_sensor_extractor}"' in install_script
    assert 'selected_bundle_root="${DEFAULT_BUNDLED_BUNDLE_ROOT}"' in install_script
    assert '--candidate-bundle-root "${selected_bundle_root}"' in install_script
    assert 'copy_file_with_owner_mode()' in install_script
    assert 'ensure_dir_with_owner_mode()' in install_script
    assert 'set_owner_group()' in install_script


def test_install_helper_routes_service_enable_by_mode() -> None:
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    assert "enable_mode_services" in install_script
    assert "systemctl enable ids-operator-console.service ids-operator-console-notify.service" in install_script
    assert "systemctl enable ids-live-sensor.service ids-operator-console.service ids-operator-console-notify.service" in install_script
    assert "Finalizing %s install path" in install_script


def test_install_helper_defaults_full_stack_bootstrap_to_shipped_bundle_root() -> None:
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")
    build_script = (REPO_ROOT / "ops" / "build_release.sh").read_text(encoding="utf-8")

    shipped_root = "artifacts/final_model/catboost_full_data_v1"
    assert shipped_root in install_script
    assert shipped_root in build_script
    assert 'local selected_bundle_root="${CANDIDATE_BUNDLE_ROOT}"' in install_script
    assert 'selected_bundle_root="${DEFAULT_BUNDLED_BUNDLE_ROOT}"' in install_script
    assert 'require_dir "${selected_bundle_root}"' in install_script
    assert 'Cannot run --bootstrap without --candidate-bundle-root.' not in install_script


def test_install_helper_explicit_override_stays_fail_closed() -> None:
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    candidate_index = install_script.index('local selected_bundle_root="${CANDIDATE_BUNDLE_ROOT}"')
    fallback_index = install_script.index('selected_bundle_root="${DEFAULT_BUNDLED_BUNDLE_ROOT}"')
    require_index = install_script.index('require_dir "${selected_bundle_root}"')
    bootstrap_index = install_script.index('--candidate-bundle-root "${selected_bundle_root}"')

    assert 'if [[ -z "${selected_bundle_root}" ]]; then' in install_script
    assert candidate_index < fallback_index < require_index < bootstrap_index
    assert 'selected_bundle_root="${CANDIDATE_BUNDLE_ROOT}"' in install_script
    assert 'selected_bundle_root="${DEFAULT_BUNDLED_BUNDLE_ROOT}"' in install_script
    assert 'require_dir "${selected_bundle_root}"' in install_script
    assert '--candidate-bundle-root "${selected_bundle_root}"' in install_script


def test_install_helper_full_stack_defaults_to_shipped_bundle_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "opt" / "ids_ml_new"
    _copy_install_surface(repo_root)
    log_path = tmp_path / "install.log"
    fake_bin = _write_install_fakes(tmp_path / "fake-bin", log_path=log_path)
    fake_python = _to_bash_path(fake_bin / "python3.11")
    paths = {
        "service_dir": tmp_path / "service-dir",
        "ops_config_dir": tmp_path / "etc" / "ids-operator-console",
        "live_sensor_config_dir": tmp_path / "etc" / "ids-live-sensor",
        "sensor_state_dir": tmp_path / "var" / "lib" / "ids-live-sensor",
        "sensor_log_dir": tmp_path / "var" / "log" / "ids-live-sensor",
        "operator_state_dir": tmp_path / "var" / "lib" / "ids-operator-console",
        "operator_backup_dir": tmp_path / "var" / "backups" / "ids-operator-console",
    }
    operator_env_dest = paths["ops_config_dir"] / "ids-operator-console.env"
    operator_env_src = _write_operator_env_template(
        tmp_path / "fixtures" / "operator.env",
        database_path=paths["operator_state_dir"] / "operator_console.db",
        alerts_output_path=paths["sensor_log_dir"] / "ids_live_alerts.jsonl",
        quarantine_output_path=paths["sensor_log_dir"] / "ids_live_quarantine.jsonl",
        summary_output_path=paths["sensor_log_dir"] / "ids_live_sensor_summary.jsonl",
        secret_key_file=paths["ops_config_dir"] / "console.secret",
    )
    admin_password_file = tmp_path / "secrets" / "admin.password"
    admin_password_file.parent.mkdir(parents=True, exist_ok=True)
    admin_password_file.write_text("secret-password\n", encoding="utf-8")
    bundled_root = repo_root / "artifacts" / "final_model" / "catboost_full_data_v1"
    bundled_root.mkdir(parents=True, exist_ok=True)
    env = _install_helper_env(repo_root, fake_bin, paths, log_path)

    completed = _run_install_helper(
        repo_root,
        env=env,
        paths=paths,
        args=[
            "--mode",
            "full-stack-same-host",
            "--create-secrets",
            "--bootstrap",
            "--python-bin",
            fake_python,
            "--operator-env-src",
            _to_bash_path(operator_env_src),
            "--operator-env-dest",
            _to_bash_path(operator_env_dest),
            "--admin-password-file",
            _to_bash_path(admin_password_file),
        ],
    )

    assert completed.returncode == 0, completed.stderr
    assert (
        f"--candidate-bundle-root {_to_bash_path(bundled_root)}"
        in log_path.read_text(encoding="utf-8")
    )


def test_install_helper_seeds_live_sensor_env_contract() -> None:
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")
    env_text = (REPO_ROOT / "ops" / "ids-live-sensor.env.example").read_text(encoding="utf-8")
    live_sensor_service = (REPO_ROOT / "deploy" / "systemd" / "ids-live-sensor.service").read_text(
        encoding="utf-8"
    )

    assert "EnvironmentFile=-/etc/ids-live-sensor/ids-live-sensor.env" in live_sensor_service
    assert "Environment=" not in live_sensor_service, "live-sensor service must not hardcode Environment="
    assert "ExecStartPre=/opt/ids_ml_new/.venv/bin/python -m ids.ops.live_sensor_preflight" in live_sensor_service
    assert "ExecStart=/opt/ids_ml_new/.venv/bin/python -m ids.runtime.live_sensor" in live_sensor_service
    assert "ExecStart=/usr/bin/bash -lc" not in live_sensor_service
    assert "IDS_LIVE_SENSOR_INTERFACE=eth0" in env_text
    assert "IDS_LIVE_SENSOR_SPOOL_DIR=/var/lib/ids-live-sensor" in env_text
    assert "IDS_LIVE_SENSOR_ALERTS_OUTPUT=/var/log/ids-live-sensor/ids_live_alerts.jsonl" in env_text
    assert "IDS_LIVE_SENSOR_QUARANTINE_OUTPUT=/var/log/ids-live-sensor/ids_live_quarantine.jsonl" in env_text
    assert "IDS_LIVE_SENSOR_SUMMARY_OUTPUT=/var/log/ids-live-sensor/ids_live_sensor_summary.jsonl" in env_text
    assert "IDS_LIVE_SENSOR_DUMPCAP_BINARY=/usr/bin/dumpcap" in env_text
    assert "IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX=/opt/ids_ml_new/.venv/bin/ids-offline-window-extractor" in env_text
    assert "IDS_LIVE_SENSOR_ACTIVE_BUNDLE_PATH=/var/lib/ids-live-sensor/active_bundle.json" in env_text
    assert '--extractor-command-prefix ${IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX}' in live_sensor_service
    assert 'require_file "${LIVE_SENSOR_ENV_SRC}"' in install_script
    assert 'ensure_dir_with_owner_mode 0750 root ids-sensor "${LIVE_SENSOR_CONFIG_DIR}"' in install_script
    assert 'copy_file_with_owner_mode 0640 root ids-sensor "${LIVE_SENSOR_ENV_SRC}" "${LIVE_SENSOR_ENV_DEST}"' in install_script
    assert 'set_env_value "${LIVE_SENSOR_ENV_DEST}" IDS_LIVE_SENSOR_DUMPCAP_BINARY "${DUMPCAP_BINARY}"' in install_script
    assert 'set_env_value "${LIVE_SENSOR_ENV_DEST}" IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX "${EXTRACTOR_COMMAND_PREFIX}"' in install_script
    assert 'live_sensor_dumpcap=$(live_sensor_env_value IDS_LIVE_SENSOR_DUMPCAP_BINARY)' in install_script
    assert 'live_sensor_extractor=$(live_sensor_env_value IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX)' in install_script
    assert 'chmod 0640 "${LIVE_SENSOR_ENV_DEST}"' in install_script
    assert 'set_owner_group root:ids-sensor "${LIVE_SENSOR_ENV_DEST}"' in install_script
    assert 'seed_live_sensor_env' in install_script


def test_install_helper_rejects_multi_token_live_sensor_extractor_contract() -> None:
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    assert '--extractor-command-prefix-token' not in install_script
    assert 'multi-token overrides are compatibility-only and not accepted by ops/install.sh.' in install_script
    assert 'if [[ "${MODE}" == "full-stack-same-host" && "${EXTRACTOR_COMMAND_PREFIX}" =~ [[:space:]] ]]; then' in install_script


def test_install_helper_full_stack_rejects_multi_token_extractor_override(tmp_path: Path) -> None:
    repo_root = tmp_path / "opt" / "ids_ml_new"
    _copy_install_surface(repo_root)
    log_path = tmp_path / "install.log"
    fake_bin = _write_install_fakes(tmp_path / "fake-bin", log_path=log_path)
    fake_python = _to_bash_path(fake_bin / "python3.11")
    paths = {
        "service_dir": tmp_path / "service-dir",
        "ops_config_dir": tmp_path / "etc" / "ids-operator-console",
        "live_sensor_config_dir": tmp_path / "etc" / "ids-live-sensor",
        "sensor_state_dir": tmp_path / "var" / "lib" / "ids-live-sensor",
        "sensor_log_dir": tmp_path / "var" / "log" / "ids-live-sensor",
        "operator_state_dir": tmp_path / "var" / "lib" / "ids-operator-console",
        "operator_backup_dir": tmp_path / "var" / "backups" / "ids-operator-console",
    }
    operator_env_src = _write_operator_env_template(
        tmp_path / "fixtures" / "operator.env",
        database_path=paths["operator_state_dir"] / "operator_console.db",
        alerts_output_path=paths["sensor_log_dir"] / "ids_live_alerts.jsonl",
        quarantine_output_path=paths["sensor_log_dir"] / "ids_live_quarantine.jsonl",
        summary_output_path=paths["sensor_log_dir"] / "ids_live_sensor_summary.jsonl",
        secret_key_file=paths["ops_config_dir"] / "console.secret",
    )
    admin_password_file = tmp_path / "secrets" / "admin.password"
    admin_password_file.parent.mkdir(parents=True, exist_ok=True)
    admin_password_file.write_text("secret-password\n", encoding="utf-8")
    env = _install_helper_env(repo_root, fake_bin, paths, log_path)

    completed = _run_install_helper(
        repo_root,
        env=env,
        paths=paths,
        args=[
            "--mode",
            "full-stack-same-host",
            "--bootstrap",
            "--python-bin",
            fake_python,
            "--operator-env-src",
            _to_bash_path(operator_env_src),
            "--admin-password-file",
            _to_bash_path(admin_password_file),
            "--extractor-command-prefix",
            "/usr/bin/env python",
        ],
    )

    assert completed.returncode == 1
    assert "multi-token overrides are compatibility-only and not accepted by ops/install.sh." in completed.stderr


def test_install_helper_hardens_preseeded_env_file() -> None:
    """The installer must re-permission an existing operator env file.

    The documented install path allows operators to cp the env example
    before running the installer.  If the file already exists, the
    installer must harden ownership and permissions to prevent leaking
    secrets (e.g. Telegram bot token) to other local users.
    """
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    # The else branch of seed_operator_env must apply secure permissions
    assert 'chmod 0640 "${OPERATOR_ENV_DEST}"' in install_script, (
        "install.sh must chmod existing env file to 0640"
    )
    assert 'set_owner_group root:ids-operator "${OPERATOR_ENV_DEST}"' in install_script, (
        "install.sh must chown existing env file to root:ids-operator"
    )


def test_install_helper_keeps_console_admin_password_root_only() -> None:
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    assert 'chmod 0600 "${admin_password_file}"' in install_script
    assert 'set_owner_group root:root "${admin_password_file}"' in install_script


def test_install_helper_enables_notify_worker_service() -> None:
    """The installer must enable the notification worker alongside the base services.

    A fresh install should leave ids-operator-console-notify.service enabled
    so that Telegram notification dispatch is operational after reboot without
    requiring a separate manual post-install step.
    """
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    assert "ids-operator-console-notify.service" in install_script, (
        "install.sh must reference the notify worker service"
    )
    # The enable line must include all three services
    assert (
        "systemctl enable ids-live-sensor.service ids-operator-console.service ids-operator-console-notify.service"
        in install_script
    ), (
        "install.sh must enable ids-operator-console-notify.service alongside the base services"
    )


def test_install_helper_console_only_mode_executes_console_lifecycle(tmp_path: Path) -> None:
    repo_root = tmp_path / "opt" / "ids_ml_new"
    _copy_install_surface(repo_root)
    log_path = tmp_path / "install.log"
    fake_bin = _write_install_fakes(tmp_path / "fake-bin", log_path=log_path)
    fake_python = _to_bash_path(fake_bin / "python3.11")
    paths = {
        "service_dir": tmp_path / "service-dir",
        "ops_config_dir": tmp_path / "etc" / "ids-operator-console",
        "live_sensor_config_dir": tmp_path / "etc" / "ids-live-sensor",
        "sensor_state_dir": tmp_path / "var" / "lib" / "ids-live-sensor",
        "sensor_log_dir": tmp_path / "var" / "log" / "ids-live-sensor",
        "operator_state_dir": tmp_path / "var" / "lib" / "ids-operator-console",
        "operator_backup_dir": tmp_path / "var" / "backups" / "ids-operator-console",
    }
    operator_env_dest = paths["ops_config_dir"] / "ids-operator-console.env"
    operator_env_src = _write_operator_env_template(
        tmp_path / "fixtures" / "operator.env",
        database_path=paths["operator_state_dir"] / "operator_console.db",
        alerts_output_path=paths["sensor_log_dir"] / "ids_live_alerts.jsonl",
        quarantine_output_path=paths["sensor_log_dir"] / "ids_live_quarantine.jsonl",
        summary_output_path=paths["sensor_log_dir"] / "ids_live_sensor_summary.jsonl",
        secret_key_file=paths["ops_config_dir"] / "console.secret",
    )
    env = _install_helper_env(repo_root, fake_bin, paths, log_path)

    completed = _run_install_helper(
        repo_root,
        env=env,
        paths=paths,
        args=[
            "--mode",
            "console-only",
            "--create-secrets",
            "--python-bin",
            fake_python,
            "--operator-env-src",
            _to_bash_path(operator_env_src),
            "--operator-env-dest",
            _to_bash_path(operator_env_dest),
        ],
    )

    assert completed.returncode == 0, completed.stderr
    log_text = log_path.read_text(encoding="utf-8")
    assert "ids-stack " not in log_text
    assert "systemctl enable ids-operator-console.service ids-operator-console-notify.service" in log_text
    assert "systemctl start ids-operator-console.service ids-operator-console-notify.service" in log_text
    assert "venv-python -m ids.ops.operator_console_manage --database-path" in log_text
    assert "--json migrate --allow-bootstrap" in log_text
    assert "--json bootstrap-admin --username admin --password-file" in log_text
    assert "--json status" in log_text
    assert "--json smoke" in log_text
    assert "--json notify-status" in log_text
    assert (paths["ops_config_dir"] / "admin.password").exists()


def test_install_helper_full_stack_mode_writes_env_backed_runtime_contract(tmp_path: Path) -> None:
    repo_root = tmp_path / "opt" / "ids_ml_new"
    _copy_install_surface(repo_root)
    log_path = tmp_path / "install.log"
    fake_bin = _write_install_fakes(tmp_path / "fake-bin", log_path=log_path)
    fake_python = _to_bash_path(fake_bin / "python3.11")
    paths = {
        "service_dir": tmp_path / "service-dir",
        "ops_config_dir": tmp_path / "etc" / "ids-operator-console",
        "live_sensor_config_dir": tmp_path / "etc" / "ids-live-sensor",
        "sensor_state_dir": tmp_path / "var" / "lib" / "ids-live-sensor",
        "sensor_log_dir": tmp_path / "var" / "log" / "ids-live-sensor",
        "operator_state_dir": tmp_path / "var" / "lib" / "ids-operator-console",
        "operator_backup_dir": tmp_path / "var" / "backups" / "ids-operator-console",
    }
    operator_env_dest = paths["ops_config_dir"] / "ids-operator-console.env"
    operator_env_src = _write_operator_env_template(
        tmp_path / "fixtures" / "operator.env",
        database_path=paths["operator_state_dir"] / "operator_console.db",
        alerts_output_path=paths["sensor_log_dir"] / "ids_live_alerts.jsonl",
        quarantine_output_path=paths["sensor_log_dir"] / "ids_live_quarantine.jsonl",
        summary_output_path=paths["sensor_log_dir"] / "ids_live_sensor_summary.jsonl",
        secret_key_file=paths["ops_config_dir"] / "console.secret",
    )
    admin_password_file = tmp_path / "secrets" / "admin.password"
    admin_password_file.parent.mkdir(parents=True, exist_ok=True)
    admin_password_file.write_text("secret-password\n", encoding="utf-8")
    candidate_bundle_root = tmp_path / "bundles" / "candidate"
    candidate_bundle_root.mkdir(parents=True, exist_ok=True)
    env = _install_helper_env(repo_root, fake_bin, paths, log_path)

    completed = _run_install_helper(
        repo_root,
        env=env,
        paths=paths,
        args=[
            "--mode",
            "full-stack-same-host",
            "--create-secrets",
            "--bootstrap",
            "--python-bin",
            fake_python,
            "--operator-env-src",
            _to_bash_path(operator_env_src),
            "--operator-env-dest",
            _to_bash_path(operator_env_dest),
            "--admin-password-file",
            _to_bash_path(admin_password_file),
            "--candidate-bundle-root",
            _to_bash_path(candidate_bundle_root),
            "--dumpcap-binary",
            "/custom/dumpcap",
            "--extractor-command-prefix",
            "/custom/extractor",
            "--proxy-public-url",
            "https://console.example",
        ],
    )

    assert completed.returncode == 0, completed.stderr
    live_sensor_env = (paths["live_sensor_config_dir"] / "ids-live-sensor.env").read_text(encoding="utf-8")
    assert "IDS_LIVE_SENSOR_DUMPCAP_BINARY=/custom/dumpcap" in live_sensor_env
    assert "IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX=/custom/extractor" in live_sensor_env

    log_text = log_path.read_text(encoding="utf-8")
    assert "systemctl enable ids-live-sensor.service ids-operator-console.service ids-operator-console-notify.service" in log_text
    assert "ids-stack --repo-root" in log_text
    assert "--activation-path" in log_text
    assert _to_bash_path(paths["sensor_state_dir"] / "active_bundle.json") in log_text
    assert "--dumpcap-binary /custom/dumpcap" in log_text
    assert "--extractor-command-prefix /custom/extractor" in log_text


def test_install_helper_full_stack_rejects_skip_service_enable(tmp_path: Path) -> None:
    repo_root = tmp_path / "opt" / "ids_ml_new"
    _copy_install_surface(repo_root)
    log_path = tmp_path / "install.log"
    fake_bin = _write_install_fakes(tmp_path / "fake-bin", log_path=log_path)
    fake_python = _to_bash_path(fake_bin / "python3.11")
    paths = {
        "service_dir": tmp_path / "service-dir",
        "ops_config_dir": tmp_path / "etc" / "ids-operator-console",
        "live_sensor_config_dir": tmp_path / "etc" / "ids-live-sensor",
        "sensor_state_dir": tmp_path / "var" / "lib" / "ids-live-sensor",
        "sensor_log_dir": tmp_path / "var" / "log" / "ids-live-sensor",
        "operator_state_dir": tmp_path / "var" / "lib" / "ids-operator-console",
        "operator_backup_dir": tmp_path / "var" / "backups" / "ids-operator-console",
    }
    operator_env_src = _write_operator_env_template(
        tmp_path / "fixtures" / "operator.env",
        database_path=paths["operator_state_dir"] / "operator_console.db",
        alerts_output_path=paths["sensor_log_dir"] / "ids_live_alerts.jsonl",
        quarantine_output_path=paths["sensor_log_dir"] / "ids_live_quarantine.jsonl",
        summary_output_path=paths["sensor_log_dir"] / "ids_live_sensor_summary.jsonl",
        secret_key_file=paths["ops_config_dir"] / "console.secret",
    )
    env = _install_helper_env(repo_root, fake_bin, paths, log_path)

    completed = _run_install_helper(
        repo_root,
        env=env,
        paths=paths,
        args=[
            "--mode",
            "full-stack-same-host",
            "--bootstrap",
            "--skip-service-enable",
            "--python-bin",
            fake_python,
            "--operator-env-src",
            _to_bash_path(operator_env_src),
        ],
    )

    assert completed.returncode == 1
    assert "full-stack-same-host does not support --skip-service-enable" in completed.stderr


def test_build_release_uses_git_archive_not_manual_excludes() -> None:
    """The release helper must use git archive for a safe export surface."""
    build_script = (REPO_ROOT / "ops" / "build_release.sh").read_text(encoding="utf-8")

    # Must use git archive as the primary export mechanism
    assert "git archive" in build_script, (
        "build_release.sh must use 'git archive' to export only tracked files"
    )
    assert 'git -C "${REPO_ROOT}" archive HEAD' in build_script
    assert "load_model_bundle_manifest" in build_script
    assert 'DEFAULT_BUNDLE_ROOT="${BUNDLE_DIR}/artifacts/final_model/catboost_full_data_v1"' in build_script

    # Must NOT fall back to the old manual-exclude tar approach
    assert "tar -cf - ." not in build_script, (
        "build_release.sh must not tar the raw working tree"
    )
    assert "-cf - ." not in build_script, (
        "build_release.sh must not archive the raw working directory"
    )

    # Wheelhouse dependency building should still be present
    assert '"${PYTHON_BIN}" -m pip wheel -r "${REPO_ROOT}/requirements.txt" --wheel-dir "${WHEELHOUSE_DIR}"' in build_script

    # Must not build the project itself as a wheel (only deps)
    assert 'pip wheel "${REPO_ROOT}"' not in build_script


def test_build_release_succeeds_for_valid_default_bundle(tmp_path: Path) -> None:
    repo_root, output_dir, fake_python = _make_release_fixture_repo(tmp_path, valid_bundle=True)

    completed = _run_build_release(repo_root, output_dir, fake_python)

    archive_path = output_dir / f"ids_ml_new-{FIXED_RELEASE_TIMESTAMP}.tar.gz"
    assert completed.returncode == 0, completed.stderr
    assert "[1/4] Exporting tracked files via git archive..." in completed.stdout
    assert "[2/4] Validating staged bundled default production artifact..." in completed.stdout
    assert archive_path.is_file(), completed.stdout

    with tarfile.open(archive_path, "r:gz") as handle:
        archive_names = handle.getnames()

    assert "ids_ml_new/pyproject.toml" in archive_names
    assert "ids_ml_new/artifacts/final_model/catboost_full_data_v1/model_bundle.json" in archive_names


def test_install_helper_next_checks_include_activation_status_for_full_stack() -> None:
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    assert 'ids-model-bundle-manage --activation-path ${SENSOR_STATE_DIR}/active_bundle.json --json status' in install_script
    assert '--json bootstrap --candidate-bundle-root <bundle-root>' not in install_script


def test_install_helper_console_only_next_checks_use_operator_console_manage() -> None:
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    next_checks_start = install_script.index("printf '\\nInstall complete.\\n'")
    console_only_branch_start = install_script.index(
        'if [[ "${MODE}" == "console-only" ]]; then',
        next_checks_start,
    )
    console_only_branch_end = install_script.index('else', console_only_branch_start)
    console_only_block = install_script[console_only_branch_start:console_only_branch_end]

    assert 'ids-stack --repo-root' not in console_only_block
    assert 'ids.ops.operator_console_manage' in console_only_block
    assert '--json status' in console_only_block
    assert '--json smoke' in console_only_block
    assert '--json notify-status' in console_only_block


def test_build_release_fails_closed_for_invalid_default_bundle(tmp_path: Path) -> None:
    repo_root, output_dir, fake_python = _make_release_fixture_repo(tmp_path, valid_bundle=False)

    completed = _run_build_release(repo_root, output_dir, fake_python)

    archive_path = output_dir / f"ids_ml_new-{FIXED_RELEASE_TIMESTAMP}.tar.gz"
    assert completed.returncode != 0
    assert "[1/4] Exporting tracked files via git archive..." in completed.stdout
    assert "[2/4] Validating staged bundled default production artifact..." in completed.stdout
    assert "Bundle feature schema digest mismatch" in completed.stderr
    assert not archive_path.exists()


def test_build_release_ignores_uncommitted_invalid_working_tree_bundle_when_head_is_valid(tmp_path: Path) -> None:
    repo_root, output_dir, fake_python = _make_release_fixture_repo(tmp_path, valid_bundle=True)
    _rewrite_working_tree_bundle_contract(repo_root, valid=False)

    completed = _run_build_release(repo_root, output_dir, fake_python)

    archive_path = output_dir / f"ids_ml_new-{FIXED_RELEASE_TIMESTAMP}.tar.gz"
    assert completed.returncode == 0, completed.stderr
    assert "[2/4] Validating staged bundled default production artifact..." in completed.stdout
    assert archive_path.is_file(), completed.stdout


def test_build_release_fails_when_head_bundle_is_invalid_even_if_working_tree_is_fixed(tmp_path: Path) -> None:
    repo_root, output_dir, fake_python = _make_release_fixture_repo(tmp_path, valid_bundle=False)
    _rewrite_working_tree_bundle_contract(repo_root, valid=True)

    completed = _run_build_release(repo_root, output_dir, fake_python)

    archive_path = output_dir / f"ids_ml_new-{FIXED_RELEASE_TIMESTAMP}.tar.gz"
    assert completed.returncode != 0
    assert "[2/4] Validating staged bundled default production artifact..." in completed.stdout
    assert "Bundle feature schema digest mismatch" in completed.stderr
    assert not archive_path.exists()


# ── Phase 4 closure proof: cross-surface contract verification ─────────────


def test_settings_template_is_root_path_aware() -> None:
    """The settings template must generate URLs relative to root_path.

    This is a compile-time proof that the settings form, test button,
    and any redirect-related markup honor the mounted-path contract.
    """
    template_text = (
        REPO_ROOT / "ids" / "console" / "templates" / "settings.html"
    ).read_text(encoding="utf-8")

    # Form action must be dynamically generated with root_path prefix
    assert "{{ root_path }}/settings" in template_text, (
        "settings.html form action must use {{ root_path }} prefix"
    )
    # Test button URL must be dynamically generated with root_path prefix
    assert "{{ root_path }}/settings/test" in template_text, (
        "settings.html test URL must use {{ root_path }} prefix"
    )
    # Must NOT have hardcoded action="/settings" (without root_path)
    assert 'action="/settings"' not in template_text, (
        "settings.html must not have hardcoded action='/settings'"
    )


def test_settings_js_reads_test_url_from_data_attribute() -> None:
    """The console JS must read the test URL from a data attribute,
    not hardcode it, so it works under mounted reverse-proxy paths."""
    js_text = (
        REPO_ROOT / "ids" / "console" / "static" / "console.js"
    ).read_text(encoding="utf-8")

    assert "data-test-url" in js_text, (
        "console.js must read the test URL from a data-test-url attribute"
    )
    # Must NOT have a hardcoded fetch to '/settings/test'
    assert "fetch('/settings/test'" not in js_text, (
        "console.js must not hardcode fetch('/settings/test')"
    )


def test_effective_telegram_config_resolver_shared_across_surfaces() -> None:
    """The web layer, runtime, and preflight must all use the same
    resolve_telegram_config function for the DB > env fallback rule."""
    web_text = (REPO_ROOT / "ids" / "console" / "web.py").read_text(encoding="utf-8")
    runtime_text = (REPO_ROOT / "ids" / "console" / "notification_runtime.py").read_text(encoding="utf-8")
    preflight_text = (REPO_ROOT / "ids" / "ops" / "operator_console_preflight.py").read_text(encoding="utf-8")

    # web.py must import and use resolve_telegram_config
    assert "from .notification_runtime import resolve_telegram_config" in web_text, (
        "web.py must import resolve_telegram_config from notification_runtime"
    )
    assert "resolve_telegram_config(" in web_text, (
        "web.py must call resolve_telegram_config"
    )

    # notification_runtime.py must define and export resolve_telegram_config
    assert "def resolve_telegram_config(" in runtime_text, (
        "notification_runtime.py must define resolve_telegram_config"
    )
    assert '"resolve_telegram_config"' in runtime_text, (
        "notification_runtime.py must export resolve_telegram_config in __all__"
    )

    # preflight must check DB settings (same precedence rule)
    assert "_load_telegram_settings_from_db" in preflight_text, (
        "preflight must load Telegram settings from DB"
    )


def test_env_example_documents_full_telegram_surface() -> None:
    """The env example must document the complete Telegram configuration surface
    including env vars, token file, chat ID, and the Settings UI alternative."""
    env_text = (REPO_ROOT / "ops" / "ids-operator-console.env.example").read_text(encoding="utf-8")

    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN=" in env_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_BOT_TOKEN_FILE=" in env_text
    assert "IDS_OPERATOR_CONSOLE_TELEGRAM_CHAT_ID=" in env_text
    assert "Settings UI" in env_text, (
        "Env example must mention the Settings UI as an alternative config path"
    )
    assert "DB settings" in env_text or "database" in env_text.lower(), (
        "Env example must explain DB precedence"
    )


def test_deployment_docs_match_corrected_install_contract() -> None:
    """The deployment quickstart docs must match the repaired install/runtime behavior."""
    docs_text = (
        REPO_ROOT / "docs" / "current" / "operations" / "deployment_quickstart.md"
    ).read_text(encoding="utf-8")

    # Must document git archive as the safe export surface
    assert "git archive" in docs_text or "git-tracked export" in docs_text, (
        "Docs must describe the safe export surface (git archive)"
    )
    # Must document the Settings UI approach
    assert "Settings" in docs_text, (
        "Docs must mention the Settings UI for Telegram configuration"
    )
    # Must document the env file approach
    assert "Environment file" in docs_text or "environment file" in docs_text or "env file" in docs_text, (
        "Docs must mention the environment file approach"
    )
    # Must document DB precedence
    assert "precedence" in docs_text.lower() or "take priority" in docs_text.lower() or "wins" in docs_text.lower(), (
        "Docs must explain DB settings precedence over env"
    )
    # Must document the notify worker
    assert "ids-operator-console-notify" in docs_text, (
        "Docs must mention the notification worker service"
    )


def test_git_archive_excludes_ignored_and_untracked_files() -> None:
    """Regression: prove that git archive does not include ignored/untracked files.

    This test creates a temporary untracked file in the repo, runs git archive,
    and verifies the file is absent from the produced tarball.  This is the
    concrete proof that the safe export surface works.
    """
    # Pick a filename that is clearly not tracked and is .gitignore'd
    # (.claude is listed in .gitignore)
    sentinel_name = ".claude/_test_leak_sentinel.txt"
    sentinel_path = REPO_ROOT / sentinel_name

    # Also test a random untracked file outside .gitignore
    untracked_name = "_untracked_secret_test_file.tmp"
    untracked_path = REPO_ROOT / untracked_name

    try:
        # Create sentinel files
        sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        sentinel_path.write_text("THIS MUST NOT APPEAR IN RELEASE", encoding="utf-8")
        untracked_path.write_text("THIS MUST NOT APPEAR IN RELEASE", encoding="utf-8")

        # Run git archive and capture the tarball
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "archive", "HEAD", "-o", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"git archive failed: {result.stderr}"

        # Inspect the tarball contents
        with tarfile.open(tmp_path, "r") as tf:
            archive_names = tf.getnames()

        # The sentinel files MUST be absent
        assert sentinel_name not in archive_names, (
            f"Ignored file {sentinel_name!r} was included in git archive output"
        )
        assert untracked_name not in archive_names, (
            f"Untracked file {untracked_name!r} was included in git archive output"
        )

        # Sanity: some known tracked files SHOULD be present
        assert any("pyproject.toml" in n for n in archive_names), (
            "pyproject.toml should be in the archive"
        )
        assert any("ids/__init__.py" in n for n in archive_names), (
            "ids/__init__.py should be in the archive"
        )

    finally:
        # Clean up sentinel files
        if sentinel_path.exists():
            sentinel_path.unlink()
        if untracked_path.exists():
            untracked_path.unlink()
        if tmp_path.exists():
            tmp_path.unlink()
        # Clean up .claude dir if we created it and it's empty
        if sentinel_path.parent.exists():
            try:
                sentinel_path.parent.rmdir()
            except OSError:
                pass  # Not empty (other files exist), leave it


# ── Phase 4 closure proof tests ────────────────────────────────────────────


def test_deploy_surface_closure_proof() -> None:
    """Comprehensive proof that the Phase 4 deploy surface repairs hold together.

    This test verifies all three fix domains in a single pass:
    1. Release artifact safety (git archive, no raw-tree tar)
    2. Install-time hardening (env file perms, notify service enable)
    3. Docs alignment (quickstart and README reflect corrected behavior)
    """
    build_script = (REPO_ROOT / "ops" / "build_release.sh").read_text(encoding="utf-8")
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    # ── 1. Release artifact safety ──────────────────────────────────────
    # git archive is the export mechanism, not raw-tree tar
    assert "git archive" in build_script
    assert "-cf - ." not in build_script

    # ── 2. Install-time hardening ─────────────────────────────────────��─
    # Pre-seeded env file gets hardened
    assert 'chmod 0640 "${OPERATOR_ENV_DEST}"' in install_script
    assert 'set_owner_group root:ids-operator "${OPERATOR_ENV_DEST}"' in install_script
    # Notify worker is enabled with the base services
    assert re.search(
        r"systemctl enable.*ids-operator-console-notify\.service",
        install_script,
    ), "install.sh must enable the notify worker service"

    # ── 3. Docs alignment ───────────────────────────────────────────────
    quickstart = (REPO_ROOT / "docs" / "current" / "operations" / "deployment_quickstart.md")
    if quickstart.exists():
        qs_text = quickstart.read_text(encoding="utf-8")
        # Must mention git archive or tracked-only export
        assert "git archive" in qs_text or "tracked" in qs_text.lower(), (
            "deployment_quickstart.md must document the safe export surface"
        )
        # Must document effective Telegram config behavior
        assert "fallback" in qs_text.lower() or "precedence" in qs_text.lower(), (
            "deployment_quickstart.md must document Telegram config precedence"
        )

    ops_readme = REPO_ROOT / "ops" / "README-deploy.md"
    if ops_readme.exists():
        ops_text = ops_readme.read_text(encoding="utf-8")
        # Must document the notify worker
        assert "ids-operator-console-notify" in ops_text, (
            "README-deploy.md must reference the notification worker service"
        )
        # Must document config precedence
        assert "precedence" in ops_text.lower() or "database" in ops_text.lower(), (
            "README-deploy.md must document DB > env config precedence"
        )


def test_settings_effective_config_contract_aligns_web_and_runtime() -> None:
    """Prove that web.py and notification_runtime.py use the same resolver.

    This is a static proof that the settings page and the runtime worker
    use the same resolve_telegram_config function, not separate
    reimplementations.
    """
    web_source = (REPO_ROOT / "ids" / "console" / "web.py").read_text(encoding="utf-8")

    # web.py must import resolve_telegram_config from notification_runtime
    assert "from .notification_runtime import resolve_telegram_config" in web_source, (
        "web.py must import resolve_telegram_config from notification_runtime"
    )
    # web.py settings_page must use resolve_telegram_config_with_source
    assert "resolve_telegram_config_with_source(" in web_source, (
        "settings_page must call resolve_telegram_config_with_source"
    )
    # web.py settings_test must use resolve_telegram_config
    assert "resolve_telegram_config(runtime_store, env_fallback)" in web_source, (
        "settings_test must call resolve_telegram_config with env fallback"
    )


def test_install_helper_hardens_db_file_permissions() -> None:
    """The installer must harden the SQLite DB file that now stores the bot token.

    After bootstrap or on a subsequent install run, the DB file should be
    chmod 0640 and chown root:ids-operator to prevent other local users
    from reading the plaintext Telegram bot token.
    """
    install_script = (REPO_ROOT / "ops" / "install.sh").read_text(encoding="utf-8")

    assert 'OPERATOR_STATE_DIR="/var/lib/ids-operator-console"' in install_script
    assert 'OPERATOR_STATE_DIR="${IDS_INSTALL_OPERATOR_STATE_DIR:-${OPERATOR_STATE_DIR}}"' in install_script
    assert 'chmod 0640 "${OPERATOR_STATE_DIR}/operator_console.db"' in install_script, (
        "install.sh must chmod the DB file to 0640"
    )
    assert 'set_owner_group root:ids-operator "${OPERATOR_STATE_DIR}/operator_console.db"' in install_script, (
        "install.sh must chown the DB file to root:ids-operator"
    )


def test_settings_root_path_contract() -> None:
    """Prove that the settings template is root-path-aware.

    This is a static proof that the form action and test URL
    use root_path from the template context.
    """
    template_path = REPO_ROOT / "ids" / "console" / "templates" / "settings.html"
    template_source = template_path.read_text(encoding="utf-8")

    # Form action must be root-path-aware
    assert "{{ root_path }}/settings" in template_source, (
        "settings.html form action must use root_path"
    )
    # Test URL must be root-path-aware
    assert "{{ root_path }}/settings/test" in template_source, (
        "settings.html test URL must use root_path"
    )
