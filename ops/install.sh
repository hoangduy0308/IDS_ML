#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install the IDS same-host stack onto a Linux target host.

Usage:
  sudo ./ops/install.sh [options]

Options:
  --python-bin PATH             Python binary used to create the target venv (default: python3.11)
  --operator-env-src PATH       Template env file to seed (default: ops/ids-operator-console.env.example)
  --operator-env-dest PATH      Host env file path (default: /etc/ids-operator-console/ids-operator-console.env)
  --console-secret-file PATH    Host secret key file path (default: /etc/ids-operator-console/console.secret)
  --telegram-token-file PATH    Host Telegram token file path (default: /etc/ids-operator-console/telegram-bot-token.secret)
  --dumpcap-binary PATH         dumpcap path passed to ids-stack bootstrap (default: /usr/bin/dumpcap)
  --extractor-command-prefix P  Single-token flow extractor command prefix (default: /opt/cicflowmeter/Cmd)
  --extractor-command-prefix-token P
                               Repeat to pass a multi-token extractor command prefix
  --candidate-bundle-root PATH  Bundle root for ids-stack bootstrap (required with --bootstrap)
  --admin-username NAME         Admin username for bootstrap (default: admin)
  --admin-password-file PATH    Admin password file for bootstrap
  --proxy-public-url URL        Public console URL used for smoke checks
  --bootstrap                   Run ids-stack bootstrap after installation
  --create-secrets              Generate a console secret file if one does not exist yet
  --skip-service-enable         Install files but do not enable/start systemd units
  -h, --help                    Show this help

Notes:
  - Run this script from the extracted checkout at /opt/ids_ml_new/ops/install.sh.
  - The script recreates /opt/ids_ml_new/.venv on the target host and installs the app via pip install -e.
  - If wheelhouse/ is present under the checkout, the script prefers it for dependency installation only.
  - ids-stack remains the canonical lifecycle surface; this script only prepares the host and optionally invokes bootstrap.
EOF
}

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
INSTALL_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
PYTHON_BIN="python3.11"
SERVICE_DIR="/etc/systemd/system"
OPS_CONFIG_DIR="/etc/ids-operator-console"
OPERATOR_ENV_SRC="${INSTALL_ROOT}/ops/ids-operator-console.env.example"
OPERATOR_ENV_DEST="${OPS_CONFIG_DIR}/ids-operator-console.env"
CONSOLE_SECRET_FILE="${OPS_CONFIG_DIR}/console.secret"
TELEGRAM_TOKEN_FILE="${OPS_CONFIG_DIR}/telegram-bot-token.secret"
DUMPCAP_BINARY="/usr/bin/dumpcap"
EXTRACTOR_COMMAND_PREFIX=("/opt/cicflowmeter/Cmd")
ADMIN_USERNAME="admin"
ADMIN_PASSWORD_FILE=""
PROXY_PUBLIC_URL=""
BOOTSTRAP=0
CREATE_SECRETS=0
SKIP_SERVICE_ENABLE=0
CANDIDATE_BUNDLE_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
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
      shift 2
      ;;
    --extractor-command-prefix)
      EXTRACTOR_COMMAND_PREFIX=("$2")
      shift 2
      ;;
    --extractor-command-prefix-token)
      EXTRACTOR_COMMAND_PREFIX+=("$2")
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

ensure_system_user() {
  local user=$1
  if ! id -u "$user" >/dev/null 2>&1; then
    useradd --system --home /nonexistent --shell /usr/sbin/nologin "$user"
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
  if [[ ${BOOTSTRAP} -ne 1 ]]; then
    return
  fi
  if [[ -z "${ADMIN_PASSWORD_FILE}" ]]; then
    printf 'Cannot run --bootstrap without --admin-password-file.\n' >&2
    exit 1
  fi
  if [[ -z "${CANDIDATE_BUNDLE_ROOT}" ]]; then
    printf 'Cannot run --bootstrap without --candidate-bundle-root.\n' >&2
    exit 1
  fi
  require_file "${ADMIN_PASSWORD_FILE}"
  require_dir "${CANDIDATE_BUNDLE_ROOT}"

  local stack_cmd="${INSTALL_ROOT}/.venv/bin/ids-stack"
  local activation_path="/var/lib/ids-live-sensor/active_bundle.json"
  local smoke_url="${PROXY_PUBLIC_URL}"
  if [[ -z "${smoke_url}" ]]; then
    smoke_url=$(sed -n 's/^IDS_OPERATOR_CONSOLE_PUBLIC_BASE_URL=//p' "${OPERATOR_ENV_DEST}" | tail -n 1)
  fi

  "${stack_cmd}" \
    --repo-root "${INSTALL_ROOT}" \
    --python-binary "${INSTALL_ROOT}/.venv/bin/python" \
    --operator-env-file "${OPERATOR_ENV_DEST}" \
    --activation-path "${activation_path}" \
    --dumpcap-binary "${DUMPCAP_BINARY}" \
    --extractor-command-prefix "${EXTRACTOR_COMMAND_PREFIX[@]}" \
    --spool-dir /var/lib/ids-live-sensor \
    --alerts-output-path /var/log/ids-live-sensor/ids_live_alerts.jsonl \
    --quarantine-output-path /var/log/ids-live-sensor/ids_live_quarantine.jsonl \
    --summary-output-path /var/log/ids-live-sensor/ids_live_sensor_summary.jsonl \
    --proxy-public-url "${smoke_url}" \
    --json bootstrap \
    --candidate-bundle-root "${CANDIDATE_BUNDLE_ROOT}" \
    --admin-username "${ADMIN_USERNAME}" \
    --admin-password-file "${ADMIN_PASSWORD_FILE}"
}

