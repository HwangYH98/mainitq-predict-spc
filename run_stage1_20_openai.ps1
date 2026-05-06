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

Write-Host "This script does not save your OpenAI API key to any file." -ForegroundColor Cyan
Write-Host "Paste a newly rotated key. Input is hidden and only used for this PowerShell process."
$secureKey = Read-Host "OPENAI_API_KEY" -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)

try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        throw "OPENAI_API_KEY was empty."
    }

    if ([string]::IsNullOrWhiteSpace($env:OPENAI_MODEL)) {
        $env:OPENAI_MODEL = "gpt-5-mini"
    }

    $env:AI_REPORT_PROVIDER = "openai"
    $env:OPENAI_API_KEY = $plainKey
    $env:REQUIRE_GENAI_REPORT = "1"
    $env:REQUIRE_OPENAI_REPORT = "1"
    Invoke-Stage "[0/13] OpenAI Responses API preflight..." @("src\check_openai_connection.py")

    Invoke-Stage "[1/13] Stage 1~3 baseline training..." @("src\train_baseline.py")
    Invoke-Stage "[2/13] Stage 4 threshold tuning and SHAP..." @("src\stage4_explain.py")

    # First pass creates SPC CSV/charts needed by the future-deviation step.
    # It intentionally allows fallback so the required OpenAI report is made
    # only once after the future-deviation context exists.
    Remove-Item Env:\OPENAI_API_KEY -ErrorAction SilentlyContinue
    $env:REQUIRE_GENAI_REPORT = "0"
    $env:REQUIRE_OPENAI_REPORT = "0"
    Invoke-Stage "[3/13] Stage 11 SPC context and charts..." @("src\predictive_spc.py")

    Invoke-Stage "[4/13] Stage 13 future deviation prediction..." @("src\future_deviation.py")

    $env:OPENAI_API_KEY = $plainKey
    $env:REQUIRE_GENAI_REPORT = "1"
    $env:REQUIRE_OPENAI_REPORT = "1"
    Invoke-Stage "[5/13] Stage 12 required OpenAI manager report..." @("src\predictive_spc.py")

    Invoke-Stage "[6/13] Stage 14 company CSV retraining PoC..." @("src\verify_company_generalization.py")
    Invoke-Stage "[7/13] Stage 15~18 local operations PoC..." @("src\verify_stage15_20.py")
    Invoke-Stage "[8/17] Stage 19~20 local field-event and decision integration..." @("src\verify_stage19_20_integration.py")
    Invoke-Stage "[9/17] SMOTE and threshold model strategy comparison..." @("src\compare_model_strategies.py")
    Invoke-Stage "[10/17] SPC-only vs ML+SPC alert comparison..." @("src\compare_spc_ml_alerts.py")
    Invoke-Stage "[11/17] Operational value simulation..." @("src\evaluate_operational_value.py")
    Invoke-Stage "[12/17] Smart CSV preprocessing and prediction engine..." @("src\verify_preprocessing_prediction_engine.py")
    Invoke-Stage "[13/17] MQTT local mock field bridge..." @("src\mock_field_bridge.py", "--protocol", "mqtt_mock", "--rows", "2", "--create-drafts", "--decision", "needs_review")
    Invoke-Stage "[14/17] Workflow traceability evaluation..." @("src\evaluate_workflow_traceability.py")
    Invoke-Stage "[15/17] Product comparison and thesis evidence pack..." @("src\create_product_comparison_summary.py")
    Invoke-Stage "[16/17] Regenerating presentation and roadmap documents..." @("src\create_presentation_summary.py")
    Invoke-Stage "[17/17] Full Stage 1~20 project verification..." @("src\verify_project.py")

    Write-Host ""
    Write-Host "Stage 1~20 local integration PoC passed with required OpenAI report." -ForegroundColor Green
}
finally {
    if ($keyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
    Remove-Item Env:\OPENAI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\REQUIRE_GENAI_REPORT -ErrorAction SilentlyContinue
    Remove-Item Env:\REQUIRE_OPENAI_REPORT -ErrorAction SilentlyContinue
    Remove-Item Env:\AI_REPORT_PROVIDER -ErrorAction SilentlyContinue
}
