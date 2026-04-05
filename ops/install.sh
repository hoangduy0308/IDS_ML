#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install the IDS same-host stack onto a Linux target host.

Usage:
  sudo ./ops/install.sh [options]

Options:
  --mode MODE                   Install mode: console-only or full-stack-same-host
  --python-bin PATH             Python binary used to create the target venv (default: python3.11)
  --operator-env-src PATH       Template env file to seed (default: ops/ids-operator-console.env.example)
  --operator-env-dest PATH      Host env file path (default: /etc/ids-operator-console/ids-operator-console.env)
  --live-sensor-env PATH       Host live-sensor env file path (default: /etc/ids-live-sensor/ids-live-sensor.env)
  --console-secret-file PATH    Host secret key file path (default: /etc/ids-operator-console/console.secret)
  --telegram-token-file PATH    Host Telegram token file path (default: /etc/ids-operator-console/telegram-bot-token.secret)
  --dumpcap-binary PATH         Exact dumpcap path written into the live-sensor env before bootstrap/runtime (default: /usr/bin/dumpcap)
  --extractor-command-prefix P  Exact single-token extractor helper path written into the live-sensor env before bootstrap/runtime (default: /opt/ids_ml_new/.venv/bin/ids-offline-window-extractor)
  --candidate-bundle-root PATH  Bundle root override for ids-stack bootstrap (default: /opt/ids_ml_new/artifacts/final_model/catboost_full_data_v1)
  --admin-username NAME         Admin username for console/bootstrap lifecycle (default: admin)
  --admin-password-file PATH    Admin password file for console/bootstrap lifecycle
  --proxy-public-url URL        Public console URL used for smoke checks
  --bootstrap                   Run ids-stack bootstrap after installation
  --create-secrets              Generate console/admin secret files if they do not exist yet
  --skip-service-enable         Install files but do not enable/start systemd units
  -h, --help                    Show this help

Notes:
  - Run this script from the extracted checkout at /opt/ids_ml_new/ops/install.sh.
  - The script recreates /opt/ids_ml_new/.venv on the target host and installs the app via pip install -e.
  - If wheelhouse/ is present under the checkout, the script prefers it for dependency installation only.
  - console-only runs console schema migration + admin bootstrap through ids-operator-console-manage, then starts the operator console + notification worker on the canonical packaged services.
  - full-stack-same-host auto-runs ids-stack bootstrap with the bundled default artifact unless --candidate-bundle-root overrides it.
  - packaged live-sensor runtime values come from /etc/ids-live-sensor/ids-live-sensor.env; multi-token extractor prefixes are not part of that packaged service contract.
