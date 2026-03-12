#!/usr/bin/env python3
"""
OpenClaw Cleaner (macOS 版本) — 一键清理 OpenClaw 所有本地文件、环境变量及 API 密钥残留
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os, sys, shutil, re, json, datetime, subprocess, threading, stat
from pathlib import Path

# ─────────────────────────────────────────────
#  管理员检查 (macOS)
# ─────────────────────────────────────────────
def is_admin():
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False

# ─────────────────────────────────────────────
#  常量
# ─────────────────────────────────────────────
HOME = str(Path.home())
TMP = "/tmp"

SCAN_DIRS = [
    os.path.join(HOME, ".claude"),
    os.path.join(HOME, "Library", "Application Support", "OpenClaw"),
    os.path.join(HOME, "Library", "Application Support", "openclaw"),
    os.path.join(HOME, "Library", "Application Support", "open-claw"),
    os.path.join(HOME, "Library", "Preferences", "OpenClaw"),
    os.path.join(HOME, "Library", "Caches", "OpenClaw"),
    os.path.join(HOME, "Library", "Saved Application State", "OpenClaw"),
    os.path.join(HOME, "openclaw"),
    os.path.join(HOME, ".openclaw"),
    os.path.join(HOME, "Documents", "openclaw"),
    TMP,
    os.path.join(HOME, ".claude", "plugins"),
    os.path.join(HOME, ".claude", "plans"),
    os.path.join(HOME, ".claude", "skills"),
]

# 常见 shell 配置文件
SHELL_PROFILES = [
    ".zshrc", ".bash_profile", ".bashrc", ".profile", ".zshenv", ".config/fish/config.fish"
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
MONO   = ("Menlo", 12)
UI     = ("-apple-system", 13)
UIB    = ("-apple-system", 13, "bold")

TYPE_ICON = {"file": "📄 文件", "dir": "📁 目录", "env": "🌐 环境变量", "app": "📦 应用"}


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
        self.root.title("OpenClaw Cleaner (macOS)")
        self.root.configure(bg=BG)
        self.root.geometry("1000x800")
        self.root.minsize(800, 600)

        self.items   = []          
        self.api_keys = {}         
        self._iid_idx = {}         
        self._skipped_keys = set() 

        self._build()
        self._style()

    def _build(self):
        r = self.root
        top = tk.Frame(r, bg=RED, height=52)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="⚠  OpenClaw Cleaner for macOS",
                 bg=RED, fg="white", font=("-apple-system", 18, "bold")
                 ).pack(side="left", padx=20)
        badge_text = "  管理员模式 (Root)  " if is_admin() else "  普通用户权限  "
        badge_fg   = GREEN if is_admin() else AMBER
        tk.Label(top, text=badge_text, bg=RED, fg=badge_fg, font=UIB
                 ).pack(side="right", padx=20)

        content = tk.Frame(r, bg=BG)
        content.pack(fill="both", expand=True, padx=14, pady=(10, 0))

        self._build_api_panel(content)

        left = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        self._build_log(left)

        sep_bar = tk.Frame(left, bg="#1e1e32", height=28)
        sep_bar.pack(fill="x", pady=(8, 0))
        sep_bar.pack_propagate(False)
        tk.Label(sep_bar, text="待清理文件列表",
                 bg="#1e1e32", fg=DIM, font=UIB,
                 anchor="w").pack(side="left", padx=10, pady=4)
        tk.Label(sep_bar,
                 text="双击→预览/打开  |  空格→切换勾选  |  右键/双指→更多",
                 bg="#1e1e32", fg=DIM, font=("-apple-system", 11),
                 anchor="w").pack(side="left", padx=6)
        self._count_var = tk.StringVar(value="")
        tk.Label(sep_bar, textvariable=self._count_var,
                 bg="#1e1e32", fg=AMBER, font=UIB,
                 anchor="e").pack(side="right", padx=10)

        self._build_tree(left)
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
        self.tree.tag_configure("app",  background="#1e1428", foreground="#ddaaff")

        self.tree.bind("<Double-1>",  self._on_double)
        self.tree.bind("<Return>",    self._on_double)
        self.tree.bind("<Button-2>",  self._on_right)  # macOS trackpad/mouse right click is usually Button-2 or 3
        self.tree.bind("<Button-3>",  self._on_right)
        self.tree.bind("<space>",     self._toggle_selected)
        self.tree.bind("<Button-1>",  self._on_click)

        self.menu = tk.Menu(self.root, tearoff=0,
                            bg=PANEL, fg=FG,
                            activebackground=RED, activeforeground="white",
                            relief="flat", bd=1)
        self.menu.add_command(label="☐  跳过所选项目（不清理）", command=self._skip_selected)
        self.menu.add_command(label="☑  恢复所选项目（加入清理）", command=self._restore_selected)
        self.menu.add_separator()
        self.menu.add_command(label="📂  在 Finder 中显示", command=self._menu_explorer)
        self.menu.add_command(label="🔍  预览内容", command=self._menu_preview)
        self.menu.add_separator()
        self.menu.add_command(label="🗑  从清理列表移除", command=self._menu_remove)

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
        tk.Button(top_frame, text="↻ 刷新", bg="#2a2a4e", fg=FG, font=("-apple-system", 11),
                  command=self._refresh_api_keys_check, relief="flat", cursor="hand2",
                  padx=6, pady=2).pack(side="right")

        tk.Label(panel,
                 text="删除文件前，请务必到对应\n云端控制台注销以下密钥！",
                 bg=PANEL, fg=DIM, font=("-apple-system", 12),
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

        def _on_mousewheel(event):
            try:
                if self.api_scrollbar.get() == (0.0, 1.0): return
                delta = event.delta
                if sys.platform == "darwin": scroll_units = int(-1 * delta)
                else: scroll_units = int(-1 * (delta / 120))

                if scroll_units < 0 and self.api_canvas.yview()[0] <= 0: return
                if scroll_units > 0 and self.api_canvas.yview()[1] >= 1: return
                    
                self.api_canvas.yview_scroll(scroll_units, "units")
            except Exception:
                pass
        
        self.api_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        tk.Label(self.key_frame,
                 text="尚未扫描\n请先点击「开始扫描」",
                 bg=PANEL, fg=DIM, font=("-apple-system", 12),
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
                    relief="flat", font=("-apple-system", 12, "bold"))
        s.map("Treeview",
              background=[("selected", "#2a2a5e")],
              foreground=[("selected", "white")])

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
        self._log("=== 开始扫描 macOS 残留 ===", "info")
        self._log_sep()

        self._log("【1/3】扫描用户目录及缓存文件…", "info")
        self._scan_files()
        self._log_sep()

        self._log("【2/3】扫描 Shell 环境变量文件…", "info")
        self._scan_shell_profiles()
        self._log_sep()

        self._log("【3/3】扫描 /Applications 等应用残留…", "info")
        self._scan_applications()
        self._log_sep()

        nf = sum(1 for i in self.items if i["type"] in ("file", "dir", "app"))
        ne = sum(1 for i in self.items if i["type"] == "env")
        self._log(f"完成：{nf} 个文件/目录/应用，{ne} 个环境变量相关条目，"
                  f"{len(self.api_keys)} 个发现的 API 密钥", "ok")

        self.root.after(0, self._refresh_api_panel)
        self.root.after(0, self._fill_tree)
        self.root.after(0, self._scan_done)

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
                        if not is_claw and base == os.path.join(HOME, ".claude"):
                            is_claw = self._has_claw_content(full)
                        if is_claw:
                            kind = "dir" if os.path.isdir(full) else "file"
                            self.items.append({"type": kind, "path": full})
                            self._log(f"  {'📁' if kind=='dir' else '📄'} {full}", "warn")
                            if kind == "file" and self._is_config(name):
                                self._extract_keys(full)
            except PermissionError:
                self._log(f"  ⛔ 无权限：{base}", "err")

        # TMP 目录单独扫名称
        if os.path.isdir(TMP):
            try:
                for name in os.listdir(TMP):
                    if CLAW_RE.search(name):
                        full = os.path.join(TMP, name)
                        kind = "dir" if os.path.isdir(full) else "file"
                        self.items.append({"type": kind, "path": full})
                        self._log(f"  {'📁' if kind=='dir' else '📄'} {full}", "warn")
            except Exception as e:
                self._log(f"  ⛔ TMP 读取失败：{e}", "err")

    def _has_claw_content(self, path):
        if not os.path.isfile(path): return False
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return CLAW_RE.search(f.read(8192)) is not None
        except Exception:
            return False

    def _is_config(self, name):
        exts = {".env", ".cfg", ".ini", ".json", ".yaml", ".yml", ".toml", ".conf", ".config"}
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
        if len(value) < 6: return
        masked = value[:6] + "*" * min(len(value) - 6, 20) + "…"
        self.api_keys[name] = {"masked": masked, "source": source, "type": t}
        self._log(f"  🔑 密钥 {name} = {masked}", "key")

    def _scan_shell_profiles(self):
        for p in SHELL_PROFILES:
            path = os.path.join(HOME, p)
            if not os.path.isfile(path): continue
            self._log(f"  → 检查 {p}", "dim")
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                
                bad_lines = []
                for idx, line in enumerate(lines):
                    if not line.strip() or line.strip().startswith('#'): continue
                    
                    found = False
                    if CLAW_RE.search(line):
                        found = True
                    else:
                        for k in KNOWN_KEYS:
                            if k in line:
                                found = True
                                break
                    if found:
                        bad_lines.append((idx, line))
                        self._log(f"    🌐 {p} -> {line.strip()[:60]}...", "warn")
                        
                        m_str = line.strip()
                        if 'export ' in m_str:
                            parts = m_str.split('export ', 1)[1].split('=', 1)
                            if len(parts) == 2:
                                kname = parts[0].strip()
                                kraw = parts[1].strip("'\"")
                                if any(wk in kname for wk in KNOWN_KEYS):
                                    self._save_key(kname, kraw, path, "env")

                if bad_lines:
                    self.items.append({
                        "type": "env",
                        "path": path,
                        "name": f"清理 {p} 中的环境配置",
                        "bad_lines": bad_lines
                    })
            except PermissionError:
                self._log(f"    ⛔ 无权限读取 {path}", "err")
            except Exception as e:
                self._log(f"    ⛔ 解析失败 {path}: {e}", "err")
        
        if not any(i["type"] == "env" for i in self.items):
            self._log("  ✅ 未发现终端环境变量配置污染", "ok")

    def _scan_applications(self):
        apps = ["/Applications", os.path.join(HOME, "Applications")]
        found = False
        for adir in apps:
            if not os.path.isdir(adir): continue
            try:
                for app in os.listdir(adir):
                    if CLAW_RE.search(app):
                        full = os.path.join(adir, app)
                        self.items.append({"type": "app", "path": full})
                        self._log(f"  📦 发现应用：{full}", "warn")
                        found = True
            except Exception:
                pass
        if not found:
            self._log("  ✅ 未发现 OpenClaw 应用程序", "ok")


    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self._iid_idx.clear()
        for idx, item in enumerate(self.items):
            t = item["type"]
            path = item.get("path", "")
            if t in ("file", "dir", "app"):
                name   = os.path.basename(path)
                detail = os.path.dirname(path)
                size   = "<目录/应用>" if t in ("dir", "app") else (
                    fmt_size(os.path.getsize(path)) if os.path.exists(path) else "—"
                )
            elif t == "env":
                name   = item["name"]
                detail = path
                size   = f"{len(item['bad_lines'])} 项"
            else:
                name = detail = size = "—"

            key = self._item_key(item)
            cb = "☐" if key in self._skipped_keys else "☑"
            iid = self.tree.insert("", "end", values=(cb, TYPE_ICON.get(t, t), name, detail, size), tags=(t,))
            self._iid_idx[iid] = idx

        self._update_count()

    def _selected(self):
        focused = self.tree.focus()
        iid = focused if focused else (self.tree.selection() or [None])[0]
        if not iid: return None
        idx = self._iid_idx.get(iid)
        if idx is None or idx >= len(self.items): return None
        return self.items[idx]

    def _item_key(self, item):
        return item.get("path", item.get("name", ""))

    def _update_count(self):
        total = len(self.items)
        checked = sum(1 for item in self.items if self._item_key(item) not in self._skipped_keys)
        if total: self._count_var.set(f"共 {total} 项  ·  已勾选 {checked} 项")
        else: self._count_var.set("")

    def _refresh_checkboxes(self):
        for iid, idx in self._iid_idx.items():
            key = self._item_key(self.items[idx])
            cb = "☐" if key in self._skipped_keys else "☑"
            vals = list(self.tree.item(iid, "values"))
            if vals:
                vals[0] = cb
                self.tree.item(iid, values=vals)
        self._update_count()
        checked = sum(1 for item in self.items if self._item_key(item) not in self._skipped_keys)
        if self.btn_clean["state"] != "disabled" or checked > 0:
            try:
                self.btn_clean.configure(state="normal" if checked > 0 else "disabled")
            except Exception: pass

    def _skip_selected(self):
        for iid in self.tree.selection():
            idx = self._iid_idx.get(iid)
            if idx is not None: self._skipped_keys.add(self._item_key(self.items[idx]))
        self._refresh_checkboxes()

    def _restore_selected(self):
        for iid in self.tree.selection():
            idx = self._iid_idx.get(iid)
            if idx is not None: self._skipped_keys.discard(self._item_key(self.items[idx]))
        self._refresh_checkboxes()

    def _toggle_selected(self, _=None):
        sel = self.tree.selection()
        if not sel: return
        any_checked = any(self._item_key(self.items[self._iid_idx[iid]]) not in self._skipped_keys for iid in sel if self._iid_idx.get(iid) is not None)
        if any_checked: self._skip_selected()
        else: self._restore_selected()

    def _select_all(self):
        self._skipped_keys.clear()
        self._refresh_checkboxes()

    def _on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        col = self.tree.identify_column(event.x)
        if region == "cell" and col == "#1":
            iid = self.tree.identify_row(event.y)
            if iid:
                idx = self._iid_idx.get(iid)
                if idx is not None:
                    key = self._item_key(self.items[idx])
                    if key in self._skipped_keys: self._skipped_keys.discard(key)
                    else: self._skipped_keys.add(key)
                    self._refresh_checkboxes()
                return "break"

    def _on_double(self, _=None):
        item = self._selected()
        if not item: return
        t = item["type"]
        if t in ("file", "env"):
            self._preview_file(item["path"])
        elif t in ("dir", "app"):
            try: subprocess.run(["open", item["path"]])
            except: pass

    def _on_right(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection(): self.tree.selection_set(row)
        item = self._selected()
        if not item: return
        t = item["type"]
        has_sel = bool(self.tree.selection())
        self.menu.entryconfigure(0, state="normal" if has_sel else "disabled")
        self.menu.entryconfigure(1, state="normal" if has_sel else "disabled")
        self.menu.entryconfigure(3, state="normal" if t in ("file", "dir", "app", "env") else "disabled")
        self.menu.entryconfigure(4, state="normal" if t in ("file", "env") else "disabled")
        self.menu.tk_popup(event.x_root, event.y_root)

    def _menu_explorer(self):
        item = self._selected()
        if not item: return
        path = item["path"]
        try: subprocess.run(["open", "-R", str(path)])
        except Exception as e: messagebox.showerror("错误", str(e))

    def _menu_preview(self):
        item = self._selected()
        if item and item["type"] in ("file", "env"):
            self._preview_file(item["path"])

    def _menu_remove(self):
        sel = self.tree.selection()
        if not sel: return
        if not messagebox.askyesno("移除确认", f"从清理列表彻底移除所选？"): return
        indices = sorted((self._iid_idx[iid] for iid in sel if self._iid_idx.get(iid) is not None), reverse=True)
        for idx in indices:
            self._skipped_keys.discard(self._item_key(self.items[idx]))
            self.items.pop(idx)
        self._fill_tree()
        n = len(self.items)
        self._status.set(f"扫描完成，共 {n} 项待清理")
        if n == 0: self.btn_clean.configure(state="disabled")

    def _preview_file(self, path):
        MAX = 128 * 1024
        try:
            size = os.path.getsize(path)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(MAX)
            if size > MAX: content += f"\n\n… (仅显示前 {MAX//1024} KB)"
        except Exception as e:
            messagebox.showerror("读取失败", str(e)); return
        show_preview(self.root, f"预览 ({os.path.basename(path)})", content)

    def _refresh_api_keys_check(self):
        still_exists = {}
        for kname, info in list(self.api_keys.items()):
            t = info["type"]
            src = info["source"]
            if os.path.isfile(src):
                try:
                    with open(src, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    search_key = kname.split(".")[-1]
                    if search_key.upper() in content.upper():
                        still_exists[kname] = info
                except Exception: pass
        
        removed = len(self.api_keys) - len(still_exists)
        self.api_keys = still_exists
        self._refresh_api_panel()
        if removed > 0: messagebox.showinfo("刷新完成", f"已刷新。有 {removed} 个 API 密钥已被清理。\n当前剩余 {len(self.api_keys)} 个。")
        else: messagebox.showinfo("刷新完成", f"所有（{len(self.api_keys)} 个） API 密钥仍存在。")

    def _refresh_api_panel(self):
        for w in self.key_frame.winfo_children(): w.destroy()
        if not self.api_keys:
            tk.Label(self.key_frame, text="✅ 未发现 API 密钥残留", bg=PANEL, fg=GREEN, font=UIB).pack(pady=20)
            self.key_frame.update_idletasks()
            self.api_canvas.configure(scrollregion=self.api_canvas.bbox("all"))
            return

        def open_src(event, src):
            if os.path.exists(src): subprocess.Popen(["open", "-R", str(src)])
            else: messagebox.showerror("未找到", "该文件已不存在。")

        for kname, info in self.api_keys.items():
            card = tk.Frame(self.key_frame, bg="#1f1500", highlightthickness=1, highlightbackground=AMBER, cursor="hand2")
            card.pack(fill="x", pady=3)
            
            lbl1 = tk.Label(card, text=kname, bg="#1f1500", fg=AMBER, font=("-apple-system", 11, "bold"), anchor="w", cursor="hand2")
            lbl1.pack(fill="x", padx=8, pady=(5, 0))
            lbl2 = tk.Label(card, text=info["masked"], bg="#1f1500", fg=FG, font=("Menlo", 11), anchor="w", cursor="hand2")
            lbl2.pack(fill="x", padx=8, pady=(0, 5))
            
            handler = lambda e, s=info["source"]: open_src(e, s)
            card.bind("<Button-1>", handler)
            lbl1.bind("<Button-1>", handler)
            lbl2.bind("<Button-1>", handler)

        tk.Frame(self.key_frame, bg="#2a2a3e", height=1).pack(fill="x", pady=(8, 4))
        tk.Label(self.key_frame, text="⚠ 请登录云端平台吊销以上密钥！", bg=PANEL, fg=RED, font=("-apple-system", 12, "bold"), justify="center").pack(pady=(4, 10))

        self.key_frame.update_idletasks()
        self.api_canvas.configure(scrollregion=self.api_canvas.bbox("all"))

    def _scan_done(self):
        self.prog.stop()
        n = len(self.items)
        checked = sum(1 for item in self.items if self._item_key(item) not in self._skipped_keys)
        if n:
            self._status.set(f"扫描完成，共 {n} 项（已勾选 {checked} 项）")
            self.btn_clean.configure(state="normal" if checked > 0 else "disabled")
        else:
            self._status.set("未发现 OpenClaw 残留，系统干净 ✅")
        self.btn_scan.configure(state="normal")

    def _remove_readonly(self, func, path, exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception: pass

    def _start_clean(self):
        items = [item for item in self.items if self._item_key(item) not in self._skipped_keys]
        if not items: return
        if self.api_keys:
            if not messagebox.askyesno("⚠ API 密钥报警", "发现 API 密钥！\n请务必先到对应平台注销 / 吊销这些密钥！\n\n确认已吊销后继续？", icon="warning"): return
        if not messagebox.askyesno("确认清理", f"即将删除 {len(items)} 个条目。\n此操作不可撤销！是否继续？", icon="warning"): return
        self._items_to_clean = items
        self.btn_scan.configure(state="disabled")
        self.btn_clean.configure(state="disabled")
        self.prog.start(12)
        self._status.set("正在清理…")
        threading.Thread(target=self._clean_thread, daemon=True).start()

    def _clean_thread(self):
        self._log_sep()
        self._log("=== 开始执行清理 ===", "info")
        errors = []
        for item in list(self._items_to_clean):
            try:
                t = item["type"]
                p = item["path"]
                if t == "file":
                    os.remove(p)
                    self._log(f"  ✅ 删除文件：{p}", "ok")
                elif t in ("dir", "app"):
                    shutil.rmtree(p, onerror=self._remove_readonly)
                    self._log(f"  ✅ 删除目录/应用：{p}", "ok")
                elif t == "env":
                    bad_lines = {idx for idx, _ in item["bad_lines"]}
                    with open(p, "r", encoding="utf-8") as f: lines = f.readlines()
                    with open(p, "w", encoding="utf-8") as f:
                        for i, l in enumerate(lines):
                            if i not in bad_lines: f.write(l)
                    self._log(f"  ✅ 清理环境变量配置：{p}", "ok")
            except Exception as e:
                errors.append((item, str(e)))
                self._log(f"  ❌ 失败：{item.get('name', '?')} — {e}", "err")

        self._log_sep()
        self._log("清理完成 ✅" if not errors else f"完成，{len(errors)} 项失败", "ok" if not errors else "warn")
        self.root.after(0, self._clean_done, errors)

    def _clean_done(self, errors):
        self.prog.stop()
        self.btn_scan.configure(state="normal")
        self._status.set("清理完成" if not errors else f"完成（{len(errors)} 项失败）")
        msg = "清理完成！\n\n如果清理了包含环境变量的 Shell 配置文件，\n建议重新打开终端或执行 source 命令生效。"
        messagebox.showinfo("清理完成", msg)

    def _goodbye(self):
        if not messagebox.askyesno("GoodBye — 卸载应用", "确定要彻底删除 OpenClaw Cleaner 自己吗？\n这是不可逆操作！"): return

        exe_path = os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
        if '.app/Contents/MacOS' in exe_path:
            target = exe_path.split('.app/Contents/MacOS')[0] + '.app'
        else:
            target = exe_path

        script = [
            "#!/bin/bash",
            "sleep 1",
            f"rm -rf \"{target}\"",
            f"rm -f \"$0\""
        ]
        sh_path = "/tmp/_clawcleaner_goodbye.sh"
        try:
            with open(sh_path, "w") as f: f.write("\n".join(script))
            os.chmod(sh_path, 0o755)
            # macOS nohup bg process to delete after we exit
            subprocess.Popen(["nohup", sh_path], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sys.exit(0)
        except Exception as e:
            messagebox.showerror("错误", f"无法执行自删除脚本：{e}")

if __name__ == "__main__":
    App().root.mainloop()