@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [Error] Python 3.10-3.13 was not found in PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed

".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :failed

echo.
echo Setup complete. Connect the Android phone, then copy a config template.
pause
exit /b 0

:failed
echo.
echo [Error] Setup stopped. Check the messages above.
pause
exit /b 1
