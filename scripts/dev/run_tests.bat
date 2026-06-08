@echo off
setlocal

REM Move to the project root.
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

"%PYTHON%" -m pytest -q
if errorlevel 1 goto error

echo.
echo Unit tests passed.
exit /b 0

:error
echo.
echo Unit tests failed. Please read the error message above.
exit /b 1
