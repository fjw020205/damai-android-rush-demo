@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "HATICKETS_LAUNCH_CONFIG=%~dp0config\preselected-formal.jsonc"
set "HATICKETS_LAUNCH_RESULT=%~dp0logs\preselected-formal-result.json"
set "PYTHONPATH=%~dp0"

if not exist "%~dp0.venv\Scripts\python.exe" (echo [Error] Run setup.bat first.&pause&exit /b 1)
if not exist "%HATICKETS_LAUNCH_CONFIG%" (echo [Error] Create config\preselected-formal.jsonc from its .example first.&pause&exit /b 1)

echo Preselected-SKU formal mode: direct rapid taps, then "Submit Order".
echo It never starts payment. Verify the configuration and rehearsal first.
echo.
"%~dp0.venv\Scripts\python.exe" -m mobile.damai_app --config "%HATICKETS_LAUNCH_CONFIG%" --result-json "%HATICKETS_LAUNCH_RESULT%"
set "HATICKETS_EXIT_CODE=%ERRORLEVEL%"
echo Result: %HATICKETS_LAUNCH_RESULT%
pause
exit /b %HATICKETS_EXIT_CODE%
