"""主窗口模块"""
import logging
import customtkinter as ctk
import tkinter.ttk as ttk
from tkinter import filedialog
import threading
import os
from typing import Optional, List, Dict, Any
from pathlib import Path

# 添加src到路径（仅源码运行；PyInstaller 已自动处理）
import sys
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.scanner import WizTreeScanner, PathValidator, ScanOptions
from src.analyzer import RuleEngine
from src.models import FileInfo, ScanResult
from src.ui.animations.smooth_progress import SmoothProgressBar, SpinnerLabel
from src.ui.components.skeleton import SkeletonWidget, SkeletonLine
from src.ui.components.virtual_treeview import VirtualTreeview

logger = logging.getLogger(__name__)

# Stage 4 (v1.2.0): tkinterdnd2 拖放支持 — 优雅降级
try:
    from tkinterdnd2 import DND_FILES  # type: ignore
    from tkinterdnd2.TkinterDnD import DnDWrapper  # type: ignore
    _DND_AVAILABLE = True
except ImportError:
    DND_FILES = None  # type: ignore
    DnDWrapper = None  # type: ignore
    _DND_AVAILABLE = False
    logger.warning(
        "tkinterdnd2 不可用 — 拖放支持已禁用 (Stage 4 优雅降级, 其他功能正常)"
    )


