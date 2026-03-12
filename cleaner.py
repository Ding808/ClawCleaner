"""
OpenClaw Cleaner — 一键清理 OpenClaw 所有本地文件、环境变量及 API 密钥残留
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os, sys, winreg, shutil, re, json, datetime, ctypes, subprocess, threading, stat
from pathlib import Path

# 设置高 DPI 感知（修复界面模糊）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ─────────────────────────────────────────────
#  管理员提权
# ─────────────────────────────────────────────
def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def relaunch_as_admin():
    exe = sys.executable
    arg = "" if getattr(sys, "frozen", False) else f'"{__file__}"'
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, arg, None, 1)
    sys.exit(0)


# ─────────────────────────────────────────────
#  常量
# ─────────────────────────────────────────────
UP   = os.environ.get("USERPROFILE", str(Path.home()))
AD   = os.environ.get("APPDATA", "")
LAD  = os.environ.get("LOCALAPPDATA", "")
TMP  = os.environ.get("TEMP", "")
DSK  = os.path.join(UP, "Desktop")

SCAN_DIRS = [
    os.path.join(UP,  ".claude"),
    os.path.join(AD,  "openclaw"),   os.path.join(AD,  "OpenClaw"),
    os.path.join(AD,  "open-claw"),
    os.path.join(LAD, "openclaw"),   os.path.join(LAD, "OpenClaw"),
    os.path.join(LAD, "open-claw"),
    os.path.join(UP,  "openclaw"),   os.path.join(UP,  ".openclaw"),
    os.path.join(UP,  "Documents", "openclaw"),
    TMP,
    os.path.join(UP, ".claude", "plugins"),
    os.path.join(UP, ".claude", "plans"),
    os.path.join(UP, ".claude", "skills"),
]

CLAW_RE = re.compile(r"open.?claw", re.IGNORECASE)

KNOWN_KEYS = [
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "OPENCLAW_API_KEY",
    "OPENCLAW_KEY", "COHERE_API_KEY", "MISTRAL_API_KEY",
    "PERPLEXITY_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY",
    "HUGGINGFACE_API_KEY", "HF_TOKEN",
]

ENV_RE = re.compile(
    r'^([A-Z0-9_]*(API_KEY|TOKEN|SECRET|KEY)[A-Z0-9_]*)\s*=\s*(.+)$',
    re.IGNORECASE | re.MULTILINE,
)

# ─────────────────────────────────────────────
#  主题
# ─────────────────────────────────────────────
BG     = "#0f0f1a"
PANEL  = "#1a1a2e"
RED    = "#e94560"
AMBER  = "#f5a623"
GREEN  = "#0fd47d"
FG     = "#e0e0e0"
DIM    = "#888899"
MONO   = ("Consolas", 9)
UI     = ("Segoe UI", 10)
UIB    = ("Segoe UI", 10, "bold")

TYPE_ICON = {"file": "📄 文件", "dir": "📁 目录", "env": "🌐 环境变量", "reg": "🗂 注册表"}


# ─────────────────────────────────────────────
#  预览弹窗（独立函数）
# ─────────────────────────────────────────────
def show_preview(parent, title, content):
    w = tk.Toplevel(parent)
    w.title(title)
    w.configure(bg=BG)
    w.geometry("720x500")
    w.resizable(True, True)

    bar = tk.Frame(w, bg=PANEL)
    bar.pack(fill="x")
    tk.Label(bar, text=title, bg=PANEL, fg=FG, font=UIB,
             anchor="w").pack(side="left", padx=12, pady=8)
    tk.Button(bar, text="关闭", command=w.destroy,
              bg=RED, fg="white", font=UIB, relief="flat",
              padx=12, pady=4, cursor="hand2").pack(side="right", padx=10, pady=6)

    txt = scrolledtext.ScrolledText(w, bg="#0b0b14", fg=FG, font=MONO,
                                    wrap="none", state="normal",
                                    relief="flat", bd=0, insertbackground=FG)
    txt.pack(fill="both", expand=True, padx=8, pady=8)
    txt.insert("1.0", content)
    txt.configure(state="disabled")


# ─────────────────────────────────────────────
#  辅助：格式化字节数
# ─────────────────────────────────────────────
def fmt_size(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"


# ─────────────────────────────────────────────
#  主应用
# ─────────────────────────────────────────────
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("OpenClaw Cleaner")
        self.root.configure(bg=BG)
        self.root.geometry("1000x800")
        self.root.minsize(800, 600)

        self.items   = []          # 待清理条目
        self.api_keys = {}         # 发现的 API 密钥 {name: masked}
        self._iid_idx = {}         # treeview iid → items 索引
        self._skipped_keys = set() # 跳过清理的条目 key 集合

        self._build()
        self._style()

        # 设置窗口图标
        try:
            base = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                                   else os.path.abspath(__file__))
            ico = os.path.join(base, "icon.ico")
            if os.path.isfile(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass

    # ─── 布局 ────────────────────────────────
    def _build(self):
        r = self.root

        # ── 顶栏 ──
        top = tk.Frame(r, bg=RED, height=52)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="⚠  OpenClaw Cleaner",
                 bg=RED, fg="white", font=("Segoe UI", 14, "bold")
                 ).pack(side="left", padx=20)
        badge_text = "  管理员模式  " if is_admin() else "  建议以管理员运行  "
        badge_fg   = GREEN if is_admin() else AMBER
        tk.Label(top, text=badge_text, bg=RED, fg=badge_fg, font=UIB
                 ).pack(side="right", padx=20)

        # ── 内容区（水平）──
        content = tk.Frame(r, bg=BG)
        content.pack(fill="both", expand=True, padx=14, pady=(10, 0))

        # 右侧 API 面板（固定宽度）
        self._build_api_panel(content)

        # 左侧（上下分割）
        left = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        # 上：日志
        self._build_log(left)

        # 分隔条标题
        sep_bar = tk.Frame(left, bg="#1e1e32", height=28)
        sep_bar.pack(fill="x", pady=(8, 0))
        sep_bar.pack_propagate(False)
        tk.Label(sep_bar, text="待清理文件列表",
                 bg="#1e1e32", fg=DIM, font=UIB,
                 anchor="w").pack(side="left", padx=10, pady=4)
        tk.Label(sep_bar,
                 text="双击→预览/打开  |  空格→切换勾选  |  右键→更多",
                 bg="#1e1e32", fg=DIM, font=("Segoe UI", 8),
                 anchor="w").pack(side="left", padx=6)
        self._count_var = tk.StringVar(value="")
        tk.Label(sep_bar, textvariable=self._count_var,
                 bg="#1e1e32", fg=AMBER, font=UIB,
                 anchor="e").pack(side="right", padx=10)

        # 下：Treeview
        self._build_tree(left)

        # ── 底栏 ──
        self._build_bottom(r)

    def _build_log(self, parent):
        self.log = scrolledtext.ScrolledText(
            parent, height=10,
            bg="#0b0b14", fg=FG, insertbackground=FG,
            font=MONO, wrap="word", state="disabled",
            relief="flat", highlightthickness=1,
            highlightbackground="#2a2a3e",
        )
        self.log.pack(fill="x", pady=(0, 0))
        for tag, fg_, bg_ in [
            ("warn", AMBER,     ""),
            ("ok",   GREEN,     ""),
            ("err",  RED,       ""),
            ("info", "#66aaff", ""),
            ("dim",  DIM,       ""),
            ("key",  "#ffdd57", "#2a220a"),
        ]:
            kw = {"foreground": fg_}
            if bg_:
                kw["background"] = bg_
            self.log.tag_config(tag, **kw)

    def _build_tree(self, parent):
        # 用一个 Frame 包裹，内部纯 grid
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="both", expand=True)

        cols = ("sel", "type", "name", "detail", "size")
        self.tree = ttk.Treeview(wrap, columns=cols,
                                  show="headings", selectmode="extended")
        self.tree.heading("sel",    text="清理",       anchor="center")
        self.tree.heading("type",   text="类型",       anchor="w")
        self.tree.heading("name",   text="名称",       anchor="w")
        self.tree.heading("detail", text="路径 / 说明", anchor="w")
        self.tree.heading("size",   text="大小",       anchor="e")
        self.tree.column("sel",    width=42,  minwidth=42,  stretch=False, anchor="center")
        self.tree.column("type",   width=100, minwidth=80,  stretch=False)
        self.tree.column("name",   width=210, minwidth=120, stretch=False)
        self.tree.column("detail", width=10,  minwidth=120, stretch=True)
        self.tree.column("size",   width=80,  minwidth=60,  stretch=False, anchor="e")

        vsb = ttk.Scrollbar(wrap, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self.tree.tag_configure("file", background="#141428", foreground=FG)
        self.tree.tag_configure("dir",  background="#141e28", foreground="#aaddff")
        self.tree.tag_configure("env",  background="#1e1428", foreground=AMBER)
        self.tree.tag_configure("reg",  background="#141814", foreground="#aaffaa")

        self.tree.bind("<Double-1>",  self._on_double)
        self.tree.bind("<Return>",    self._on_double)
        self.tree.bind("<Button-3>",  self._on_right)
        self.tree.bind("<space>",     self._toggle_selected)
        self.tree.bind("<Button-1>",  self._on_click)

        # 右键菜单
        self.menu = tk.Menu(self.root, tearoff=0,
                            bg=PANEL, fg=FG,
                            activebackground=RED, activeforeground="white",
                            relief="flat", bd=1)
        self.menu.add_command(label="☐  跳过所选项目（不清理）",
                              command=self._skip_selected)
        self.menu.add_command(label="☑  恢复所选项目（加入清理）",
                              command=self._restore_selected)
        self.menu.add_separator()
        self.menu.add_command(label="📂  在资源管理器中显示",
                              command=self._menu_explorer)
        self.menu.add_command(label="🔍  预览文件内容",
                              command=self._menu_preview)
        self.menu.add_separator()
        self.menu.add_command(label="🗑  从清理列表移除",
                              command=self._menu_remove)

    def _build_api_panel(self, parent):
        panel = tk.Frame(parent, bg=PANEL, width=320,
                         highlightthickness=1,
                         highlightbackground="#2a2a3e")
        panel.pack(side="right", fill="y", padx=(12, 0))
        panel.pack_propagate(False)

        top_frame = tk.Frame(panel, bg=PANEL)
        top_frame.pack(fill="x", padx=12, pady=(14, 4))
        tk.Label(top_frame, text="⚠  发现的 API 密钥",
                 bg=PANEL, fg=AMBER, font=UIB
                 ).pack(side="left")
        tk.Button(top_frame, text="↻ 刷新", bg="#2a2a4e", fg=FG, font=("Segoe UI", 8),
                  command=self._refresh_api_keys_check, relief="flat", cursor="hand2",
                  padx=6, pady=2).pack(side="right")

        tk.Label(panel,
                 text="删除文件前，请务必到对应\n云端控制台注销以下密钥！",
                 bg=PANEL, fg=DIM, font=("Segoe UI", 9),
                 justify="left", wraplength=280,
                 ).pack(padx=12, anchor="w")
        tk.Frame(panel, bg="#2a2a3e", height=1).pack(fill="x", padx=8, pady=8)

        canvas_frame = tk.Frame(panel, bg=PANEL)
        canvas_frame.pack(fill="both", expand=True, padx=2, pady=0)
        
        self.api_canvas = tk.Canvas(canvas_frame, bg=PANEL, highlightthickness=0)
        self.api_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.api_canvas.yview)
        
        self.key_frame = tk.Frame(self.api_canvas, bg=PANEL)
        
        self.api_canvas.create_window((0, 0), window=self.key_frame, anchor="nw", tags="self.key_frame")
        self.api_canvas.configure(yscrollcommand=self.api_scrollbar.set)
        
        self.api_canvas.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.api_scrollbar.pack(side="right", fill="y")
        
        self.key_frame.bind("<Configure>", lambda e: self.api_canvas.configure(scrollregion=self.api_canvas.bbox("all")))
        self.api_canvas.bind("<Configure>", lambda e: self.api_canvas.itemconfig("self.key_frame", width=e.width))

        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            try:
                # 只在需要滚动时滚动（如果没出现滚动条说明内容很少，无需滚动）
                if self.api_scrollbar.get() == (0.0, 1.0):
                    return
                
                # event.delta > 0 向上滚， yview()[0] 是当前视图的顶部比例
                if event.delta > 0 and self.api_canvas.yview()[0] <= 0:
                    return
                    
                # event.delta < 0 向下滚， yview()[1] 是当前视图的底部比例
                if event.delta < 0 and self.api_canvas.yview()[1] >= 1:
                    return
                    
                self.api_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass
        
        self.api_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        tk.Label(self.key_frame,
                 text="尚未扫描\n请先点击「开始扫描」",
                 bg=PANEL, fg=DIM, font=("Segoe UI", 9),
                 justify="center").pack(pady=30)

    def _build_bottom(self, parent):
        bar = tk.Frame(parent, bg=BG)
        bar.pack(fill="x", padx=14, pady=10)

        self.prog = ttk.Progressbar(bar, mode="indeterminate", length=180)
        self.prog.pack(side="left", padx=(0, 14))

        self._status = tk.StringVar(value="等待操作…")
        tk.Label(bar, textvariable=self._status,
                 bg=BG, fg=DIM, font=UI).pack(side="left")

        tk.Button(
            bar, text="GoodBye 👋", command=self._goodbye,
            bg="#2a1a1a", fg="#cc4444", font=UIB, relief="flat",
            padx=12, pady=7, cursor="hand2",
        ).pack(side="left", padx=(14, 0))

        self.btn_clean = tk.Button(
            bar, text="清理并删除  🗑", command=self._start_clean,
            bg="#8b0000", fg="white", font=UIB, relief="flat",
            padx=16, pady=7, cursor="hand2", state="disabled",
        )
        self.btn_clean.pack(side="right", padx=(6, 0))

        self.btn_scan = tk.Button(
            bar, text="开始扫描  🔍", command=self._start_scan,
            bg=RED, fg="white", font=UIB, relief="flat",
            padx=16, pady=7, cursor="hand2",
        )
        self.btn_scan.pack(side="right", padx=(6, 0))

        tk.Button(
            bar, text="☑ 全选", command=self._select_all,
            bg="#2a2a4e", fg=FG, font=UI, relief="flat",
            padx=10, pady=7, cursor="hand2",
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            bar, text="☐ 跳过所选", command=self._skip_selected,
            bg="#2a2a4e", fg=AMBER, font=UI, relief="flat",
            padx=10, pady=7, cursor="hand2",
        ).pack(side="right", padx=(0, 0))

    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Treeview",
                    background="#10101e", fieldbackground="#10101e",
                    foreground=FG, rowheight=24, font=MONO)
        s.configure("Treeview.Heading",
                    background="#1e1e32", foreground=DIM,
                    relief="flat", font=("Segoe UI", 9, "bold"))
        s.map("Treeview",
              background=[("selected", "#2a2a5e")],
              foreground=[("selected", "white")])

    # ─── 日志 ────────────────────────────────
    def _log(self, text, tag=""):
        def update_ui():
            self.log.configure(state="normal")
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}]  {text}\n"
            self.log.insert("end", line, tag) if tag else self.log.insert("end", line)
            self.log.configure(state="disabled")
            self.log.see("end")
        self.root.after(0, update_ui)

    def _log_sep(self):
        def update_ui():
            self.log.configure(state="normal")
            self.log.insert("end", "─" * 68 + "\n", "dim")
            self.log.configure(state="disabled")
        self.root.after(0, update_ui)

    # ─── 扫描 ────────────────────────────────
    def _start_scan(self):
        self.btn_scan.configure(state="disabled")
        self.btn_clean.configure(state="disabled")
        self.items.clear()
        self.api_keys.clear()
        self._iid_idx.clear()
        self._skipped_keys.clear()
        self.tree.delete(*self.tree.get_children())
        self._count_var.set("")
        self.prog.start(12)
        self._status.set("正在扫描…")
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        self._log("=== 开始扫描 OpenClaw 残留 ===", "info")
        self._log_sep()

        self._log("【1/3】扫描本地文件和目录…", "info")
        self._scan_files()
        self._log_sep()

        self._log("【2/3】扫描 Windows 环境变量…", "info")
        self._scan_envvars()
        self._log_sep()

        self._log("【3/3】扫描注册表 Uninstall 条目…", "info")
        self._scan_registry()
        self._log_sep()

        nf = sum(1 for i in self.items if i["type"] in ("file", "dir"))
        ne = sum(1 for i in self.items if i["type"] == "env")
        nr = sum(1 for i in self.items if i["type"] == "reg")
        self._log(f"完成：{nf} 个文件/目录，{ne} 个环境变量，"
                  f"{nr} 个注册表项，{len(self.api_keys)} 个 API 密钥", "ok")

        self.root.after(0, self._refresh_api_panel)
        self.root.after(0, self._fill_tree)
        self.root.after(0, self._scan_done)

    # 文件扫描
    def _scan_files(self):
        seen = set()
        for base in SCAN_DIRS:
            base = os.path.normpath(base)
            if base in seen or not os.path.exists(base):
                continue
            seen.add(base)
            is_claw_base = CLAW_RE.search(base) is not None
            try:
                for root_dir, dirs, files in os.walk(base):
                    for name in dirs + files:
                        full = os.path.join(root_dir, name)
                        is_claw = is_claw_base or CLAW_RE.search(name) is not None
                        if not is_claw and base == os.path.join(UP, ".claude"):
                            is_claw = self._has_claw_content(full)
                        if is_claw:
                            kind = "dir" if os.path.isdir(full) else "file"
                            self.items.append({"type": kind, "path": full})
                            self._log(f"  {'📁' if kind=='dir' else '📄'} {full}", "warn")
                            if kind == "file" and self._is_config(name):
                                self._extract_keys(full)
            except PermissionError:
                self._log(f"  ⛔ 无权限：{base}", "err")

        # TEMP 目录单独扫名称
        if os.path.isdir(TMP):
            try:
                for name in os.listdir(TMP):
                    if CLAW_RE.search(name):
                        full = os.path.join(TMP, name)
                        kind = "dir" if os.path.isdir(full) else "file"
                        self.items.append({"type": kind, "path": full})
                        self._log(f"  {'📁' if kind=='dir' else '📄'} {full}", "warn")
            except Exception as e:
                self._log(f"  ⛔ TEMP 读取失败：{e}", "err")

        if not any(i["type"] in ("file", "dir") for i in self.items):
            self._log("  ✅ 未找到相关文件", "ok")

    def _has_claw_content(self, path):
        if not os.path.isfile(path):
            return False
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return CLAW_RE.search(f.read(8192)) is not None
        except Exception:
            return False

    def _is_config(self, name):
        exts = {".env", ".cfg", ".ini", ".json", ".yaml", ".yml",
                ".toml", ".conf", ".config"}
        return Path(name).suffix.lower() in exts or name.startswith(".env")

    def _extract_keys(self, filepath):
        try:
            if os.path.getsize(filepath) > 1024 * 1024:
                return
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if filepath.endswith(".json"):
                try:
                    for k, v in self._flat(json.loads(content)):
                        ku = k.upper()
                        if any(w in ku for w in ("API_KEY", "TOKEN", "SECRET")):
                            self._save_key(k, str(v), filepath, "file")
                except Exception:
                    pass
            for m in ENV_RE.finditer(content):
                self._save_key(m.group(1), m.group(3).strip().strip('"').strip("'"), filepath, "file")
        except Exception:
            pass

    def _flat(self, d, prefix=""):
        if isinstance(d, dict):
            for k, v in d.items():
                yield from self._flat(v, f"{prefix}.{k}" if prefix else k)
        else:
            yield prefix, d

    def _save_key(self, name, value, source, t="file"):
        if len(value) < 6:
            return
        masked = value[:6] + "*" * min(len(value) - 6, 20) + "…"
        self.api_keys[name] = {"masked": masked, "source": source, "type": t}
        self._log(f"  🔑 密钥  {name} = {masked}", "key")

    # 环境变量扫描
    def _scan_envvars(self):
        levels = [
            ("用户级 (HKCU)", winreg.HKEY_CURRENT_USER,
             r"Environment"),
            ("系统级 (HKLM)", winreg.HKEY_LOCAL_MACHINE,
             r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        ]
        for label, hive, sub in levels:
            self._log(f"  → {label}", "dim")
            try:
                with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ) as key:
                    idx = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, idx)
                            idx += 1
                            if CLAW_RE.search(name):
                                self.items.append({
                                    "type": "env", "name": name,
                                    "value": str(value), "hive": label,
                                    "hive_key": hive, "subkey": sub,
                                })
                                self._log(f"    🌐 {label}  {name} = {str(value)[:80]}", "warn")
                            if name.upper() in [k.upper() for k in KNOWN_KEYS]:
                                masked = str(value)[:6] + "*" * min(len(str(value))-6, 20) + "…"
                                self.api_keys[name] = {
                                    "masked": masked, "source": label, "type": "env",
                                    "hive_key": hive, "subkey": sub
                                }
                                self._log(f"    🔑 {name} = {masked}", "key")
                        except OSError:
                            break
            except PermissionError:
                self._log(f"    ⛔ 无权限读取 {label}", "err")
            except Exception as e:
                self._log(f"    ⛔ {label} 失败：{e}", "err")

        if not any(i["type"] == "env" for i in self.items):
            self._log("  ✅ 未发现相关环境变量", "ok")

    # 注册表扫描
    def _scan_registry(self):
        paths = [
            (winreg.HKEY_CURRENT_USER,
             r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hive, path in paths:
            try:
                with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
                    idx = 0
                    while True:
                        try:
                            sub = winreg.EnumKey(key, idx)
                            idx += 1
                            if CLAW_RE.search(sub):
                                full = f"{path}\\{sub}"
                                self.items.append({
                                    "type": "reg", "hive_key": hive,
                                    "subkey": full, "name": sub,
                                })
                                self._log(f"  🗂  {full}", "warn")
                        except OSError:
                            break
            except Exception:
                pass

        if not any(i["type"] == "reg" for i in self.items):
            self._log("  ✅ 未发现相关注册表条目", "ok")

    # ─── Treeview ────────────────────────────
    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self._iid_idx.clear()
        for idx, item in enumerate(self.items):
            t = item["type"]
            if t in ("file", "dir"):
                path   = item["path"]
                name   = os.path.basename(path)
                detail = os.path.dirname(path)
                size   = "<目录>" if t == "dir" else (
                    fmt_size(os.path.getsize(path))
                    if os.path.exists(path) else "—"
                )
            elif t == "env":
                name   = item["name"]
                detail = f"[{item['hive']}]  {item['value'][:60]}"
                size   = "—"
            else:
                name   = item["name"]
                detail = item["subkey"]
                size   = "—"

            key = self._item_key(item)
            cb = "☐" if key in self._skipped_keys else "☑"
            iid = self.tree.insert("", "end",
                                   values=(cb, TYPE_ICON.get(t, t), name, detail, size),
                                   tags=(t,))
            self._iid_idx[iid] = idx

        self._update_count()

    def _selected(self):
        """Return the single focused item (for preview/explorer actions)."""
        focused = self.tree.focus()
        iid = focused if focused else (self.tree.selection() or [None])[0]
        if not iid:
            return None
        idx = self._iid_idx.get(iid)
        if idx is None or idx >= len(self.items):
            return None
        return self.items[idx]

    def _item_key(self, item):
        return item.get("path", item.get("name", ""))

    def _update_count(self):
        total = len(self.items)
        checked = sum(1 for item in self.items
                      if self._item_key(item) not in self._skipped_keys)
        if total:
            self._count_var.set(f"共 {total} 项  ·  已勾选 {checked} 项")
        else:
            self._count_var.set("")

    def _refresh_checkboxes(self):
        for iid, idx in self._iid_idx.items():
            key = self._item_key(self.items[idx])
            cb = "☐" if key in self._skipped_keys else "☑"
            vals = list(self.tree.item(iid, "values"))
            if vals:
                vals[0] = cb
                self.tree.item(iid, values=vals)
        self._update_count()
        checked = sum(1 for item in self.items
                      if self._item_key(item) not in self._skipped_keys)
        if self.btn_clean["state"] != "disabled" or checked > 0:
            try:
                self.btn_clean.configure(
                    state="normal" if checked > 0 else "disabled")
            except Exception:
                pass

    def _skip_selected(self):
        for iid in self.tree.selection():
            idx = self._iid_idx.get(iid)
            if idx is not None:
                self._skipped_keys.add(self._item_key(self.items[idx]))
        self._refresh_checkboxes()

    def _restore_selected(self):
        for iid in self.tree.selection():
            idx = self._iid_idx.get(iid)
            if idx is not None:
                self._skipped_keys.discard(self._item_key(self.items[idx]))
        self._refresh_checkboxes()

    def _toggle_selected(self, _=None):
        sel = self.tree.selection()
        if not sel:
            return
        any_checked = any(
            self._item_key(self.items[self._iid_idx[iid]]) not in self._skipped_keys
            for iid in sel if self._iid_idx.get(iid) is not None
        )
        if any_checked:
            self._skip_selected()
        else:
            self._restore_selected()

    def _select_all(self):
        """Re-check all items (clear all skips)."""
        self._skipped_keys.clear()
        self._refresh_checkboxes()

    def _on_click(self, event):
        """Toggle checkbox when clicking the 'sel' column."""
        region = self.tree.identify_region(event.x, event.y)
        col = self.tree.identify_column(event.x)
        if region == "cell" and col == "#1":
            iid = self.tree.identify_row(event.y)
            if iid:
                idx = self._iid_idx.get(iid)
                if idx is not None:
                    key = self._item_key(self.items[idx])
                    if key in self._skipped_keys:
                        self._skipped_keys.discard(key)
                    else:
                        self._skipped_keys.add(key)
                    self._refresh_checkboxes()
                return "break"

    def _on_double(self, _=None):
        item = self._selected()
        if not item:
            return
        t = item["type"]
        if t == "file":
            self._preview_file(item["path"])
        elif t == "dir":
            try:
                os.startfile(item["path"])
            except Exception as e:
                messagebox.showerror("错误", str(e))
        elif t == "env":
            show_preview(self.root, f"环境变量：{item['name']}",
                         f"变量名：{item['name']}\n来源：{item['hive']}\n\n值：\n{item['value']}")
        else:
            show_preview(self.root, f"注册表项：{item['name']}",
                         f"路径：{item['subkey']}")

    def _on_right(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            # If clicking outside current selection, replace selection
            if row not in self.tree.selection():
                self.tree.selection_set(row)
        item = self._selected()
        if not item:
            return
        t = item["type"]
        # Entries: 0=skip, 1=restore, 2=sep, 3=explorer, 4=preview, 5=sep, 6=remove
        has_sel = bool(self.tree.selection())
        self.menu.entryconfigure(0, state="normal" if has_sel else "disabled")
        self.menu.entryconfigure(1, state="normal" if has_sel else "disabled")
        self.menu.entryconfigure(3, state="normal" if t in ("file", "dir") else "disabled")
        self.menu.entryconfigure(4, state="normal" if t == "file" else "disabled")
        self.menu.tk_popup(event.x_root, event.y_root)

    def _menu_explorer(self):
        item = self._selected()
        if not item or item["type"] not in ("file", "dir"):
            return
        path = item["path"]
        if item["type"] == "file":
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            try:
                os.startfile(path)
            except Exception as e:
                messagebox.showerror("错误", str(e))

    def _menu_preview(self):
        item = self._selected()
        if item and item["type"] == "file":
            self._preview_file(item["path"])

    def _menu_remove(self):
        sel = self.tree.selection()
        if not sel:
            return
        count = len(sel)
        if not messagebox.askyesno("移除确认",
                                   f"从清理列表彻底移除所选 {count} 个条目（本次不删除）？"):
            return
        # Collect indices to remove (sorted descending to preserve indices)
        indices = sorted(
            (self._iid_idx[iid] for iid in sel if self._iid_idx.get(iid) is not None),
            reverse=True,
        )
        for idx in indices:
            key = self._item_key(self.items[idx])
            self._skipped_keys.discard(key)
            self.items.pop(idx)
        self._fill_tree()
        n = len(self.items)
        self._status.set(f"扫描完成，共 {n} 项待清理")
        if n == 0:
            self.btn_clean.configure(state="disabled")

    def _preview_file(self, path):
        MAX = 128 * 1024
        try:
            size = os.path.getsize(path)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(MAX)
            if size > MAX:
                content += f"\n\n… (仅显示前 {MAX//1024} KB，文件共 {fmt_size(size)})"
        except Exception:
            try:
                with open(path, "rb") as f:
                    raw = f.read(512)
                size = os.path.getsize(path)
                content = (f"[二进制文件]\n大小：{fmt_size(size)}\n\n"
                           f"前 512 字节 (hex):\n" +
                           " ".join(f"{b:02x}" for b in raw))
            except Exception as e:
                messagebox.showerror("读取失败", str(e))
                return
        show_preview(self.root, f"预览：{os.path.basename(path)}", content)

    # ─── API 密钥面板 ────────────────────────
    def _refresh_api_keys_check(self):
        still_exists = {}
        for kname, info in list(self.api_keys.items()):
            t = info["type"]
            src = info["source"]
            if t == "file":
                if os.path.isfile(src):
                    try:
                        with open(src, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        
                        # 考虑 JSON 嵌套导致的 key 是 a.b.KEY 的情况
                        search_key = kname.split(".")[-1]
                        if search_key.upper() in content.upper():
                            still_exists[kname] = info
                    except Exception:
                        pass
            elif t == "env":
                try:
                    with winreg.OpenKey(info["hive_key"], info["subkey"], 0, winreg.KEY_READ) as key:
                        val, _ = winreg.QueryValueEx(key, kname)
                        if val:
                            still_exists[kname] = info
                except Exception:
                    pass
        
        removed = len(self.api_keys) - len(still_exists)
        self.api_keys = still_exists
        self._refresh_api_panel()
        if removed > 0:
            messagebox.showinfo("刷新完成", f"已刷新。有 {removed} 个 API 密钥由于文件被删或修改已不复存在。\n\n当前剩余 {len(self.api_keys)} 个残留。")
        else:
            messagebox.showinfo("刷新完成", f"已刷新。所有（{len(self.api_keys)} 个） API 密钥仍存在。")

    def _refresh_api_panel(self):
        for w in self.key_frame.winfo_children():
            w.destroy()
        if not self.api_keys:
            tk.Label(self.key_frame, text="✅ 未发现 API 密钥残留",
                     bg=PANEL, fg=GREEN, font=UIB).pack(pady=20)
            self.key_frame.update_idletasks()
            self.api_canvas.configure(scrollregion=self.api_canvas.bbox("all"))
            return

        def open_src(event, src, t):
            if t == "file":
                if os.path.exists(src):
                    subprocess.Popen(f'explorer /select,"{os.path.normpath(src)}"')
                else:
                    messagebox.showerror("未找到", "该文件已不存在。")
            else:
                messagebox.showinfo("环境变量", f"该密钥位于环境变量：\n{src}\n\n请在系统或用户环境变量中清理。")

        for kname, info in self.api_keys.items():
            masked = info["masked"]
            src = info["source"]
            t = info["type"]
            
            card = tk.Frame(self.key_frame, bg="#1f1500", highlightthickness=1, highlightbackground=AMBER, cursor="hand2")
            card.pack(fill="x", pady=3)
            
            lbl1 = tk.Label(card, text=kname, bg="#1f1500", fg=AMBER, font=("Segoe UI", 8, "bold"), anchor="w", cursor="hand2")
            lbl1.pack(fill="x", padx=8, pady=(5, 0))
            lbl2 = tk.Label(card, text=masked, bg="#1f1500", fg=FG, font=("Consolas", 8), anchor="w", cursor="hand2")
            lbl2.pack(fill="x", padx=8, pady=(0, 5))
            
            # 绑定点击事件到各组件
            handler = lambda e, s=src, t_=t: open_src(e, s, t_)
            card.bind("<Button-1>", handler)
            lbl1.bind("<Button-1>", handler)
            lbl2.bind("<Button-1>", handler)

        tk.Frame(self.key_frame, bg="#2a2a3e", height=1).pack(fill="x", pady=(8, 4))
        tk.Label(self.key_frame,
                 text="⚠ 清理前请登录对应平台\n吊销 / 注销以上密钥！",
                 bg=PANEL, fg=RED, font=("Segoe UI", 9, "bold"),
                 justify="center", wraplength=220).pack(pady=(4, 10))

        self.key_frame.update_idletasks()
        self.api_canvas.configure(scrollregion=self.api_canvas.bbox("all"))

    def _scan_done(self):
        self.prog.stop()
        n = len(self.items)
        checked = sum(1 for item in self.items
                      if self._item_key(item) not in self._skipped_keys)
        if n:
            self._status.set(f"扫描完成，共 {n} 项（已勾选 {checked} 项）")
            self.btn_clean.configure(state="normal" if checked > 0 else "disabled")
        else:
            self._status.set("未发现 OpenClaw 残留，系统干净 ✅")
        self.btn_scan.configure(state="normal")

    # ─── 清理 ────────────────────────────────
    def _start_clean(self):
        items_to_clean = [item for item in self.items
                          if self._item_key(item) not in self._skipped_keys]
        if not items_to_clean:
            messagebox.showinfo("提示", "没有勾选需要清理的项目。")
            return
        skipped = len(self.items) - len(items_to_clean)
        if self.api_keys:
            keys_str = "\n".join(f"• {k}" for k in self.api_keys)
            if not messagebox.askyesno(
                "⚠  请确认已吊销 API 密钥",
                f"发现以下 API 密钥：\n\n{keys_str}\n\n"
                "请务必先到对应平台注销 / 吊销这些密钥！\n\n"
                "确认已吊销后，点击「是」继续。",
                icon="warning",
            ):
                return
        skip_note = f"\n（已跳过 {skipped} 项不清理）" if skipped else ""
        if not messagebox.askyesno(
            "确认清理",
            f"即将删除 {len(items_to_clean)} 个条目。{skip_note}\n此操作不可撤销！是否继续？",
            icon="warning",
        ):
            return
        self._items_to_clean = items_to_clean
        self.btn_scan.configure(state="disabled")
        self.btn_clean.configure(state="disabled")
        self.prog.start(12)
        self._status.set("正在清理…")
        threading.Thread(target=self._clean_thread, daemon=True).start()

    def _delete_reg_key_tree(self, hive, subkey):
        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
                while True:
                    try:
                        sub = winreg.EnumKey(key, 0)
                        self._delete_reg_key_tree(hive, f"{subkey}\\{sub}")
                    except OSError:
                        break
            winreg.DeleteKey(hive, subkey)
        except Exception as e:
            raise e

    def _remove_readonly(self, func, path, exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    def _clean_thread(self):
        self._log_sep()
        self._log("=== 开始执行清理 ===", "info")
        errors = []
        for item in list(self._items_to_clean):
            try:
                t = item["type"]
                if t == "file":
                    os.remove(item["path"])
                    self._log(f"  ✅ 删除文件：{item['path']}", "ok")
                elif t == "dir":
                    shutil.rmtree(item["path"], onerror=self._remove_readonly)
                    self._log(f"  ✅ 删除目录：{item['path']}", "ok")
                elif t == "env":
                    with winreg.OpenKey(item["hive_key"], item["subkey"],
                                        0, winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key, item["name"])
                    self._log(f"  ✅ 删除环境变量：{item['name']}", "ok")
                    ctypes.windll.user32.SendMessageTimeoutW(
                        0xFFFF, 0x001A, 0, "Environment", 2, 1000, None)
                elif t == "reg":
                    self._delete_reg_key_tree(item["hive_key"], item["subkey"])
                    self._log(f"  ✅ 删除注册表项：{item['subkey']}", "ok")
            except Exception as e:
                errors.append((item, str(e)))
                self._log(f"  ❌ 失败：{item.get('path', item.get('name', '?'))} — {e}", "err")

        log_path = self._write_log(errors)
        self._log_sep()
        self._log("全部完成 ✅" if not errors else f"完成，{len(errors)} 项失败",
                  "ok" if not errors else "warn")
        self._log(f"报告：{log_path}", "info")
        self.root.after(0, self._clean_done, log_path, errors)

    def _write_log(self, errors):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(DSK, f"OpenClaw_清理报告_{ts}.txt")
        lines = [
            "=" * 60,
            "  OpenClaw Cleaner — 安全清理报告",
            f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60, "",
        ]
        if self.api_keys:
            lines += ["【发现的 API 密钥 — 请立即注销！】", "-" * 40]
            for k, info in self.api_keys.items():
                lines.append(f"  {k:40s}  前缀：{info['masked']}")
            lines += [
                "", "  常用密钥管理地址：",
                "  • Google Gemini  →  https://aistudio.google.com/app/apikey",
                "  • OpenAI         →  https://platform.openai.com/api-keys",
                "  • Anthropic      →  https://console.anthropic.com/settings/keys",
                "  • Groq           →  https://console.groq.com/keys",
                "  • Hugging Face   →  https://huggingface.co/settings/tokens", "",
            ]
        lines += ["【清理项目列表】", "-" * 40]
        for item in self.items:
            t = item["type"]
            if t in ("file", "dir"):
                lines.append(f"  [{t.upper()}] {item['path']}")
            elif t == "env":
                lines.append(f"  [ENV] [{item['hive']}] {item['name']}")
            else:
                lines.append(f"  [REG] {item['subkey']}")
        if errors:
            lines += ["", "【失败项目】", "-" * 40]
            for item, err in errors:
                lines.append(f"  ❌ {item.get('path', item.get('name','?'))} — {err}")
        lines += ["", "=" * 60,
                  "  请确认以上 API 密钥均已注销后，方可安心使用。",
                  "=" * 60]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            self._log(f"  ⚠ 日志保存失败：{e}", "err")
            path = "(保存失败)"
        return path

    def _clean_done(self, log_path, errors):
        self.prog.stop()
        self.btn_scan.configure(state="normal")
        self._status.set("清理完成" if not errors else f"完成（{len(errors)} 项失败）")
        msg = "清理完成！\n\n"
        if self.api_keys:
            msg += "⚠ 请务必登录相关平台注销已发现的 API 密钥！\n\n"
        msg += f"报告已保存到桌面：\n{os.path.basename(log_path)}"
        messagebox.showinfo("清理完成", msg)
        if os.path.isfile(log_path):
            os.startfile(log_path)

    # ─── GoodBye 自删除 ──────────────────────
    def _goodbye(self):
        if not messagebox.askyesno(
            "GoodBye — 卸载 Claw Cleaner",
            "此操作将删除所有 Claw Cleaner 相关的文件和快捷方式，\n"
            "包括程序本身。\n\n"
            "确定要彻底移除 Claw Cleaner 吗？",
            icon="warning",
        ):
            return

        exe_path = os.path.normpath(
            sys.executable if getattr(sys, "frozen", False)
            else os.path.abspath(__file__)
        )

        targets = {exe_path}

        # Desktop copy placed by build.bat
        desktop_exe = os.path.join(DSK, "OpenClaw Cleaner.exe")
        if os.path.isfile(desktop_exe):
            targets.add(os.path.normpath(desktop_exe))

        # Any .lnk / .exe shortcuts on Desktop that mention claw
        name_re = re.compile(r'(open.?claw|claw.?cleaner)', re.IGNORECASE)
        try:
            for name in os.listdir(DSK):
                if name_re.search(name) and name.lower().endswith(('.lnk', '.exe')):
                    targets.add(os.path.join(DSK, name))
        except Exception:
            pass

        # Write self-deleting batch script to TEMP
        bat_lines = ["@echo off", "timeout /t 2 /nobreak > nul"]
        for t in targets:
            bat_lines.append(f'del /f /q "{t}" 2>nul')
        bat_lines.append('del /f /q "%~f0"')

        bat_path = os.path.join(TMP, "_claw_cleaner_goodbye.bat")
        try:
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write("\n".join(bat_lines))
            subprocess.Popen(
                ["cmd", "/c", bat_path],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        except Exception as e:
            messagebox.showerror("错误", f"无法执行自删除脚本：{e}")
            return

        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────
#  入口
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not is_admin():
        ans = ctypes.windll.user32.MessageBoxW(
            0,
            "建议以「管理员」身份运行，以便清理系统级环境变量。\n\n"
            "点击「是」以管理员重新启动，点击「否」以当前权限继续。",
            "OpenClaw Cleaner — 权限提示",
            0x00000024,
        )
        if ans == 6:
            relaunch_as_admin()

    App().run()
