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

echo Starting Stage 16-lite FastAPI prediction server...
echo Open API docs at http://127.0.0.1:8000/docs
"%PYTHON%" -m uvicorn src.api_server:app --host 127.0.0.1 --port 8000