class MainWindow(ctk.CTk):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.title("WizTree CLI Agent - AI Disk Cleanup")
        self.geometry("1400x900")
        self.minsize(1200, 800)

        # Stage 4 (v1.2.0): 应用保存的主题 (失败时回退 dark/blue)
        self._apply_saved_theme()

        # Stage 3 (v1.3.0): 注册主题切换回调
        self._style = ttk.Style()
        try:
            from src.ui.themes.modern_theme import ModernTheme as _MT
            _MT.on_theme_change(self._on_theme_changed)
            _MT.apply_ttk_style(self._style)
        except Exception as e:  # pragma: no cover
            logger.debug("主题回调注册失败: %s", e)

        # 初始化组件
        self.scanner = None
        self.validator = PathValidator()
        self.rule_engine = RuleEngine()
        self.scan_result = None
        self.recommendations = []
        self._llm_router = None
        
        # 文件池：存储扫描结果，用于动态调整显示数量
        self._file_pool = []  # 所有扫描结果（按大小排序）
        self._display_count = 50  # 当前显示的文件数量
        self._batch_size = 50  # 每批显示的文件数量
        self._current_batch = 0  # 当前批次（从0开始）

        # 初始化UI
        self.setup_ui()

        # 检测可用磁盘
        self.detect_drives()

        # 绑定窗口缩放事件
        self.bind("<Configure>", self.on_window_resize)

        # Stage 4 (v1.2.0): DnD + 键盘快捷键（在 UI 完成后挂载）
        self._setup_dnd()
        self._setup_keybindings()

    # ----------------------------------------------------------------
    # Stage 4: 主题 / DnD / 快捷键 辅助方法
    # ----------------------------------------------------------------
    def _apply_saved_theme(self):
        """应用 ConfigLoader 中持久化的主题；失败时回退 dark/blue。"""
        try:
            from src.ui.themes.modern_theme import ModernTheme
            ModernTheme.apply(ModernTheme.get_current())
        except Exception as e:
            logger.debug("ModernTheme.apply 失败, 回退默认: %s", e)
            try:
                ctk.set_appearance_mode("dark")
                ctk.set_default_color_theme("blue")
            except Exception:  # pragma: no cover
                logger.warning("Fallback theme apply failed", exc_info=True)

    def _on_theme_changed(self, theme_name: str) -> None:
        """Stage 3 (v1.3.0): 主题切换回调 — 更新 ttk 样式和骨架屏颜色。"""
        try:
            from src.ui.themes.modern_theme import ModernTheme
            ModernTheme.apply_ttk_style(self._style)
        except Exception as e:  # pragma: no cover
            logger.debug("ttk 样式更新失败: %s", e)

        # 更新骨架屏颜色（如果存在）
        try:
            skeleton_bg = self._style.lookup("Treeview", "background") or "#1e1e2e"
            for attr in ("_scan_skeleton_frame", "_ai_skeleton_frame"):
                frame = getattr(self, attr, None)
                if frame is not None:
                    frame.configure(fg_color=skeleton_bg)
        except Exception as e:  # pragma: no cover
            logger.debug("骨架屏颜色更新失败: %s", e)

    def _setup_dnd(self):
        """Stage 4: 集成 tkinterdnd2 — 在主窗口注册 file drop target。"""
        if not _DND_AVAILABLE:
            return
        try:
            # DnDWrapper 把 self.tk 转换为支持 tkdnd 的子类，
            # 并为 self 添加 drop_target_register / dnd_bind 方法。
            DnDWrapper(self)
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
        except Exception as e:  # pragma: no cover
            logger.debug("DnD 初始化失败: %s", e)

    def _setup_keybindings(self):
        """Stage 4: 注册 5 个键盘快捷键（Ctrl+S/R/L/, + Escape）。"""
        try:
            from src.ui.keybindings import KeyBindings
            KeyBindings.bind_all(self)
        except Exception as e:  # pragma: no cover
            logger.debug("KeyBindings 注册失败: %s", e)

    def _on_drop(self, event):
        """Stage 4: <<Drop>> 事件处理 — 解析拖入的路径，填入 scope_entry。"""
        try:
            data = event.data
            if not data:
                return
            paths = self._parse_drop_paths(data)
            if not paths:
                return
            target = self._resolve_drop_target(paths)
            if not target:
                return
            scope_entry = getattr(self, "scope_entry", None)
            if scope_entry is None:
                return
            try:
                scope_entry.delete(0, "end")
                scope_entry.insert(0, target)
            except Exception:  # pragma: no cover
                logger.warning("DnD scope entry update failed", exc_info=True)
            if hasattr(self, "update_status"):
                self.update_status(f"📂 Dropped: {target}", "green")
        except Exception as e:  # pragma: no cover
            logger.debug("Drop 处理失败: %s", e)

    @staticmethod
    def _parse_drop_paths(data: str) -> List[str]:
        """
        解析 tkdnd 的 drop data 字符串为路径列表。

        tkdnd 格式：多个路径用空格分隔；含空格的路径用 ``{ }`` 包裹。
        例子：``{C:\\path with space} C:\\other C:\\file.txt``
        """
        paths: List[str] = []
        cur = ""
        in_brace = False
        for ch in data:
            if ch == "{":
                in_brace = True
                cur = ""
            elif ch == "}":
                if in_brace and cur:
                    paths.append(cur)
                in_brace = False
                cur = ""
            elif ch == " " and not in_brace:
                if cur:
                    paths.append(cur)
                    cur = ""
            else:
                cur += ch
        if cur:
            paths.append(cur)
        return [p for p in paths if p]

    @staticmethod
    def _resolve_drop_target(paths: List[str]) -> Optional[str]:
        """
        从多个拖入路径解析单一目标：
            - 单个目录 → 该目录
            - 单个文件 → 父目录
            - 多个路径 → 公共父目录
        """
        if not paths:
            return None
        if len(paths) == 1:
            p = paths[0]
            if os.path.isdir(p):
                return p
            parent = os.path.dirname(p)
            return parent or p
        try:
            common = os.path.commonpath(paths)
            return common if common else paths[0]
        except ValueError:
            return paths[0] if paths else None

    # ----------------------------------------------------------------
    # Stage 4: Ctrl+S / Ctrl+L / Escape 调用的入口方法
    # （keybindings.py 用 hasattr 探测；v1.1.0 无这些方法会被优雅跳过）
    # ----------------------------------------------------------------
    def _start_scan(self):
        """Ctrl+S: 启动扫描（与公开 start_scan 同义，但跳过重复点击）。"""
        scan_btn = getattr(self, "scan_button", None)
        if scan_btn is not None:
            try:
                state = str(scan_btn.cget("state"))
                if state == "disabled":
                    return
            except Exception:  # pragma: no cover
                logger.warning("Scan button state check failed", exc_info=True)
        self.start_scan()

    def _clear_results(self):
        """Ctrl+L: 清空所有结果表与缓存的 scan_result。"""
        for tree_name in ("scan_tree", "action_tree"):
            tree = getattr(self, tree_name, None)
            if tree is None:
                continue
            try:
                for item in tree.get_children():
                    tree.delete(item)
            except Exception:  # pragma: no cover
                logger.warning("Tree delete items failed", exc_info=True)
        self.recommendations = []
        self.scan_result = None
        if hasattr(self, "stats_labels"):
            try:
                for key in ("total_files", "total_size", "duration", "recommendations"):
                    if key in self.stats_labels:
                        self.stats_labels[key].configure(
                            text=("0" if key in ("total_files", "recommendations")
                                  else ("0 B" if key == "total_size" else "0.0s"))
                        )
            except Exception:  # pragma: no cover
                logger.warning("Stats labels update failed", exc_info=True)
        if hasattr(self, "update_status"):
            self.update_status("Results cleared", "gray")

    def _cancel_operation(self):
        """
        Escape: 取消当前操作（占位 — v1.1.0 无 active cancel 钩子）。
        """
        if hasattr(self, "update_status"):
            self.update_status("Operation cancelled (no active op)", "yellow")
        
    def setup_ui(self):
        """设置UI布局"""
        # 配置网格权重
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ========== 顶部工具栏（Stage 2 新增：⚙️ Settings 入口）==========
        self.toolbar = ctk.CTkFrame(self, fg_color="transparent", height=44)
        self.toolbar.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="ew")
        self.toolbar.grid_propagate(False)

        # 左侧：应用标题
        ctk.CTkLabel(
            self.toolbar,
            text="🧙 WizTree CLI Agent",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=8, pady=8)

        # 右侧：⚙️ Settings 齿轮按钮（Stage 2）
        self.settings_button = ctk.CTkButton(
            self.toolbar,
            text="⚙️ Settings",
            width=120,
            height=32,
            command=self.open_settings,
        )
        self.settings_button.pack(side="right", padx=8, pady=6)

        # ========== 左侧配置面板 ==========
        self.config_frame = ctk.CTkFrame(self, width=300, corner_radius=10)
        self.config_frame.grid(row=1, column=0, padx=(10, 5), pady=10, sticky="nsew")
        self.config_frame.grid_propagate(False)
        
        # 创建可滚动的配置面板
        self.config_scroll = ctk.CTkScrollableFrame(self.config_frame, fg_color="transparent")
        self.config_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 配置面板标题
        ctk.CTkLabel(
            self.config_scroll, 
            text="⚙️ Configuration",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(10, 15), padx=10)
        
        # ========== 扫描配置分组 ==========
        self.create_section_header(self.config_scroll, "Scan Configuration", "🔍")
        
        # WizTree路径
        self.create_input_field(self.config_scroll, "WizTree Path:", "wiztree_path", 
                               placeholder="W:\\WizTree\\WizTree64.exe", default="W:\\WizTree\\WizTree64.exe",
                               browse_type="file")
        
        # 目标磁盘
        self.create_drive_selector(self.config_scroll)
        
        # 深度检索文件夹
        self.create_input_field(self.config_scroll, "Deep Search Folder:", "scope_entry",
                               placeholder="e.g. C:\\Users\\you\\AppData",
                               browse_type="folder")
        
        # 最小文件大小
        self.create_input_field(self.config_scroll, "Min File Size:", "min_size_entry",
                               placeholder=">100m")
        
        # 扫描按钮和进度区域
        self.create_scan_controls(self.config_scroll)
        
        # LLM Model Selector
        self.create_section_header(self.config_scroll, "LLM Model", "🤖")

        model_frame = ctk.CTkFrame(self.config_scroll, fg_color="transparent")
        model_frame.pack(fill="x", padx=10, pady=5)

        self.model_status_label = ctk.CTkLabel(
            model_frame, text="Checking API keys...",
            text_color="gray", anchor="w"
        )
        self.model_status_label.pack(fill="x", pady=(0, 5))

        self.model_var = ctk.StringVar(value="")
        self.model_dropdown = ctk.CTkOptionMenu(
            model_frame,
            values=["(no API key configured)"],
            variable=self.model_var,
            height=32,
            command=self._on_model_selected
        )
        self.model_dropdown.pack(fill="x")

        self.config_keys_btn = ctk.CTkButton(
            model_frame,
            text="⚙️ Configure API Keys...",
            height=28,
            command=self.open_settings
        )

        self._refresh_model_selector()

        # ========== 右侧内容区 ==========
        self.content_frame = ctk.CTkFrame(self, corner_radius=10)
        self.content_frame.grid(row=1, column=1, padx=(5, 10), pady=10, sticky="nsew")
        
        # 标签页
        self.tabview = ctk.CTkTabview(self.content_frame)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 扫描结果标签页（v1.1.0 保留 — 勿改）
        self.scan_tab = self.tabview.add("📊 Scan Results")
        self.setup_scan_tab()
        
        # AI分析标签页（v1.1.0 保留 — 勿改）
        self.ai_tab = self.tabview.add("🤖 AI Analysis")
        self.setup_ai_tab()
        
        # 文件操作标签页（v1.1.0 保留 — 勿改）
        self.action_tab = self.tabview.add("🗑️ File Actions")
        self.setup_action_tab()

        # History, Prompts, Models tabs removed (v1.2.1) — always empty, no data sources

    def open_settings(self):
        """打开设置对话框（Stage 2：⚙️ 齿轮按钮回调）"""
        import traceback
        try:
            from src.ui.settings_dialog import SettingsDialog
            SettingsDialog(master=self, on_close=self._on_settings_closed)
        except Exception as e:
            error_msg = f"{e}\n\n{traceback.format_exc()}"
            logger.error("Settings error: %s", error_msg)
            from tkinter import messagebox
            messagebox.showerror("Settings Error", error_msg[:500])

    def _on_settings_closed(self):
        self._apply_saved_theme()
        self._refresh_model_selector()

    def _on_model_selected(self, choice):
        """模型选择变更回调"""
        logger.info("LLM model selected: %s", choice)

    def _refresh_model_selector(self):
        """刷新模型选择器：后台检查哪些 provider 有 API key"""
        def _check():
            try:
                from src.utils.credential_store import CredentialStore
                store = CredentialStore()
            except Exception:
                store = None

            available = []
            if store:
                try:
                    from src.analyzer.llm_router import LLMRouter
                    if not self._llm_router:
                        self._llm_router = LLMRouter()
                    for name, info in self._llm_router.get_provider_status().items():
                        if info.get("has_api_key"):
                            for model in info.get("models", []):
                                available.append(f"{name}: {model}")
                except Exception:
                    logger.warning("LLM router provider status query failed", exc_info=True)

            def _update():
                try:
                    if not self.winfo_exists():
                        return
                    if available:
                        self.model_dropdown.configure(values=available)
                        self.model_var.set(available[0])
                        self.model_status_label.configure(
                            text=f"✓ {len(available)} models available", text_color="green"
                        )
                        self.config_keys_btn.pack_forget()
                    else:
                        self.model_dropdown.configure(values=["(no API key configured)"])
                        self.model_var.set("(no API key configured)")
                        self.model_status_label.configure(
                            text="No API keys configured", text_color="orange"
                        )
                        self.config_keys_btn.pack(fill="x", pady=(5, 0))
                except Exception:
                    logger.warning("Model selector UI update failed", exc_info=True)
            self.after(0, _update)

        import threading
        threading.Thread(target=_check, daemon=True).start()
        
    def create_section_header(self, parent, title, icon=""):
        """创建分组标题"""
        # 分隔线
        ctk.CTkFrame(parent, height=2, fg_color="gray60").pack(fill="x", padx=10, pady=(15, 5))
        
        # 标题
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        ctk.CTkLabel(
            header_frame,
            text=f"{icon} {title}",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w"
        ).pack(side="left")
        
    def create_input_field(self, parent, label_text, attr_name, placeholder="", default="", show=None, browse_type=None):
        """创建输入字段"""
        field_frame = ctk.CTkFrame(parent, fg_color="transparent")
        field_frame.pack(fill="x", padx=10, pady=(0, 8))
        
        ctk.CTkLabel(field_frame, text=label_text, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 2))
        
        if browse_type:
            row = ctk.CTkFrame(field_frame, fg_color="transparent")
            row.pack(fill="x")
            entry = ctk.CTkEntry(row, placeholder_text=placeholder, show=show, height=32)
            entry.pack(side="left", fill="x", expand=True)
            if browse_type == "folder":
                cmd = lambda e=entry: self._browse_folder(e)
            elif browse_type == "file":
                cmd = lambda e=entry: self._browse_file(e)
            else:
                cmd = None
            browse_btn = ctk.CTkButton(row, text="Browse...", width=80, command=cmd)
            browse_btn.pack(side="right", padx=(5, 0))
        else:
            entry = ctk.CTkEntry(field_frame, placeholder_text=placeholder, show=show, height=32)
            entry.pack(fill="x")
        
        if default:
            entry.insert(0, default)
            
        setattr(self, attr_name, entry)
        
    def _browse_folder(self, entry):
        """Open folder picker and fill selected path into entry."""
        folder = filedialog.askdirectory(title="Select folder to scan")
        if folder:
            entry.delete(0, "end")
            entry.insert(0, folder)

    def _browse_file(self, entry):
        """Open file picker and fill selected path into entry."""
        path = filedialog.askopenfilename(
            title="Select WizTree executable",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
        )
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)
        
    def create_drive_selector(self, parent):
        """创建磁盘选择器"""
        field_frame = ctk.CTkFrame(parent, fg_color="transparent")
        field_frame.pack(fill="x", padx=10, pady=(0, 8))
        
        ctk.CTkLabel(field_frame, text="Target Drive:", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 2))
        
        self.drive_var = ctk.StringVar(value="C:\\")
        self.drive_menu = ctk.CTkOptionMenu(field_frame, variable=self.drive_var, values=["C:\\"])
        self.drive_menu.pack(fill="x")
        
    def create_scan_controls(self, parent):
        """创建扫描控制区域"""
        # 扫描按钮
        self.scan_button = ctk.CTkButton(
            parent,
            text="🔍 Scan & Analyze",
            command=self.start_scan,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.scan_button.pack(fill="x", padx=10, pady=(15, 5))
        
        # 进度条
        self.progress_frame = ctk.CTkFrame(parent, fg_color="transparent", height=25)
        self.progress_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.progress_frame.pack_propagate(False)
        
        self.progress_bar = SmoothProgressBar(self.progress_frame)
        self.progress_bar.pack(fill="x", expand=True)
        self.progress_bar.set(0)
        
        # 状态标签和加载动画
        status_frame = ctk.CTkFrame(parent, fg_color="transparent")
        status_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w"
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        
        self.spinner = SpinnerLabel(status_frame, size=20)
        self.spinner.pack(side="right", padx=(5, 0))
        self.spinner.stop()
        
    def setup_scan_tab(self):
        """设置扫描结果标签页"""
        # 统计信息卡片区域
        self.stats_frame = ctk.CTkFrame(self.scan_tab, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # 创建统计卡片
        self.create_stats_cards()
        
        # 扫描结果表格
        table_frame = ctk.CTkFrame(self.scan_tab, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        columns = ("rank", "path", "size", "modified")
        self.scan_tree = VirtualTreeview(table_frame, columns=columns, show="headings", height=15)
        
        self.scan_tree.heading("rank", text="#")
        self.scan_tree.heading("path", text="File Path")
        self.scan_tree.heading("size", text="Size")
        self.scan_tree.heading("modified", text="Modified")
        
        self.scan_tree.column("rank", width=50, anchor="center")
        self.scan_tree.column("path", width=600)
        self.scan_tree.column("size", width=100, anchor="e")
        self.scan_tree.column("modified", width=150, anchor="center")
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.scan_tree.yview)
        self.scan_tree.configure(yscrollcommand=scrollbar.set)
        
        self.scan_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Stage 3 (v1.3.0): 扫描结果骨架屏覆盖层
        self._scan_skeleton_frame = ctk.CTkFrame(table_frame, fg_color="transparent")
        for _i in range(5):
            SkeletonLine(self._scan_skeleton_frame, width="full").pack(
                fill="x", padx=4, pady=3,
            )
        self._scan_skeleton_visible = False
        
    def create_stats_cards(self):
        """创建统计信息卡片"""
        # 清空现有卡片
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
            
        # 卡片数据
        cards_data = [
            ("📁 Files", "0", "total_files"),
            ("💾 Total Size", "0 B", "total_size"),
            ("⏱️ Duration", "0.0s", "duration"),
            ("🗑️ Recommendations", "0", "recommendations")
        ]
        
        self.stats_labels = {}
        
        for i, (title, value, key) in enumerate(cards_data):
            card = ctk.CTkFrame(self.stats_frame, corner_radius=8, height=70)
            card.pack(side="left", fill="x", expand=True, padx=(0, 5) if i < len(cards_data)-1 else (0, 0))
            card.pack_propagate(False)
            
            # 标题
            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=11),
                text_color="gray70"
            ).pack(pady=(10, 2))
            
            # 数值
            value_label = ctk.CTkLabel(
                card,
                text=value,
                font=ctk.CTkFont(size=16, weight="bold")
            )
            value_label.pack(pady=(0, 10))
            
            self.stats_labels[key] = value_label
        
    def setup_ai_tab(self):
        """设置AI分析标签页"""
        # 顶部工具栏
        toolbar = ctk.CTkFrame(self.ai_tab, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(
            toolbar,
            text="AI Analysis Results",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")
        
        # 复制按钮
        self.copy_button = ctk.CTkButton(
            toolbar,
            text="📋 Copy",
            width=80,
            height=28,
            command=self.copy_ai_text
        )
        self.copy_button.pack(side="right")
        
        # AI分析结果文本框
        text_frame = ctk.CTkFrame(self.ai_tab, fg_color="transparent")
        text_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        self.ai_text = ctk.CTkTextbox(
            text_frame,
            font=ctk.CTkFont(size=13, family="Consolas"),
            fg_color="#1e1e2e",
            text_color="#cdd6f4",
            border_width=1,
            border_color="#45475a",
            corner_radius=8
        )
        self.ai_text.pack(fill="both", expand=True)
        self.ai_text.insert("1.0", "AI analysis results will appear here...\n\n")
        self.ai_text.configure(state="disabled")

        # Stage 3 (v1.3.0): AI 分析骨架屏覆盖层
        self._ai_skeleton_frame = ctk.CTkFrame(text_frame, fg_color="transparent")
        for _i in range(7):
            SkeletonLine(self._ai_skeleton_frame, width="full").pack(
                fill="x", padx=4, pady=3,
            )
        self._ai_skeleton_visible = False
        
        # 加载动画
        self.ai_loading_frame = ctk.CTkFrame(self.ai_tab, fg_color="transparent")
        self.ai_loading_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.ai_spinner = SpinnerLabel(self.ai_loading_frame, size=24)
        self.ai_spinner.pack(side="left", padx=(0, 10))
        
        self.ai_status_label = ctk.CTkLabel(
            self.ai_loading_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.ai_status_label.pack(side="left")
        
        # 初始隐藏加载动画
        self.ai_loading_frame.pack_forget()
        
    def setup_action_tab(self):
        """设置文件操作标签页"""
        # 顶部工具栏
        toolbar = ctk.CTkFrame(self.action_tab, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(10, 5))
        
        # 全选/取消全选
        self.select_all_var = ctk.BooleanVar(value=False)
        self.select_all_cb = ctk.CTkCheckBox(
            toolbar,
            text="Select All",
            variable=self.select_all_var,
            command=self.toggle_select_all,
            font=ctk.CTkFont(size=12)
        )
        self.select_all_cb.pack(side="left")
        
        # 风险筛选
        filter_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        filter_frame.pack(side="right")
        
        ctk.CTkLabel(filter_frame, text="Risk Filter:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        
        self.risk_filter_var = ctk.StringVar(value="All")
        self.risk_filter = ctk.CTkOptionMenu(
            filter_frame,
            variable=self.risk_filter_var,
            values=["All", "Critical", "High", "Medium", "Low"],
            width=100,
            command=self.filter_by_risk
        )
        self.risk_filter.pack(side="left")
        
        # 文件操作表格
        table_frame = ctk.CTkFrame(self.action_tab, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        columns = ("select", "path", "size", "reason", "risk")
        self.action_tree = VirtualTreeview(table_frame, columns=columns, show="headings", height=15)
        
        self.action_tree.heading("select", text="✓")
        self.action_tree.heading("path", text="File Path")
        self.action_tree.heading("size", text="Size")
        self.action_tree.heading("reason", text="Reason")
        self.action_tree.heading("risk", text="Risk")
        
        self.action_tree.column("select", width=40, anchor="center")
        self.action_tree.column("path", width=400)
        self.action_tree.column("size", width=80, anchor="e")
        self.action_tree.column("reason", width=250)
        self.action_tree.column("risk", width=80, anchor="center")
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.action_tree.yview)
        self.action_tree.configure(yscrollcommand=scrollbar.set)
        
        self.action_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 绑定点击事件
        self.action_tree.bind("<ButtonRelease-1>", self.on_action_tree_click)
        
        # 底部操作区域
        bottom_frame = ctk.CTkFrame(self.action_tab, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # 选中信息
        info_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)
        
        self.selected_label = ctk.CTkLabel(
            info_frame,
            text="0 files selected (0 B)",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.selected_label.pack(side="left")
        
        # 操作按钮
        btn_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        btn_frame.pack(side="right")
        
        self.preview_button = ctk.CTkButton(
            btn_frame,
            text="👁️ Preview",
            width=100,
            height=32,
            command=self.preview_selected,
            state="disabled"
        )
        self.preview_button.pack(side="left", padx=(0, 5))
        
        self.delete_button = ctk.CTkButton(
            btn_frame,
            text="🗑️ Delete Selected",
            width=140,
            height=32,
            command=self.delete_selected,
            fg_color="#c0392b",
            hover_color="#e74c3c",
            state="disabled"
        )
        self.delete_button.pack(side="left")
        
        # 批次导航按钮
        self.prev_batch_button = ctk.CTkButton(
            btn_frame,
            text="⬅️ Previous Batch",
            width=120,
            height=32,
            command=self.prev_batch,
            state="disabled"
        )
        self.prev_batch_button.pack(side="left", padx=(10, 5))
        
        self.next_batch_button = ctk.CTkButton(
            btn_frame,
            text="Next Batch ➡️",
            width=120,
            height=32,
            command=self.next_batch,
            state="disabled"
        )
        self.next_batch_button.pack(side="left")
        
    def on_window_resize(self, event):
        """处理窗口缩放事件"""
        if event.widget != self:
            return
        
        if "_last_config_width" not in self.__dict__:
            self._last_config_width = 0

        width = event.width
        if width == self._last_config_width:
            return
        self._last_config_width = width

        if width < 1300:
            new_width = 250
        elif width < 1600:
            new_width = 300
        else:
            new_width = 350

        def _apply():
            try:
                self.config_frame.configure(width=new_width)
            except Exception:
                logger.debug("Failed to configure config frame width", exc_info=True)

        self.after_idle(_apply)
        
    def detect_drives(self):
        """检测可用磁盘"""
        import ctypes
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if bitmask & 1:
                drives.append(f"{letter}:\\")
            bitmask >>= 1
        
        if drives:
            self.drive_menu.configure(values=drives)
            self.drive_var.set(drives[0])
            
    def copy_ai_text(self):
        """复制AI分析文本"""
        self.clipboard_clear()
        text = self.ai_text.get("1.0", "end-1c")
        self.clipboard_append(text)
        self.update_status("Copied to clipboard", "green")
        
    def toggle_select_all(self):
        """全选/取消全选"""
        select_all = self.select_all_var.get()
        for rec in self.recommendations:
            rec.selected = select_all
        data = []
        for rec in self.recommendations:
            checkbox = "☑" if rec.selected else "☐"
            data.append((checkbox, str(rec.file.path),
                         self.format_size(rec.file.size), rec.reason, rec.risk_level.value))
        self.action_tree.set_data(data)
        self.action_tree.refresh()
        self.update_selected_count()
        
    def filter_by_risk(self, value):
        """按风险等级筛选"""
        data = []
        for rec in self.recommendations:
            if value == "All" or rec.risk_level.value.lower() == value.lower():
                size_str = self.format_size(rec.file.size)
                checkbox = "☑" if rec.selected else "☐"
                data.append((checkbox, str(rec.file.path), size_str, rec.reason, rec.risk_level.value))
        self.action_tree.set_data(data)
        self.action_tree.refresh()
                
    def preview_selected(self):
        """预览选中的文件"""
        selected = [str(rec.file.path) for rec in self.recommendations if rec.selected]
             
        if not selected:
            return
            
        # 显示预览对话框
        preview_text = "Selected files:\n\n"
        for path in selected[:20]:  # 最多显示20个
            preview_text += f"• {path}\n"
            
        if len(selected) > 20:
            preview_text += f"\n... and {len(selected) - 20} more files"
            
        from tkinter import messagebox
        messagebox.showinfo("Preview", preview_text)
        
    def update_status(self, message, color="gray"):
        """更新状态标签"""
        self.status_label.configure(text=message, text_color=color)
            
    def start_scan(self):
        """开始扫描"""
        wiztree_path = self.wiztree_path.get().strip()

        # 验证WizTree路径
        if not wiztree_path or not os.path.isfile(wiztree_path):
            self.show_error("WizTree executable not found. Please check the path.")
            return

        # Stage 3: 初始化扫描器（带进度回调，每 100 文件更新一次 UI）
        self.scanner = WizTreeScanner(
            wiztree_path=wiztree_path,
            progress_callback=self._on_scan_progress,
        )

        # 禁用按钮并启动动画
        self.scan_button.configure(state="disabled", text="⏳ Scanning...")
        self.progress_bar.start_animation()
        self.spinner.start()
        self.update_status("Scanning in progress...", "yellow")

        # Stage 3 (v1.3.0): 显示骨架屏
        self._show_scan_skeleton()
        self._show_ai_skeleton()

        # 显示AI加载动画
        self.show_ai_loading(True)

        # 在后台线程中执行扫描
        scope = self.scope_entry.get().strip()
        target = scope if (scope and os.path.isdir(scope)) else self.drive_var.get()
        options = ScanOptions()
        min_size = self.min_size_entry.get().strip()
        if min_size:
            options.min_size = min_size
        thread = threading.Thread(target=self.scan_thread, args=(target, options), daemon=True)
        thread.start()

    def _on_scan_progress(self, progress_info) -> None:
        """Stage 3: 扫描进度回调 — 通过 after(0, …) 安全更新 UI"""
        try:
            msg = progress_info.message or "Scanning..."
            files = getattr(progress_info, "files_scanned", 0)
            self.after(0, lambda m=msg, f=files: self._apply_progress(m, f))
        except Exception:
            logger.warning("Scan progress callback failed", exc_info=True)

    def _apply_progress(self, message: str, files_scanned: int) -> None:
        """Stage 3: 在 UI 线程中应用进度更新"""
        try:
            if not self.winfo_exists():
                return
            if files_scanned > 0:
                self.update_status(f"{message} ({files_scanned} files)", "yellow")
            else:
                self.update_status(message, "yellow")
        except Exception:
            logger.warning("Apply progress update failed", exc_info=True)

    def scan_thread(self, target, options):
        """扫描线程"""
        def _safe_call(fn):
            try:
                if not self.winfo_exists():
                    return
                fn()
            except Exception:
                logger.warning("Safe call wrapper failed", exc_info=True)

        try:
            # Stage 3: 使用带缓存的扫描
            self.after(0, lambda: _safe_call(lambda: self.update_status(f"Scanning {target}...", "yellow")))
            self.scan_result = self.scanner.scan_with_cache(target, options)
            
            # v1.7.1: 限制扫描结果最大文件数，防止内存爆炸
            if self.scan_result and len(self.scan_result.files) > self.MAX_SCAN_FILES:
                original_count = len(self.scan_result.files)
                self.scan_result.files = self.scan_result.files[:self.MAX_SCAN_FILES]
                logger.warning(
                    "Scan truncated: %d → %d files", 
                    original_count, self.MAX_SCAN_FILES
                )
            
            # 初始化文件池：按大小排序的所有扫描结果
            if self.scan_result:
                self._file_pool = sorted(self.scan_result.files, key=lambda x: x.size, reverse=True)
                self._current_batch = 0
            
            # 更新扫描结果
            self.after(0, lambda: _safe_call(self.update_scan_results))

            # 执行规则引擎分析
            self.after(0, lambda: _safe_call(lambda: self.update_ai_status("Analyzing files...")))
            self.recommendations, _ = self.rule_engine.analyze_files(self.scan_result.files)

            # 更新AI分析结果
            self.after(0, lambda: _safe_call(self.update_ai_analysis))
            self.after(0, lambda: _safe_call(self.update_action_table))
            
            # 完成
            self.after(0, lambda: _safe_call(lambda: self.update_status(
                f"✅ Done! Found {len(self.scan_result.files)} files, {len(self.recommendations)} recommendations",
                "green"
            )))
            
        except Exception as e:
            self.after(0, lambda: _safe_call(lambda: self.show_error(f"Scan failed: {str(e)}")))
        finally:
            # 停止动画
            self.after(0, lambda: _safe_call(self.stop_scan_animations))
            
    def stop_scan_animations(self):
        """停止扫描动画"""
        self.scan_button.configure(state="normal", text="🔍 Scan & Analyze")
        self.progress_bar.stop_animation()
        self.spinner.stop()
        
    def show_ai_loading(self, show=True):
        """显示/隐藏AI加载动画"""
        if show:
            self.ai_loading_frame.pack(fill="x", padx=10, pady=(0, 10))
            self.ai_spinner.start()
        else:
            self.ai_spinner.stop()
            self.ai_loading_frame.pack_forget()

    # ------------------------------------------------------------------
    # Stage 3 (v1.3.0): 骨架屏 API
    # ------------------------------------------------------------------
    def _show_scan_skeleton(self) -> None:
        """显示扫描结果骨架屏（覆盖 scan_tree 区域）。"""
        if self._scan_skeleton_visible:
            return
        self._scan_skeleton_visible = True
        parent = self.scan_tree.master
        self._scan_skeleton_frame.place(
            relx=0, rely=0, relwidth=1, relheight=1,
        )
        self._scan_skeleton_frame.lift()

    def _hide_scan_skeleton(self) -> None:
        """隐藏扫描结果骨架屏。"""
        if not self._scan_skeleton_visible:
            return
        self._scan_skeleton_visible = False
        self._scan_skeleton_frame.place_forget()

    def _show_ai_skeleton(self) -> None:
        """显示 AI 分析骨架屏（覆盖 ai_text 区域）。"""
        if self._ai_skeleton_visible:
            return
        self._ai_skeleton_visible = True
        self._ai_skeleton_frame.place(
            relx=0, rely=0, relwidth=1, relheight=1,
        )
        self._ai_skeleton_frame.lift()

    def _hide_ai_skeleton(self) -> None:
        """隐藏 AI 分析骨架屏。"""
        if not self._ai_skeleton_visible:
            return
        self._ai_skeleton_visible = False
        self._ai_skeleton_frame.place_forget()
            
    def update_ai_status(self, message):
        """更新AI状态"""
        self.ai_status_label.configure(text=message)
        self.update_status(message, "yellow")
        
    # ----------------------------------------------------------------
    # v1.7.1: 文件显示上限 (防止大量文件撑爆内存)
    # ----------------------------------------------------------------
    MAX_SCAN_FILES = 5000
    MAX_DISPLAY_FILES = 500

    def update_scan_results(self):
        """更新扫描结果表格"""
        # Stage 3 (v1.3.0): 隐藏扫描骨架屏
        self._hide_scan_skeleton()

        # 清空表格
        for item in self.scan_tree.get_children():
            self.scan_tree.delete(item)
            
        if not self.scan_result:
            return
            
        # 更新统计卡片
        self.update_stats_cards()
        
        total = len(self.scan_result.files)
        display_count = min(total, self.MAX_DISPLAY_FILES)
        
        # 添加数据（使用虚拟滚动）
        data = []
        for i, file_info in enumerate(self.scan_result.files[:display_count], 1):
            size_str = self.format_size(file_info.size)
            data.append((
                i,
                str(file_info.path),
                size_str,
                file_info.modified_time.strftime("%Y-%m-%d %H:%M") if file_info.modified_time else ""
            ))
        self.scan_tree.set_data(data)
        self.scan_tree.refresh()
        
        # 显示截断提示
        if total > self.MAX_DISPLAY_FILES:
            self.update_status(
                f"Showing {self.MAX_DISPLAY_FILES:,} of {total:,} files (scan capped at {self.MAX_SCAN_FILES:,})",
                "orange"
            )
            
    def update_stats_cards(self):
        """更新统计卡片"""
        if not self.scan_result:
            return
            
        # 更新文件数量
        self.stats_labels["total_files"].configure(text=str(self.scan_result.total_files))
        
        # 更新总大小
        self.stats_labels["total_size"].configure(text=self.format_size(self.scan_result.total_size))
        
        # 更新扫描时长
        self.stats_labels["duration"].configure(text=f"{self.scan_result.duration_seconds:.1f}s")
            
    def update_ai_analysis(self):
        """更新AI分析结果"""
        # Stage 3 (v1.3.0): 隐藏 AI 骨架屏
        self._hide_ai_skeleton()

        # 隐藏加载动画
        self.show_ai_loading(False)
        
        # 更新推荐数量统计卡片
        self.stats_labels["recommendations"].configure(text=str(len(self.recommendations)))
        
        self.ai_text.configure(state="normal")
        self.ai_text.delete("1.0", "end")
        
        if not self.scan_result:
            self.ai_text.insert("1.0", "No scan results available.")
            self.ai_text.configure(state="disabled")
            return
            
        # 显示统计信息
        total_size = self.format_size(self.scan_result.total_size)
        self.ai_text.insert("end", "═" * 50 + "\n")
        self.ai_text.insert("end", "  📊 SCAN SUMMARY\n")
        self.ai_text.insert("end", "═" * 50 + "\n\n")
        self.ai_text.insert("end", f"  📁 Total files: {self.scan_result.total_files}\n")
        self.ai_text.insert("end", f"  💾 Total size: {total_size}\n")
        self.ai_text.insert("end", f"  ⏱️ Scan duration: {self.scan_result.duration_seconds:.1f}s\n\n")
        
        # 显示规则引擎分析结果
        self.ai_text.insert("end", "═" * 50 + "\n")
        self.ai_text.insert("end", "  🤖 RULE ENGINE ANALYSIS\n")
        self.ai_text.insert("end", "═" * 50 + "\n\n")
        self.ai_text.insert("end", f"  Found {len(self.recommendations)} cleanup candidates\n\n")
        
        # 显示前20个建议
        if self.recommendations:
            self.ai_text.insert("end", "─" * 50 + "\n")
            self.ai_text.insert("end", "  TOP RECOMMENDATIONS\n")
            self.ai_text.insert("end", "─" * 50 + "\n\n")
            
            for i, rec in enumerate(self.recommendations[:20], 1):
                size_str = self.format_size(rec.file.size)
                risk_icon = "⛔" if rec.risk_level.value == "critical" else "🔴" if rec.risk_level.value == "high" else "🟡" if rec.risk_level.value == "medium" else "🟢"
                self.ai_text.insert("end", f"  #{i} {risk_icon} [{rec.risk_level.value.upper()}]\n")
                self.ai_text.insert("end", f"     📄 {rec.file.path}\n")
                self.ai_text.insert("end", f"     💾 Size: {size_str}\n")
                self.ai_text.insert("end", f"     💡 Reason: {rec.reason}\n\n")
            
        self.ai_text.configure(state="disabled")
        
    def update_action_table(self):
        """更新文件操作表格"""
        data = []
        # 显示文件池中的文件（按批次）
        start_idx = self._current_batch * self._batch_size
        end_idx = start_idx + self._batch_size
        batch_files = self._file_pool[start_idx:end_idx]
        
        for i, file_info in enumerate(batch_files):
            size_str = self.format_size(file_info.size)
            # 检查是否在推荐列表中
            rec = next((r for r in self.recommendations if r.file.path == file_info.path), None)
            if rec:
                checkbox = "☑" if rec.selected else "☐"
                reason = rec.reason
                risk = rec.risk_level.value
            else:
                checkbox = "☐"
                reason = "Not recommended for deletion"
                risk = "N/A"
            data.append((checkbox, str(file_info.path), size_str, reason, risk))
        self.action_tree.set_data(data)
        self.action_tree.refresh()
        
        # 更新批次按钮状态
        self.update_batch_buttons()
            
    def on_action_tree_click(self, event):
        """处理文件操作表格点击"""
        region = self.action_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
            
        column = self.action_tree.identify_column(event.x)
        item = self.action_tree.identify_row(event.y)
        
        if not item:
            return
            
        # 切换选中状态
        if column == "#1":  # Select列
            values = list(self.action_tree.item(item, "values"))
            values[0] = "☑" if values[0] == "☐" else "☐"
            self.action_tree.item(item, values=values)
            is_selected = values[0] == "☑"
            path = values[1]
            for rec in self.recommendations:
                if str(rec.file.path) == path:
                    rec.selected = is_selected
                    break
            self.update_selected_count()
            
    def update_selected_count(self):
        """更新选中文件计数"""
        count = 0
        total_size = 0
        for rec in self.recommendations:
            if rec.selected:
                count += 1
                total_size += rec.file.size
                 
        size_text = self.format_size(int(total_size)) if total_size > 0 else "0 B"
        self.selected_label.configure(text=f"{count} files selected ({size_text})")
        
        # 更新按钮状态
        state = "normal" if count > 0 else "disabled"
        self.delete_button.configure(state=state)
        self.preview_button.configure(state=state)
        
    def delete_selected(self):
        """删除选中的文件"""
        # 获取当前批次中选中的文件
        start_idx = self._current_batch * self._batch_size
        end_idx = start_idx + self._batch_size
        batch_files = self._file_pool[start_idx:end_idx]
        
        selected_files = []
        for file_info in batch_files:
            rec = next((r for r in self.recommendations if r.file.path == file_info.path), None)
            if rec and rec.selected:
                selected_files.append((file_info, rec))
        
        if not selected_files:
            return
             
        # 确认对话框
        from tkinter import messagebox
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete {len(selected_files)} files?\n\n"
            "Files will be moved to Recycle Bin if send2trash is available.",
            icon="warning"
        )
        
        if not confirm:
            return
             
        # 执行删除
        try:
            from send2trash import send2trash
            use_send2trash = True
        except ImportError:
            logger.debug("send2trash not available, falling back to os.remove")
            use_send2trash = False
             
        deleted = 0
        errors = 0
        deleted_paths = set()
        for file_info, rec in selected_files:
            try:
                path = str(file_info.path)
                if os.path.exists(path):
                    if use_send2trash:
                        send2trash(path)
                    else:
                        os.remove(path)
                    deleted += 1
                    deleted_paths.add(path)
            except Exception:
                logger.warning("Delete failed: %s", file_info.path, exc_info=True)
                errors += 1
                 
        # 从文件池中移除已删除的文件
        self._file_pool = [f for f in self._file_pool if str(f.path) not in deleted_paths]
        
        # 从推荐列表中移除已删除的文件
        self.recommendations = [rec for rec in self.recommendations if str(rec.file.path) not in deleted_paths]
        
        # 重新分析文件池中的文件（如果推荐列表为空）
        if not self.recommendations and self._file_pool:
            # 从文件池中取出下一批文件进行分析
            start_idx = self._current_batch * self._batch_size
            end_idx = start_idx + self._batch_size
            next_batch = self._file_pool[start_idx:end_idx]
            if next_batch:
                self.recommendations, _ = self.rule_engine.analyze_files(next_batch)
        
        # 更新表格显示
        self.update_action_table()
        self.update_selected_count()
        
        # 显示结果
        messagebox.showinfo("Delete Result", f"Deleted: {deleted}\nErrors: {errors}")
        
    def prev_batch(self):
        """显示上一批文件"""
        if self._current_batch > 0:
            self._current_batch -= 1
            self.update_action_table()
            self.update_batch_buttons()
        
    def next_batch(self):
        """显示下一批文件"""
        max_batch = (len(self._file_pool) - 1) // self._batch_size
        if self._current_batch < max_batch:
            self._current_batch += 1
            self.update_action_table()
            self.update_batch_buttons()
        
    def update_batch_buttons(self):
        """更新批次按钮状态"""
        max_batch = (len(self._file_pool) - 1) // self._batch_size if self._file_pool else 0
        
        # 更新“上一轮”按钮状态
        if self._current_batch > 0:
            self.prev_batch_button.configure(state="normal")
        else:
            self.prev_batch_button.configure(state="disabled")
        
        # 更新“下一轮”按钮状态
        if self._current_batch < max_batch:
            self.next_batch_button.configure(state="normal")
        else:
            self.next_batch_button.configure(state="disabled")
        
    def show_error(self, message: str):
        """显示错误消息"""
        from tkinter import messagebox
        messagebox.showerror("Error", message)
        
    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"