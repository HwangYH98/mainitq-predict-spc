@echo off
chcp 65001 >nul
setlocal

REM Move to the folder where this .bat file is located.
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

"%PYTHON%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo PyInstaller is not installed. Installing into the local .venv...
    "%PYTHON%" -m pip install pyinstaller
    if errorlevel 1 goto error
)

if not exist "tools\windows_launcher.py" (
    echo Missing launcher source: tools\windows_launcher.py
    exit /b 1
)

echo Building Windows launcher EXE...
"%PYTHON%" -m PyInstaller ^
    --onefile ^
    --console ^
    --name "AI_predictive_maintenance_dashboard" ^
    tools\windows_launcher.py
if errorlevel 1 goto error

"%PYTHON%" -c "from pathlib import Path; src=Path('dist')/'AI_predictive_maintenance_dashboard.exe'; dst=Path('dist')/('AI_'+'\uc608\uc9c0\ubcf4\uc804_'+'\ub300\uc2dc\ubcf4\ub4dc.exe'); dst.write_bytes(src.read_bytes()); print(dst)"
if errorlevel 1 goto error

echo.
echo Build finished:
echo   dist\AI_[Korean-name]_dashboard.exe
echo   dist\AI_predictive_maintenance_dashboard.exe
echo.
echo This EXE is a launcher. Run it from this project folder so it can use .venv, app, data, and outputs.
exit /b 0

:error
echo.
echo Build failed. Please read the error message above.
exit /b 1
