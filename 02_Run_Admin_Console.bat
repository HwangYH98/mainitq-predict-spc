@echo off
chcp 65001 >nul
setlocal

REM Official local Admin console runner.
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    echo Virtual environment was not found.
    echo Please run these commands from this folder:
    echo   py -3 -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
    pause
    exit /b 1
)

if not defined ADMIN_CONSOLE_PORT (
    set "ADMIN_CONSOLE_PORT=8502"
)
set "ADMIN_CONSOLE_URL=http://127.0.0.1:%ADMIN_CONSOLE_PORT%"

if not defined APP_ADMIN_PASSWORD (
    echo.
    echo Admin console password is not set for this window.
    echo The password you type here is used only for this app session.
    echo It is not written to any file, .env, Git, or README.
    echo.
    set /p "APP_ADMIN_PASSWORD=Enter admin console password: "
    powershell -NoProfile -Command "if ([string]::IsNullOrWhiteSpace($env:APP_ADMIN_PASSWORD)) { exit 1 } else { exit 0 }" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo APP_ADMIN_PASSWORD was empty. Admin console was not started.
        exit /b 1
    )
    cls
    echo Admin console password was received for this session only.
)

echo.
echo Starting MaintiQ Admin Console
echo URL: %ADMIN_CONSOLE_URL%
echo Login ID: admin
echo Password: the APP_ADMIN_PASSWORD value for this session
echo.
echo If the browser does not open, paste the URL above into your browser.
powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process '%ADMIN_CONSOLE_URL%'" >nul 2>nul
"%PYTHON%" -m streamlit run app\admin_dashboard.py --server.port %ADMIN_CONSOLE_PORT% --server.headless true --browser.gatherUsageStats false
if errorlevel 1 goto error
exit /b 0

:error
echo.
echo Admin console failed. Please read the error message above.
echo Common fixes:
echo   1. Close any existing app using port %ADMIN_CONSOLE_PORT%, or set ADMIN_CONSOLE_PORT to another value.
echo   2. Install dependencies:
echo      "%PYTHON%" -m pip install -r requirements-lock.txt
pause
exit /b 1
