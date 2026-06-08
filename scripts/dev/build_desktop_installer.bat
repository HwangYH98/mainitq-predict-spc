@echo off
chcp 65001 >nul
setlocal

REM Package the portable app folder with Inno Setup from the project root.
cd /d "%~dp0..\.."

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    echo Virtual environment was not found.
    echo Please run 03_Build_User_Installer.bat from the project root after creating .venv.
    exit /b 1
)

echo Building the current Full portable app folder first...
call "%~dp0build_desktop_app.bat"
if errorlevel 1 goto error

"%PYTHON%" tools\validate_desktop_distribution.py dist\MaintiQ_Predict
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
    if exist "tools\inno_setup_6\ISCC.exe" set "ISCC=tools\inno_setup_6\ISCC.exe"
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
    echo Inno Setup was not found, so the installer EXE could not be created.
    echo Install Inno Setup 6 on the development PC, then run this file again:
    echo   winget install --id JRSoftware.InnoSetup -e
    echo.
    echo The portable app folder is still ready here:
    echo   dist\MaintiQ_Predict\MaintiQ_Predict.exe
    exit /b 2
)

if not exist "installer\MaintiQ_Predict.iss" (
    echo Missing installer script: installer\MaintiQ_Predict.iss
    exit /b 1
)

if not exist "release" mkdir release

echo Building MaintiQ Predict installer...
"%ISCC%" "installer\MaintiQ_Predict.iss"
if errorlevel 1 goto error

echo.
echo Installer build finished:
echo   release\MaintiQ_Predict_Setup.exe
"%PYTHON%" tools\create_release_checksums.py >nul 2>nul
if "%MAINTIQ_SIGN_CERT_SHA1%"=="" (
    echo.
    echo Signing certificate was not configured. Installer is unsigned.
    echo To sign release installers later:
    echo   set MAINTIQ_SIGN_CERT_SHA1=your-certificate-thumbprint
    echo   scripts\dev\local\sign_windows_release.bat
)
exit /b 0

:error
echo.
echo MaintiQ Predict installer build failed. Please read the error above.
exit /b 1
