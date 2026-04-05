#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Build a release bundle for deploying IDS_ML_New onto another Linux host.

Usage:
  ./ops/build_release.sh [--repo-root PATH] [--output-dir PATH] [--python-bin PATH]

Output layout:
  <output-dir>/
    wheelhouse/                 Optional dependency wheels matching requirements.txt
    ids_ml_new-<timestamp>.tar.gz

The tarball contains a git-tracked export (via git archive) plus an optional
dependency wheelhouse so the target host can run ops/install.sh from
/opt/ids_ml_new.  Only committed files are included; untracked and ignored
local files (secrets, .claude/, etc.) are excluded by construction.
EOF
}

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
OUTPUT_DIR="${REPO_ROOT}/dist/release"
PYTHON_BIN="python3.11"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      REPO_ROOT=$(cd -- "$2" && pwd)
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR=$2
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN=$2
      shift 2
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

require_file() {
  local path=$1
  if [[ ! -f "$path" ]]; then
    printf 'Required file not found: %s\n' "$path" >&2
    exit 1
  fi
}

require_file "${REPO_ROOT}/pyproject.toml"
require_file "${REPO_ROOT}/requirements.txt"
command -v "${PYTHON_BIN}" >/dev/null 2>&1 || {
  printf 'Python binary not found: %s\n' "${PYTHON_BIN}" >&2
  exit 1
}

TIMESTAMP=$("${PYTHON_BIN}" -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))")
STAGING_DIR="${OUTPUT_DIR}/staging-${TIMESTAMP}"
BUNDLE_DIR="${STAGING_DIR}/ids_ml_new"
WHEELHOUSE_DIR="${BUNDLE_DIR}/wheelhouse"
ARCHIVE_PATH="${OUTPUT_DIR}/ids_ml_new-${TIMESTAMP}.tar.gz"
DEFAULT_BUNDLE_ROOT="${BUNDLE_DIR}/artifacts/final_model/catboost_full_data_v1"

printf '[1/4] Exporting tracked files via git archive...\n'
mkdir -p "${BUNDLE_DIR}"
# Safety: use git archive so only committed/tracked files are exported.
# This prevents untracked secrets, credentials, .claude/, and other local-only
# files from leaking into the release artifact.
git -C "${REPO_ROOT}" archive HEAD | tar -C "${BUNDLE_DIR}" -xf -

printf '[2/4] Validating staged bundled default production artifact...\n'
"${PYTHON_BIN}" -c "import sys; from pathlib import Path; repo_root = Path(sys.argv[1]); bundle_root = Path(sys.argv[2]); sys.path.insert(0, str(repo_root)); from ids.core.model_bundle import load_model_bundle_manifest; load_model_bundle_manifest(bundle_root)" "${BUNDLE_DIR}" "${DEFAULT_BUNDLE_ROOT}"

mkdir -p "${WHEELHOUSE_DIR}"

printf '[3/4] Building dependency wheelhouse...\n'
"${PYTHON_BIN}" -m pip wheel setuptools wheel --wheel-dir "${WHEELHOUSE_DIR}"
"${PYTHON_BIN}" -m pip wheel -r "${REPO_ROOT}/requirements.txt" --wheel-dir "${WHEELHOUSE_DIR}"

printf '[4/4] Writing archive...\n'
mkdir -p "${OUTPUT_DIR}"
tar -C "${STAGING_DIR}" -czf "${ARCHIVE_PATH}" ids_ml_new

printf '\nRelease bundle created:\n'
printf '  %s\n' "${ARCHIVE_PATH}"
printf '\nTarget-host flow:\n'
printf '  1. Copy archive to the target host.\n'
printf '  2. Extract to /opt/ids_ml_new (or another staging path).\n'
printf '  3. Run sudo bash /opt/ids_ml_new/ops/install.sh\n'
