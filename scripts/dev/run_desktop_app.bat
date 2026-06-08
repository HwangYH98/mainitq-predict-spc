@echo off
chcp 65001 >nul
setlocal

REM Move to the project root.
REM This makes the script work even if PowerShell starts in C:\WINDOWS\system32.
cd /d "%~dp0..\.."

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    echo Virtual environment was not found.
    echo Please run:
    echo   py -3 -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

"%PYTHON%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo PySide6 is not installed. Installing into the local .venv...
    "%PYTHON%" -m pip install PySide6
    if errorlevel 1 goto error
)

echo Starting native desktop app...
"%PYTHON%" desktop_app\main.py
if errorlevel 1 goto error
exit /b 0

:error
echo.
echo Native desktop app failed. Please read the error message above.
pause
exit /b 1
