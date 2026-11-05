$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$web = Join-Path $root "apps\web"

if (-not (Test-Path $python)) {
    Write-Host "Python environment not found. Run the first-time setup in README.md." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $web "node_modules"))) {
    Write-Host "Frontend dependencies not found. Run 'npm install' in apps\web first." -ForegroundColor Red
    exit 1
}

Start-Process -FilePath $python -ArgumentList @(
    "-m", "uvicorn", "mfd_dashboard.main:app",
    "--app-dir", "apps/api/src",
    "--host", "127.0.0.1",
    "--port", "8000",
    "--reload"
) -WorkingDirectory $root

Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") -WorkingDirectory $web

Write-Host "Backend:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:3000" -ForegroundColor Green
Write-Host "Close the two new PowerShell windows to stop the app."
