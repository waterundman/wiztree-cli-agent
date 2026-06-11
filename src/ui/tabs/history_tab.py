"""
HistoryTab — 审计历史 + 还原标签页 (v1.2.0 / Stage 5)

布局
====

::

    ┌─────────────────────────────────────────────────────────────────┐
    │ Search: [_______]  Type: [All ▾]  🔄 Refresh  📊 Stats         │  ← 顶栏 toolbar
    ├─────────────────────────────────────────────────────────────────┤
    │ ID │ Time                │ Action     │ Path     │ Status │ User │  ← 中部 tree
    │ 12 │ 2026-06-01 18:21:33 │ file_delete│ C:\\x.tmp │ success│ wxy  │
    │ 11 │ 2026-06-01 18:20:00 │ scan       │ D:\      │ success│ wxy  │
    │ ...                                                              │
    ├─────────────────────────────────────────────────────────────────┤
    │ Details: {...}                          [↩️ Restore Selected]   │  ← 底部详情 + 按钮
    └─────────────────────────────────────────────────────────────────┘

交互
====

* Search:  按 ``target_path`` 模糊匹配（client-side 过滤；list_recent 不支持）
* Type:    All / file_delete / file_move / restore / scan
* Refresh: 重新调用 ``self.refresh()`` — Ctrl+R 也会触发 (Stage 4 KeyBindings)
* Stats:   弹窗显示 ``AuditLogger.get_stats()`` 总览
* 单击行 → 详情面板显示该条 ``metadata``
* Restore: 调用 ``AuditLogger.restore(action_id)`` 并显示 toast

设计原则 (与 Stage 2-4 一致)
=============================

* ``HistoryTab`` 内部 ``self.frame = ctk.CTkFrame(master, ...)`` 真正是 CTkFrame
* ``refresh()`` 公开 API，由 Ctrl+R 通过 ``KeyBindings._safe_refresh_tab`` 触发
* 不在 import 阶段 import ctk / tkinter；用 ``_CTK_AVAILABLE`` 探测
* 失败时优雅降级（log + 状态栏），不抛异常
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Dict

logger = logging.getLogger(__name__)

# 延迟 import ctk / ttk
try:
    import customtkinter as ctk
    import tkinter.ttk as ttk
    from tkinter import messagebox
    _CTK_AVAILABLE = True
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore
    ttk = None  # type: ignore
    messagebox = None  # type: ignore
    _CTK_AVAILABLE = False

from ...safety.audit_logger import AuditLogger  # noqa: E402

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
TYPE_FILTERS: List[str] = [
    "All", "file_delete", "file_move", "restore", "scan",
]

TREE_COLUMNS: List[str] = ["id", "time", "action", "path", "status", "user"]
TREE_HEADINGS: Dict[str, str] = {
    "id": "ID",
    "time": "Time",
    "action": "Action",
    "path": "Path",
    "status": "Status",
    "user": "User",
}
TREE_WIDTHS: Dict[str, int] = {
    "id": 50,
    "time": 160,
    "action": 100,
    "path": 360,
    "status": 80,
    "user": 100,
}


class HistoryTab:
    """
    History 标签页（Stage 5）。
    
    用法::
    
        tab = HistoryTab(parent_tab, audit_db_path="audit.db")
        # parent_tab 必须是一个 CTk 容器（通常是 CTkTabview.add() 的返回值）
        
    Attributes:
        frame:  ctk.CTkFrame（实际承载所有 UI 控件的容器）
        tree:   ttk.Treeview（中部树形表格）
        search_entry: ctk.CTkEntry（搜索框）
        type_filter:  ctk.CTkOptionMenu（类型过滤下拉）
        refresh_btn:  ctk.CTkButton（刷新）
        stats_btn:    ctk.CTkButton（统计弹窗）
        restore_btn:  ctk.CTkButton（还原）
    """
    
    DEFAULT_LIMIT: int = 50
    
    def __init__(
        self,
        master: Any,
        *,
        audit_db_path: str = "audit.db",
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        """
        Args:
            master:        父 CTk 容器（来自 ``tabview.add("...")``）
            audit_db_path: SQLite 数据库路径；与全项目 ``audit.db`` 共享
            audit_logger:  可选传入已有 AuditLogger 实例（便于测试 mock）
        """
        if not _CTK_AVAILABLE:
            raise RuntimeError(
                "customtkinter / tkinter 不可用，无法实例化 HistoryTab"
            )
        
        self._db_path = audit_db_path
        self._audit_logger = audit_logger or AuditLogger(audit_db_path)
        
        # 内部状态
        self._search: str = ""
        self._type_filter: str = "All"
        self._selected_id: Optional[int] = None
        self._selected_record: Optional[Dict[str, Any]] = None
        self._toast_after_id: Any = None
        self._stats_window: Any = None
        
        # UI 引用
        self._search_var: Any = None
        self._type_var: Any = None
        self._status_label: Any = None
        self._detail_box: Any = None
        self._toast: Any = None
        
        # 真正创建 CTkFrame
        self.frame: "ctk.CTkFrame" = ctk.CTkFrame(master, fg_color="transparent")
        self._build_ui()
        self.refresh()
    
    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # === 顶栏 toolbar ===
        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))
        
        # Search
        ctk.CTkLabel(top, text="Search:").pack(side="left", padx=(0, 4))
        self._search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            top, placeholder_text="path substring…", width=200,
            textvariable=self._search_var,
        )
        self.search_entry.pack(side="left", padx=4)
        self.search_entry.bind("<KeyRelease>", self._on_search_change)
        
        # Type filter
        ctk.CTkLabel(top, text="Type:").pack(side="left", padx=(8, 4))
        self._type_var = ctk.StringVar(value="All")
        self.type_filter = ctk.CTkOptionMenu(
            top, values=TYPE_FILTERS, variable=self._type_var, width=130,
            command=self._on_type_change,
        )
        self.type_filter.pack(side="left", padx=4)
        
        # Refresh
        self.refresh_btn = ctk.CTkButton(
            top, text="🔄 Refresh", width=110, command=self.refresh,
        )
        self.refresh_btn.pack(side="left", padx=4)
        
        # Stats
        self.stats_btn = ctk.CTkButton(
            top, text="📊 Stats", width=100, command=self._show_stats,
        )
        self.stats_btn.pack(side="left", padx=4)
        
        # 状态行（右侧）
        self._status_label = ctk.CTkLabel(
            top, text="", text_color="gray", font=ctk.CTkFont(size=11),
        )
        self._status_label.pack(side="right", padx=4)
        
        # === 中部 tree ===
        tree_frame = ctk.CTkFrame(self.frame)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        
        self.tree = ttk.Treeview(
            tree_frame, columns=TREE_COLUMNS, show="headings", height=12,
        )
        for col in TREE_COLUMNS:
            self.tree.heading(col, text=TREE_HEADINGS[col])
            anchor = "center" if col in ("id", "status", "user", "action") else "w"
            self.tree.column(col, width=TREE_WIDTHS[col], anchor=anchor)
        
        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview,
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 行选中
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        
        # === 底部详情 + 按钮 ===
        bottom = ctk.CTkFrame(self.frame, fg_color="transparent")
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(
            bottom, text="Details:", font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(2, 0))
        
        self._detail_box = ctk.CTkTextbox(
            bottom, height=70, font=ctk.CTkFont(family="Consolas", size=11),
            border_width=1, border_color="#45475a",
        )
        self._detail_box.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))
        self._detail_box.insert("1.0", "(select a row to view metadata)")
        self._detail_box.configure(state="disabled")
        
        # 还原按钮（右下方）
        self.restore_btn = ctk.CTkButton(
            bottom, text="↩️ Restore Selected", width=180, height=32,
            command=self._on_restore_click, state="disabled",
            fg_color="#2980b9", hover_color="#3498db",
        )
        self.restore_btn.grid(row=1, column=1, sticky="e", padx=4, pady=(0, 4))
        
        # toast（隐藏）
        self._toast = ctk.CTkLabel(
            self.frame, text="", fg_color="#2ecc71", text_color="white",
            corner_radius=6, padx=12, pady=4,
        )
    
    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def _on_search_change(self, _event: Any = None) -> None:
        try:
            self._search = (self._search_var.get() or "").strip()
        except Exception:
            logger.debug("Failed to get search variable", exc_info=True)
            self._search = ""
        self._render_tree()
    
    def _on_type_change(self, value: str) -> None:
        self._type_filter = value
        self.refresh()
    
    def _on_tree_select(self, _event: Any = None) -> None:
        sel = self.tree.selection()
        if not sel:
            self._selected_id = None
            self._selected_record = None
            self._set_detail_text("(select a row to view metadata)")
            try:
                self.restore_btn.configure(state="disabled")
            except Exception:
                logger.debug("Failed to disable restore button", exc_info=True)
            return
        item = self.tree.item(sel[0])
        values = item.get("values") or []
        if not values:
            return
        try:
            self._selected_id = int(values[0])
        except (ValueError, TypeError):
            self._selected_id = None
        # 从审计日志重新读取该 id 的完整记录（保证 metadata 是最新的）
        if self._selected_id is not None:
            record = self._find_record_by_id(self._selected_id)
            self._selected_record = record
            if record is not None:
                meta = record.get("metadata")
                meta_str = json_pretty(meta) if meta is not None else "(no metadata)"
                self._set_detail_text(
                    f"id={record.get('id')}\n"
                    f"timestamp={record.get('timestamp')}\n"
                    f"action_type={record.get('action_type')}\n"
                    f"target_path={record.get('target_path')}\n"
                    f"status={record.get('status')}\n"
                    f"user={record.get('user')}\n"
                    f"metadata:\n{meta_str}"
                )
                # 只有 file_delete / file_move 才能还原
                if record.get("action_type") in ("file_delete", "file_move"):
                    try:
                        self.restore_btn.configure(state="normal")
                    except Exception:
                        logger.debug("Failed to enable restore button", exc_info=True)
                else:
                    try:
                        self.restore_btn.configure(state="disabled")
                    except Exception:
                        logger.debug("Failed to disable restore button", exc_info=True)
        # else: keep restore disabled
    
    def _on_restore_click(self) -> None:
        if self._selected_id is None:
            return
        action_id = self._selected_id
        try:
            ok = self._audit_logger.restore(action_id)
        except Exception as e:
            logger.exception("restore failed")
            self.show_toast(f"Restore failed: {e}", error=True)
            return
        if ok:
            self.show_toast(f"✓ Restored action #{action_id}")
        else:
            self.show_toast(
                f"✗ Could not restore #{action_id} "
                "(missing trash entry / file gone / unsupported type)",
                error=True,
            )
        self.refresh()
    
    # ------------------------------------------------------------------
    # 数据加载 + 渲染
    # ------------------------------------------------------------------
    def _effective_action_type(self) -> Optional[str]:
        if self._type_filter and self._type_filter != "All":
            return self._type_filter
        return None
    
    def _load_records(self) -> List[Dict[str, Any]]:
        """从 AuditLogger 拉取原始记录（应用类型过滤；搜索是 client-side）。"""
        try:
            records = self._audit_logger.list_recent(
                limit=self.DEFAULT_LIMIT,
                action_type=self._effective_action_type(),
            )
        except Exception as e:
            logger.exception("list_recent failed")
            self._set_status(f"Load error: {e}", "red")
            return []
        return records
    
    def _apply_search_filter(
        self,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not self._search:
            return records
        needle = self._search.lower()
        out: List[Dict[str, Any]] = []
        for r in records:
            path = (r.get("target_path") or "").lower()
            if needle in path:
                out.append(r)
        return out
    
    def _find_record_by_id(self, action_id: int) -> Optional[Dict[str, Any]]:
        """从 list_recent(limit=self.DEFAULT_LIMIT) 中找 id 匹配的记录；
        若超出 limit 范围则用 list_recent(limit=1000) 再尝试一次（避免刷新时丢失选中）。"""
        try:
            for r in self._audit_logger.list_recent(limit=self.DEFAULT_LIMIT):
                if r.get("id") == action_id:
                    return r
            # 备选：扩大 limit 再查
            for r in self._audit_logger.list_recent(limit=1000):
                if r.get("id") == action_id:
                    return r
        except Exception:
            logger.warning("find_record_by_id failed", exc_info=True)
        return None
    
    def _render_tree(self) -> None:
        # 清空 tree
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
        except Exception:
            logger.debug("Failed to clear tree items", exc_info=True)
            return
        
        records = self._load_records()
        records = self._apply_search_filter(records)
        
        for r in records:
            ts = r.get("timestamp", "") or ""
            # 截到秒级显示
            if len(ts) > 19:
                ts = ts[:19]
            self.tree.insert(
                "", "end", values=(
                    r.get("id"),
                    ts,
                    r.get("action_type", ""),
                    r.get("target_path", ""),
                    r.get("status", ""),
                    r.get("user", ""),
                ),
            )
        
        suffix = (
            f" / search: '{self._search}'" if self._search else ""
        )
        self._set_status(
            f"{len(records)} record(s) [type={self._type_filter}{suffix}]",
            "gray",
        )
    
    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """
        重新从 audit.db 加载并渲染 tree。
        
        该方法也是 KeyBindings 探测的入口（Ctrl+R → tab.refresh()）。
        """
        self._render_tree()
    
    def _show_stats(self) -> None:
        """弹窗显示 AuditLogger.get_stats() 的总览。"""
        try:
            stats = self._audit_logger.get_stats()
        except Exception as e:
            logger.exception("get_stats failed")
            messagebox.showerror("Stats error", f"无法获取统计：{e}")
            return
        
        # 复用单一 stats 弹窗
        if self._stats_window is not None:
            try:
                self._stats_window.destroy()
            except Exception:
                logger.debug("Failed to destroy stats window", exc_info=True)
            self._stats_window = None
        
        win = ctk.CTkToplevel(self.frame)
        win.title("Audit Statistics")
        win.geometry("480x420")
        try:
            win.grab_set()
        except Exception:
            logger.debug("Failed to grab focus for stats window", exc_info=True)
        self._stats_window = win
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_stats(win))
        
        ctk.CTkLabel(
            win, text="📊 Audit Statistics",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(12, 8))
        
        body = ctk.CTkTextbox(
            win, font=ctk.CTkFont(family="Consolas", size=12),
            border_width=1, border_color="#45475a",
        )
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        body.insert("1.0", _format_stats(stats))
        body.configure(state="disabled")
        
        ctk.CTkButton(
            win, text="Close", width=100, command=lambda: self._close_stats(win),
        ).pack(pady=(0, 12))
    
    def _close_stats(self, win: Any) -> None:
        try:
            win.destroy()
        except Exception:
            logger.debug("Failed to destroy stats window", exc_info=True)
        if self._stats_window is win:
            self._stats_window = None
    
    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    def _set_status(self, text: str, color: str = "gray") -> None:
        if self._status_label is None:
            return
        try:
            self._status_label.configure(text=text, text_color=color)
        except Exception:
            logger.debug("Failed to set status label", exc_info=True)
    
    def _set_detail_text(self, text: str) -> None:
        if self._detail_box is None:
            return
        try:
            self._detail_box.configure(state="normal")
            self._detail_box.delete("1.0", "end")
            self._detail_box.insert("1.0", text)
            self._detail_box.configure(state="disabled")
        except Exception:
            logger.debug("Failed to set detail text", exc_info=True)
    
    def show_toast(self, message: str, *, error: bool = False) -> None:
        if self._toast is None:
            return
        if self._toast_after_id is not None:
            try:
                self.frame.after_cancel(self._toast_after_id)
            except Exception:
                logger.debug("Failed to cancel toast timer", exc_info=True)
            self._toast_after_id = None
        try:
            self._toast.configure(
                text=message,
                fg_color="#e74c3c" if error else "#2ecc71",
            )
            self._toast.place(relx=0.5, rely=0.95, anchor="s")
        except Exception:
            logger.debug("Failed to show toast", exc_info=True)
            return
        try:
            self._toast_after_id = self.frame.after(2500, self._hide_toast)
        except Exception:
            logger.debug("Failed to set toast hide timer", exc_info=True)
    
    def _hide_toast(self) -> None:
        if self._toast is not None:
            try:
                self._toast.place_forget()
            except Exception:
                logger.debug("Failed to hide toast", exc_info=True)
        self._toast_after_id = None


# ---------------------------------------------------------------------------
# 模块级 helper
# ---------------------------------------------------------------------------
def json_pretty(obj: Any) -> str:
    """Pretty-print JSON-like object (always str, never raises)."""
    import json as _json
    try:
        return _json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return repr(obj)


def _format_stats(stats: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=" * 50)
    lines.append("Total actions : {}".format(stats.get("total_actions", 0)))
    lines.append("Last 24h      : {}".format(stats.get("recent_24h", 0)))
    lines.append("=" * 50)
    lines.append("")
    lines.append("By type:")
    by_type = stats.get("by_type") or {}
    if by_type:
        for k in sorted(by_type.keys()):
            lines.append(f"  {k:<16} {by_type[k]}")
    else:
        lines.append("  (no data)")
    lines.append("")
    lines.append("By status:")
    by_status = stats.get("by_status") or {}
    if by_status:
        for k in sorted(by_status.keys()):
            lines.append(f"  {k:<16} {by_status[k]}")
    else:
        lines.append("  (no data)")
    return "\n".join(lines)


__all__ = ["HistoryTab", "TYPE_FILTERS"]
