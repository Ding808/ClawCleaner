#!/bin/bash
# 简单的用于在 Mac 环境下打包成 .app 的脚本
# 需要环境安装了 pyinstaller （ pip install pyinstaller ）
echo "============================================"
echo "  OpenClaw Cleaner macOS Build Script"
echo "============================================"

# 检测是否有 pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "[ERROR] PyInstaller is not installed."
    echo "Please install it using: python3 -m pip install pyinstaller"
    exit 1
fi

echo "[1/2] Running PyInstaller..."
pyinstaller --noconfirm --onedir --windowed --name "OpenClaw_Cleaner" \
    --target-architecture universal2 \
    mac_cleaner.py

echo "[2/2] Moving .app to current directory..."
cp -R "dist/OpenClaw_Cleaner.app" "./OpenClaw_Cleaner.app"

echo "============================================"
echo "  Build successful! "
echo "  Look for OpenClaw_Cleaner.app in this folder."
echo "============================================"