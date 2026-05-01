@echo off
setlocal

REM Move to the folder where this .bat file is located.
REM This makes the script work even if PowerShell starts in C:\WINDOWS\system32.
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    echo Virtual environment was not found.
    echo Please run these setup commands from this folder:
    echo   py -3 -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

"%PYTHON%" --version >nul 2>nul
if errorlevel 1 (
    echo The virtual environment exists, but Python did not run correctly.
    echo Please recreate it with:
    echo   py -3 -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Creating Predictive SPC and AI report outputs...
"%PYTHON%" src\predictive_spc.py
if errorlevel 1 goto error

echo.
echo Creating presentation summary...
"%PYTHON%" src\create_presentation_summary.py
if errorlevel 1 goto error

echo.
echo Done. Check outputs\presentation_summary.md and outputs\final_paper_outline.md.
pause
exit /b 0

:error
echo.
echo Something failed. Please read the error message above.
pause
exit /b 1
