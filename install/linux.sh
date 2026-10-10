#!/usr/bin/env bash
# Installs Phoenix Contract Masters for the current Linux user:
# a private Python environment (.venv) plus an application-menu entry (and a desktop icon if ~/Desktop exists).
#   ./install/linux.sh            (add --no-shortcuts to skip the menu entry)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
NAME="Phoenix Contract Masters"

command -v python3 >/dev/null || { echo "Python 3.10+ is required (sudo apt install python3 python3-venv)"; exit 1; }
if [ ! -x "$VENV/bin/python" ]; then
    echo "Creating Python environment in $VENV ..."
    python3 -m venv "$VENV" || { echo "Install python3-venv first (sudo apt install python3-venv)"; exit 1; }
fi
echo "Installing packages (first time takes a few minutes) ..."
"$VENV/bin/python" -m pip install --disable-pip-version-check -q --upgrade pip
"$VENV/bin/python" -m pip install --disable-pip-version-check -q -r "$ROOT/requirements.txt"
(cd "$ROOT" && "$VENV/bin/python" -m core.inputs >/dev/null)  # quick self-check of the install

if [ "${1:-}" != "--no-shortcuts" ]; then
    APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    mkdir -p "$APPS"
    cat > "$APPS/phoenix-contract-masters.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$NAME
Comment=Build NSE / BSE / MCX contract masters
Exec="$VENV/bin/python" -m gui
Path=$ROOT
Icon=$ROOT/gui/assets/app.png
Terminal=false
Categories=Office;Finance;
StartupWMClass=phoenix-contract-masters
EOF
    chmod +x "$APPS/phoenix-contract-masters.desktop"
    if [ -d "$HOME/Desktop" ]; then
        cp "$APPS/phoenix-contract-masters.desktop" "$HOME/Desktop/"
        chmod +x "$HOME/Desktop/phoenix-contract-masters.desktop"
    fi
    echo "Added \"$NAME\" to the application menu."
fi
echo "Done. Start it from the application menu, or: $VENV/bin/python -m gui"
