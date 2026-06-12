param(
    [string]$RunId = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = "quick-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
}

$RunDir = Join-Path $ProjectRoot "outputs\experiments\$RunId"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = "python"
}

function Write-CommandLog {
    param(
        [string]$Name,
        [string[]]$Command,
        [int]$ExitCode
    )
    if (-not (Test-Path $RunDir)) {
        return
    }
    $Record = [ordered]@{
        timestamp_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        phase = $Name
        command = $Command
        cwd = $ProjectRoot
        exit_code = $ExitCode
    }
    $LogPath = Join-Path $RunDir "command_log.txt"
    ($Record | ConvertTo-Json -Compress -Depth 6) | Add-Content -Path $LogPath -Encoding UTF8
}

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$Command
    )
    Write-Host "[$Name] $($Command -join ' ')"
    $Exe = $Command[0]
    $Args = @()
    if ($Command.Count -gt 1) {
        $Args = $Command[1..($Command.Count - 1)]
    }
    & $Exe @Args
    $ExitCode = $LASTEXITCODE
    if ($null -eq $ExitCode) {
        $ExitCode = 0
    }
    Write-CommandLog -Name $Name -Command $Command -ExitCode $ExitCode
    if ($ExitCode -ne 0) {
        throw "Step failed: $Name (exit code $ExitCode)"
    }
}

Invoke-Step "freeze_baseline" @($Python, "src\freeze_baseline.py", "--run-id", $RunId)
Invoke-Step "compileall" @($Python, "-m", "compileall", "-q", "src", "app", "desktop_app", "tools", "streamlit_app.py")
Invoke-Step "pytest_core" @(
    $Python,
    "-m",
    "pytest",
    "-q",
    "tests\test_thesis_methodology_validation.py",
    "tests\test_experiment_run.py",
    "tests\test_data_integrity.py",
    "tests\test_evaluation_metrics.py",
    "tests\test_bootstrap_intervals.py",
    "tests\test_robust_validation.py"
)
Invoke-Step "desktop_check" @($Python, "desktop_app\main.py", "--check")
Invoke-Step "desktop_engine_smoke" @($Python, "desktop_app\main.py", "--engine-smoke-test")
Invoke-Step "verify_reproduction_bundle" @($Python, "src\verify_reproduction_bundle.py", $RunDir)

Write-Host "Reproduction quick run completed."
Write-Host "RUN_ID=$RunId"
Write-Host "RUN_DIR=$RunDir"
