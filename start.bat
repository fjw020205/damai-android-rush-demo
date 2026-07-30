@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "HATICKETS_LAUNCH_CONFIG=%~dp0config\rehearsal.jsonc"
set "HATICKETS_LAUNCH_RESULT=%~dp0logs\rehearsal-result.json"
set "PYTHONPATH=%~dp0"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [Error] Run setup.bat first.
    pause
    exit /b 1
)

if not exist "%HATICKETS_LAUNCH_CONFIG%" (
    echo [Error] Create config\rehearsal.jsonc from rehearsal.jsonc.example first.
    pause
    exit /b 1
)

echo Extra-selection rehearsal: selects session and ticket tier by index.
echo It stops before "Submit Order" and never pays.
echo.
"%~dp0.venv\Scripts\python.exe" -m mobile.damai_app --config "%HATICKETS_LAUNCH_CONFIG%" --result-json "%HATICKETS_LAUNCH_RESULT%"
pause
