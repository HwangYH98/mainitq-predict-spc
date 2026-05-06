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

echo [1/13] Verifying Stage 14 company retraining outputs...
"%PYTHON%" src\verify_company_generalization.py
if errorlevel 1 goto error

echo.
echo [2/13] Verifying Stage 15-18 local operations outputs...
"%PYTHON%" src\verify_stage15_20.py
if errorlevel 1 goto error

echo.
echo [3/13] Verifying Stage 19-20 local field-event and decision integration...
"%PYTHON%" src\verify_stage19_20_integration.py
if errorlevel 1 goto error

echo.
echo [4/13] Running model strategy comparison including SMOTE...
"%PYTHON%" src\compare_model_strategies.py
if errorlevel 1 goto error

echo.
echo [5/13] Running SPC-only vs ML+SPC alert comparison...
"%PYTHON%" src\compare_spc_ml_alerts.py
if errorlevel 1 goto error

echo.
echo [6/13] Running operational value simulation...
"%PYTHON%" src\evaluate_operational_value.py
if errorlevel 1 goto error

echo.
echo [7/13] Verifying smart CSV preprocessing and prediction engine...
"%PYTHON%" src\verify_preprocessing_prediction_engine.py
if errorlevel 1 goto error

echo.
echo [8/13] Running local MQTT mock field bridge...
"%PYTHON%" src\mock_field_bridge.py --protocol mqtt_mock --rows 2 --create-drafts --decision needs_review
if errorlevel 1 goto error

echo.
echo [9/13] Evaluating workflow traceability...
"%PYTHON%" src\evaluate_workflow_traceability.py
if errorlevel 1 goto error

echo.
echo [10/13] Creating product comparison and thesis evidence pack...
"%PYTHON%" src\create_product_comparison_summary.py
if errorlevel 1 goto error

echo.
echo [11/13] Regenerating presentation and Stage 19-20 design documents...
"%PYTHON%" src\create_presentation_summary.py
if errorlevel 1 goto error

echo.
echo [12/13] Verifying Stage 19-20 operations design document...
"%PYTHON%" src\verify_stage19_20_design.py
if errorlevel 1 goto error

echo.
echo [13/13] Verifying project files and outputs through Stage 20 local integration...
"%PYTHON%" src\verify_project.py
if errorlevel 1 goto error

echo.
echo Verification passed through Stage 20 local integration, thesis evidence, and smart CSV prediction outputs.
pause
exit /b 0

:error
echo.
echo Verification failed. Please read the error message above.
pause
exit /b 1
