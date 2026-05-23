@echo off
chcp 65001 >nul
setlocal

REM Build the lightweight MaintiQ Predict desktop app folder.
cd /d "%~dp0"
set "MAINTIQ_RUNTIME_PROFILE=lite"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    echo Virtual environment was not found.
    echo Please run:
    echo   py -3 -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)

"%PYTHON%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo PySide6 is not installed. Installing into the local .venv...
    "%PYTHON%" -m pip install PySide6
    if errorlevel 1 goto error
)

"%PYTHON%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo PyInstaller is not installed. Installing into the local .venv...
    "%PYTHON%" -m pip install pyinstaller
    if errorlevel 1 goto error
)

echo Checking MaintiQ Predict Lite source...
"%PYTHON%" desktop_app\lite_main.py --check
if errorlevel 1 goto error

echo Closing any running MaintiQ Predict Lite process...
taskkill /IM MaintiQ_Predict_Lite.exe /F >nul 2>nul

echo Cleaning previous Lite build folders...
if exist "build\MaintiQ_Predict_Lite" (
    attrib -R "build\MaintiQ_Predict_Lite\*" /S /D >nul 2>nul
    rmdir /S /Q "build\MaintiQ_Predict_Lite"
)
if exist "dist\MaintiQ_Predict_Lite" (
    attrib -R "dist\MaintiQ_Predict_Lite\*" /S /D >nul 2>nul
    rmdir /S /Q "dist\MaintiQ_Predict_Lite"
)

echo Building MaintiQ Predict Lite app folder...
"%PYTHON%" -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "MaintiQ_Predict_Lite" ^
    --exclude-module "xgboost" ^
    --exclude-module "shap" ^
    --exclude-module "numba" ^
    --exclude-module "llvmlite" ^
    --exclude-module "pyarrow" ^
    --exclude-module "matplotlib" ^
    --exclude-module "pandas" ^
    --exclude-module "sklearn" ^
    --exclude-module "scipy" ^
    --exclude-module "PIL" ^
    desktop_app\lite_main.py
if errorlevel 1 goto error

echo Copying Lite runtime snapshot...
"%PYTHON%" tools\prepare_desktop_lite_snapshot.py
if errorlevel 1 goto error

echo Validating Lite distribution...
"%PYTHON%" tools\check_lite_distribution.py dist\MaintiQ_Predict_Lite
if errorlevel 1 goto error

echo.
echo Lite build finished:
echo   dist\MaintiQ_Predict_Lite\MaintiQ_Predict_Lite.exe
echo.
echo This Lite build excludes the research runtime packages used by the Full build.
exit /b 0

:error
echo.
echo MaintiQ Predict Lite build failed. Please read the error message above.
exit /b 1
