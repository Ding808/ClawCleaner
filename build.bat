@echo off
chcp 65001 > nul
title OpenClaw Cleaner — 构建 EXE

echo ============================================
echo   OpenClaw Cleaner  ^|  构建脚本
echo ============================================
echo.

:: 构建 EXE
echo.
echo [1/2] 使用 PyInstaller 打包...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "OpenClaw Cleaner" ^
    --icon icon.ico ^
    --uac-admin ^
    --clean ^
    --noconfirm ^
    cleaner.py

if errorlevel 1 (
    echo.
    echo [错误] 构建失败！请检查 PyInstaller 是否已安装。
    echo 安装命令：pip install pyinstaller
    pause
    exit /b 1
)

:: 复制到桌面
echo.
echo [2/2] 复制 EXE 到桌面...
copy /Y "dist\OpenClaw Cleaner.exe" "%USERPROFILE%\Desktop\OpenClaw Cleaner.exe"

echo.
echo ============================================
echo   构建成功！
echo   EXE 路径：dist\OpenClaw Cleaner.exe
echo   已复制到桌面：OpenClaw Cleaner.exe
echo ============================================
echo.
pause
