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

Write-Host "This script does not save your OpenAI API key to any file." -ForegroundColor Cyan
Write-Host "Paste a newly rotated key. Input is hidden and only used for this PowerShell process."
$secureKey = Read-Host "OPENAI_API_KEY" -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)

try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        throw "OPENAI_API_KEY was empty."
    }

    $env:OPENAI_API_KEY = $plainKey
    $env:AI_REPORT_PROVIDER = "openai"
    if ([string]::IsNullOrWhiteSpace($env:OPENAI_MODEL)) {
        $env:OPENAI_MODEL = "gpt-5-mini"
    }

    Write-Host "[1/4] Creating Predictive SPC and AI report outputs..."
    & $pythonPath src\predictive_spc.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host ""
    Write-Host "[2/4] Creating future deviation prediction outputs..."
    & $pythonPath src\future_deviation.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host ""
    Write-Host "[3/4] Regenerating presentation documents..."
    & $pythonPath src\create_presentation_summary.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host ""
    Write-Host "[4/4] Verifying project outputs..."
    & $pythonPath src\verify_project.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host ""
    Write-Host "Done. Check outputs\ai_report_context.json for report_generation_mode." -ForegroundColor Green
}
finally {
    if ($keyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
    Remove-Item Env:\OPENAI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\AI_REPORT_PROVIDER -ErrorAction SilentlyContinue
}
