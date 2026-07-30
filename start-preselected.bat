@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "HATICKETS_LAUNCH_CONFIG=%~dp0config\preselected-rehearsal.jsonc"
set "HATICKETS_LAUNCH_RESULT=%~dp0logs\preselected-rehearsal-result.json"
set "HATICKETS_CTA_FIRST_TAP_DELAY_MS=0"
set "PYTHONPATH=%~dp0"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [Error] Run setup.bat first.
    pause
    exit /b 1
)
if not exist "%HATICKETS_LAUNCH_CONFIG%" (
    echo [Error] Create config\preselected-rehearsal.jsonc from its .example first.
    pause
    exit /b 1
)

echo Preselected-SKU rehearsal: direct rapid taps at T0.
echo It skips session and ticket-tier selection, then stops before "Submit Order".
echo.
"%~dp0.venv\Scripts\python.exe" -m mobile.damai_app --config "%HATICKETS_LAUNCH_CONFIG%" --result-json "%HATICKETS_LAUNCH_RESULT%"
set "HATICKETS_EXIT_CODE=%ERRORLEVEL%"
echo.
if "%HATICKETS_EXIT_CODE%"=="0" (echo Rehearsal finished without submitting.) else (echo Rehearsal stopped with code %HATICKETS_EXIT_CODE%.)
echo Result: %HATICKETS_LAUNCH_RESULT%
pause
exit /b %HATICKETS_EXIT_CODE%
