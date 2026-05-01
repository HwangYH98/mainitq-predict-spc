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
Write-Host "Paste a newly rotated key. Input is hidden and only used while Streamlit is running."
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

    Write-Host "Starting Streamlit dashboard with OpenAI API enabled..."
    Write-Host "Open http://127.0.0.1:8501 after the server starts."
    & $pythonPath -m streamlit run app\dashboard.py --server.headless true --browser.gatherUsageStats false
}
finally {
    if ($keyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
    Remove-Item Env:\OPENAI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\AI_REPORT_PROVIDER -ErrorAction SilentlyContinue
}
