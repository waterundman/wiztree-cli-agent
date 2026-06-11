"""
ModernTheme 主题管理 (v1.3.0 / Stage 4)
========================================

提供 6 套精选深色主题（color palette + customtkinter theme JSON 写入），
统一管理 customtkinter 颜色 + 通过 ConfigLoader 持久化用户偏好。

6 主题（顺序固定，与 SPEC Stage 4 契约一致）：
    1. Steam Dark
    2. Catppuccin Mocha
    3. OLED Black
    4. GitHub Dark
    5. Nord
    6. Dracula

公开 API（v1.2.0 新增）:
    ModernTheme.list_themes() -> List[str]
    ModernTheme.get_current() -> str
    ModernTheme.apply(theme_name: str) -> None
    ModernTheme.apply_ttk_style(style: ttk.Style) -> None   # v1.3.0 新增

兼容 v1.1.0（保留不变）:
    ModernTheme(mode='dark')            # 实例构造
    .apply_theme()                      # 实例方法
    .get_color(name)                    # 实例方法
    .toggle_mode()                      # 实例方法
    .DARK_COLORS / .LIGHT_COLORS        # 类属性
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# 自定义 tkinter（Stage 4 依赖；不可用时 ctk=None，所有 GUI API 跳过但持久化仍然执行）
try:
    import customtkinter as ctk  # type: ignore
except ImportError:
    ctk = None  # type: ignore


# ---------------------------------------------------------------------------
# 6 主题色板（与 SPEC Stage 4 / 1. 一致；色值参考 Material / Nord / Dracula 公开调色板）
# ---------------------------------------------------------------------------
THEMES: Dict[str, Dict[str, str]] = {
    "Steam Dark": {
        "fg_color": "#1e2837",
        "button_color": "#2a475e",
        "text_color": "#c7d5e0",
        "border_color": "#1b2838",
        "progressbar_color": "#66c0f4",
        "hover_color": "#3a6090",
    },
    "Catppuccin Mocha": {
        "fg_color": "#1e1e2e",
        "button_color": "#89b4fa",
        "text_color": "#cdd6f4",
        "border_color": "#45475a",
        "progressbar_color": "#a6e3a1",
        "hover_color": "#b4befe",
    },
    "OLED Black": {
        "fg_color": "#000000",
        "button_color": "#1a1a1a",
        "text_color": "#e0e0e0",
        "border_color": "#0a0a0a",
        "progressbar_color": "#00ff88",
        "hover_color": "#2a2a2a",
    },
    "GitHub Dark": {
        "fg_color": "#0d1117",
        "button_color": "#21262d",
        "text_color": "#c9d1d9",
        "border_color": "#30363d",
        "progressbar_color": "#58a6ff",
        "hover_color": "#30363d",
    },
    "Nord": {
        "fg_color": "#2e3440",
        "button_color": "#3b4252",
        "text_color": "#eceff4",
        "border_color": "#4c566a",
        "progressbar_color": "#88c0d0",
        "hover_color": "#434c5e",
    },
    "Dracula": {
        "fg_color": "#282a36",
        "button_color": "#44475a",
        "text_color": "#f8f8f2",
        "border_color": "#6272a4",
        "progressbar_color": "#bd93f9",
        "hover_color": "#44475a",
    },
}

THEME_ORDER: List[str] = [
    "Steam Dark",
    "Catppuccin Mocha",
    "OLED Black",
    "GitHub Dark",
    "Nord",
    "Dracula",
]

DEFAULT_THEME: str = "GitHub Dark"

REQUIRED_KEYS = (
    "fg_color",
    "button_color",
    "text_color",
    "border_color",
    "progressbar_color",
    "hover_color",
)


# ---------------------------------------------------------------------------
# 内部辅助：customtkinter theme JSON 序列化
# ---------------------------------------------------------------------------
def _build_ctk_theme_json(theme_name: str) -> Dict[str, Any]:
    """
    将 6-key 简化色板展开为 customtkinter 内部 theme JSON 结构。

    customtkinter 的 theme JSON 为每个 widget 类定义 [light_mode, dark_mode] 二元组；
    6 主题都是 dark，light 槽位填充同样的颜色以保持一致。
    """
    if theme_name not in THEMES:
        raise ValueError(
            f"Unknown theme: {theme_name!r}. Available: {THEME_ORDER}"
        )
    palette = THEMES[theme_name]
    fg = palette["fg_color"]
    btn = palette["button_color"]
    txt = palette["text_color"]
    brd = palette["border_color"]
    pgb = palette["progressbar_color"]
    hov = palette["hover_color"]
    disabled_txt = "#7a7a7a"
    return {
        "CTk": {
            "fg_color": [fg, fg],
            "bg_color": ["#ffffff", "#000000"],
            "text_color": [txt, txt],
            "text_color_disabled": [disabled_txt, disabled_txt],
        },
        "CTkButton": {
            "fg_color": [btn, btn],
            "hover_color": [hov, hov],
            "text_color": [txt, txt],
            "text_color_disabled": [disabled_txt, disabled_txt],
            "border_color": [brd, brd],
            "border_width": 1,
            "corner_radius": 6,
        },
        "CTkLabel": {
            "corner_radius": 0,
            "fg_color": "transparent",
            "text_color": [txt, txt],
            "text_color_disabled": [disabled_txt, disabled_txt],
        },
        "CTkEntry": {
            "corner_radius": 6,
            "border_width": 2,
            "fg_color": [btn, btn],
            "border_color": [brd, brd],
            "text_color": [txt, txt],
            "placeholder_text_color": ["#a0a0a0", "#a0a0a0"],
        },
        "CTkTextbox": {
            "corner_radius": 6,
            "border_width": 0,
            "fg_color": [btn, btn],
            "border_color": [brd, brd],
            "text_color": [txt, txt],
            "scrollbar_button_color": [hov, hov],
            "scrollbar_button_hover_color": [pgb, pgb],
        },
        "CTkFrame": {
            "corner_radius": 6,
            "border_width": 0,
            "fg_color": [fg, fg],
            "top_fg_color": [fg, fg],
            "border_color": [brd, brd],
        },
        "CTkTabview": {
            "fg_color": [fg, fg],
            "border_color": [brd, brd],
            "text_color": [txt, txt],
            "text_color_disabled": [disabled_txt, disabled_txt],
        },
        "CTkProgressBar": {
            "corner_radius": 1000,
            "border_width": 0,
            "fg_color": [brd, brd],
            "progress_color": [pgb, pgb],
            "border_color": [brd, brd],
        },
        "CTkOptionMenu": {
            "corner_radius": 6,
            "fg_color": [btn, btn],
            "button_color": [hov, hov],
            "button_hover_color": [hov, hov],
            "text_color": [txt, txt],
            "text_color_disabled": [disabled_txt, disabled_txt],
        },
        "CTkSwitch": {
            "corner_radius": 1000,
            "border_width": 3,
            "button_length": 0,
            "fg_color": [brd, brd],
            "progress_color": [pgb, pgb],
            "button_color": [hov, hov],
            "button_hover_color": [txt, txt],
            "text_color": [txt, txt],
            "text_color_disabled": [disabled_txt, disabled_txt],
        },
        "CTkRadioButton": {
            "corner_radius": 1000,
            "border_width_checked": 6,
            "border_width_unchecked": 3,
            "fg_color": [btn, btn],
            "border_color": [brd, brd],
            "hover_color": [hov, hov],
            "text_color": [txt, txt],
            "text_color_disabled": [disabled_txt, disabled_txt],
        },
        "CTkSlider": {
            "corner_radius": 1000,
            "button_corner_radius": 1000,
            "border_width": 6,
            "button_length": 0,
            "fg_color": [brd, brd],
            "progress_color": [pgb, pgb],
            "button_color": [btn, btn],
            "button_hover_color": [hov, hov],
        },
        "CTkCheckBox": {
            "corner_radius": 6,
            "border_width": 3,
            "fg_color": [btn, btn],
            "hover_color": [hov, hov],
            "border_color": [brd, brd],
            "checkmark_color": [pgb, pgb],
            "text_color": [txt, txt],
            "text_color_disabled": [disabled_txt, disabled_txt],
        },
        "CTkComboBox": {
            "corner_radius": 6,
            "border_width": 2,
            "fg_color": [btn, btn],
            "border_color": [brd, brd],
            "button_color": [brd, brd],
            "button_hover_color": [hov, hov],
            "text_color": [txt, txt],
            "text_color_disabled": [disabled_txt, disabled_txt],
        },
        "CTkSegmentedButton": {
            "corner_radius": 6,
            "border_width": 2,
            "fg_color": [brd, brd],
            "selected_color": [btn, btn],
            "selected_hover_color": [hov, hov],
            "unselected_color": [brd, brd],
            "unselected_hover_color": [hov, hov],
            "text_color": [txt, txt],
            "text_color_disabled": [disabled_txt, disabled_txt],
        },
        "CTkScrollbar": {
            "corner_radius": 1000,
            "border_spacing": 4,
            "fg_color": "transparent",
            "button_color": [hov, hov],
            "button_hover_color": [pgb, pgb],
        },
        "CTkScrollableFrame": {
            "label_fg_color": [fg, fg],
        },
        "DropdownMenu": {
            "fg_color": [fg, fg],
            "hover_color": [hov, hov],
            "text_color": [txt, txt],
        },
        "CTkFont": {
            "family": "Roboto",
            "size": 13,
            "weight": "normal",
        },
        "CTkToplevel": {
            "fg_color": [fg, fg],
        },
    }


def _theme_dir() -> Path:
    """
    主题 JSON 文件的存储目录。

    优先级：
        1. 环境变量 WIZTREE_THEME_DIR（测试可覆盖）
        2. ~/.wiztree-cli-agent/themes/（默认）
    """
    override = os.environ.get("WIZTREE_THEME_DIR")
    if override:
        return Path(override)
    return Path.home() / ".wiztree-cli-agent" / "themes"


def _theme_file_path(theme_name: str) -> Path:
    """主题 JSON 文件路径"""
    safe = theme_name.replace(" ", "_").lower()
    return _theme_dir() / f"{safe}.json"


def _ensure_theme_file(theme_name: str) -> Path:
    """确保主题 JSON 文件存在，否则创建并返回文件路径。"""
    path = _theme_file_path(theme_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _build_ctk_theme_json(theme_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------------------
# ModernTheme 主体
# ---------------------------------------------------------------------------
class ModernTheme:
    """现代主题管理类（v1.2.0）"""

    # ------------------------------------------------------------------
    # 内部状态：类级别当前主题（与单例 ConfigLoader 同步）
    # ------------------------------------------------------------------
    _current: Optional[str] = None
    _lock = threading.Lock()
    _on_change_callbacks: list = []

    # ------------------------------------------------------------------
    # v1.2.0 新增：类方法 API（与 SPEC Stage 4 contract 一致）
    # ------------------------------------------------------------------
    @staticmethod
    def list_themes() -> List[str]:
        """返回 6 个主题名（顺序固定，与 THEME_ORDER 一致）"""
        return list(THEME_ORDER)

    @staticmethod
    def get_current() -> str:
        """
        返回当前主题名。

        优先级：
            1. 类内 _current 状态（apply 后的内存值）
            2. ConfigLoader.get('ui.theme') 持久化值
            3. 内建默认 DEFAULT_THEME
        """
        with ModernTheme._lock:
            cached = ModernTheme._current
        if cached is not None and cached in THEMES:
            return cached
        try:
            from src.utils.config_loader import ConfigLoader
            saved = ConfigLoader.get_instance().get("ui.theme", None)
            if saved and saved in THEMES:
                return saved
        except Exception as e:  # pragma: no cover
            logger.debug("ConfigLoader 不可用, 使用内建默认: %s", e)
        return DEFAULT_THEME

    @staticmethod
    def apply(theme_name: str) -> None:
        """
        动态切换 CTk 主题并持久化到 ConfigLoader。

        Args:
            theme_name: 主题名（必须出现在 THEMES / list_themes() 中）

        Raises:
            ValueError: 主题名未知
        """
        if theme_name not in THEMES:
            raise ValueError(
                f"Unknown theme: {theme_name!r}. Available: {THEME_ORDER}"
            )

        with ModernTheme._lock:
            ModernTheme._current = theme_name

        # 写入主题 JSON 并调用 CTk API（customtkinter 不可用时仅记录）
        theme_path: Optional[Path] = None
        try:
            theme_path = _ensure_theme_file(theme_name)
        except OSError as e:  # pragma: no cover
            logger.warning("无法写入主题文件: %s", e)

        # 使用模块级别的 ctk 引用（可被测试 mock 替换）
        if ctk is not None:
            try:
                ctk.set_appearance_mode("dark")
                if theme_path is not None:
                    ctk.set_default_color_theme(str(theme_path))
            except Exception as e:  # pragma: no cover
                logger.debug("CTk 主题切换失败: %s", e)

        # 持久化到 ConfigLoader
        try:
            from src.utils.config_loader import ConfigLoader
            ConfigLoader.get_instance().set("ui.theme", theme_name)
        except Exception as e:  # pragma: no cover
            logger.debug("ConfigLoader 持久化失败: %s", e)

        # v1.3.0: 触发回调通知（ttk 样式 / StatusBar / SkeletonWidget 同步）
        with ModernTheme._lock:
            callbacks = list(ModernTheme._on_change_callbacks)
        for cb in callbacks:
            try:
                cb(theme_name)
            except Exception as e:  # pragma: no cover
                logger.debug("主题切换回调失败: %s", e)

    @staticmethod
    def apply_ttk_style(style: Any) -> None:
        """
        将当前主题的 ttk 样式应用到 Treeview 等 ttk 控件。

        ttk.Treeview 不完全支持 ctk 主题，需要手动设置 ttk.Style()。
        此方法根据当前主题色板配置 Treeview 和 Treeview.Heading 的样式。

        Args:
            style: tkinter.ttk.Style 实例
        """
        current = ModernTheme.get_current()
        if current not in THEMES:
            return
        palette = THEMES[current]
        bg = palette["fg_color"]
        fg = palette["text_color"]
        btn = palette["button_color"]
        brd = palette["border_color"]
        pgb = palette["progressbar_color"]
        hov = palette["hover_color"]

        try:
            style.theme_use("clam")
        except Exception:
            logger.debug("Failed to set ttk theme to 'clam'", exc_info=True)

        style.configure(
            "Treeview",
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            bordercolor=brd,
            rowheight=24,
        )
        style.configure(
            "Treeview.Heading",
            background=btn,
            foreground=fg,
            bordercolor=brd,
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", hov)],
            foreground=[("selected", fg)],
        )
        style.map(
            "Treeview.Heading",
            background=[("active", hov)],
        )
        # Scrollbar ttk 样式同步
        style.configure(
            "Vertical.TScrollbar",
            background=btn,
            troughcolor=bg,
            bordercolor=brd,
            arrowcolor=fg,
        )

    @staticmethod
    def on_theme_change(callback: Callable[[str], None]) -> None:
        """注册主题切换回调（v1.3.0 新增）。

        回调签名: ``callback(theme_name: str) -> None``
        """
        with ModernTheme._lock:
            ModernTheme._on_change_callbacks.append(callback)

    # ------------------------------------------------------------------
    # v1.1.0 兼容：实例 API（保留不变 — Stage 1 测试依赖）
    # ------------------------------------------------------------------
    DARK_COLORS = {
        "bg": "#1e1e2e",
        "fg": "#cdd6f4",
        "accent": "#89b4fa",
        "success": "#a6e3a1",
        "warning": "#f9e2af",
        "error": "#f38ba8",
        "surface": "#313244",
        "overlay": "#45475a",
    }

    LIGHT_COLORS = {
        "bg": "#eff1f5",
        "fg": "#4c4f69",
        "accent": "#1e66f5",
        "success": "#40a02b",
        "warning": "#df8e1d",
        "error": "#d20f39",
        "surface": "#ccd0da",
        "overlay": "#bcc0cc",
    }

    def __init__(self, mode: str = "dark"):
        self.mode = mode
        self.colors = self.DARK_COLORS if mode == "dark" else self.LIGHT_COLORS

    def apply_theme(self):
        """应用主题（v1.1.0 兼容 API）"""
        if ctk is not None:
            try:
                ctk.set_appearance_mode(self.mode)
            except Exception:  # pragma: no cover
                logger.debug("Failed to set appearance mode", exc_info=True)

    def get_color(self, name: str) -> str:
        """获取颜色（v1.1.0 兼容 API）"""
        return self.colors.get(name, "#000000")

    def toggle_mode(self):
        """切换模式（v1.1.0 兼容 API）"""
        self.mode = "light" if self.mode == "dark" else "dark"
        self.colors = self.DARK_COLORS if self.mode == "dark" else self.LIGHT_COLORS
        self.apply_theme()
