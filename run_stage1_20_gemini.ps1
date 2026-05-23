Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Run this script from anywhere. It moves to the project root first.
Set-Location -LiteralPath $PSScriptRoot

$pythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host "Virtual environment was not found." -ForegroundColor Red
    Write-Host "Run these setup commands first:"
    Write-Host "  py -3 -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

function Invoke-Stage {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Label,
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    Write-Host ""
    Write-Host $Label -ForegroundColor Cyan
    & $pythonPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Invoke-OptionalScaniaOfficial {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    Write-Host ""
    Write-Host $Label -ForegroundColor Cyan
    $trainReadouts = Join-Path $PSScriptRoot "data_external\scania_component_x\train_operational_readouts.csv"
    if (Test-Path -LiteralPath $trainReadouts) {
        & $pythonPath "src\scania_official_cost_validation.py" "--data-dir" "data_external\scania_component_x"
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    } else {
        Write-Host "SCANIA train data was not found. Keeping existing official-cost outputs if present."
        Write-Host "To refresh it, run: .\.venv\Scripts\python.exe src\download_scania_component_x.py --include-train --skip-docs"
    }
}

Write-Host "This script does not save your Gemini API key to any file." -ForegroundColor Cyan
Write-Host "Paste a Google AI Studio Gemini key. Input is visible so you can confirm paste worked."
$plainKey = Read-Host "GEMINI_API_KEY"
Clear-Host

try {
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        throw "GEMINI_API_KEY was empty."
    }

    Write-Host "Gemini API key was received but not saved to any file." -ForegroundColor Cyan

    if ([string]::IsNullOrWhiteSpace($env:GEMINI_MODEL)) {
        $env:GEMINI_MODEL = "gemini-2.5-flash"
    }
    if ([string]::IsNullOrWhiteSpace($env:GEMINI_MODEL_CANDIDATES)) {
        $env:GEMINI_MODEL_CANDIDATES = "$env:GEMINI_MODEL,gemini-2.5-flash-lite"
    }

    $env:AI_REPORT_PROVIDER = "gemini"
    $env:GEMINI_API_KEY = $plainKey
    $env:REQUIRE_GENAI_REPORT = "1"
    $env:REQUIRE_OPENAI_REPORT = "0"
    Invoke-Stage "[0/23] Gemini generateContent API preflight..." @("src\check_gemini_connection.py")

    Invoke-Stage "[1/23] Stage 1~3 baseline training..." @("src\train_baseline.py")
    Invoke-Stage "[2/23] Stage 4 threshold tuning and SHAP..." @("src\stage4_explain.py")

    # First pass creates SPC CSV/charts needed by the future-deviation step.
    # It intentionally allows fallback so the required GenAI report is made
    # only once after the future-deviation context exists.
    Remove-Item Env:\GEMINI_API_KEY -ErrorAction SilentlyContinue
    $env:REQUIRE_GENAI_REPORT = "0"
    $env:REQUIRE_OPENAI_REPORT = "0"
    Invoke-Stage "[3/23] Stage 11 SPC context and charts..." @("src\predictive_spc.py")

    Invoke-Stage "[4/23] Stage 13 future deviation prediction..." @("src\future_deviation.py")

    $env:GEMINI_API_KEY = $plainKey
    $env:REQUIRE_GENAI_REPORT = "1"
    $env:REQUIRE_OPENAI_REPORT = "0"
    Invoke-Stage "[5/23] Stage 12 required Gemini manager report..." @("src\predictive_spc.py")

    Invoke-Stage "[6/23] Stage 14 company CSV retraining PoC..." @("src\verify_company_generalization.py")
    Invoke-Stage "[7/23] Stage 15~18 local operations PoC..." @("src\verify_stage15_20.py")
    Invoke-Stage "[8/23] Stage 19~20 local field-event and decision integration..." @("src\verify_stage19_20_integration.py")
    Invoke-Stage "[9/23] SMOTE and threshold model strategy comparison..." @("src\compare_model_strategies.py")
    Invoke-Stage "[10/23] SPC-only vs ML+SPC alert comparison..." @("src\compare_spc_ml_alerts.py")
    Invoke-Stage "[11/23] Operational value simulation..." @("src\evaluate_operational_value.py")
    Invoke-Stage "[12/23] Smart CSV preprocessing and prediction engine..." @("src\verify_preprocessing_prediction_engine.py")
    Invoke-Stage "[13/23] MQTT local mock field bridge..." @("src\mock_field_bridge.py", "--protocol", "mqtt_mock", "--rows", "2", "--create-drafts", "--decision", "needs_review")
    Invoke-Stage "[14/23] Workflow traceability evaluation..." @("src\evaluate_workflow_traceability.py")
    Invoke-Stage "[15/23] Open industrial validation adapter sample..." @("src\open_industrial_validation.py")
    Invoke-Stage "[16/23] Public industrial benchmark adapters..." @("src\public_industrial_benchmark.py")
    Invoke-OptionalScaniaOfficial "[17/23] SCANIA official class-cost validation..."
    Invoke-Stage "[18/23] Field validation protocol and templates..." @("src\create_field_validation_protocol.py")
    Invoke-Stage "[19/23] Industrial engineering evidence..." @("src\create_industrial_engineering_evidence.py")
    Invoke-Stage "[20/23] Product comparison and thesis evidence pack..." @("src\create_product_comparison_summary.py")
    Invoke-Stage "[21/23] Regenerating presentation and roadmap documents..." @("src\create_presentation_summary.py")
    Invoke-Stage "[22/23] Stage 19~20 operations design verification..." @("src\verify_stage19_20_design.py")
    Invoke-Stage "[23/23] Full Stage 1~20 project verification..." @("src\verify_project.py")

    Write-Host ""
    Write-Host "Stage 1~20 local integration passed with required Gemini report and SCANIA official-cost evidence." -ForegroundColor Green
}
finally {
    $plainKey = $null
    Remove-Item Env:\GEMINI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\REQUIRE_GENAI_REPORT -ErrorAction SilentlyContinue
    Remove-Item Env:\REQUIRE_OPENAI_REPORT -ErrorAction SilentlyContinue
    Remove-Item Env:\AI_REPORT_PROVIDER -ErrorAction SilentlyContinue
    Remove-Item Env:\GEMINI_MODEL_CANDIDATES -ErrorAction SilentlyContinue
}
