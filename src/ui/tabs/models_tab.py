"""
ModelsTab — 模型浏览器标签页（v1.2.0 / Stage 2）

布局
====

::

    ┌────────────────────────────────────────────────────────────┐
    │ Provider: [All|OpenAI|Anthropic|OpenRouter|DeepSeek|Google]│  ← 顶栏
    │ Sort:    [name|price|context]   Search: [_______]   🔄     │
    ├────────────────────────────────────────────────────────────┤
    │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │  ← 卡片网格
    │ │ openai   │ │ anthropic│ │ openrouter│ │ ...       │       │
    │ │ GPT-4o   │ │ Sonnet   │ │ Gemini    │ │          │       │
    │ │ ctx: 128k│ │ ctx: 200k│ │ ctx: 1M    │ │          │       │
    │ │ $0.15/M  │ │ $3.00/M  │ │ $0.00/M    │ │          │       │
    │ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
    │                                                            │
    │ ... 滚动 ...                                                │
    └────────────────────────────────────────────────────────────┘

交互
====

* 选择卡片 → 写入 ``ConfigLoader.set("llm.selected_model", id)`` + 显示 toast
* 顶栏变更 → 重新过滤+排序+搜索
* ``refresh()`` → 重新从缓存/网络加载
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# 延迟 import ctk 避免 import 阶段就崩
try:
    import customtkinter as ctk
    _CTK_AVAILABLE = True
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore
    _CTK_AVAILABLE = False

from src.analyzer.model_catalog import ModelCatalog, ModelInfo  # noqa: E402
from ..components.skeleton import SkeletonLine  # noqa: E402


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
PROVIDER_FILTERS: List[str] = [
    "All", "OpenAI", "Anthropic", "OpenRouter", "DeepSeek", "Google",
]
SORT_OPTIONS: List[str] = ["name", "price", "context"]

# Provider 标签 → catalog 中 provider 字符串
_PROVIDER_NORMALIZE = {
    "all": "all",
    "openai": "openai",
    "anthropic": "anthropic",
    "openrouter": "openrouter",
    "deepseek": "deepseek",
    "google": "google",
}


class ModelsTab:
    """
    Models 标签页（不强制继承 ctk.CTkFrame —— 实例化时才延迟继承，
    以便在无 tkinter 环境下 import 整个模块）。
    """

    SELECTED_KEY: str = "llm.selected_model"

    def __init__(
        self,
        master: Any,
        *,
        catalog: Optional[ModelCatalog] = None,
        config_loader: Optional[Any] = None,
        on_select: Optional[Any] = None,
    ) -> None:
        """
        Args:
            master:         父容器（CTkTabview tab）
            catalog:        ModelCatalog 实例；None 则新建
            config_loader:  ConfigLoader 实例；None 则取全局单例
            on_select:      选中卡片时的回调（model: ModelInfo）
        """
        if not _CTK_AVAILABLE:
            raise RuntimeError(
                "customtkinter / tkinter 不可用，无法实例化 ModelsTab"
            )

        self._catalog = catalog or ModelCatalog()
        self._on_select_cb = on_select

        # 解析 ConfigLoader
        if config_loader is None:
            from src.utils.config_loader import ConfigLoader
            config_loader = ConfigLoader.get_instance()
        self._config = config_loader

        # 内部状态
        self._provider: str = "All"
        self._sort_by: str = "name"
        self._search: str = ""

        # 真正创建 CTkFrame 子控件
        self.frame: "ctk.CTkFrame" = ctk.CTkFrame(master, fg_color="transparent")

        # UI 引用
        self._cards_frame: Any = None
        self._search_var: Any = None
        self._toast_label: Any = None
        self._toast_after_id: Any = None
        self._status_label: Any = None

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # 顶栏
        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))

        # Provider SegmentedButton
        self._provider_seg = ctk.CTkSegmentedButton(
            top, values=PROVIDER_FILTERS, width=520,
            command=self._on_provider_change,
        )
        self._provider_seg.set("All")
        self._provider_seg.pack(side="left", padx=(0, 8))

        # Sort OptionMenu
        ctk.CTkLabel(top, text="Sort:").pack(side="left", padx=(8, 4))
        self._sort_var = ctk.StringVar(value="name")
        self._sort_menu = ctk.CTkOptionMenu(
            top, values=SORT_OPTIONS, variable=self._sort_var, width=110,
            command=self._on_sort_change,
        )
        self._sort_menu.pack(side="left", padx=4)

        # Search Entry
        ctk.CTkLabel(top, text="Search:").pack(side="left", padx=(8, 4))
        self._search_var = ctk.StringVar()
        self._search_entry = ctk.CTkEntry(
            top, placeholder_text="gpt, claude, …", width=180,
            textvariable=self._search_var,
        )
        self._search_entry.pack(side="left", padx=4)
        self._search_entry.bind("<KeyRelease>", self._on_search_change)

        # Refresh button
        ctk.CTkButton(
            top, text="🔄 Refresh", width=90, command=self._on_refresh_click,
        ).pack(side="right", padx=4)

        # 状态行
        status = ctk.CTkFrame(self.frame, fg_color="transparent", height=20)
        status.pack(fill="x", padx=8, pady=(0, 4))
        self._status_label = ctk.CTkLabel(
            status, text="", text_color="gray", font=ctk.CTkFont(size=11),
        )
        self._status_label.pack(side="left")

        # 卡片网格
        self._cards_frame = ctk.CTkScrollableFrame(self.frame, label_text="")
        self._cards_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Stage 3 (v1.3.0): 模型加载骨架屏覆盖层
        self._skeleton_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        for _i in range(4):
            SkeletonLine(self._skeleton_frame, width="full").pack(
                fill="x", padx=4, pady=3,
            )
        self._skeleton_visible = False

        # toast（隐藏式）
        self._toast_label = ctk.CTkLabel(
            self.frame, text="", fg_color="#2ecc71", text_color="white",
            corner_radius=6, padx=12, pady=4,
        )
        # 不立即 pack；show_toast 时短暂置于底部居中

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------
    def _on_provider_change(self, value: str) -> None:
        self._provider = value
        self._render_cards()

    def _on_sort_change(self, value: str) -> None:
        self._sort_by = value
        self._render_cards()

    def _on_search_change(self, _event: Any = None) -> None:
        try:
            self._search = self._search_var.get()
        except Exception:
            self._search = ""
        self._render_cards()

    def _on_refresh_click(self) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # 渲染卡片网格
    # ------------------------------------------------------------------
    def _render_cards(self) -> None:
        # Stage 3 (v1.3.0): 隐藏骨架屏
        self._hide_skeleton()

        # 清空旧卡片
        if self._cards_frame is not None:
            for w in list(self._cards_frame.winfo_children()):
                try:
                    w.destroy()
                except Exception:
                    logger.debug("Failed to destroy card widget", exc_info=True)

        provider_key = _PROVIDER_NORMALIZE.get(self._provider.lower(), "all")
        try:
            models = self._catalog.list(
                provider=None if provider_key == "all" else provider_key,
                sort_by=self._sort_by,
                search=self._search or None,
            )
        except Exception as e:
            logger.exception("list models failed")
            self._set_status(f"Error loading models: {e}", "red")
            return

        if not models:
            ctk.CTkLabel(
                self._cards_frame,
                text="(no models match the current filter)",
                text_color="gray",
            ).grid(row=0, column=0, padx=8, pady=16)
            self._set_status(f"0 models", "gray")
            return

        # 4 列网格
        cols = 4
        for idx, model in enumerate(models):
            r, c = divmod(idx, cols)
            self._build_card(self._cards_frame, model).grid(
                row=r, column=c, padx=6, pady=6, sticky="nsew",
            )

        # 列权重
        for c in range(cols):
            self._cards_frame.grid_columnconfigure(c, weight=1, uniform="model_col")

        self._set_status(
            f"{len(models)} model(s) — source: {self._catalog.info().get('source', '?')}",
            "gray",
        )

    def _build_card(self, parent: Any, model: ModelInfo) -> Any:
        card = ctk.CTkFrame(parent, corner_radius=8, border_width=1, border_color="#3a3a4a")

        # Provider
        ctk.CTkLabel(
            card, text=model.provider, text_color="#7f8fa6",
            font=ctk.CTkFont(size=11), anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 0))

        # Name
        ctk.CTkLabel(
            card, text=model.name, font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w", wraplength=220, justify="left",
        ).pack(fill="x", padx=10, pady=(0, 2))

        # ID (truncated)
        ctk.CTkLabel(
            card, text=model.id, text_color="gray",
            font=ctk.CTkFont(size=10), anchor="w", wraplength=220, justify="left",
        ).pack(fill="x", padx=10, pady=(0, 4))

        # Context
        ctk.CTkLabel(
            card, text=f"ctx: {self._format_int(model.context_length)}",
            anchor="w", font=ctk.CTkFont(size=11),
        ).pack(fill="x", padx=10, pady=1)

        # Price
        price_text = (
            f"in ${model.prompt_price:.2f}/M  ·  out ${model.completion_price:.2f}/M"
        )
        ctk.CTkLabel(
            card, text=price_text, anchor="w",
            font=ctk.CTkFont(size=11), text_color="#a0a0a0",
        ).pack(fill="x", padx=10, pady=(0, 6))

        # Select button
        ctk.CTkButton(
            card, text="Use this model", height=26,
            command=lambda m=model: self._on_card_select(m),
        ).pack(fill="x", padx=10, pady=(2, 10))

        return card

    # ------------------------------------------------------------------
    # 选中
    # ------------------------------------------------------------------
    def _on_card_select(self, model: ModelInfo) -> None:
        # 写入 ConfigLoader
        try:
            self._config.set(self.SELECTED_KEY, model.id, persist=True)
        except Exception as e:  # pragma: no cover
            logger.warning("set selected_model failed: %s", e)
            self.show_toast(f"Failed to save: {e}", error=True)
            return

        # 回调
        try:
            if self._on_select_cb is not None:
                self._on_select_cb(model)
        except Exception:  # pragma: no cover
            logger.exception("on_select callback failed")

        self.show_toast(f"✓ Selected: {model.id}")

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """重新加载目录（强制从网络/Cache 拉一次）"""
        self._show_skeleton()
        try:
            self._catalog.refresh()
        except Exception as e:  # pragma: no cover
            logger.warning("catalog.refresh failed: %s", e)
        self._render_cards()

    def show_toast(self, message: str, *, error: bool = False) -> None:
        """显示 2 秒 toast（覆盖式浮层）"""
        if self._toast_label is None:
            return
        # 取消上次的定时
        if self._toast_after_id is not None:
            try:
                self.frame.after_cancel(self._toast_after_id)
            except Exception:
                logger.debug("Failed to cancel toast timer", exc_info=True)
            self._toast_after_id = None
        try:
            self._toast_label.configure(
                text=message,
                fg_color="#e74c3c" if error else "#2ecc71",
            )
            self._toast_label.place(relx=0.5, rely=0.95, anchor="s")
        except Exception:  # pragma: no cover
            logger.debug("Failed to show toast", exc_info=True)
            return
        try:
            self._toast_after_id = self.frame.after(2000, self._hide_toast)
        except Exception:
            logger.debug("Failed to set toast hide timer", exc_info=True)

    def _hide_toast(self) -> None:
        if self._toast_label is not None:
            try:
                self._toast_label.place_forget()
            except Exception:
                logger.debug("Failed to hide toast", exc_info=True)
        self._toast_after_id = None

    def _set_status(self, text: str, color: str = "gray") -> None:
        if self._status_label is None:
            return
        try:
            self._status_label.configure(text=text, text_color=color)
        except Exception:  # pragma: no cover
            logger.debug("Failed to set status label", exc_info=True)

    # ------------------------------------------------------------------
    # Stage 3 (v1.3.0): 骨架屏
    # ------------------------------------------------------------------
    def _show_skeleton(self) -> None:
        """显示模型加载骨架屏（覆盖卡片网格区域）。"""
        if self._skeleton_visible:
            return
        self._skeleton_visible = True
        self._skeleton_frame.place(
            relx=0, rely=0, relwidth=1, relheight=1,
        )
        self._skeleton_frame.lift()

    def _hide_skeleton(self) -> None:
        """隐藏模型加载骨架屏。"""
        if not self._skeleton_visible:
            return
        self._skeleton_visible = False
        self._skeleton_frame.place_forget()

    # ------------------------------------------------------------------
    # 内部 helper
    # ------------------------------------------------------------------
    @staticmethod
    def _format_int(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}k"
        return str(n)


__all__ = ["ModelsTab", "PROVIDER_FILTERS", "SORT_OPTIONS"]
