# Install Gemlin, a tiny AI creature that lives on your desktop: https://gemlin.dev
#
#   powershell -ExecutionPolicy ByPass -c "irm https://gemlin.dev/install.ps1 | iex"
#
# What this does, step by step:
#   1. Gets uv (https://docs.astral.sh/uv), a tool that installs Python apps, if you don't have it.
#   2. Uses uv to install Gemlin with its own copy of Python, so nothing else on your computer changes.
#   3. Makes the `gemlin` command work in new terminals.
#   4. Wakes Gemlin up, and asks whether it should wake up whenever you log in.
# Run it again any time to update Gemlin. To remove it: gemlin autostart off; uv tool uninstall gemlin
# Keep this file plain ASCII: Windows PowerShell 5.1 reads BOM-less files as Windows-1252,
# where UTF-8 symbols like a check mark turn into stray quote characters and break parsing.
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
# uv prints notes like "already in PATH" to stderr. Windows PowerShell 5.1 turns redirected
# native stderr into errors, which "Stop" would make fatal, so relax it for this one call.
$ErrorActionPreference = "Continue"
& $uv tool update-shell *> $null
$ErrorActionPreference = "Stop"

$bin = (& $uv tool dir --bin).Trim()
$gemlin = Join-Path $bin "gemlin.exe"
Write-Host "  [ok] Installed $(& $gemlin --version)"

if ($env:GEMLIN_NO_START) { return }

$answer = Read-Host "`n  Wake Gemlin up whenever you log in? [Y/n]"
if ($answer -notmatch "^[nN]") { & $gemlin autostart on }

Write-Host ""
& $gemlin start
Write-Host ""
Write-Host "  Next time, open a new terminal and use:  gemlin start, gemlin stop, gemlin --help"
Write-Host "  Make Gemlin yours: click `"Customize me`" under its chat box, or visit https://gemlin.dev/create"
Write-Host ""
