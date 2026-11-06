@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0tools\check_encoding.py"
) else (
    python "%~dp0tools\check_encoding.py"
)
pause
