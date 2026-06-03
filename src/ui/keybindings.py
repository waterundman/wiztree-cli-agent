"""
键盘快捷键注册 (v1.2.0 / Stage 4)
==================================

5 个快捷键（与 SPEC Stage 4 contract 一致）：
    Ctrl+S     : 启动扫描      (window._start_scan)
    Ctrl+R     : 刷新当前标签   (window.tabview.get().refresh())
    Ctrl+L     : 清空结果      (window._clear_results)
    Ctrl+,     : 打开设置      (window.open_settings)
    Escape     : 取消当前操作   (window._cancel_operation)

设计原则 — 优雅 fallback：
    - window 没有对应方法/属性时跳过该快捷键绑定（不抛异常）
    - window.bind() 抛异常时跳过该快捷键（不影响其他快捷键）
    - 这确保 v1.1.0 / Stages 1-3 中没有这些方法的应用仍然能工作

参考：
    - fezcode/atlas.doomwalker — TUI 键盘快捷键模式（Ctrl + 首字母）
    - thomastschinkel/prompt-os — Settings 齿轮按钮（Ctrl+,）
"""
from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


class KeyBindings:
    """键盘快捷键注册器（v1.2.0 / Stage 4）"""

    # 5 快捷键 → 方法映射
    # 每条：(event_seq, existence_attr, handler_id)
    #   - existence_attr: 用于 hasattr() 检查的 window 属性名
    #   - handler_id:    传给 _make_handler 决定如何调用
    SHORTCUTS: List[Tuple[str, str, str]] = [
        ("<Control-s>",     "_start_scan",      "_start_scan"),
        ("<Control-r>",     "tabview",          "tabview"),
        ("<Control-l>",     "_clear_results",   "_clear_results"),
        ("<Control-comma>", "open_settings",    "open_settings"),
        ("<Escape>",        "_cancel_operation", "_cancel_operation"),
    ]

    @staticmethod
    def bind_all(window: Any) -> None:
        """
        注册所有快捷键到 window。

        对每个快捷键：
            - 如果 window 不存在对应属性 → 跳过
            - 否则绑定（handler 是闭包，捕获 window）
        """
        for event_seq, existence_attr, handler_id in KeyBindings.SHORTCUTS:
            if not hasattr(window, existence_attr):
                logger.debug(
                    "KeyBindings: 跳过 %s — window 缺少 %s",
                    event_seq, existence_attr,
                )
                continue
            try:
                handler = KeyBindings._make_handler(window, handler_id)
                if handler is None:
                    continue
                window.bind(event_seq, handler)
            except Exception as e:  # pragma: no cover
                logger.debug("KeyBindings: 绑定 %s 失败: %s", event_seq, e)

    @staticmethod
    def _make_handler(window: Any, handler_id: str) -> Optional[Callable[[Any], None]]:
        """根据 handler_id 构造事件处理器（lambda 闭包）"""
        if handler_id == "_start_scan":
            return lambda e: window._start_scan()
        if handler_id == "_clear_results":
            return lambda e: window._clear_results()
        if handler_id == "open_settings":
            return lambda e: window.open_settings()
        if handler_id == "_cancel_operation":
            return lambda e: window._cancel_operation()
        if handler_id == "tabview":
            return lambda e: KeyBindings._safe_refresh_tab(window)
        return None  # pragma: no cover

    @staticmethod
    def _safe_refresh_tab(window: Any) -> None:
        """
        刷新当前标签。

        安全语义：如果当前 tab 没有 .refresh()（如 Scan / AI / File Actions tab），
        则 no-op，不抛异常。
        """
        try:
            tab = window.tabview.get()
            if tab is not None and hasattr(tab, "refresh"):
                tab.refresh()
        except Exception as e:  # pragma: no cover
            logger.debug("KeyBindings: 刷新当前标签失败: %s", e)
