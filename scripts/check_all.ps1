param(
    [switch]$BrowserAudit,
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $RepoRoot ".venv2\Scripts\python.exe"
$TmpRoot = Join-Path $RepoRoot "tmp_check_all"
$RunRoot = Join-Path $TmpRoot "run_$PID"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}

Push-Location $RepoRoot
try {
    New-Item -ItemType Directory -Force -Path $TmpRoot, $RunRoot | Out-Null
    $env:TMP = $RunRoot
    $env:TEMP = $RunRoot
    $env:TMPDIR = $RunRoot
    Remove-Item Env:\PYTEST_DEBUG_TEMPROOT -ErrorAction SilentlyContinue
    Remove-Item Env:\RUFF_CACHE_DIR -ErrorAction SilentlyContinue

    Invoke-Checked -Description "ruff" -Command {
        & $Python -m ruff check scripts src tests --ignore N999 --no-cache
    }
    Invoke-Checked -Description "pytest" -Command {
        & $Python -m pytest `
            -p no:cacheprovider `
            tests\test_dashboard `
            tests\test_api `
            tests\test_intelligence\test_storage_intelligence.py `
            tests\test_signals `
            tests\test_scripts `
            -q
    }

    if ($BrowserAudit) {
        try {
            Invoke-Checked -Description "playwright chromium check" -Command {
                & $Python -m playwright install chromium --dry-run
            }
        }
        catch {
            throw "Playwright Chromium is not installed. Run: $Python -m playwright install chromium"
        }
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $listener) {
            try {
                Invoke-WebRequest -Uri "http://localhost:$Port" -UseBasicParsing -TimeoutSec 5 | Out-Null
            }
            catch {
                throw "Dashboard is not reachable on port $Port. Start it with scripts\start_dashboard.ps1 first."
            }
        }
        $env:DASHBOARD_AUDIT_BASE_URL = "http://localhost:$Port"
        Invoke-Checked -Description "dashboard browser audit" -Command {
            & $Python scripts\audit_dashboard_pages.py
        }
    }
}
finally {
    Pop-Location
}
