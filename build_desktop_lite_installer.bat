@echo off
chcp 65001 >nul
setlocal

REM Package the MaintiQ Predict Lite app folder with Inno Setup.
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    echo Virtual environment was not found.
    echo Please create .venv and install requirements first.
    exit /b 1
)

"%PYTHON%" tools\check_lite_distribution.py dist\MaintiQ_Predict_Lite >nul 2>nul
if errorlevel 1 (
    echo Lite portable app folder is missing or contains forbidden runtime files.
    echo Building it first...
    call build_desktop_lite_app.bat
    if errorlevel 1 goto error
) else (
    echo Existing Lite portable app passed validation:
    echo   dist\MaintiQ_Predict_Lite\MaintiQ_Predict_Lite.exe
)

"%PYTHON%" tools\check_lite_distribution.py dist\MaintiQ_Predict_Lite
if errorlevel 1 goto error

echo Checking release readiness metadata...
"%PYTHON%" tools\check_release_readiness.py
if errorlevel 1 goto error

set "ISCC="
where iscc >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('where iscc') do (
        if not defined ISCC set "ISCC=%%I"
    )
)

if not defined ISCC (
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)
if not defined ISCC (
    if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)
if not defined ISCC (
    if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
)

if not defined ISCC (
    echo.
    echo Inno Setup was not found, so the Lite installer EXE could not be created.
    echo Install Inno Setup 6 on the development PC, then run this file again:
    echo   winget install --id JRSoftware.InnoSetup -e
    echo.
    echo The Lite portable app folder is still ready here:
    echo   dist\MaintiQ_Predict_Lite\MaintiQ_Predict_Lite.exe
    exit /b 2
)

if not exist "installer\MaintiQ_Predict_Lite.iss" (
    echo Missing installer script: installer\MaintiQ_Predict_Lite.iss
    exit /b 1
)

if not exist "release" mkdir release

echo Building MaintiQ Predict Lite installer...
"%ISCC%" "installer\MaintiQ_Predict_Lite.iss"
if errorlevel 1 goto error

"%PYTHON%" tools\check_lite_distribution.py dist\MaintiQ_Predict_Lite
if errorlevel 1 goto error

echo.
echo Lite installer build finished:
echo   release\MaintiQ_Predict_Lite_Setup.exe
"%PYTHON%" tools\create_release_checksums.py
if "%MAINTIQ_SIGN_CERT_SHA1%"=="" (
    echo.
    echo Signing certificate was not configured. Lite installer is unsigned.
    echo To sign release installers later:
    echo   set MAINTIQ_SIGN_CERT_SHA1=your-certificate-thumbprint
    echo   sign_windows_release.bat
)
exit /b 0

:error
echo.
echo MaintiQ Predict Lite installer build failed. Please read the error above.
exit /b 1