EOF
}

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
INSTALL_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
MODE=""
PYTHON_BIN="python3.11"
SERVICE_DIR="/etc/systemd/system"
OPS_CONFIG_DIR="/etc/ids-operator-console"
LIVE_SENSOR_CONFIG_DIR="/etc/ids-live-sensor"
OPERATOR_ENV_SRC="${INSTALL_ROOT}/ops/ids-operator-console.env.example"
OPERATOR_ENV_DEST="${OPS_CONFIG_DIR}/ids-operator-console.env"
LIVE_SENSOR_ENV_SRC="${INSTALL_ROOT}/ops/ids-live-sensor.env.example"
LIVE_SENSOR_ENV_DEST="${LIVE_SENSOR_CONFIG_DIR}/ids-live-sensor.env"
CONSOLE_SECRET_FILE="${OPS_CONFIG_DIR}/console.secret"
TELEGRAM_TOKEN_FILE="${OPS_CONFIG_DIR}/telegram-bot-token.secret"
DUMPCAP_BINARY="/usr/bin/dumpcap"
EXTRACTOR_COMMAND_PREFIX="/opt/ids_ml_new/.venv/bin/ids-offline-window-extractor"
DUMPCAP_BINARY_WAS_SET=0
EXTRACTOR_COMMAND_PREFIX_WAS_SET=0
ADMIN_USERNAME="admin"
ADMIN_PASSWORD_FILE=""
PROXY_PUBLIC_URL=""
BOOTSTRAP=0
CREATE_SECRETS=0
SKIP_SERVICE_ENABLE=0
CANDIDATE_BUNDLE_ROOT=""
DEFAULT_BUNDLED_BUNDLE_ROOT="${INSTALL_ROOT}/artifacts/final_model/catboost_full_data_v1"
DEFAULT_CONSOLE_ADMIN_PASSWORD_FILE="${OPS_CONFIG_DIR}/admin.password"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE=$2
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN=$2
      shift 2
      ;;
    --operator-env-src)
      OPERATOR_ENV_SRC=$2
      shift 2
      ;;
    --operator-env-dest)
      OPERATOR_ENV_DEST=$2
      shift 2
      ;;
    --live-sensor-env)
      LIVE_SENSOR_ENV_DEST=$2
      shift 2
      ;;
    --console-secret-file)
      CONSOLE_SECRET_FILE=$2
      shift 2
      ;;
    --telegram-token-file)
      TELEGRAM_TOKEN_FILE=$2
      shift 2
      ;;
    --dumpcap-binary)
      DUMPCAP_BINARY=$2
      DUMPCAP_BINARY_WAS_SET=1
      shift 2
      ;;
    --extractor-command-prefix)
      EXTRACTOR_COMMAND_PREFIX=$2
      EXTRACTOR_COMMAND_PREFIX_WAS_SET=1
      shift 2
      ;;
    --candidate-bundle-root)
      CANDIDATE_BUNDLE_ROOT=$2
      shift 2
      ;;
    --admin-username)
      ADMIN_USERNAME=$2
      shift 2
      ;;
    --admin-password-file)
      ADMIN_PASSWORD_FILE=$2
      shift 2
      ;;
    --proxy-public-url)
      PROXY_PUBLIC_URL=$2
      shift 2
      ;;
    --bootstrap)
      BOOTSTRAP=1
      shift
      ;;
    --create-secrets)
      CREATE_SECRETS=1
      shift
      ;;
    --skip-service-enable)
      SKIP_SERVICE_ENABLE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  printf 'This script must run as root.\n' >&2
  exit 1
fi

if [[ "${INSTALL_ROOT}" != "/opt/ids_ml_new" ]]; then
  printf 'This installer must run from the canonical checkout root /opt/ids_ml_new.\n' >&2
  printf 'Current checkout root: %s\n' "${INSTALL_ROOT}" >&2
  exit 1
fi

# Verify Python binary exists and meets minimum version requirement (3.11+)
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  printf 'Python binary not found: %s\nPython 3.11+ is required.\n' "${PYTHON_BIN}" >&2
  exit 1
fi
py_version=$("${PYTHON_BIN}" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
if [[ -z "${py_version}" ]]; then
  printf 'Could not determine Python version from %s.\nPython 3.11+ is required.\n' "${PYTHON_BIN}" >&2
  exit 1
fi
py_major="${py_version%%.*}"
py_minor="${py_version#*.}"
if [[ "${py_major}" -lt 3 ]] || { [[ "${py_major}" -eq 3 ]] && [[ "${py_minor}" -lt 11 ]]; }; then
  printf 'Python 3.11+ required, found %s (%s).\n' "${py_version}" "${PYTHON_BIN}" >&2
  exit 1
fi

require_file() {
  local path=$1
  if [[ ! -f "$path" ]]; then
    printf 'Required file not found: %s\n' "$path" >&2
    exit 1
  fi
}

require_dir() {
  local path=$1
  if [[ ! -d "$path" ]]; then
    printf 'Required directory not found: %s\n' "$path" >&2
    exit 1
  fi
}

require_mode() {
  case "${MODE}" in
    console-only|full-stack-same-host)
      return
      ;;
    "")
      printf 'Missing required --mode. Use console-only or full-stack-same-host.\n' >&2
      exit 2
      ;;
    *)
      printf 'Unknown install mode: %s\n' "${MODE}" >&2
      exit 2
      ;;
  esac
}

