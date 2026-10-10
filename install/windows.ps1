# Installs Phoenix Contract Masters for the current Windows user:
# a private Python environment (.venv) plus Desktop and Start-menu shortcuts.
#   Right-click > Run with PowerShell, or:  powershell -ExecutionPolicy Bypass -File install\windows.ps1
param([switch]$NoShortcuts)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$Name = "Phoenix Contract Masters"

if (-not (Test-Path "$Venv\Scripts\python.exe")) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $Base = @("py", "-3") }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $Base = @("python") }
    else { throw "Python 3.10+ is required: install it from https://www.python.org/downloads/ and run this again." }
    Write-Host "Creating Python environment in $Venv ..."
    & $Base[0] $Base[1..9] -m venv $Venv
    if ($LASTEXITCODE) { throw "Could not create the virtual environment." }
}
$Py = "$Venv\Scripts\python.exe"
Write-Host "Installing packages (first time takes a few minutes) ..."
& $Py -m pip install --disable-pip-version-check -q --upgrade pip
& $Py -m pip install --disable-pip-version-check -q -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE) { throw "Package installation failed." }
& $Py -m core.inputs | Out-Null  # quick self-check of the install
if ($LASTEXITCODE) { throw "Self-check failed." }

if (-not $NoShortcuts) {
    $Shell = New-Object -ComObject WScript.Shell
    foreach ($Dir in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"))) {
        $Lnk = $Shell.CreateShortcut((Join-Path $Dir "$Name.lnk"))
        $Lnk.TargetPath = "$Venv\Scripts\pythonw.exe"   # pythonw: no console window
        $Lnk.Arguments = "-m gui"
        $Lnk.WorkingDirectory = $Root
        $Lnk.IconLocation = (Join-Path $Root "gui\assets\app.ico")
        $Lnk.Description = "Build NSE / BSE / MCX contract masters"
        $Lnk.Save()
    }
    Write-Host "Shortcuts created on the Desktop and in the Start menu."
}
Write-Host "Done. Start '$Name' from the Desktop or Start menu."
