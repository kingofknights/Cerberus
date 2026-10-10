#!/usr/bin/env bash
# Command-line entrypoint: build contract masters (see ./run_all.sh --help).
set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 is not installed or not in PATH."
    exit 1
fi
exec python3 "${SCRIPT_DIR}/run_all.py" "$@"