ensure_mode_contract() {
  if [[ "${MODE}" == "console-only" ]]; then
    if [[ ${BOOTSTRAP} -eq 1 || -n "${CANDIDATE_BUNDLE_ROOT}" ]]; then
      printf 'console-only mode does not accept bootstrap or bundle inputs.\n' >&2
      exit 1
    fi
  fi

  if [[ "${MODE}" == "full-stack-same-host" && ${BOOTSTRAP} -ne 1 ]]; then
    printf 'full-stack-same-host mode requires --bootstrap.\n' >&2
    exit 1
  fi

  if [[ "${MODE}" == "full-stack-same-host" && "${EXTRACTOR_COMMAND_PREFIX}" =~ [[:space:]] ]]; then
    printf 'full-stack-same-host uses one exact extractor helper path in %s; multi-token overrides are compatibility-only and not accepted by ops/install.sh.\n' "${LIVE_SENSOR_ENV_DEST}" >&2
    exit 1
  fi
}

require_mode
ensure_mode_contract

ensure_system_user() {
  local user=$1
  if ! id -u "$user" >/dev/null 2>&1; then
    useradd --system --home /nonexistent --shell /usr/sbin/nologin "$user"
  fi
}

operator_env_value() {
  local key=$1
  sed -n "s/^${key}=//p" "${OPERATOR_ENV_DEST}" | tail -n 1
}

live_sensor_env_value() {
  local key=$1
  sed -n "s/^${key}=//p" "${LIVE_SENSOR_ENV_DEST}" | tail -n 1
}

set_env_value() {
  local env_file=$1
  local key=$2
  local value=$3
  local tmp_file
  tmp_file=$(mktemp)
  awk -v key="${key}" -v value="${value}" '
    BEGIN { updated = 0 }
    index($0, key "=") == 1 { print key "=" value; updated = 1; next }
    { print }
    END { if (updated == 0) print key "=" value }
  ' "${env_file}" > "${tmp_file}"
  cat "${tmp_file}" > "${env_file}"
  rm -f "${tmp_file}"
}

require_nonempty_env_value() {
  local key=$1
  local value=$2
  if [[ -z "${value}" ]]; then
    printf '%s must be set in %s before full-stack bootstrap runs.\n' "${key}" "${LIVE_SENSOR_ENV_DEST}" >&2
    exit 1
  fi
}

require_single_token_value() {
  local key=$1
  local value=$2
  require_nonempty_env_value "${key}" "${value}"
  if [[ "${value}" =~ [[:space:]] ]]; then
    printf '%s in %s must be one executable path. Multi-token extractor prefixes are not part of the packaged live-sensor env/service contract.\n' "${key}" "${LIVE_SENSOR_ENV_DEST}" >&2
    exit 1
  fi
}

seed_operator_env() {
  mkdir -p "$(dirname -- "${OPERATOR_ENV_DEST}")"
  if [[ ! -f "${OPERATOR_ENV_DEST}" ]]; then
    install -m 0640 -o root -g ids-operator "${OPERATOR_ENV_SRC}" "${OPERATOR_ENV_DEST}"
  else
    # Harden a pre-seeded env file that may contain secrets (e.g. Telegram bot token).
    # The documented install path allows operators to copy the env example before
    # running the installer, so we must ensure safe ownership and permissions
    # regardless of how the file was created.
    chmod 0640 "${OPERATOR_ENV_DEST}"
    chown root:ids-operator "${OPERATOR_ENV_DEST}"
  fi
}

