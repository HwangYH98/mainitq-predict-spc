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

echo Checking native desktop app source...
"%PYTHON%" desktop_app\main.py --check
if errorlevel 1 goto error

echo Closing any running MaintiQ Predict process...
taskkill /IM MaintiQ_Predict.exe /F >nul 2>nul

echo Cleaning previous desktop build folders...
if exist "build\MaintiQ_Predict" (
    attrib -R "build\MaintiQ_Predict\*" /S /D >nul 2>nul
    rmdir /S /Q "build\MaintiQ_Predict"
)
if exist "dist\MaintiQ_Predict" (
    attrib -R "dist\MaintiQ_Predict\*" /S /D >nul 2>nul
    rmdir /S /Q "dist\MaintiQ_Predict"
)

echo Building MaintiQ Predict desktop app folder...
"%PYTHON%" -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "MaintiQ_Predict" ^
    --paths "src" ^
    --collect-binaries "xgboost" ^
    --collect-data "xgboost" ^
    --hidden-import "xgboost" ^
    --exclude-module "xgboost.testing" ^
    --exclude-module "xgboost.spark" ^
    --exclude-module "xgboost.dask" ^
    --exclude-module "pytest" ^
    desktop_app\main.py
if errorlevel 1 goto error

echo Verifying PyInstaller runtime files...
"%PYTHON%" tools\repair_pyinstaller_collect.py
if errorlevel 1 goto error

echo Copying runtime snapshot into the app folder...
"%PYTHON%" tools\prepare_desktop_runtime_snapshot.py
if errorlevel 1 goto error

echo Pruning optional desktop distribution files...
"%PYTHON%" tools\prune_desktop_distribution.py dist\MaintiQ_Predict
if errorlevel 1 goto error
echo dist\MaintiQ_Predict\MaintiQ_Predict.exe

echo Validating desktop distribution...
"%PYTHON%" tools\validate_desktop_distribution.py dist\MaintiQ_Predict
if errorlevel 1 goto error

echo.
echo Build finished:
echo   dist\MaintiQ_Predict\MaintiQ_Predict.exe
echo.
echo MaintiQ Predict is a native desktop app. It opens an app window without Streamlit or a browser.
echo Keep the generated folder together when moving it to another location.
echo The folder includes a runtime snapshot of src, data, and outputs, excluding local DB/runtime folders.
exit /b 0

:error
echo.
echo Desktop app build failed. Please read the error message above.
exit /b 1
