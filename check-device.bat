@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Error] Run setup.bat first.
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\python.exe" -m adbutils -l
echo.
echo One connected phone: set "serial" to null in the config.
echo Multiple phones: copy the required serial into the config.
pause