seed_live_sensor_env() {
  if [[ "${MODE}" != "full-stack-same-host" ]]; then
    return
  fi
  if [[ "${EXTRACTOR_COMMAND_PREFIX}" =~ [[:space:]] ]]; then
    printf 'full-stack-same-host install requires --extractor-command-prefix to be one executable path so bootstrap and systemd keep the same live-sensor contract.\n' >&2
    exit 1
  fi
  mkdir -p "$(dirname -- "${LIVE_SENSOR_ENV_DEST}")"
  if [[ ! -f "${LIVE_SENSOR_ENV_DEST}" ]]; then
    install -m 0640 -o root -g ids-sensor "${LIVE_SENSOR_ENV_SRC}" "${LIVE_SENSOR_ENV_DEST}"
  else
    chmod 0640 "${LIVE_SENSOR_ENV_DEST}"
    chown root:ids-sensor "${LIVE_SENSOR_ENV_DEST}"
  fi
  if [[ ${DUMPCAP_BINARY_WAS_SET} -eq 1 ]]; then
    set_env_value "${LIVE_SENSOR_ENV_DEST}" IDS_LIVE_SENSOR_DUMPCAP_BINARY "${DUMPCAP_BINARY}"
  fi
  if [[ ${EXTRACTOR_COMMAND_PREFIX_WAS_SET} -eq 1 ]]; then
    set_env_value "${LIVE_SENSOR_ENV_DEST}" IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX "${EXTRACTOR_COMMAND_PREFIX}"
  fi
  chmod 0640 "${LIVE_SENSOR_ENV_DEST}"
  chown root:ids-sensor "${LIVE_SENSOR_ENV_DEST}"
  require_single_token_value IDS_LIVE_SENSOR_INTERFACE "$(live_sensor_env_value IDS_LIVE_SENSOR_INTERFACE)"
  require_single_token_value IDS_LIVE_SENSOR_DUMPCAP_BINARY "$(live_sensor_env_value IDS_LIVE_SENSOR_DUMPCAP_BINARY)"
  require_single_token_value IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX "$(live_sensor_env_value IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX)"
  require_nonempty_env_value IDS_LIVE_SENSOR_SPOOL_DIR "$(live_sensor_env_value IDS_LIVE_SENSOR_SPOOL_DIR)"
  require_nonempty_env_value IDS_LIVE_SENSOR_ALERTS_OUTPUT "$(live_sensor_env_value IDS_LIVE_SENSOR_ALERTS_OUTPUT)"
  require_nonempty_env_value IDS_LIVE_SENSOR_QUARANTINE_OUTPUT "$(live_sensor_env_value IDS_LIVE_SENSOR_QUARANTINE_OUTPUT)"
  require_nonempty_env_value IDS_LIVE_SENSOR_SUMMARY_OUTPUT "$(live_sensor_env_value IDS_LIVE_SENSOR_SUMMARY_OUTPUT)"
  require_nonempty_env_value IDS_LIVE_SENSOR_ACTIVE_BUNDLE_PATH "$(live_sensor_env_value IDS_LIVE_SENSOR_ACTIVE_BUNDLE_PATH)"
}

seed_console_admin_password() {
  local admin_password_file=$1
  if [[ -z "${admin_password_file}" ]]; then
    printf 'console-only mode requires --create-secrets or --admin-password-file.\n' >&2
    exit 1
  fi

  if [[ -f "${admin_password_file}" ]]; then
    chmod 0640 "${admin_password_file}"
    chown root:ids-operator "${admin_password_file}"
    return
  fi

  if [[ ${CREATE_SECRETS} -ne 1 ]]; then
    printf 'console-only mode requires --create-secrets or --admin-password-file.\n' >&2
    exit 1
  fi

  mkdir -p "$(dirname -- "${admin_password_file}")"
  "${PYTHON_BIN}" - <<'PY' > "${admin_password_file}"
import secrets
print(secrets.token_hex(24))
PY
  chmod 0640 "${admin_password_file}"
  chown root:ids-operator "${admin_password_file}"
}

seed_console_secret() {
  if [[ -f "${CONSOLE_SECRET_FILE}" ]]; then
    chmod 0640 "${CONSOLE_SECRET_FILE}"
    chown root:ids-operator "${CONSOLE_SECRET_FILE}"
    return
  fi
  if [[ ${CREATE_SECRETS} -ne 1 ]]; then
    return
  fi
  mkdir -p "$(dirname -- "${CONSOLE_SECRET_FILE}")"
  "${PYTHON_BIN}" - <<'PY' > "${CONSOLE_SECRET_FILE}"
import secrets
print(secrets.token_hex(32))
PY
  chmod 0640 "${CONSOLE_SECRET_FILE}"
  chown root:ids-operator "${CONSOLE_SECRET_FILE}"
}

