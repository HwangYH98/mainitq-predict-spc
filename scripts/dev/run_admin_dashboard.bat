@echo off
setlocal

REM Move to the project root.
REM This makes the script work even if PowerShell starts in C:\WINDOWS\system32.
cd /d "%~dp0..\.."

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    echo Virtual environment was not found.
    echo Please run these setup commands from this folder:
    echo   py -3 -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

"%PYTHON%" --version >nul 2>nul
if errorlevel 1 (
    echo The virtual environment exists, but Python did not run correctly.
    echo Please recreate it with:
    echo   py -3 -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

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

echo Starting research validation Admin Console on http://127.0.0.1:8502 ...
"%PYTHON%" -m streamlit run app\admin_dashboard.py --server.port 8502 --server.headless true --browser.gatherUsageStats false
if errorlevel 1 goto error

exit /b 0

:error
echo.
echo Something failed. Please read the error message above.
echo If Streamlit is missing, run:
echo   "%PYTHON%" -m pip install -r requirements.txt
pause
exit /b 1
