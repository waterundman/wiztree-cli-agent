"""
DiffPreviewDialog — Before/After 差异预览对话框 (v1.2.0 / Stage 5)

用法::

    dlg = DiffPreviewDialog(parent, old_path="C:\\a.txt",
                             new_path=None, action="delete")
    if dlg.show():
        do_delete(...)

布局
====

::

    ┌──────────────────────────────────────────────────────┐
    │ Preview: delete                                       │
    ├──────────────────────────────────────────────────────┤
    │ Before:                                                │
    │   Path    : C:\\Users\\me\\a.txt                        │
    │   Size    : 12.4 KB                                   │
    │   Modified: 2026-05-31 14:22:11                       │
    │                                                       │
    │ After:                                                 │
    │   🗑️ DELETE                                           │
    │                                                       │
    │ ⚠️  This action can be restored from History tab      │
    │                                                       │
    │              [ Cancel ]   [ Confirm ]                 │
    └──────────────────────────────────────────────────────┘

设计原则
========

* ``show()`` 模态（grab_set），返回 ``True`` / ``False``
* 关闭 / Cancel → ``False``；Confirm → ``True``
* 当 ``action == 'delete'`` 且 new_path 为 None → 显示 🗑️ DELETE
* 当 ``action == 'move'`` 且 new_path 非空 → 显示 ↩️ MOVE to <new_path>
* 其他 action → 显示 new_path（或 "(no change)"）
* 文件不存在 / 无权限时，size / mtime 显示为 ``"(unavailable)"``，不抛异常
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import customtkinter as ctk
    from tkinter import messagebox
    _CTK_AVAILABLE = True
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore
    messagebox = None  # type: ignore
    _CTK_AVAILABLE = False


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
_DELETE_LABEL = "🗑️ DELETE"
_MOVE_PREFIX = "↩️ MOVE to "
_NO_AFTER = "(no change)"

_WARNING_TEXT = "⚠️  This action can be restored from History tab"


def _format_size(size: Optional[int]) -> str:
    if size is None or size < 0:
        return "(unavailable)"
    try:
        s = float(size)
    except (TypeError, ValueError):
        return "(unavailable)"
    if s < 1024:
        return f"{int(s)} B"
    if s < 1024 ** 2:
        return f"{s / 1024:.1f} KB"
    if s < 1024 ** 3:
        return f"{s / (1024 ** 2):.1f} MB"
    return f"{s / (1024 ** 3):.2f} GB"


def _format_mtime(mtime: Optional[float]) -> str:
    if mtime is None or mtime <= 0:
        return "(unavailable)"
    try:
        from datetime import datetime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "(unavailable)"


def _file_info(path: str) -> dict:
    """Best-effort 文件元信息；不抛异常。"""
    info = {"size_str": "(unavailable)", "mtime": "(unavailable)", "exists": False}
    if not path:
        return info
    try:
        if os.path.exists(path):
            info["exists"] = True
            st = os.stat(path)
            info["size_str"] = _format_size(int(st.st_size))
            info["mtime"] = _format_mtime(float(st.st_mtime))
    except OSError as e:
        logger.debug("stat(%s) failed: %s", path, e)
    return info


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------
class DiffPreviewDialog:
    """
    Before/After 差异预览弹窗（Stage 5）。
    
    Attributes:
        old_path: 操作前的路径
        new_path: 操作后的路径（delete 时为 None）
        action:   操作类型（'delete' / 'move' / 其他自由字符串）
        top:      ctk.CTkToplevel 实例
    """
    
    def __init__(
        self,
        parent: Any,
        old_path: str,
        new_path: Optional[str],
        action: str,
    ) -> None:
        """
        Args:
            parent:   父 CTk 控件
            old_path: 操作前的路径
            new_path: 操作后的路径（None 表示删除/不适用）
            action:   操作类型 — 'delete' / 'move' / 其他自由字符串
        """
        if not _CTK_AVAILABLE:
            raise RuntimeError(
                "customtkinter / tkinter 不可用，无法实例化 DiffPreviewDialog"
            )
        
        self.old_path = old_path
        self.new_path = new_path
        self.action = action
        self.result: bool = False  # 用户最终选择（True=Confirm, False=Cancel/Close）
        
        self.top: "ctk.CTkToplevel" = ctk.CTkToplevel(parent)
        self.top.title(f"Preview: {action}")
        self.top.geometry("620x440")
        self.top.resizable(True, True)
        
        # 模态
        try:
            self.top.grab_set()
        except Exception:
            logger.debug("Failed to grab focus for diff preview dialog", exc_info=True)
        try:
            self.top.focus_set()
        except Exception:
            logger.debug("Failed to set focus for diff preview dialog", exc_info=True)
        
        # 关窗协议
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        self._build_ui()
    
    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # 标题
        ctk.CTkLabel(
            self.top, text=f"Preview: {self.action}",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(12, 8))
        
        body = ctk.CTkFrame(self.top, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        
        # Before
        before = ctk.CTkFrame(body)
        before.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            before, text="Before:", font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 2))
        info = _file_info(self.old_path)
        for label, val in (
            ("Path", self.old_path or "(empty)"),
            ("Size", info["size_str"]),
            ("Modified", info["mtime"]),
        ):
            row = ctk.CTkFrame(before, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(
                row, text=f"  {label:<10}", font=ctk.CTkFont(size=12),
                text_color="gray", width=100, anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=str(val), font=ctk.CTkFont(size=12),
                anchor="w", wraplength=420, justify="left",
            ).pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(before, text="", height=2).pack(pady=(0, 4))
        
        # After
        after = ctk.CTkFrame(body)
        after.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            after, text="After:", font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 2))
        after_text = self._format_after()
        ctk.CTkLabel(
            after, text=f"  {after_text}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#e67e22" if self._is_destructive() else "#2ecc71",
            anchor="w", wraplength=540, justify="left",
        ).pack(fill="x", padx=10, pady=(0, 8))
        
        # Warning
        warn = ctk.CTkLabel(
            body, text=_WARNING_TEXT, text_color="#f39c12",
            font=ctk.CTkFont(size=12),
        )
        warn.pack(pady=(0, 8))
        
        # 按钮
        btn_frame = ctk.CTkFrame(self.top, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(
            btn_frame, text="Cancel", width=120, height=34,
            command=self._on_cancel,
        ).pack(side="right", padx=(8, 0))
        confirm_label = "🗑️ Confirm Delete" if self._is_destructive() else "✅ Confirm"
        ctk.CTkButton(
            btn_frame, text=confirm_label, width=160, height=34,
            fg_color="#c0392b" if self._is_destructive() else "#27ae60",
            hover_color="#e74c3c" if self._is_destructive() else "#2ecc71",
            command=self._on_confirm,
        ).pack(side="right")
    
    def _format_after(self) -> str:
        a = (self.action or "").lower()
        if a == "delete" or self.new_path is None and a != "move":
            return _DELETE_LABEL
        if a == "move":
            return f"{_MOVE_PREFIX}{self.new_path or '(unknown)'}"
        # 通用：显示 new_path
        return self.new_path or _NO_AFTER
    
    def _is_destructive(self) -> bool:
        a = (self.action or "").lower()
        return a in ("delete", "file_delete")
    
    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def _on_confirm(self) -> None:
        self.result = True
        self._close()
    
    def _on_cancel(self) -> None:
        self.result = False
        self._close()
    
    def _close(self) -> None:
        try:
            self.top.grab_release()
        except Exception:
            logger.debug("Failed to release grab for diff preview dialog", exc_info=True)
        try:
            self.top.destroy()
        except Exception:
            logger.debug("Failed to destroy diff preview dialog", exc_info=True)
    
    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def show(self) -> bool:
        """
        模态显示对话框并返回用户选择。
        
        Returns:
            True  = 用户按 Confirm
            False = 用户按 Cancel / 关窗
        """
        try:
            self.top.wait_window()
        except Exception:
            # 若 wait_window 失败（例如已销毁），返回当前 result
            logger.debug("wait_window failed (dialog may have been destroyed)", exc_info=True)
        return bool(self.result)


__all__ = ["DiffPreviewDialog"]
