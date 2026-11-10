[CmdletBinding()]
param(
    [switch]$Setup,
    [switch]$Build,
    [ValidateRange(1, 65535)][int]$Port = 8000,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$dashboardRoot = Split-Path -Parent $PSScriptRoot
$dashboardPython = Join-Path $dashboardRoot '.venv\Scripts\python.exe'
if ($Check -and ($Setup -or $Build)) {
    throw '-Check is read-only. Run it separately from -Setup or -Build.'
}

Push-Location $dashboardRoot
try {
    if (-not (Test-Path -LiteralPath $dashboardPython)) {
        if (-not $Setup) { throw 'Run .\scripts\start_web_dashboard.cmd -Setup once to create the application environment.' }
        $candidates = @(
            @{ Name = 'python3.11.exe'; Prefix = @() },
            @{ Name = 'py.exe'; Prefix = @('-3.11') },
            @{ Name = 'python.exe'; Prefix = @() }
        )
        $created = $false
        foreach ($candidate in $candidates) {
            $executable = Get-Command $candidate.Name -ErrorAction SilentlyContinue
            if (-not $executable) { continue }
            $version = & $executable.Source @($candidate.Prefix) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -ne 0 -or $version -ne '3.11') { continue }
            & $executable.Source @($candidate.Prefix) -m venv .venv
            if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $dashboardPython)) {
                $created = $true
                break
            }
        }
        if (-not $created) { throw 'Could not create .venv. Install a working Python 3.11 (64-bit) and retry.' }
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

    # Resolve packages without importing the application or starting a worker.
    & $dashboardPython -c "import importlib.util, sys; required = ('uvicorn', 'fastapi', 'multipart', 'numpy', 'pandas', 'pyarrow', 'scipy', 'sklearn', 'xgboost', 'joblib', 'lightgbm', 'ngboost', 'ortools', 'psutil', 'tzdata'); missing = [name for name in required if importlib.util.find_spec(name) is None]; print('Missing dependencies: ' + ', '.join(missing) if missing else 'Application dependencies: available.'); sys.exit(bool(missing))"
    if ($LASTEXITCODE -ne 0) { throw 'Missing dependencies. Run .\scripts\start_web_dashboard.cmd -Setup.' }
    & $dashboardPython -c "from web_dashboard.thesis_profile import validate_release; print('Bundled proposal profile: ' + validate_release())"
    if ($LASTEXITCODE -ne 0) { throw 'Bundled proposal profile is incomplete. Use the release branch with all model files.' }

    $dashboardIndex = Join-Path $dashboardRoot 'web_dashboard\frontend\dist\index.html'
    if ($Check) {
        if (-not (Test-Path -LiteralPath $dashboardIndex)) {
            throw 'Frontend is not built. Run .\scripts\start_web_dashboard.cmd -Build.'
        }
        $dashboardHtml = Get-Content -LiteralPath $dashboardIndex -Raw -Encoding UTF8
        if ($dashboardHtml -notmatch '<div\s+id="root"' -or $dashboardHtml -notmatch '/assets/') {
            throw 'Frontend output is invalid. Run .\scripts\start_web_dashboard.cmd -Build.'
        }
        Write-Host "Project: $dashboardRoot"
        Write-Host "Python: $dashboardPython ($dashboardVersion)"
        Write-Host "Dashboard URL: http://127.0.0.1:$Port"
        Write-Host 'CHECK PASSED. No server, browser, notebook, or editor was started.'
        return
    }

    if ($Build -or $Setup -or -not (Test-Path -LiteralPath $dashboardIndex)) {
        Push-Location (Join-Path $dashboardRoot 'web_dashboard\frontend')
        try {
            if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
                throw 'Install Node.js 22+ (including npm), reopen your terminal, and run with -Setup.'
            }
            if ($Setup -or -not (Test-Path -LiteralPath 'node_modules')) {
                & npm.cmd ci --no-fund --no-audit
                if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
            }
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
        } finally { Pop-Location }
    }

    # Report a port conflict instead of sending the user to another local app.
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $dashboardListener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
        if ($dashboardListener) {
            throw "Port $Port is already in use. Choose another port, for example: .\scripts\start_web_dashboard.cmd -Port 8001"
        }
    }
    Write-Host "Aeolus web dashboard: http://127.0.0.1:$Port"
    Write-Host 'Enter this URL in your browser yourself. This command never opens a browser or editor.'
    Write-Host 'Stop the server with Ctrl+C.'
    & $dashboardPython -m uvicorn web_dashboard.app:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Dashboard server exited with code $LASTEXITCODE." }
} finally { Pop-Location }
