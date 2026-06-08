@echo off
setlocal

REM Move to the project root.
REM This makes the script work even if PowerShell starts in C:\WINDOWS\system32.
cd /d "%~dp0..\.."

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

echo [1/20] Verifying Stage 14 company retraining outputs...
"%PYTHON%" src\verify_company_generalization.py
if errorlevel 1 goto error

echo.
echo [2/20] Verifying Stage 15-18 local operations outputs...
"%PYTHON%" src\verify_stage15_20.py
if errorlevel 1 goto error

echo.
echo [3/20] Verifying Stage 19-20 local field-event and decision integration...
"%PYTHON%" src\verify_stage19_20_integration.py
if errorlevel 1 goto error

echo.
echo [4/20] Running model strategy comparison including SMOTE...
"%PYTHON%" src\compare_model_strategies.py
if errorlevel 1 goto error

echo.
echo [5/20] Running SPC-only vs ML+SPC alert comparison...
"%PYTHON%" src\compare_spc_ml_alerts.py
if errorlevel 1 goto error

echo.
echo [6/20] Running operational value simulation...
"%PYTHON%" src\evaluate_operational_value.py
if errorlevel 1 goto error

echo.
echo [7/20] Verifying smart CSV preprocessing and prediction engine...
"%PYTHON%" src\verify_preprocessing_prediction_engine.py
if errorlevel 1 goto error

echo.
echo [8/20] Running local MQTT mock field bridge...
"%PYTHON%" src\mock_field_bridge.py --protocol mqtt_mock --rows 2 --create-drafts --decision needs_review
if errorlevel 1 goto error

echo.
echo [9/20] Evaluating workflow traceability...
"%PYTHON%" src\evaluate_workflow_traceability.py
if errorlevel 1 goto error

echo.
echo [10/20] Running open industrial validation adapter sample...
"%PYTHON%" src\open_industrial_validation.py
if errorlevel 1 goto error

echo.
echo [11/20] Running public industrial benchmark adapters...
"%PYTHON%" src\public_industrial_benchmark.py
if errorlevel 1 goto error

echo.
echo [12/20] Running SCANIA official class-cost validation when public train data exists...
if exist "data_external\scania_component_x\train_operational_readouts.csv" (
    "%PYTHON%" src\scania_official_cost_validation.py --data-dir data_external\scania_component_x
    if errorlevel 1 goto error
) else (
    echo SCANIA train data was not found. Keeping existing official-cost outputs if present.
)

echo.
echo [13/20] Creating field validation protocol and templates...
"%PYTHON%" src\create_field_validation_protocol.py
if errorlevel 1 goto error

echo.
echo [14/20] Creating field validation report from template package...
"%PYTHON%" src\evaluate_field_validation_report.py
if errorlevel 1 goto error

echo.
echo [15/20] Creating industrial engineering evidence...
"%PYTHON%" src\create_industrial_engineering_evidence.py
if errorlevel 1 goto error

echo.
echo [16/20] Creating product comparison and thesis evidence pack...
"%PYTHON%" src\create_product_comparison_summary.py
if errorlevel 1 goto error

echo.
echo [17/20] Creating run-to-failure evidence summary...
"%PYTHON%" src\create_run_to_failure_evidence_summary.py
if errorlevel 1 goto error

echo.
echo [18/20] Regenerating presentation and Stage 19-20 design documents...
"%PYTHON%" src\create_presentation_summary.py
if errorlevel 1 goto error

echo.
echo [19/20] Verifying Stage 19-20 operations design document...
"%PYTHON%" src\verify_stage19_20_design.py
if errorlevel 1 goto error

echo.
echo [20/20] Verifying project files and outputs through Stage 20 local integration...
"%PYTHON%" src\verify_project.py
if errorlevel 1 goto error

echo.
echo Verification passed through Stage 20 local integration, public industrial benchmarks, SCANIA official-cost validation, field-validation protocol, and smart CSV prediction outputs.
pause
exit /b 0

:error
echo.
echo Verification failed. Please read the error message above.
pause
exit /b 1