require_file "${INSTALL_ROOT}/pyproject.toml"
require_file "${INSTALL_ROOT}/requirements.txt"
require_file "${INSTALL_ROOT}/deploy/systemd/ids-live-sensor.service"
require_file "${INSTALL_ROOT}/deploy/systemd/ids-operator-console.service"
require_file "${INSTALL_ROOT}/deploy/systemd/ids-operator-console-notify.service"
require_file "${OPERATOR_ENV_SRC}"

ensure_system_user ids-sensor
ensure_system_user ids-operator

printf '[1/6] Verifying extracted checkout at %s...\n' "${INSTALL_ROOT}"
require_dir "${INSTALL_ROOT}/ids"
require_dir "${INSTALL_ROOT}/ops"

printf '[2/6] Creating host directories...\n'
install -d -m 0750 -o ids-sensor -g ids-sensor /var/lib/ids-live-sensor
install -d -m 0750 -o ids-sensor -g ids-sensor /var/log/ids-live-sensor
install -d -m 0750 -o ids-operator -g ids-operator /var/lib/ids-operator-console
install -d -m 0750 -o ids-operator -g ids-operator /var/backups/ids-operator-console
install -d -m 0750 -o root -g ids-operator "${OPS_CONFIG_DIR}"

printf '[3/6] Creating target virtual environment...\n'
install_python_product

printf '[4/6] Seeding operator env and secrets...\n'
seed_operator_env
seed_console_secret
if [[ ! -f "${TELEGRAM_TOKEN_FILE}" ]]; then
  install -m 0640 -o root -g ids-operator /dev/null "${TELEGRAM_TOKEN_FILE}"
fi

printf '[5/6] Installing systemd units...\n'
install_service_units

if [[ ${SKIP_SERVICE_ENABLE} -ne 1 ]]; then
  printf '[6/6] Enabling base services...\n'
  systemctl enable ids-live-sensor.service ids-operator-console.service ids-operator-console-notify.service >/dev/null
else
  printf '[6/6] Skipping systemd enable as requested...\n'
fi

printf 'Finalizing bootstrap path...\n'
run_bootstrap

# Harden SQLite DB file permissions if it exists (the DB now contains
# the Telegram bot token stored via the Settings UI).
chmod 0640 /var/lib/ids-operator-console/operator_console.db 2>/dev/null || true
chown root:ids-operator /var/lib/ids-operator-console/operator_console.db 2>/dev/null || true

printf '\nInstall complete.\n'
printf 'Next checks:\n'
printf '  %s\n' "${INSTALL_ROOT}/.venv/bin/ids-stack --repo-root ${INSTALL_ROOT} --operator-env-file ${OPERATOR_ENV_DEST} --activation-path /var/lib/ids-live-sensor/active_bundle.json --json preflight"
printf '  %s\n' "${INSTALL_ROOT}/.venv/bin/ids-stack --repo-root ${INSTALL_ROOT} --operator-env-file ${OPERATOR_ENV_DEST} --activation-path /var/lib/ids-live-sensor/active_bundle.json --json status"
printf '  %s\n' "${INSTALL_ROOT}/.venv/bin/ids-stack --repo-root ${INSTALL_ROOT} --operator-env-file ${OPERATOR_ENV_DEST} --activation-path /var/lib/ids-live-sensor/active_bundle.json --proxy-public-url https://console.example --json smoke"
