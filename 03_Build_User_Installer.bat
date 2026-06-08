@echo off
chcp 65001 >nul
setlocal

REM Official Full installer build entrypoint.
cd /d "%~dp0"

echo Building the official MaintiQ Predict Full user installer...
call "scripts\dev\build_desktop_installer.bat"
if errorlevel 1 goto error

echo.
echo Official installer is ready:
echo   release\MaintiQ_Predict_Setup.exe
echo Attach this EXE to a GitHub Release; do not commit release\ or dist\ to Git.
exit /b 0

:error
echo.
echo Official installer build failed. Please read the error message above.
exit /b 1
