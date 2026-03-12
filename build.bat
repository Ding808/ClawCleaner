@echo off
title OpenClaw Cleaner - Build

echo ============================================
echo   OpenClaw Cleaner Build Script
echo ============================================
echo.

echo [1/2] Running PyInstaller...
python -m PyInstaller --onefile --windowed --name "OpenClaw Cleaner" --icon icon.ico --uac-admin --clean --noconfirm cleaner.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check that Python is in PATH.
    echo Install PyInstaller with: python -m pip install pyinstaller
    pause
    exit /b 1
)

echo.
echo [2/2] Copying EXE to Desktop...
copy /Y "dist\OpenClaw Cleaner.exe" "%USERPROFILE%\Desktop\OpenClaw Cleaner.exe"

echo.
echo ============================================
echo   Build successful!
echo   EXE: dist\OpenClaw Cleaner.exe
echo   Copied to Desktop: OpenClaw Cleaner.exe
echo ============================================
echo.
pause
