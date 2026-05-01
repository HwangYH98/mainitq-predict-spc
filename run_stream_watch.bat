@echo off
setlocal

REM Move to the folder where this .bat file is located.
cd /d "%~dp0"

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

echo Watching outputs\realtime_stream\incoming for CSV files.
echo Press Ctrl+C to stop.
"%PYTHON%" src\watch_realtime_folder.py
