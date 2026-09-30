# AMCH-RAG PowerShell Startup Script
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "Starting AMCH-RAG Agentic System..." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 1. Check & Start Qdrant
Write-Host "[1/3] Checking Qdrant Vector Database..." -ForegroundColor Yellow
$qdrantListening = Get-NetTCPConnection -LocalPort 6333 -ErrorAction SilentlyContinue
if (-not $qdrantListening) {
    Write-Host "Starting Qdrant daemon on port 6333..." -ForegroundColor Green
    Start-Process -FilePath "bin\qdrant.exe" -WindowStyle Minimized
    Start-Sleep -Seconds 3
} else {
    Write-Host "Qdrant is already running on port 6333." -ForegroundColor Green
}

# 2. Open Browser
Write-Host "[2/3] Opening browser..." -ForegroundColor Yellow
Start-Process "http://localhost:8000"

# 3. Start FastAPI Server
Write-Host "[3/3] Starting FastAPI Server on http://localhost:8000..." -ForegroundColor Green
$pythonExe = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
& $pythonExe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