install_service_units() {
  install -m 0644 "${INSTALL_ROOT}/deploy/systemd/ids-live-sensor.service" "${SERVICE_DIR}/ids-live-sensor.service"
  install -m 0644 "${INSTALL_ROOT}/deploy/systemd/ids-operator-console.service" "${SERVICE_DIR}/ids-operator-console.service"
  install -m 0644 "${INSTALL_ROOT}/deploy/systemd/ids-operator-console-notify.service" "${SERVICE_DIR}/ids-operator-console-notify.service"
  systemctl daemon-reload
}

enable_mode_services() {
  if [[ "${MODE}" == "console-only" ]]; then
    systemctl enable ids-operator-console.service ids-operator-console-notify.service >/dev/null
    return
  fi

  systemctl enable ids-live-sensor.service ids-operator-console.service ids-operator-console-notify.service >/dev/null
}

install_python_product() {
  command -v "${PYTHON_BIN}" >/dev/null 2>&1 || {
    printf 'Python binary not found: %s\n' "${PYTHON_BIN}" >&2
    exit 1
  }
  "${PYTHON_BIN}" -m venv --clear "${INSTALL_ROOT}/.venv"
  if [[ -d "${INSTALL_ROOT}/wheelhouse" ]]; then
    "${INSTALL_ROOT}/.venv/bin/python" -m pip install --no-index --find-links "${INSTALL_ROOT}/wheelhouse" setuptools wheel
    "${INSTALL_ROOT}/.venv/bin/python" -m pip install --no-index --find-links "${INSTALL_ROOT}/wheelhouse" -r "${INSTALL_ROOT}/requirements.txt"
  else
    "${INSTALL_ROOT}/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
    "${INSTALL_ROOT}/.venv/bin/python" -m pip install -r "${INSTALL_ROOT}/requirements.txt"
  fi
  "${INSTALL_ROOT}/.venv/bin/python" -m pip install --no-deps -e "${INSTALL_ROOT}"
}

