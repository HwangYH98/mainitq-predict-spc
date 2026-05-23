@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

if "%MAINTIQ_SIGN_CERT_SHA1%"=="" if "%MAINTIQ_SIGN_PFX%"=="" (
    echo No signing certificate was configured.
    echo Set MAINTIQ_SIGN_CERT_SHA1 for a certificate installed in the Windows certificate store.
    echo Or set MAINTIQ_SIGN_PFX and optionally MAINTIQ_SIGN_PFX_PASSWORD for a PFX file.
    echo Skipping Authenticode signing. Unsigned installers may trigger Windows SmartScreen warnings.
    exit /b 0
)

set "SIGNTOOL="
where signtool >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('where signtool') do (
        if not defined SIGNTOOL set "SIGNTOOL=%%I"
    )
)

if not defined SIGNTOOL (
    for /r "%ProgramFiles(x86)%\Windows Kits" %%I in (signtool.exe) do (
        if not defined SIGNTOOL set "SIGNTOOL=%%I"
    )
)

if not defined SIGNTOOL (
    echo signtool.exe was not found. Install Windows SDK or add signtool to PATH.
    exit /b 1
)

if not exist "release\MaintiQ_Predict_Setup.exe" (
    echo Missing release\MaintiQ_Predict_Setup.exe
    exit /b 1
)

if not exist "release\MaintiQ_Predict_Lite_Setup.exe" (
    echo Missing release\MaintiQ_Predict_Lite_Setup.exe
    exit /b 1
)

echo Signing MaintiQ Predict installers...
call :sign_file "release\MaintiQ_Predict_Setup.exe"
if errorlevel 1 exit /b 1

call :sign_file "release\MaintiQ_Predict_Lite_Setup.exe"
if errorlevel 1 exit /b 1

echo Signature verification:
"%SIGNTOOL%" verify /pa /v "release\MaintiQ_Predict_Setup.exe"
if errorlevel 1 exit /b 1
"%SIGNTOOL%" verify /pa /v "release\MaintiQ_Predict_Lite_Setup.exe"
if errorlevel 1 exit /b 1

echo Signing finished.
exit /b 0

:sign_file
set "TARGET_FILE=%~1"
if not "%MAINTIQ_SIGN_PFX%"=="" (
    if not exist "%MAINTIQ_SIGN_PFX%" (
        echo MAINTIQ_SIGN_PFX was set but the file was not found:
        echo %MAINTIQ_SIGN_PFX%
        exit /b 1
    )
    if not "%MAINTIQ_SIGN_PFX_PASSWORD%"=="" (
        "%SIGNTOOL%" sign /f "%MAINTIQ_SIGN_PFX%" /p "%MAINTIQ_SIGN_PFX_PASSWORD%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "%TARGET_FILE%"
    ) else (
        "%SIGNTOOL%" sign /f "%MAINTIQ_SIGN_PFX%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "%TARGET_FILE%"
    )
) else (
    "%SIGNTOOL%" sign /sha1 "%MAINTIQ_SIGN_CERT_SHA1%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "%TARGET_FILE%"
)
exit /b %ERRORLEVEL%
