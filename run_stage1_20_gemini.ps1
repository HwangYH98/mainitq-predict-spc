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
    Invoke-Stage "[0/10] Gemini generateContent API preflight..." @("src\check_gemini_connection.py")

    Invoke-Stage "[1/10] Stage 1~3 baseline training..." @("src\train_baseline.py")
    Invoke-Stage "[2/10] Stage 4 threshold tuning and SHAP..." @("src\stage4_explain.py")

    # First pass creates SPC CSV/charts needed by the future-deviation step.
    # It intentionally allows fallback so the required GenAI report is made
    # only once after the future-deviation context exists.
    Remove-Item Env:\GEMINI_API_KEY -ErrorAction SilentlyContinue
    $env:REQUIRE_GENAI_REPORT = "0"
    $env:REQUIRE_OPENAI_REPORT = "0"
    Invoke-Stage "[3/10] Stage 11 SPC context and charts..." @("src\predictive_spc.py")

    Invoke-Stage "[4/10] Stage 13 future deviation prediction..." @("src\future_deviation.py")

    $env:GEMINI_API_KEY = $plainKey
    $env:REQUIRE_GENAI_REPORT = "1"
    $env:REQUIRE_OPENAI_REPORT = "0"
    Invoke-Stage "[5/10] Stage 12 required Gemini manager report..." @("src\predictive_spc.py")

    Invoke-Stage "[6/10] Stage 14 company CSV retraining PoC..." @("src\verify_company_generalization.py")
    Invoke-Stage "[7/10] Stage 15~18 local operations PoC..." @("src\verify_stage15_20.py")
    Invoke-Stage "[8/10] Stage 19~20 local field-event and decision integration..." @("src\verify_stage19_20_integration.py")
    Invoke-Stage "[9/10] Regenerating presentation and roadmap documents..." @("src\create_presentation_summary.py")
    Invoke-Stage "[10/10] Full Stage 1~20 project verification..." @("src\verify_project.py")

    Write-Host ""
    Write-Host "Stage 1~20 local integration PoC passed with required Gemini report." -ForegroundColor Green
}
finally {
    $plainKey = $null
    Remove-Item Env:\GEMINI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\REQUIRE_GENAI_REPORT -ErrorAction SilentlyContinue
    Remove-Item Env:\REQUIRE_OPENAI_REPORT -ErrorAction SilentlyContinue
    Remove-Item Env:\AI_REPORT_PROVIDER -ErrorAction SilentlyContinue
    Remove-Item Env:\GEMINI_MODEL_CANDIDATES -ErrorAction SilentlyContinue
}
