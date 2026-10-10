#!/usr/bin/env bash
# Launch the Contract Downloader desktop GUI.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"
cd "${SCRIPT_DIR}" && exec python3 -m gui "$@"
