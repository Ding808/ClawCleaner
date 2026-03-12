#!/bin/bash
# 简单的用于在 Mac 环境下打包成 .app 的脚本
# 需要环境安装了 pyinstaller （ pip install pyinstaller ）
echo "============================================"
echo "  OpenClaw Cleaner macOS Build Script"
echo "============================================"

# 检查如何调用 pyinstaller
if python3 -m pyinstaller --version &> /dev/null; then
    PYINSTALLER_CMD="python3 -m pyinstaller"
elif command -v pyinstaller &> /dev/null; then
    PYINSTALLER_CMD="pyinstaller"
else
    echo "[ERROR] PyInstaller is not installed."
    echo "Please install it using: python3 -m pip install pyinstaller"
    exit 1
fi

echo "[1/2] Running PyInstaller..."
# 移除 --target-architecture universal2 以避免因本地 Python 不是 Universal2 架构导致共享库加载失败
$PYINSTALLER_CMD --noconfirm --onedir --windowed --name "OpenClaw_Cleaner" mac_cleaner.py

echo "[2/2] Moving .app to current directory..."
cp -R "dist/OpenClaw_Cleaner.app" "./OpenClaw_Cleaner.app"

echo "============================================"
echo "  Build successful! "
echo "  Look for OpenClaw_Cleaner.app in this folder."
echo "============================================"