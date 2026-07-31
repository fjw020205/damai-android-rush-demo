@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [Error] Run setup.bat first.
    pause
    exit /b 1
)

set "PYTHONPATH=%~dp0"
start "Damai rush console" "%~dp0.venv\Scripts\python.exe" "%~dp0console_server.py"
timeout /t 1 /nobreak >nul
start "" "http://127.0.0.1:8765/"
echo Console started at http://127.0.0.1:8765/