run_bootstrap() {
  if [[ "${MODE}" == "console-only" ]]; then
    local operator_db_path
    local console_admin_password_file
    local console_manage_cmd

    operator_db_path=$(operator_env_value IDS_OPERATOR_CONSOLE_DATABASE_PATH)
    if [[ -z "${operator_db_path}" ]]; then
      printf 'console-only mode requires IDS_OPERATOR_CONSOLE_DATABASE_PATH in %s.\n' "${OPERATOR_ENV_DEST}" >&2
      exit 1
    fi

    console_admin_password_file="${ADMIN_PASSWORD_FILE}"
    if [[ -z "${console_admin_password_file}" ]]; then
      console_admin_password_file="${DEFAULT_CONSOLE_ADMIN_PASSWORD_FILE}"
    fi
    seed_console_admin_password "${console_admin_password_file}"

    console_manage_cmd=(
      "${INSTALL_ROOT}/.venv/bin/python"
      -m
      ids.ops.operator_console_manage
      --database-path
      "${operator_db_path}"
    )

    "${console_manage_cmd[@]}" --json migrate --allow-bootstrap
    "${console_manage_cmd[@]}" \
      --json bootstrap-admin \
      --username "${ADMIN_USERNAME}" \
      --password-file "${console_admin_password_file}"
    if [[ ${SKIP_SERVICE_ENABLE} -ne 1 ]]; then
      systemctl start ids-operator-console.service ids-operator-console-notify.service >/dev/null
    fi
    "${console_manage_cmd[@]}" --json status
    "${console_manage_cmd[@]}" --json smoke
    "${console_manage_cmd[@]}" --json notify-status
    return
  fi

  if [[ ${BOOTSTRAP} -ne 1 ]]; then
    return
  fi
  if [[ -z "${ADMIN_PASSWORD_FILE}" ]]; then
    printf 'Cannot run --bootstrap without --admin-password-file.\n' >&2
    exit 1
  fi
  require_file "${ADMIN_PASSWORD_FILE}"

    local selected_bundle_root="${CANDIDATE_BUNDLE_ROOT}"
    local live_sensor_interface
    local live_sensor_dumpcap
    local live_sensor_extractor
    local live_sensor_spool_dir
    local live_sensor_alerts_output
    local live_sensor_quarantine_output
    local live_sensor_summary_output
    local activation_path
    if [[ -z "${selected_bundle_root}" ]]; then
      selected_bundle_root="${DEFAULT_BUNDLED_BUNDLE_ROOT}"
    fi
    require_dir "${selected_bundle_root}"
    live_sensor_interface=$(live_sensor_env_value IDS_LIVE_SENSOR_INTERFACE)
    live_sensor_dumpcap=$(live_sensor_env_value IDS_LIVE_SENSOR_DUMPCAP_BINARY)
    live_sensor_extractor=$(live_sensor_env_value IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX)
    live_sensor_spool_dir=$(live_sensor_env_value IDS_LIVE_SENSOR_SPOOL_DIR)
    live_sensor_alerts_output=$(live_sensor_env_value IDS_LIVE_SENSOR_ALERTS_OUTPUT)
    live_sensor_quarantine_output=$(live_sensor_env_value IDS_LIVE_SENSOR_QUARANTINE_OUTPUT)
    live_sensor_summary_output=$(live_sensor_env_value IDS_LIVE_SENSOR_SUMMARY_OUTPUT)
    activation_path=$(live_sensor_env_value IDS_LIVE_SENSOR_ACTIVE_BUNDLE_PATH)
    require_single_token_value IDS_LIVE_SENSOR_INTERFACE "${live_sensor_interface}"
    require_single_token_value IDS_LIVE_SENSOR_DUMPCAP_BINARY "${live_sensor_dumpcap}"
    require_single_token_value IDS_LIVE_SENSOR_EXTRACTOR_COMMAND_PREFIX "${live_sensor_extractor}"
    require_nonempty_env_value IDS_LIVE_SENSOR_SPOOL_DIR "${live_sensor_spool_dir}"
    require_nonempty_env_value IDS_LIVE_SENSOR_ALERTS_OUTPUT "${live_sensor_alerts_output}"
    require_nonempty_env_value IDS_LIVE_SENSOR_QUARANTINE_OUTPUT "${live_sensor_quarantine_output}"
    require_nonempty_env_value IDS_LIVE_SENSOR_SUMMARY_OUTPUT "${live_sensor_summary_output}"
    require_nonempty_env_value IDS_LIVE_SENSOR_ACTIVE_BUNDLE_PATH "${activation_path}"

    local stack_cmd="${INSTALL_ROOT}/.venv/bin/ids-stack"
    local smoke_url="${PROXY_PUBLIC_URL}"
  if [[ -z "${smoke_url}" ]]; then
    smoke_url=$(sed -n 's/^IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL=//p' "${OPERATOR_ENV_DEST}" | tail -n 1)
  fi

  "${stack_cmd}" \
    --repo-root "${INSTALL_ROOT}" \
      --python-binary "${INSTALL_ROOT}/.venv/bin/python" \
      --operator-env-file "${OPERATOR_ENV_DEST}" \
      --activation-path "${activation_path}" \
      --interface "${live_sensor_interface}" \
      --dumpcap-binary "${live_sensor_dumpcap}" \
      --extractor-command-prefix "${live_sensor_extractor}" \
      --spool-dir "${live_sensor_spool_dir}" \
      --alerts-output-path "${live_sensor_alerts_output}" \
      --quarantine-output-path "${live_sensor_quarantine_output}" \
      --summary-output-path "${live_sensor_summary_output}" \
    --proxy-public-url "${smoke_url}" \
    --json bootstrap \
    --candidate-bundle-root "${selected_bundle_root}" \
    --admin-username "${ADMIN_USERNAME}" \
    --admin-password-file "${ADMIN_PASSWORD_FILE}"
}

require_file "${INSTALL_ROOT}/pyproject.toml"
require_file "${INSTALL_ROOT}/requirements.txt"
require_file "${INSTALL_ROOT}/deploy/systemd/ids-live-sensor.service"
require_file "${INSTALL_ROOT}/deploy/systemd/ids-operator-console.service"
require_file "${INSTALL_ROOT}/deploy/systemd/ids-operator-console-notify.service"
require_file "${OPERATOR_ENV_SRC}"
require_file "${LIVE_SENSOR_ENV_SRC}"

