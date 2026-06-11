@echo off
chcp 65001 >nul
setlocal
setlocal EnableDelayedExpansion

REM Official local Streamlit operator dashboard runner.
REM Streamlit is a local web server, so this script starts the server and opens the browser.
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    echo Virtual environment was not found.
    echo Please run:
    echo   py -3 -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

if not defined STREAMLIT_PORT (
    set "STREAMLIT_PORT=8501"
)

if not defined APP_OPERATOR_PASSWORD (
    for /f "delims=" %%P in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N').Substring(0, 10)"') do set "APP_OPERATOR_PASSWORD=%%P"
    powershell -NoProfile -Command "Set-Clipboard -Value '!APP_OPERATOR_PASSWORD!'" >nul 2>nul
    echo.
    echo A temporary operator login password was created for this session.
    echo It was copied to your clipboard and is not written to any file.
    echo Login ID: operator_01
    echo Password: !APP_OPERATOR_PASSWORD!
    echo.
)

set "STREAMLIT_URL=http://127.0.0.1:%STREAMLIT_PORT%"
echo Starting MaintiQ Streamlit Dashboard on %STREAMLIT_URL% ...
powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process '%STREAMLIT_URL%'" >nul 2>nul
"%PYTHON%" -m streamlit run streamlit_app.py --server.port %STREAMLIT_PORT% --server.headless true --browser.gatherUsageStats false
if errorlevel 1 goto error
exit /b 0

:error
echo.
echo Streamlit dashboard failed. Please read the error message above.
echo If Streamlit is missing, run:
echo   "%PYTHON%" -m pip install -r requirements.txt
pause
exit /b 1
