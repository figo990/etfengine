param(
    [switch]$BrowserAudit,
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $RepoRoot ".venv2\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}

Push-Location $RepoRoot
try {
    & $Python -m ruff check scripts src tests --ignore N999
    & $Python -m pytest tests\test_dashboard tests\test_api tests\test_intelligence\test_storage_intelligence.py tests\test_signals tests\test_scripts -q

    if ($BrowserAudit) {
        try {
            & $Python -m playwright install chromium --dry-run | Out-Null
        }
        catch {
            throw "Playwright Chromium is not installed. Run: $Python -m playwright install chromium"
        }
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $listener) {
            throw "Dashboard is not listening on port $Port. Start it with scripts\start_dashboard.ps1 first."
        }
        $env:DASHBOARD_AUDIT_BASE_URL = "http://localhost:$Port"
        & $Python scripts\audit_dashboard_pages.py
    }
}
finally {
    Pop-Location
}
