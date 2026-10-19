param([switch]$Setup, [switch]$Build, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$dashboardRoot = Split-Path -Parent $PSScriptRoot
$dashboardPython = Join-Path $dashboardRoot '.venv\Scripts\python.exe'
Push-Location $dashboardRoot
try {
    if (-not (Test-Path -LiteralPath $dashboardPython)) {
        if (-not $Setup) { throw 'Run .\scripts\start_web_dashboard.ps1 -Setup once to create the application environment.' }
        if (Get-Command py.exe -ErrorAction SilentlyContinue) {
            & py.exe -3.11 -m venv .venv
        } elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
            & python.exe -m venv .venv
        } else {
            throw 'Install Python 3.11 (64-bit) and Node.js 22+ first, then run with -Setup.'
        }
        if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv. Install Python 3.11 (64-bit) first.' }
    }
    $dashboardVersion = & $dashboardPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0 -or $dashboardVersion -ne '3.11') {
        throw 'The saved checkpoints require the verified Python 3.11 environment. Use Python 3.11 for this project.'
    }
    if ($Setup) {
        & $dashboardPython -m pip install -r requirements-app.txt
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
        & $dashboardPython -m pip check
        if ($LASTEXITCODE -ne 0) { throw 'Python dependencies are incompatible.' }
        & $dashboardPython -c "from src.simulation.native_dual_core_pipeline import NativeDualCorePipeline; NativeDualCorePipeline().load_and_verify_models(); print('Bundled model checkpoints: verified.')"
        if ($LASTEXITCODE -ne 0) { throw 'Bundled model checkpoint verification failed.' }
    }
    $dashboardIndex = Join-Path $dashboardRoot 'web_dashboard\frontend\dist\index.html'
    if ($Build -or $Setup -or -not (Test-Path -LiteralPath $dashboardIndex)) {
        Push-Location (Join-Path $dashboardRoot 'web_dashboard\frontend')
        try {
            if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
                throw 'Install Node.js 22+ (including npm), reopen PowerShell, and run with -Setup.'
            }
            if ($Setup -or -not (Test-Path -LiteralPath 'node_modules')) {
                & npm.cmd ci --no-fund --no-audit
                if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
            }
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
        } finally { Pop-Location }
    }
    Write-Host "Aeolus web dashboard: http://127.0.0.1:$Port"
    Write-Host 'Stop with Ctrl+C. The existing Streamlit dashboard is unchanged.'
    & $dashboardPython -m uvicorn web_dashboard.app:app --host 127.0.0.1 --port $Port
} finally { Pop-Location }
