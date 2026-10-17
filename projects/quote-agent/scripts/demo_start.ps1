# Start the Streamlit app (if not running), wait until healthy, then open it in the default browser.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\demo_start.ps1 [-Port 8501] [-NoBrowser] [-Stop]
param([int]$Port = 8501, [switch]$NoBrowser, [switch]$Stop)

$root = Split-Path -Parent $PSScriptRoot
$url = "http://localhost:$Port"
$health = "$url/_stcore/health"

function Test-Up {
    try { return (Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 2).Content -eq "ok" } catch { return $false }
}

if ($Stop) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue }
    Write-Host "stopped listener(s) on port $Port"
    exit 0
}

if (Test-Up) {
    Write-Host "already running: $url"
} else {
    $logDir = Join-Path $root "logs"
    New-Item -ItemType Directory -Force $logDir | Out-Null
    Start-Process -FilePath "python" -WorkingDirectory $root -WindowStyle Minimized `
        -ArgumentList @("-m", "streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "$Port", "--browser.gatherUsageStats", "false") `
        -RedirectStandardOutput (Join-Path $logDir "streamlit.out.log") -RedirectStandardError (Join-Path $logDir "streamlit.err.log")
    $deadline = (Get-Date).AddSeconds(45)
    while (-not (Test-Up)) {
        if ((Get-Date) -gt $deadline) { Write-Host "FAILED to start within 45s. see logs\streamlit.err.log"; exit 1 }
        Start-Sleep -Milliseconds 500
    }
    Write-Host "started: $url"
}

if (-not $NoBrowser) { Start-Process $url }
