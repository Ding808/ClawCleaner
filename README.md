# OpenClaw Cleaner

**English** | [中文](#中文)

---

## English

A Windows utility that safely removes all traces of the OpenClaw / Claude Code application from your system — including local files, environment variables, registry entries, and exposed API keys.

### Features

- **File & Directory Scan** — Finds OpenClaw-related files across AppData, Program Files, Desktop, VSCode/Cursor extensions, and Temp folders
- **Environment Variable Cleanup** — Detects and removes OpenClaw entries from both user-level and system-level Windows environment variables
- **Registry Cleanup** — Scans Uninstall entries in HKCU and HKLM for OpenClaw remnants
- **API Key Detection** — Identifies exposed API keys (OpenAI, Anthropic, Gemini, Groq, etc.) in config files and warns you to revoke them before deletion
- **Selective Cleanup** — Check/uncheck individual items before deleting; preview file contents before acting
- **GoodBye Button** — Fully uninstalls the cleaner itself after use
- **Cleanup Report** — Saves a detailed `.txt` report to your Desktop after each run
- **Admin Elevation** — Prompts for administrator privileges to handle system-level entries

### Requirements

- Windows 10 / 11
- No Python installation required — the distributed `.exe` is self-contained

### Usage

1. Download `OpenClaw Cleaner.exe`
2. Double-click to run (click **Yes** on the UAC prompt for full cleanup capability)
3. Click **开始扫描 / Start Scan** to detect all OpenClaw remnants
4. Review the list — uncheck anything you want to keep
5. Click **清理并删除 / Clean & Delete** to remove selected items
6. Optionally click **GoodBye 👋** to uninstall the cleaner itself when done

### Build from Source

```bash
# Install dependencies
pip install pyinstaller

# Build (run as Administrator for UAC manifest embedding)
build.bat
```

The compiled executable will be placed in `dist\OpenClaw Cleaner.exe` and copied to your Desktop automatically.

### Project Structure

```
ClawCleaner/
├── cleaner.py          # Main application source
├── build.bat           # PyInstaller build script
├── icon.ico            # Application icon
└── make_icon.py        # Icon generator utility
```

---

## 中文

<a name="中文"></a>

一款 Windows 清理工具，用于安全地移除系统中所有与 OpenClaw / Claude Code 相关的文件、环境变量、注册表项及暴露的 API 密钥。

### 功能特性

- **文件与目录扫描** — 在 AppData、Program Files、桌面、VSCode/Cursor 插件目录及临时文件夹中查找 OpenClaw 相关文件
- **环境变量清理** — 检测并删除用户级和系统级 Windows 环境变量中的 OpenClaw 条目
- **注册表清理** — 扫描 HKCU 和 HKLM 的卸载项，移除 OpenClaw 残留
- **API 密钥检测** — 识别配置文件中暴露的 API 密钥（OpenAI、Anthropic、Gemini、Groq 等），并在删除前提醒你前往对应平台注销
- **选择性清理** — 删除前可逐项勾选/取消，支持预览文件内容
- **GoodBye 按钮** — 使用完毕后可一键卸载清理工具本身
- **清理报告** — 每次清理后自动在桌面保存详细的 `.txt` 报告
- **管理员提权** — 自动请求管理员权限，以处理系统级条目

### 运行环境

- Windows 10 / 11
- **无需安装 Python** — 发布的 `.exe` 为独立可执行文件，开箱即用

### 使用方法

1. 下载 `OpenClaw Cleaner.exe`
2. 双击运行（UAC 弹窗点击**是**以获得完整清理权限）
3. 点击**开始扫描**，检测所有 OpenClaw 残留
4. 查看列表，取消勾选不想删除的项目
5. 点击**清理并删除**，移除已勾选的条目
6. 使用完毕后，可点击 **GoodBye 👋** 卸载清理工具本身

### 从源码构建

```bash
# 安装依赖
pip install pyinstaller

# 构建（建议以管理员身份运行以正确嵌入 UAC 清单）
build.bat
```

编译完成后，可执行文件将生成于 `dist\OpenClaw Cleaner.exe`，并自动复制到桌面。

### 项目结构

```
ClawCleaner/
├── cleaner.py          # 主程序源码
├── build.bat           # PyInstaller 构建脚本
├── icon.ico            # 应用图标
└── make_icon.py        # 图标生成工具
```

### 免责声明

本工具仅用于清理本机残留数据，不会上传任何信息。删除操作不可撤销，请在清理前仔细核对列表。

---

> **⚠ 重要提示 / Important**
> API keys found during scanning are **not** automatically revoked — you must manually invalidate them on the respective platform's dashboard before deleting the files.
