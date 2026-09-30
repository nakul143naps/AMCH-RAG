@echo off
title AMCH-RAG Production Server
echo ===================================================
echo Starting AMCH-RAG Agentic System...
echo ===================================================

cd /d "%~dp0"

REM 1. Check and Start Native Qdrant Vector Database
echo [1/3] Checking Qdrant Vector Database...
netstat -ano | findstr 6333 >nul
if %errorlevel% neq 0 (
    echo Starting Qdrant daemon on port 6333...
    start "" /min "bin\qdrant.exe"
    timeout /t 3 /nobreak >nul
) else (
    echo Qdrant is already running on port 6333.
)

REM 2. Launch Browser
echo [2/3] Preparing UI launcher...
start http://localhost:8000

REM 3. Start FastAPI Server + SPA Frontend
echo [3/3] Starting FastAPI Server on http://localhost:8000...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
) else (
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
)

pause
