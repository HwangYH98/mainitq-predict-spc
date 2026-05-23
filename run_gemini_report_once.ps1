param(
    [string]$Model = "gemini-2.5-flash"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment was not found." -ForegroundColor Red
    Write-Host "Run: py -3 -m venv .venv"
    Write-Host "Run: .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

Write-Host ""
Write-Host "Gemini key is used only in this PowerShell process." -ForegroundColor Cyan
Write-Host "Do not use a key that was pasted into chat or screenshots." -ForegroundColor Yellow
Write-Host "Rotate exposed keys first in Google AI Studio or Google Cloud Console." -ForegroundColor Yellow
Write-Host ""

$key = Read-Host "Enter NEW GEMINI_API_KEY"
if ([string]::IsNullOrWhiteSpace($key)) {
    Write-Host "GEMINI_API_KEY was empty." -ForegroundColor Red
    exit 1
}

try {
    $env:GEMINI_API_KEY = $key
    $env:AI_REPORT_PROVIDER = "gemini"
    $env:GEMINI_MODEL = $Model
    $env:REQUIRE_GENAI_REPORT = "1"

    Write-Host ""
    Write-Host "[1/2] Gemini preflight..." -ForegroundColor Cyan
    .\.venv\Scripts\python.exe src\check_gemini_connection.py

    Write-Host ""
    Write-Host "[2/2] Required Gemini AI manager report..." -ForegroundColor Cyan
    .\.venv\Scripts\python.exe src\predictive_spc.py

    Write-Host ""
    Write-Host "Done. Check outputs\ai_report_context.json and outputs\ai_manager_report.md." -ForegroundColor Green
} finally {
    Remove-Item Env:\GEMINI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\AI_REPORT_PROVIDER -ErrorAction SilentlyContinue
    Remove-Item Env:\GEMINI_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:\REQUIRE_GENAI_REPORT -ErrorAction SilentlyContinue
}
