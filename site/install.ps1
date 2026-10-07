# Install Gemlin, a tiny AI creature that lives on your desktop: https://gemlin.dev
#
#   powershell -ExecutionPolicy ByPass -c "irm https://gemlin.dev/install.ps1 | iex"
#
# What this does, step by step:
#   1. Gets uv (https://docs.astral.sh/uv), a tool that installs Python apps, if you don't have it.
#   2. Uses uv to install Gemlin with its own copy of Python, so nothing else on your computer changes.
#   3. Makes the `gemlin` command work in new terminals.
#   4. Adds Gemlin to the Start menu.
#   5. Wakes Gemlin up, and asks whether it should wake up whenever you log in.
# Run it again any time to update Gemlin. To remove it: gemlin uninstall
$ErrorActionPreference = "Stop"

$Source = if ($env:GEMLIN_SOURCE) { $env:GEMLIN_SOURCE } else { "https://github.com/alexinslc/gemlin/archive/refs/heads/main.zip" }
$PythonVersion = "3.13"

Write-Host ""
Write-Host "  Installing Gemlin..."
Write-Host ""

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (-not (Test-Path $uv)) {
        Write-Host "  Getting uv (it installs Python apps)..."
        $env:UV_NO_MODIFY_PATH = "1"
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression | Out-Null
    }
}

Write-Host "  Installing Gemlin and its own Python (this can take a minute the first time)..."
& $uv tool install --quiet --force --python $PythonVersion "gemlin @ $Source"
if ($LASTEXITCODE -ne 0) { throw "Gemlin didn't install. Scroll up to see why." }
& $uv tool update-shell *> $null

$bin = (& $uv tool dir --bin).Trim()
$gemlin = Join-Path $bin "gemlin.exe"
Write-Host "  ✓ Installed $(& $gemlin --version)"
$app = & $gemlin app
if ($LASTEXITCODE -eq 0) { Write-Host "  ✓ $app" } else { Write-Host "  ! $app" }

if ($env:GEMLIN_NO_START) { return }

$answer = Read-Host "`n  Wake Gemlin up whenever you log in? [Y/n]"
if ($answer -notmatch "^[nN]") { & $gemlin autostart on }

Write-Host ""
& $gemlin start
Write-Host ""
Write-Host "  You can close this window. Gemlin lives in the system tray and on your desktop:"
Write-Host "  open Gemlin from the Start menu to wake it, and right-click Gemlin (or its tray icon) for everything else."
Write-Host "  Make it yours: click `"Customize me`" under its chat box, or visit https://gemlin.dev/create"
Write-Host ""
