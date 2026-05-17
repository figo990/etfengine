param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $RepoRoot ".venv2\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}

$connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -gt 0 }

foreach ($processId in $processIds) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -like "*streamlit*src/dashboard/app.py*") {
        Write-Host "Stopping existing dashboard process $processId"
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 2

$out = Join-Path $RepoRoot "streamlit-$Port.log"
$err = Join-Path $RepoRoot "streamlit-$Port.err.log"

Write-Host "Starting dashboard on http://localhost:$Port"
Start-Process `
    -FilePath $Python `
    -ArgumentList "-m", "streamlit", "run", "src/dashboard/app.py", "--server.port", "$Port", "--server.headless", "true" `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -WindowStyle Hidden

Start-Sleep -Seconds 5
Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, State, OwningProcess
