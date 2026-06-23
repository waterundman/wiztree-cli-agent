"""主窗口模块 — Stage 2 (v2.1.0): 控制器拆解后，仅负责 UI 布局和事件绑定。"""
import logging
import customtkinter as ctk
import tkinter.ttk as ttk
from tkinter import filedialog
import threading
import os
from typing import Optional, List
from pathlib import Path

import sys
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.scanner import PathValidator, ScanOptions
from src.analyzer import RuleEngine
from src.models import FileInfo
from src.ui.animations.smooth_progress import SmoothProgressBar, SpinnerLabel
from src.ui.components.skeleton import SkeletonLine
from src.ui.components.virtual_treeview import VirtualTreeview
from src.ui.controllers import ScanController, AnalysisController, FileOperationController
from src.ui.drop_utils import parse_drop_paths, resolve_drop_target

logger = logging.getLogger(__name__)

try:
    from tkinterdnd2 import DND_FILES
    from tkinterdnd2.TkinterDnD import DnDWrapper
    _DND_AVAILABLE = True
except ImportError:
    DND_FILES = None
    DnDWrapper = None
    _DND_AVAILABLE = False


class MainWindow(ctk.CTk):
    """主窗口类 — UI 布局 + 事件绑定，业务逻辑委托给控制器。"""

    # 向后兼容常量（测试引用）
    MAX_SCAN_FILES = 5000
    MAX_DISPLAY_FILES = 500

    def __init__(self):
        super().__init__()
        self.title("WizTree CLI Agent - AI Disk Cleanup")
        self.geometry("1400x900")
        self.minsize(1200, 800)
        self._apply_saved_theme()

        self._style = ttk.Style()
        try:
            from src.ui.themes.modern_theme import ModernTheme as _MT
            _MT.on_theme_change(self._on_theme_changed)
            _MT.apply_ttk_style(self._style)
        except Exception as e:
            logger.debug("主题回调注册失败: %s", e)

        self.validator = PathValidator()
        self.rule_engine = RuleEngine()
        self._llm_router = None
        self.scan_result = None
        self.recommendations = []

        # ---- 控制器 ----
        self._scan_ctrl = ScanController(
            progress_callback=lambda m, f: self.after(0, lambda: self._apply_progress(m, f)),
            status_callback=lambda msg, c: self.after(0, lambda: self.update_status(msg, c)),
            on_batch_ready=lambda n: self.after(0, lambda: self._on_streaming_batch(n)),
            on_scan_complete=lambda f: self.after(0, lambda: self._on_scan_complete_ui(f)),
            on_scan_error=lambda e: self.after(0, lambda: self.show_error(f"Streaming scan failed: {e}")),
            on_start_animation=self._start_scan_animations,
            on_stop_animation=lambda: self.after(0, self.stop_scan_animations),
            on_show_skeleton=self._show_scan_skeleton,
            on_hide_skeleton=lambda: self.after(0, self._hide_scan_skeleton),
        )
        self._analysis_ctrl = AnalysisController(
            rule_engine=self.rule_engine,
            model_var_getter=lambda: self.model_var.get() if hasattr(self, "model_var") else "",
            on_status=lambda m, c: self.after(0, lambda: self.update_status(m, c)),
            on_ai_status=lambda m: self.after(0, lambda: self.update_ai_status(m)),
            on_prepare_streaming=lambda: self.after(0, self._prepare_streaming_ui),
            on_append_text=lambda t: self.after(0, lambda: self._append_ai_stream_text(t)),
            on_finish_streaming=lambda: self.after(0, self._finish_streaming_ui),
            on_show_fallback=lambda: self.after(0, self._show_llm_fallback),
            on_show_error=lambda e: self.after(0, lambda: self._show_llm_error(e)),
            on_update_analysis=lambda: self.after(0, self.update_ai_analysis),
            on_update_action_table=lambda: self.after(0, self.update_action_table),
        )
        self._file_ops_ctrl = FileOperationController(
            on_status=lambda m, c: self.after(0, lambda: self.update_status(m, c)),
            on_confirm=lambda m: self._confirm_deletion(m),
            on_result=lambda m: self.after(0, lambda: self._show_delete_result(m)),
        )

        self.setup_ui()
        self.detect_drives()
        self.bind("<Configure>", self.on_window_resize)
        self._setup_dnd()
        self._setup_keybindings()

    # ================================================================
    # 向后兼容代理属性（测试引用）
    # ================================================================
    @property
    def _file_pool(self):
        return self._scan_ctrl.get_file_pool()

    @_file_pool.setter
    def _file_pool(self, value):
        self._scan_ctrl._file_pool = value

    @property
    def _current_batch(self):
        return self._scan_ctrl.current_batch

    @_current_batch.setter
    def _current_batch(self, value):
        self._scan_ctrl._current_batch = value

    # ================================================================
    # 主题 / DnD / 快捷键
    # ================================================================
    def _apply_saved_theme(self):
        try:
            from src.ui.themes.modern_theme import ModernTheme
            ModernTheme.apply(ModernTheme.get_current())
        except Exception:
            try:
                ctk.set_appearance_mode("dark")
                ctk.set_default_color_theme("blue")
            except Exception:
                pass

    def _on_theme_changed(self, _name: str) -> None:
        try:
            from src.ui.themes.modern_theme import ModernTheme
            ModernTheme.apply_ttk_style(self._style)
        except Exception:
            pass
        try:
            bg = self._style.lookup("Treeview", "background") or "#1e1e2e"
            for attr in ("_scan_skeleton_frame", "_ai_skeleton_frame"):
                frame = getattr(self, attr, None)
                if frame:
                    frame.configure(fg_color=bg)
        except Exception:
            pass

    def _setup_dnd(self):
        if not _DND_AVAILABLE:
            return
        try:
            DnDWrapper(self)
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass

    def _setup_keybindings(self):
        try:
            from src.ui.keybindings import KeyBindings
            KeyBindings.bind_all(self)
        except Exception:
            pass

    def _on_drop(self, event):
        try:
            paths = parse_drop_paths(event.data or "")
            target = resolve_drop_target(paths)
            if not target:
                return
            entry = getattr(self, "scope_entry", None)
            if entry:
                entry.delete(0, "end")
                entry.insert(0, target)
                self.update_status(f"Dropped: {target}", "green")
        except Exception:
            pass

    # ================================================================
    # 快捷键入口
    # ================================================================
    def _start_scan(self):
        btn = getattr(self, "scan_button", None)
        if btn and str(btn.cget("state")) == "disabled":
            return
        self.start_scan()

    def _clear_results(self):
        for name in ("scan_tree", "action_tree"):
            tree = getattr(self, name, None)
            if tree:
                for item in tree.get_children():
                    tree.delete(item)
        self.recommendations = []
        self.scan_result = None
        self._analysis_ctrl.set_recommendations([])
        if hasattr(self, "stats_labels"):
            for k in ("total_files", "total_size", "duration", "recommendations"):
                if k in self.stats_labels:
                    self.stats_labels[k].configure(
                        text="0" if k in ("total_files", "recommendations") else ("0 B" if k == "total_size" else "0.0s"))
        self.update_status("Results cleared", "gray")

    def _cancel_operation(self):
        self.update_status("Operation cancelled", "yellow")

    # ================================================================
    # UI 布局
    # ================================================================
    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 工具栏
        tb = ctk.CTkFrame(self, fg_color="transparent", height=44)
        tb.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="ew")
        tb.grid_propagate(False)
        ctk.CTkLabel(tb, text="WizTree CLI Agent", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(tb, text="Settings", width=120, height=32, command=self.open_settings).pack(side="right", padx=8, pady=6)

        # 左侧配置面板
        self.config_frame = ctk.CTkFrame(self, width=300, corner_radius=10)
        self.config_frame.grid(row=1, column=0, padx=(10, 5), pady=10, sticky="nsew")
        self.config_frame.grid_propagate(False)
        scroll = ctk.CTkScrollableFrame(self.config_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=5)
        ctk.CTkLabel(scroll, text="Configuration", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 15), padx=10)

        self._section(scroll, "Scan Configuration")
        self._input(scroll, "WizTree Path:", "wiztree_path", default="W:\\WizTree\\WizTree64.exe", browse="file")
        self._drive_sel(scroll)
        self._input(scroll, "Deep Search Folder:", "scope_entry", browse="folder")
        self._input(scroll, "Min File Size:", "min_size_entry", placeholder=">100m")
        self._scan_ctrl_ui(scroll)

        self._section(scroll, "LLM Model")
        mf = ctk.CTkFrame(scroll, fg_color="transparent")
        mf.pack(fill="x", padx=10, pady=5)
        self.model_status_label = ctk.CTkLabel(mf, text="Checking API keys...", text_color="gray", anchor="w")
        self.model_status_label.pack(fill="x", pady=(0, 5))
        self.model_var = ctk.StringVar(value="")
        self.model_dropdown = ctk.CTkOptionMenu(mf, values=["(no API key configured)"], variable=self.model_var, height=32, command=self._on_model_selected)
        self.model_dropdown.pack(fill="x")
        self.config_keys_btn = ctk.CTkButton(mf, text="Configure API Keys...", height=28, command=self.open_settings)
        self._refresh_model_selector()

        # 右侧内容区
        cf = ctk.CTkFrame(self, corner_radius=10)
        cf.grid(row=1, column=1, padx=(5, 10), pady=10, sticky="nsew")
        self.tabview = ctk.CTkTabview(cf)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.scan_tab = self.tabview.add("Scan Results")
        self._setup_scan_tab()
        self.ai_tab = self.tabview.add("AI Analysis")
        self._setup_ai_tab()
        self.action_tab = self.tabview.add("File Actions")
        self._setup_action_tab()

    def _section(self, parent, title, icon=""):
        ctk.CTkFrame(parent, height=2, fg_color="gray60").pack(fill="x", padx=10, pady=(15, 5))
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=(5, 10))
        ctk.CTkLabel(f, text=f"{icon} {title}" if icon else title, font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(side="left")

    def _input(self, parent, label, attr, placeholder="", default="", browse=None):
        ff = ctk.CTkFrame(parent, fg_color="transparent")
        ff.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(ff, text=label, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 2))
        if browse:
            row = ctk.CTkFrame(ff, fg_color="transparent")
            row.pack(fill="x")
            entry = ctk.CTkEntry(row, placeholder_text=placeholder, height=32)
            entry.pack(side="left", fill="x", expand=True)
            cmd = (lambda e=entry: self._browse_folder(e)) if browse == "folder" else (lambda e=entry: self._browse_file(e))
            ctk.CTkButton(row, text="Browse...", width=80, command=cmd).pack(side="right", padx=(5, 0))
        else:
            entry = ctk.CTkEntry(ff, placeholder_text=placeholder, height=32)
            entry.pack(fill="x")
        if default:
            entry.insert(0, default)
        setattr(self, attr, entry)

    def _browse_folder(self, entry):
        d = filedialog.askdirectory(title="Select folder to scan")
        if d:
            entry.delete(0, "end"); entry.insert(0, d)

    def _browse_file(self, entry):
        p = filedialog.askopenfilename(title="Select WizTree", filetypes=[("Executable", "*.exe"), ("All", "*.*")])
        if p:
            entry.delete(0, "end"); entry.insert(0, p)

    def _drive_sel(self, parent):
        ff = ctk.CTkFrame(parent, fg_color="transparent")
        ff.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(ff, text="Target Drive:", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 2))
        self.drive_var = ctk.StringVar(value="C:\\")
        self.drive_menu = ctk.CTkOptionMenu(ff, variable=self.drive_var, values=["C:\\"])
        self.drive_menu.pack(fill="x")

    def _scan_ctrl_ui(self, parent):
        self.scan_button = ctk.CTkButton(parent, text="Scan & Analyze", command=self.start_scan, height=40, font=ctk.CTkFont(size=14, weight="bold"))
        self.scan_button.pack(fill="x", padx=10, pady=(15, 5))
        pf = ctk.CTkFrame(parent, fg_color="transparent", height=25)
        pf.pack(fill="x", padx=10, pady=(0, 5))
        pf.pack_propagate(False)
        self.progress_bar = SmoothProgressBar(pf)
        self.progress_bar.pack(fill="x", expand=True)
        self.progress_bar.set(0)
        sf = ctk.CTkFrame(parent, fg_color="transparent")
        sf.pack(fill="x", padx=10, pady=(0, 10))
        self.status_label = ctk.CTkLabel(sf, text="Ready", font=ctk.CTkFont(size=12), text_color="gray", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)
        self.spinner = SpinnerLabel(sf, size=20)
        self.spinner.pack(side="right", padx=(5, 0)); self.spinner.stop()

    # ================================================================
    # 标签页设置
    # ================================================================
    def _setup_scan_tab(self):
        self.stats_frame = ctk.CTkFrame(self.scan_tab, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=10, pady=(10, 5))
        self._build_stats_cards()
        tf = ctk.CTkFrame(self.scan_tab, fg_color="transparent")
        tf.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        cols = ("rank", "path", "size", "modified")
        self.scan_tree = VirtualTreeview(tf, columns=cols, show="headings", height=15)
        for c, t in zip(cols, ("#", "File Path", "Size", "Modified")):
            self.scan_tree.heading(c, text=t)
        for c, w, a in [("rank", 50, "center"), ("path", 600, "w"), ("size", 100, "e"), ("modified", 150, "center")]:
            self.scan_tree.column(c, width=w, anchor=a)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.scan_tree.yview)
        self.scan_tree.configure(yscrollcommand=sb.set)
        self.scan_tree.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self._scan_skeleton_frame = ctk.CTkFrame(tf, fg_color="transparent")
        for _ in range(5):
            SkeletonLine(self._scan_skeleton_frame, width="full").pack(fill="x", padx=4, pady=3)
        self._scan_skeleton_visible = False

    def _build_stats_cards(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        cards = [("Files", "0", "total_files"), ("Total Size", "0 B", "total_size"), ("Duration", "0.0s", "duration"), ("Recommendations", "0", "recommendations")]
        self.stats_labels = {}
        for i, (t, v, k) in enumerate(cards):
            cd = ctk.CTkFrame(self.stats_frame, corner_radius=8, height=70)
            cd.pack(side="left", fill="x", expand=True, padx=(0, 5) if i < 3 else (0, 0))
            cd.pack_propagate(False)
            ctk.CTkLabel(cd, text=t, font=ctk.CTkFont(size=11), text_color="gray70").pack(pady=(10, 2))
            lbl = ctk.CTkLabel(cd, text=v, font=ctk.CTkFont(size=16, weight="bold"))
            lbl.pack(pady=(0, 10))
            self.stats_labels[k] = lbl

    def _setup_ai_tab(self):
        tb = ctk.CTkFrame(self.ai_tab, fg_color="transparent")
        tb.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(tb, text="AI Analysis Results", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(tb, text="Copy", width=80, height=28, command=self.copy_ai_text).pack(side="right")
        tf = ctk.CTkFrame(self.ai_tab, fg_color="transparent")
        tf.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self.ai_text = ctk.CTkTextbox(tf, font=ctk.CTkFont(size=13, family="Consolas"), fg_color="#1e1e2e", text_color="#cdd6f4", border_width=1, border_color="#45475a", corner_radius=8)
        self.ai_text.pack(fill="both", expand=True)
        self.ai_text.insert("1.0", "AI analysis results will appear here...\n\n")
        self.ai_text.configure(state="disabled")
        self._ai_skeleton_frame = ctk.CTkFrame(tf, fg_color="transparent")
        for _ in range(7):
            SkeletonLine(self._ai_skeleton_frame, width="full").pack(fill="x", padx=4, pady=3)
        self._ai_skeleton_visible = False
        self.ai_loading_frame = ctk.CTkFrame(self.ai_tab, fg_color="transparent")
        self.ai_loading_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.ai_spinner = SpinnerLabel(self.ai_loading_frame, size=24)
        self.ai_spinner.pack(side="left", padx=(0, 10))
        self.ai_status_label = ctk.CTkLabel(self.ai_loading_frame, text="", font=ctk.CTkFont(size=12), text_color="gray")
        self.ai_status_label.pack(side="left")
        self.ai_loading_frame.pack_forget()

    def _setup_action_tab(self):
        tb = ctk.CTkFrame(self.action_tab, fg_color="transparent")
        tb.pack(fill="x", padx=10, pady=(10, 5))
        self.select_all_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(tb, text="Select All", variable=self.select_all_var, command=self.toggle_select_all, font=ctk.CTkFont(size=12)).pack(side="left")
        ff = ctk.CTkFrame(tb, fg_color="transparent"); ff.pack(side="right")
        ctk.CTkLabel(ff, text="Risk Filter:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        self.risk_filter_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(ff, variable=self.risk_filter_var, values=["All", "Critical", "High", "Medium", "Low"], width=100, command=self.filter_by_risk).pack(side="left")

        tf = ctk.CTkFrame(self.action_tab, fg_color="transparent")
        tf.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self.action_tree = VirtualTreeview(tf, columns=("select", "path", "size", "reason", "risk"), show="headings", height=15)
        for c, t, w, a in [("select", "", 40, "center"), ("path", "File Path", 400, "w"), ("size", "Size", 80, "e"), ("reason", "Reason", 250, "w"), ("risk", "Risk", 80, "center")]:
            self.action_tree.heading(c, text=t); self.action_tree.column(c, width=w, anchor=a)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.action_tree.yview)
        self.action_tree.configure(yscrollcommand=sb.set)
        self.action_tree.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self.action_tree.bind("<ButtonRelease-1>", self.on_action_tree_click)

        bf = ctk.CTkFrame(self.action_tab, fg_color="transparent")
        bf.pack(fill="x", padx=10, pady=(0, 10))
        inf = ctk.CTkFrame(bf, fg_color="transparent"); inf.pack(side="left", fill="x", expand=True)
        self.selected_label = ctk.CTkLabel(inf, text="0 files selected (0 B)", font=ctk.CTkFont(size=12), text_color="gray")
        self.selected_label.pack(side="left")
        btnf = ctk.CTkFrame(bf, fg_color="transparent"); btnf.pack(side="right")
        self.preview_button = ctk.CTkButton(btnf, text="Preview", width=100, height=32, command=self.preview_selected, state="disabled")
        self.preview_button.pack(side="left", padx=(0, 5))
        self.delete_button = ctk.CTkButton(btnf, text="Delete Selected", width=140, height=32, command=self.delete_selected, fg_color="#c0392b", hover_color="#e74c3c", state="disabled")
        self.delete_button.pack(side="left")
        self.prev_batch_button = ctk.CTkButton(btnf, text="Previous Batch", width=120, height=32, command=self.prev_batch, state="disabled")
        self.prev_batch_button.pack(side="left", padx=(10, 5))
        self.next_batch_button = ctk.CTkButton(btnf, text="Next Batch", width=120, height=32, command=self.next_batch, state="disabled")
        self.next_batch_button.pack(side="left")

    # ================================================================
    # Settings
    # ================================================================
    def open_settings(self):
        import traceback
        try:
            from src.ui.settings_dialog import SettingsDialog
            SettingsDialog(master=self, on_close=self._on_settings_closed)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Settings Error", f"{e}\n\n{traceback.format_exc()}"[:500])

    def _on_settings_closed(self):
        self._apply_saved_theme()
        self._refresh_model_selector()

    def _on_model_selected(self, choice):
        logger.info("LLM model selected: %s", choice)

    def _refresh_model_selector(self):
        def _check():
            available = []
            try:
                from src.utils.credential_store import CredentialStore
                store = CredentialStore()
            except Exception:
                store = None
            if store:
                try:
                    from src.analyzer.llm_router import LLMRouter
                    if not self._llm_router:
                        self._llm_router = LLMRouter()
                    self._analysis_ctrl.set_llm_router(self._llm_router)
                    for name, info in self._llm_router.get_provider_status().items():
                        if info.get("has_api_key"):
                            available.extend(f"{name}: {m}" for m in info.get("models", []))
                except Exception:
                    pass
            def _update():
                try:
                    if not self.winfo_exists(): return
                    if available:
                        self.model_dropdown.configure(values=available); self.model_var.set(available[0])
                        self.model_status_label.configure(text=f"{len(available)} models available", text_color="green")
                        self.config_keys_btn.pack_forget()
                    else:
                        self.model_dropdown.configure(values=["(no API key configured)"]); self.model_var.set("(no API key configured)")
                        self.model_status_label.configure(text="No API keys configured", text_color="orange")
                        self.config_keys_btn.pack(fill="x", pady=(5, 0))
                except Exception:
                    pass
            self.after(0, _update)
        threading.Thread(target=_check, daemon=True).start()

    # ================================================================
    # 窗口事件
    # ================================================================
    def on_window_resize(self, event):
        if event.widget != self: return
        if not hasattr(self, '_last_w'): self._last_w = 0
        w = event.width
        if w == self._last_w: return
        self._last_w = w
        nw = 250 if w < 1300 else (300 if w < 1600 else 350)
        self.after_idle(lambda: self.config_frame.configure(width=nw))

    def detect_drives(self):
        import ctypes
        bm = ctypes.windll.kernel32.GetLogicalDrives()
        drives = [f"{c}:\\" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if bm >> (ord(c) - 65) & 1]
        if drives:
            self.drive_menu.configure(values=drives); self.drive_var.set(drives[0])

    def copy_ai_text(self):
        self.clipboard_clear(); self.clipboard_append(self.ai_text.get("1.0", "end-1c"))
        self.update_status("Copied to clipboard", "green")

    # ================================================================
    # 扫描
    # ================================================================
    def start_scan(self):
        wiztree_path = self.wiztree_path.get().strip()
        if not wiztree_path or not os.path.isfile(wiztree_path):
            self.show_error("WizTree executable not found. Please check the path."); return
        scope = self.scope_entry.get().strip()
        target = scope if (scope and os.path.isdir(scope)) else self.drive_var.get()
        opts = ScanOptions()
        ms = self.min_size_entry.get().strip()
        if ms: opts.min_size = ms
        self._show_ai_skeleton(); self.show_ai_loading(True)
        self._scan_ctrl.scan(target, opts, wiztree_path)

    def _apply_progress(self, msg, files):
        try:
            if self.winfo_exists():
                self.update_status(f"{msg} ({files} files)" if files else msg, "yellow")
        except Exception:
            pass

    def _start_scan_animations(self):
        self.scan_button.configure(state="disabled", text="Scanning...")
        self.progress_bar.start_animation(); self.spinner.start()

    def _on_scan_complete_ui(self, files):
        self.scan_result = self._scan_ctrl.get_scan_result()
        self.update_scan_results()
        self.update_ai_status("Analyzing files...")
        self._analysis_ctrl.analyze(files, self.scan_result)

    def _on_streaming_batch(self, count):
        try:
            if not self.winfo_exists(): return
            self._hide_scan_skeleton()
            pool = self._scan_ctrl.get_file_pool()
            data = [(i, str(fi.path), ScanController.format_size(fi.size), fi.modified_time.strftime("%Y-%m-%d %H:%M") if fi.modified_time else "") for i, fi in enumerate(pool[:500], 1)]
            self.scan_tree.set_data(data); self.scan_tree.refresh()
            if self.stats_labels:
                self.stats_labels["total_files"].configure(text=str(count))
                self.stats_labels["total_size"].configure(text=ScanController.format_size(sum(f.size for f in pool)))
            self.update_status(f"Streaming: {count:,} files loaded...", "yellow")
            self.update_batch_buttons()
        except Exception:
            pass

    def stop_scan_animations(self):
        self.scan_button.configure(state="normal", text="Scan & Analyze")
        self.progress_bar.stop_animation(); self.spinner.stop()

    # ================================================================
    # 分析 UI 辅助
    # ================================================================
    def _prepare_streaming_ui(self):
        try:
            if not self.winfo_exists(): return
            self._hide_ai_skeleton(); self.show_ai_loading(True)
            self.ai_status_label.configure(text="LLM analyzing...", text_color="cyan")
            self.ai_text.configure(state="normal"); self.ai_text.delete("1.0", "end")
            sr = self._scan_ctrl.get_scan_result()
            fp = self._scan_ctrl.get_file_pool()
            ts = ScanController.format_size(sr.total_size) if sr else "N/A"
            tf = sr.total_files if sr else len(fp)
            self.ai_text.insert("end", "=" * 50 + "\n  SCAN SUMMARY\n" + "=" * 50 + f"\n\n  Total files: {tf}\n  Total size: {ts}\n\n")
            self.ai_text.insert("end", "=" * 50 + "\n  LLM ANALYSIS (streaming)\n" + "=" * 50 + "\n\n")
        except Exception:
            pass

    def _append_ai_stream_text(self, text):
        try:
            if not self.winfo_exists(): return
            self.ai_text.configure(state="normal"); self.ai_text.insert("end", text); self.ai_text.see("end")
        except Exception:
            pass

    def _finish_streaming_ui(self):
        try:
            if not self.winfo_exists(): return
            self.show_ai_loading(False)
            recs = self._analysis_ctrl.get_recommendations(); self.recommendations = recs
            self.ai_text.insert("end", "-" * 50 + f"\n  {len(recs)} deletion recommendations\n" + "-" * 50 + "\n")
            self.ai_text.configure(state="disabled")
            if "recommendations" in self.stats_labels:
                self.stats_labels["recommendations"].configure(text=str(len(recs)))
        except Exception:
            pass

    def _show_llm_fallback(self):
        try:
            if self.winfo_exists():
                self.ai_status_label.configure(text="Using rule engine (no LLM)", text_color="orange")
                self.update_status("Using rule engine", "orange")
        except Exception:
            pass

    def _show_llm_error(self, err):
        try:
            if self.winfo_exists():
                self.ai_status_label.configure(text=f"LLM failed, fallback: {err[:60]}", text_color="red")
                self.update_status("LLM failed, using rule engine", "red")
        except Exception:
            pass

    def show_ai_loading(self, show=True):
        if show:
            self.ai_loading_frame.pack(fill="x", padx=10, pady=(0, 10)); self.ai_spinner.start()
        else:
            self.ai_spinner.stop(); self.ai_loading_frame.pack_forget()

    def _show_scan_skeleton(self):
        if not self._scan_skeleton_visible:
            self._scan_skeleton_visible = True
            self._scan_skeleton_frame.place(relx=0, rely=0, relwidth=1, relheight=1); self._scan_skeleton_frame.lift()

    def _hide_scan_skeleton(self):
        if self._scan_skeleton_visible:
            self._scan_skeleton_visible = False; self._scan_skeleton_frame.place_forget()

    def _show_ai_skeleton(self):
        if not self._ai_skeleton_visible:
            self._ai_skeleton_visible = True
            self._ai_skeleton_frame.place(relx=0, rely=0, relwidth=1, relheight=1); self._ai_skeleton_frame.lift()

    def _hide_ai_skeleton(self):
        if self._ai_skeleton_visible:
            self._ai_skeleton_visible = False; self._ai_skeleton_frame.place_forget()

    def update_ai_status(self, msg):
        self.ai_status_label.configure(text=msg); self.update_status(msg, "yellow")

    # ================================================================
    # 结果更新
    # ================================================================
    def update_status(self, msg, color="gray"):
        self.status_label.configure(text=msg, text_color=color)

    def update_scan_results(self):
        self._hide_scan_skeleton()
        for item in self.scan_tree.get_children(): self.scan_tree.delete(item)
        sr = self._scan_ctrl.get_scan_result()
        fp = self._scan_ctrl.get_file_pool()
        if not sr and not fp: return
        files = fp if fp else (sr.files if sr else [])
        total = len(files)
        if sr: self.update_stats_cards()
        elif fp and self.stats_labels:
            self.stats_labels["total_files"].configure(text=str(total))
            self.stats_labels["total_size"].configure(text=ScanController.format_size(sum(f.size for f in fp)))
        data = [(i, str(fi.path), ScanController.format_size(fi.size), fi.modified_time.strftime("%Y-%m-%d %H:%M") if fi.modified_time else "") for i, fi in enumerate(files[:500], 1)]
        self.scan_tree.set_data(data); self.scan_tree.refresh()
        self.update_batch_buttons()
        if self._scan_ctrl.is_streaming():
            self.update_status(f"Streaming: {total:,} files loaded...", "yellow")
        elif total > 500:
            self.update_status(f"Showing 500 of {total:,} files (capped at 5,000)", "orange")

    def update_stats_cards(self):
        sr = self._scan_ctrl.get_scan_result()
        if not sr: return
        self.stats_labels["total_files"].configure(text=str(sr.total_files))
        self.stats_labels["total_size"].configure(text=ScanController.format_size(sr.total_size))
        self.stats_labels["duration"].configure(text=f"{sr.duration_seconds:.1f}s")

    def update_ai_analysis(self):
        self._hide_ai_skeleton(); self.show_ai_loading(False)
        self.recommendations = self._analysis_ctrl.get_recommendations()
        self.stats_labels["recommendations"].configure(text=str(len(self.recommendations)))
        self.ai_text.configure(state="normal"); self.ai_text.delete("1.0", "end")
        sr = self._scan_ctrl.get_scan_result()
        if not sr:
            self.ai_text.insert("1.0", "No scan results available."); self.ai_text.configure(state="disabled"); return
        self.ai_text.insert("end", "=" * 50 + "\n  SCAN SUMMARY\n" + "=" * 50 + f"\n\n  Total files: {sr.total_files}\n  Total size: {ScanController.format_size(sr.total_size)}\n  Duration: {sr.duration_seconds:.1f}s\n\n")
        self.ai_text.insert("end", "=" * 50 + "\n  RULE ENGINE ANALYSIS\n" + "=" * 50 + f"\n\n  Found {len(self.recommendations)} cleanup candidates\n\n")
        if self.recommendations:
            self.ai_text.insert("end", "-" * 50 + "\n  TOP RECOMMENDATIONS\n" + "-" * 50 + "\n\n")
            for i, rec in enumerate(self.recommendations[:20], 1):
                icon = {"critical": "!!!", "high": "!!", "medium": "!", "low": "."}.get(rec.risk_level.value, "")
                self.ai_text.insert("end", f"  #{i} {icon} [{rec.risk_level.value.upper()}]\n     {rec.file.path}\n     Size: {ScanController.format_size(rec.file.size)}\n     Reason: {rec.reason}\n\n")
        self.ai_text.configure(state="disabled")

    def update_action_table(self):
        self.recommendations = self._analysis_ctrl.get_recommendations()
        data = []
        for fi in self._scan_ctrl.get_current_batch_files():
            sz = ScanController.format_size(fi.size)
            rec = next((r for r in self.recommendations if r.file.path == fi.path), None)
            if rec:
                data.append(("☑" if rec.selected else "☐", str(fi.path), sz, rec.reason, rec.risk_level.value))
            else:
                data.append(("☐", str(fi.path), sz, "Not recommended", "N/A"))
        self.action_tree.set_data(data); self.action_tree.refresh()
        self.update_batch_buttons()

    def on_action_tree_click(self, event):
        if self.action_tree.identify_region(event.x, event.y) != "cell": return
        col = self.action_tree.identify_column(event.x)
        item = self.action_tree.identify_row(event.y)
        if not item or col != "#1": return
        vals = list(self.action_tree.item(item, "values"))
        vals[0] = "☑" if vals[0] == "☐" else "☐"
        self.action_tree.item(item, values=vals)
        for rec in self.recommendations:
            if str(rec.file.path) == vals[1]:
                rec.selected = vals[0] == "☑"; break
        self.update_selected_count()

    def toggle_select_all(self):
        sel = self.select_all_var.get()
        for rec in self.recommendations: rec.selected = sel
        data = [("☑" if r.selected else "☐", str(r.file.path), ScanController.format_size(r.file.size), r.reason, r.risk_level.value) for r in self.recommendations]
        self.action_tree.set_data(data); self.action_tree.refresh(); self.update_selected_count()

    def filter_by_risk(self, value):
        data = [("☑" if r.selected else "☐", str(r.file.path), ScanController.format_size(r.file.size), r.reason, r.risk_level.value) for r in self.recommendations if value == "All" or r.risk_level.value.lower() == value.lower()]
        self.action_tree.set_data(data); self.action_tree.refresh()

    def preview_selected(self):
        sel = [str(r.file.path) for r in self.recommendations if r.selected]
        if not sel: return
        txt = "Selected files:\n\n" + "\n".join(f"- {p}" for p in sel[:20])
        if len(sel) > 20: txt += f"\n... and {len(sel) - 20} more"
        from tkinter import messagebox; messagebox.showinfo("Preview", txt)

    def update_selected_count(self):
        cnt = sum(1 for r in self.recommendations if r.selected)
        sz = sum(r.file.size for r in self.recommendations if r.selected)
        self.selected_label.configure(text=f"{cnt} files selected ({ScanController.format_size(sz) if sz else '0 B'})")
        st = "normal" if cnt > 0 else "disabled"
        self.delete_button.configure(state=st); self.preview_button.configure(state=st)

    def _confirm_deletion(self, msg):
        from tkinter import messagebox; return messagebox.askyesno("Confirm Delete", msg, icon="warning")

    def _show_delete_result(self, msg):
        from tkinter import messagebox; messagebox.showinfo("Delete Result", msg)

    def delete_selected(self):
        sel = [(fi, r) for fi in self._scan_ctrl.get_current_batch_files() for r in self.recommendations if r.file.path == fi.path and r.selected]
        if not sel: return
        result = self._file_ops_ctrl.delete_files(sel)
        self._scan_ctrl.remove_deleted_files(result.deleted_paths)
        self._analysis_ctrl.remove_deleted_recommendations(result.deleted_paths)
        self.recommendations = self._analysis_ctrl.get_recommendations()
        if not self.recommendations and self._scan_ctrl.get_file_pool():
            nb = self._scan_ctrl.get_current_batch_files()
            if nb: self._analysis_ctrl.reanalyze_files(nb); self.recommendations = self._analysis_ctrl.get_recommendations()
        self.update_action_table(); self.update_selected_count()

    # ================================================================
    # 批次导航
    # ================================================================
    def prev_batch(self):
        self._scan_ctrl.prev_batch(); self.update_action_table(); self.update_batch_buttons()

    def next_batch(self):
        self._scan_ctrl.next_batch(
            on_wait=lambda: self.update_status("Waiting for streaming data...", "yellow"),
            on_delayed_scan=lambda i: self._scan_ctrl.delayed_scan_batch(i, on_done=lambda: self.after(0, self._on_delayed_scan_done), on_error=lambda e: self.after(0, lambda: self.update_status(f"Delayed scan failed: {e}", "red"))),
        )
        self.update_action_table(); self.update_batch_buttons()

    def _on_delayed_scan_done(self):
        self.recommendations = self._analysis_ctrl.get_recommendations()
        self.update_action_table(); self.update_batch_buttons()
        fp = self._scan_ctrl.get_file_pool()
        tb = (len(fp) - 1) // self._scan_ctrl.batch_size if fp else 0
        self.update_status(f"Batch {self._scan_ctrl.current_batch + 1} loaded ({len(fp)} files, {tb + 1} batches)", "green")

    def update_batch_buttons(self):
        st = self._scan_ctrl.get_batch_button_state()
        self.prev_batch_button.configure(state=st["prev"]); self.next_batch_button.configure(state=st["next"])

    def show_error(self, msg):
        from tkinter import messagebox; messagebox.showerror("Error", msg)

    def format_size(self, sz):
        return ScanController.format_size(sz)
