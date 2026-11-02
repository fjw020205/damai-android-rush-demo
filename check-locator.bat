@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Error] 未找到虚拟环境，请先双击 setup.bat。
    pause
    exit /b 1
)

if "%~1"=="" (
    ".venv\Scripts\python.exe" -m mobile.locator selfcheck
) else (
    ".venv\Scripts\python.exe" -m mobile.locator %*
)
pause