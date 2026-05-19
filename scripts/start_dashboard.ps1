param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $RepoRoot ".venv2\Scripts\python.exe"
$PyvenvConfig = Join-Path $RepoRoot ".venv2\pyvenv.cfg"

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
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
Start-Process `
    -FilePath $Python `
    -ArgumentList "-m", "streamlit", "run", "src/dashboard/app.py", "--server.port", "$Port", "--server.headless", "true", "--browser.gatherUsageStats", "false" `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -WindowStyle Hidden

Start-Sleep -Seconds 5
$listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
$listeners | Select-Object LocalAddress, LocalPort, State, OwningProcess

foreach ($listener in $listeners) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction SilentlyContinue
    if ($proc) {
        $allowedExecutables = @($Python)
        if (Test-Path $PyvenvConfig) {
            $baseExecutable = Select-String -Path $PyvenvConfig -Pattern "^executable\s*=\s*(.+)$" |
                ForEach-Object { $_.Matches[0].Groups[1].Value.Trim() } |
                Select-Object -First 1
            if ($baseExecutable) {
                $allowedExecutables += $baseExecutable
            }
        }
        if ($allowedExecutables -notcontains $proc.ExecutablePath) {
            Write-Warning "Dashboard listener is running with $($proc.ExecutablePath), expected venv executable $Python. Rebuild .venv2 or run with the intended environment if dependency drift appears."
        }
    }
}
