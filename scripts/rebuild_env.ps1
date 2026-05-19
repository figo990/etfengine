param(
    [string]$PythonCommand = "py -3.12",
    [switch]$InstallBrowsers
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPath = Join-Path $RepoRoot ".venv2"
$Python = Join-Path $VenvPath "Scripts\python.exe"

Push-Location $RepoRoot
try {
    if (Test-Path $VenvPath) {
        Write-Host "Removing existing virtual environment: $VenvPath"
        Remove-Item -LiteralPath $VenvPath -Recurse -Force
    }

    Write-Host "Creating virtual environment with: $PythonCommand"
    $commandParts = $PythonCommand.Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
    $pythonExecutable = $commandParts[0]
    $pythonArgs = @()
    if ($commandParts.Length -gt 1) {
        $pythonArgs = $commandParts[1..($commandParts.Length - 1)]
    }
    & $pythonExecutable @pythonArgs -m venv .venv2

    & $Python -m pip install --upgrade pip
    & $Python -m pip install -e ".[dev]"

    if ($InstallBrowsers) {
        & $Python -m playwright install chromium
    }

    Write-Host "Environment ready: $Python"
    & $Python -c "import sys; print(sys.executable); print(sys.version)"
}
finally {
    Pop-Location
}