ensure_system_user ids-sensor
ensure_system_user ids-operator

printf '[1/6] Verifying extracted checkout at %s...\n' "${INSTALL_ROOT}"
require_dir "${INSTALL_ROOT}/ids"
require_dir "${INSTALL_ROOT}/ops"

printf '[2/6] Creating host directories...\n'
install -d -m 0750 -o ids-sensor -g ids-sensor /var/lib/ids-live-sensor
install -d -m 0750 -o ids-sensor -g ids-sensor /var/log/ids-live-sensor
install -d -m 0750 -o root -g ids-sensor "${LIVE_SENSOR_CONFIG_DIR}"
install -d -m 0750 -o ids-operator -g ids-operator /var/lib/ids-operator-console
install -d -m 0750 -o ids-operator -g ids-operator /var/backups/ids-operator-console
install -d -m 0750 -o root -g ids-operator "${OPS_CONFIG_DIR}"

printf '[3/6] Creating target virtual environment...\n'
install_python_product

printf '[4/6] Seeding operator env and secrets...\n'
seed_operator_env
seed_live_sensor_env
seed_console_secret
if [[ ! -f "${TELEGRAM_TOKEN_FILE}" ]]; then
  install -m 0640 -o root -g ids-operator /dev/null "${TELEGRAM_TOKEN_FILE}"
fi

printf '[5/6] Installing systemd units...\n'
install_service_units

if [[ ${SKIP_SERVICE_ENABLE} -ne 1 ]]; then
  if [[ "${MODE}" == "console-only" ]]; then
    printf '[6/6] Enabling console-only services...\n'
  else
    printf '[6/6] Enabling full-stack services...\n'
  fi
  enable_mode_services
else
  printf '[6/6] Skipping systemd enable as requested...\n'
fi

printf 'Finalizing %s install path...\n' "${MODE}"
run_bootstrap

# Harden SQLite DB file permissions if it exists (the DB now contains
# the Telegram bot token stored via the Settings UI).
chmod 0640 /var/lib/ids-operator-console/operator_console.db 2>/dev/null || true
chown root:ids-operator /var/lib/ids-operator-console/operator_console.db 2>/dev/null || true

printf '\nInstall complete.\n'
printf 'Next checks:\n'
if [[ "${MODE}" == "console-only" ]]; then
  console_db_path=$(operator_env_value IDS_OPERATOR_CONSOLE_DATABASE_PATH)
  printf '  %s\n' "${INSTALL_ROOT}/.venv/bin/python -m ids.ops.operator_console_manage --database-path ${console_db_path} --json status"
  printf '  %s\n' "${INSTALL_ROOT}/.venv/bin/python -m ids.ops.operator_console_manage --database-path ${console_db_path} --json smoke"
  printf '  %s\n' "${INSTALL_ROOT}/.venv/bin/python -m ids.ops.operator_console_manage --database-path ${console_db_path} --json notify-status"
else
  printf '  %s\n' "${INSTALL_ROOT}/.venv/bin/ids-model-bundle-manage --activation-path /var/lib/ids-live-sensor/active_bundle.json --json status"
  printf '  %s\n' "${INSTALL_ROOT}/.venv/bin/ids-stack --repo-root ${INSTALL_ROOT} --operator-env-file ${OPERATOR_ENV_DEST} --activation-path /var/lib/ids-live-sensor/active_bundle.json --json preflight"
  printf '  %s\n' "${INSTALL_ROOT}/.venv/bin/ids-stack --repo-root ${INSTALL_ROOT} --operator-env-file ${OPERATOR_ENV_DEST} --activation-path /var/lib/ids-live-sensor/active_bundle.json --json status"
  printf '  %s\n' "${INSTALL_ROOT}/.venv/bin/ids-stack --repo-root ${INSTALL_ROOT} --operator-env-file ${OPERATOR_ENV_DEST} --activation-path /var/lib/ids-live-sensor/active_bundle.json --proxy-public-url https://console.example --json smoke"
fi
