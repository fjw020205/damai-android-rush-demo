@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "HATICKETS_LAUNCH_CONFIG=%~dp0config\formal.jsonc"
set "HATICKETS_LAUNCH_RESULT=%~dp0logs\formal-result.json"
set "PYTHONPATH=%~dp0"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [Error] Run setup.bat first.
    pause
    exit /b 1
)

if not exist "%HATICKETS_LAUNCH_CONFIG%" (
    echo [Error] Create config\formal.jsonc from formal.jsonc.example first.
    pause
    exit /b 1
)

echo Extra-selection formal mode: selects by index and clicks "Submit Order".
echo It never starts payment.
echo.
"%~dp0.venv\Scripts\python.exe" -m mobile.damai_app --config "%HATICKETS_LAUNCH_CONFIG%" --result-json "%HATICKETS_LAUNCH_RESULT%"
pause
