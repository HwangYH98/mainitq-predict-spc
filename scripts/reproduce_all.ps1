param(
    [string]$RunId = "",
    [int]$Repeats = 5,
    [int]$Folds = 5,
    [int]$BootstrapIterations = 2000,
    [int]$RandomState = 20260612
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = "all-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
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

& (Join-Path $PSScriptRoot "reproduce_quick.ps1") -RunId $RunId
if ($LASTEXITCODE -ne 0) {
    throw "reproduce_quick.ps1 failed."
}

Invoke-Step "robust_validation" @(
    $Python,
    "src\robust_validation.py",
    "--run-id",
    $RunId,
    "--repeats",
    "$Repeats",
    "--folds",
    "$Folds",
    "--bootstrap-iterations",
    "$BootstrapIterations",
    "--random-state",
    "$RandomState"
)

$OptionalStatus = [ordered]@{
    scope = "Optional workstreams intentionally skipped in first implementation pass."
    metropt3_time_axis_spc = @{ status = "SKIPPED"; reason = "Out of scope for first implementation pass." }
    genai_multi_case_evaluation = @{ status = "SKIPPED"; reason = "Requires API key and separate approved workstream." }
    scania_constraint_pareto = @{ status = "SKIPPED"; reason = "Out of scope for first implementation pass." }
    field_shadow_mode = @{ status = "SKIPPED"; reason = "Requires real company data and approval." }
    literature_matrix = @{ status = "SKIPPED"; reason = "Manuscript work is excluded from this code PR." }
}
$OptionalStatusPath = Join-Path $RunDir "optional_workstreams_status.json"
($OptionalStatus | ConvertTo-Json -Depth 6) | Set-Content -Path $OptionalStatusPath -Encoding UTF8
Write-CommandLog -Name "optional_workstreams_status" -Command @("write", $OptionalStatusPath) -ExitCode 0

Invoke-Step "verify_reproduction_bundle_full" @($Python, "src\verify_reproduction_bundle.py", $RunDir, "--require-robust")

Write-Host "Full reproduction run completed."
Write-Host "RUN_ID=$RunId"
Write-Host "RUN_DIR=$RunDir"
