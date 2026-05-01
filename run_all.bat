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

echo [1/7] Running baseline training...
"%PYTHON%" src\train_baseline.py
if errorlevel 1 goto error

echo.
echo [2/7] Running Stage 4 threshold tuning and SHAP explanation...
"%PYTHON%" src\stage4_explain.py
if errorlevel 1 goto error

echo.
echo [3/7] Creating Predictive SPC and AI report outputs...
"%PYTHON%" src\predictive_spc.py
if errorlevel 1 goto error

echo.
echo [4/7] Creating future deviation prediction outputs...
"%PYTHON%" src\future_deviation.py
if errorlevel 1 goto error

echo.
echo [5/7] Verifying Stage 14 company retraining outputs...
"%PYTHON%" src\verify_company_generalization.py
if errorlevel 1 goto error

echo.
echo [6/7] Verifying Stage 15-18 local operations outputs...
"%PYTHON%" src\verify_stage15_20.py
if errorlevel 1 goto error

echo.
echo [7/7] Creating presentation summary...
"%PYTHON%" src\create_presentation_summary.py
if errorlevel 1 goto error

echo.
echo Done. Check the outputs folder.
pause
exit /b 0

:error
echo.
echo Something failed. Please read the error message above.
pause
exit /b 1
