#!/usr/bin/env bash
# Run inside WSL: puts "Phoenix Contract Masters" on the Windows desktop and Start menu.
# The shortcut starts the app in this WSL distro through wslg.exe, so no console window appears.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DISTRO="${WSL_DISTRO_NAME:?Run this inside WSL}"
NAME="Phoenix Contract Masters"

ps() { (cd /mnt/c && powershell.exe -NoProfile -NonInteractive -Command "$1" | tr -d '\r'); }

LAUNCHER='C:\Program Files\WSL\wslg.exe'
[ -f "/mnt/c/Program Files/WSL/wslg.exe" ] || LAUNCHER='C:\Windows\System32\wsl.exe'  # older WSL: console flashes

# Icon must live on the Windows side: a \\wsl$ path only resolves while the distro is running.
LOCAL="$(ps '$env:LOCALAPPDATA')\\PhoenixContractMasters"
mkdir -p "$(wslpath -u "$LOCAL")"
cp "$ROOT/gui/assets/app.ico" "$(wslpath -u "$LOCAL")/app.ico"

ARGS="-d $DISTRO -e \"$ROOT/run_gui.sh\""  # run_gui.sh cds to its own folder; no shell quoting needed
ps "
\$sh = New-Object -ComObject WScript.Shell
foreach (\$dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
  \$lnk = \$sh.CreateShortcut((Join-Path \$dir '$NAME.lnk'))
  \$lnk.TargetPath = '$LAUNCHER'
  \$lnk.Arguments = '${ARGS//\'/\'\'}'
  \$lnk.WorkingDirectory = \$env:USERPROFILE
  \$lnk.IconLocation = '$LOCAL\\app.ico'
  \$lnk.Description = 'Build NSE / BSE / MCX contract masters'
  \$lnk.Save()
  Write-Output (Join-Path \$dir '$NAME.lnk')
}"
echo "Done. Double-click \"$NAME\" on the desktop (or find it in the Start menu)."
