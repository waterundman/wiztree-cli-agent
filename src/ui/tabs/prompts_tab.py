"""
PromptsTab — Prompt 编辑器标签页（v1.2.0 / Stage 2）

布局
====

::

    ┌────────────────────────────────────────────────────────────┐
    │ Active prompt: [default_scan ▾]   [+ New]  [💾 Save]  [🗑] │  ← 顶栏
    ├──────────────┬─────────────────────────────────────────────┤
    │  default_scan│  # Default scan prompt                       │  ← 左侧列表 / 右侧编辑器
    │  analyze_logs│  Analyze the following files and rank       │
    │  cleanup     │  them by ...                                 │
    │              │                                              │
    │              │  ...                                          │
    └──────────────┴─────────────────────────────────────────────┘

交互
====

* 切换 active → ``PromptStore.set_active(name)``
* 选列表项 → 加载到右侧编辑器
* 新建 → 弹出 ``CTkInputDialog`` 取名 + 清空编辑器
* 保存 → ``PromptStore.set(name, content)``
* 删除 → 二次确认后 ``PromptStore.delete(name)``，若是当前 active 则同步清空
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

try:
    import customtkinter as ctk
    from tkinter import simpledialog
    from tkinter import messagebox
    _CTK_AVAILABLE = True
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore
    simpledialog = None  # type: ignore
    messagebox = None  # type: ignore
    _CTK_AVAILABLE = False

from src.analyzer.prompt_store import PromptStore  # noqa: E402
from ..components.skeleton import SkeletonLine  # noqa: E402


class PromptsTab:
    """
    Prompts 标签页（不强制继承 ctk.CTkFrame —— 实例化时才延迟继承）。
    """

    PLACEHOLDER_NEW: str = "— select or create —"

    def __init__(
        self,
        master: Any,
        *,
        store: Optional[PromptStore] = None,
        on_active_change: Optional[Any] = None,
    ) -> None:
        """
        Args:
            master:            父容器
            store:             PromptStore 实例；None 则新建
            on_active_change:  active 变更回调（新 active 名）
        """
        if not _CTK_AVAILABLE:
            raise RuntimeError(
                "customtkinter / tkinter 不可用，无法实例化 PromptsTab"
            )

        self._store = store or PromptStore()
        self._on_active_cb = on_active_change
        self._current_name: Optional[str] = None
        self._dirty: bool = False
        self._toast_after_id: Any = None

        # UI refs
        self._list_frame: Any = None
        self._active_menu: Any = None
        self._active_var: Any = None
        self._editor: Any = None
        self._toast: Any = None
        self._dirty_label: Any = None

        # 真正创建 CTkFrame
        self.frame: "ctk.CTkFrame" = ctk.CTkFrame(master, fg_color="transparent")
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # 顶栏
        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(top, text="Active:").pack(side="left", padx=(0, 4))
        self._active_var = ctk.StringVar(value="")
        self._active_menu = ctk.CTkOptionMenu(
            top, values=[self.PLACEHOLDER_NEW],
            variable=self._active_var, width=200,
            command=self._on_active_select,
        )
        self._active_menu.pack(side="left", padx=4)

        ctk.CTkButton(top, text="+ New", width=80, command=self._on_new_click)\
            .pack(side="left", padx=4)
        ctk.CTkButton(top, text="💾 Save", width=80, command=self._on_save_click)\
            .pack(side="left", padx=4)
        ctk.CTkButton(top, text="🗑 Delete", width=80, command=self._on_delete_click)\
            .pack(side="left", padx=4)

        self._dirty_label = ctk.CTkLabel(
            top, text="", text_color="orange", font=ctk.CTkFont(size=11),
        )
        self._dirty_label.pack(side="right", padx=4)

        # 主区域：左 list + 右 editor
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        body.grid_columnconfigure(0, weight=1, uniform="prompts_split")
        body.grid_columnconfigure(1, weight=3, uniform="prompts_split")
        body.grid_rowconfigure(0, weight=1)

        # 左侧 list
        self._list_frame = ctk.CTkScrollableFrame(body, label_text="Prompts", width=200)
        self._list_frame.grid(row=0, column=0, padx=(0, 4), sticky="nsew")

        # Stage 3 (v1.3.0): Prompt 列表骨架屏覆盖层
        self._skeleton_frame = ctk.CTkFrame(body, fg_color="transparent")
        for _i in range(5):
            SkeletonLine(self._skeleton_frame, width="full").pack(
                fill="x", padx=4, pady=3,
            )
        self._skeleton_visible = False

        # 右侧 editor
        right = ctk.CTkFrame(body)
        right.grid(row=0, column=1, padx=(4, 0), sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        name_row = ctk.CTkFrame(right, fg_color="transparent")
        name_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        ctk.CTkLabel(name_row, text="Name:").pack(side="left")
        self._name_label = ctk.CTkLabel(
            name_row, text="(none)", font=ctk.CTkFont(weight="bold"),
        )
        self._name_label.pack(side="left", padx=8)

        self._editor = ctk.CTkTextbox(
            right, font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word", border_width=1, border_color="#45475a",
        )
        self._editor.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self._editor.bind("<<Modified>>", self._on_modified)
        # CTkTextbox 的 modified 事件不是原生，需要用 KeyRelease 兜底
        self._editor.bind("<KeyRelease>", self._on_modified)

        # toast (隐藏)
        self._toast = ctk.CTkLabel(
            self.frame, text="", fg_color="#2ecc71", text_color="white",
            corner_radius=6, padx=12, pady=4,
        )

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """重新加载列表 + active 状态。不会清空当前编辑器内容。"""
        self._show_skeleton()
        try:
            names = self._store.list()
        except Exception as e:  # pragma: no cover
            logger.exception("list prompts failed")
            names = []

        # Stage 3 (v1.3.0): 隐藏骨架屏
        self._hide_skeleton()

        # 1) 左侧 list
        if self._list_frame is not None:
            for w in list(self._list_frame.winfo_children()):
                try:
                    w.destroy()
                except Exception:
                    pass
            for name in names:
                btn = ctk.CTkButton(
                    self._list_frame, text=name, anchor="w",
                    fg_color="transparent", hover_color="#3a3a4a",
                    command=lambda n=name: self._on_pick(n),
                )
                btn.pack(fill="x", padx=2, pady=1)

        # 2) active 菜单
        values = [self.PLACEHOLDER_NEW] + names
        try:
            self._active_menu.configure(values=values)
        except Exception:  # pragma: no cover
            pass
        active = self._store.get_active() or ""
        try:
            self._active_var.set(active if active in names else "")
        except Exception:
            self._active_var.set("")

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def _on_pick(self, name: str) -> None:
        if self._dirty:
            ok = messagebox.askyesno(
                "Discard changes?",
                f"Current editor has unsaved changes. Discard and open '{name}'?",
            )
            if not ok:
                return
        self._current_name = name
        try:
            content = self._store.get(name) or ""
        except Exception as e:  # pragma: no cover
            logger.warning("get %s failed: %s", name, e)
            content = ""
        try:
            self._name_label.configure(text=name)
            self._editor.delete("1.0", "end")
            self._editor.insert("1.0", content)
        except Exception:
            pass
        self._set_dirty(False)

    def _on_active_select(self, value: str) -> None:
        if not value or value == self.PLACEHOLDER_NEW:
            try:
                self._store.set_active(None)
            except Exception as e:
                logger.warning("set_active(None) failed: %s", e)
                self.show_toast(f"Failed: {e}", error=True)
                return
            self.show_toast("Active prompt cleared")
            self._fire_active_cb(None)
            return
        try:
            self._store.set_active(value)
        except Exception as e:
            logger.warning("set_active(%s) failed: %s", value, e)
            self.show_toast(f"Failed: {e}", error=True)
            return
        self.show_toast(f"✓ Active: {value}")
        self._fire_active_cb(value)

    def _on_new_click(self) -> None:
        if self._dirty:
            ok = messagebox.askyesno(
                "Discard changes?",
                "Current editor has unsaved changes. Discard and create new?",
            )
            if not ok:
                return
        name = simpledialog.askstring(
            "New prompt", "Prompt name (letters/digits/._- and space):",
            parent=self.frame,
        )
        if not name:
            return
        name = name.strip()
        try:
            # set() 会触发 PromptStoreError on invalid name
            self._store.set(name, "")
        except Exception as e:
            messagebox.showerror("Cannot create", str(e))
            return
        self._current_name = name
        try:
            self._name_label.configure(text=name)
            self._editor.delete("1.0", "end")
        except Exception:
            pass
        self._set_dirty(True)
        self.refresh()
        self.show_toast(f"✓ Created '{name}' — write content and Save")

    def _on_save_click(self) -> None:
        if not self._current_name:
            messagebox.showinfo("Save", "Pick or create a prompt first.")
            return
        try:
            content = self._editor.get("1.0", "end-1c")
        except Exception:
            content = ""
        try:
            self._store.set(self._current_name, content)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self._set_dirty(False)
        self.show_toast(f"💾 Saved '{self._current_name}'")
        self.refresh()

    def _on_delete_click(self) -> None:
        if not self._current_name:
            return
        name = self._current_name
        ok = messagebox.askyesno(
            "Confirm delete", f"Delete prompt '{name}'? This cannot be undone.",
        )
        if not ok:
            return
        try:
            self._store.delete(name)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self._current_name = None
        try:
            self._name_label.configure(text="(none)")
            self._editor.delete("1.0", "end")
        except Exception:
            pass
        self._set_dirty(False)
        self.show_toast(f"🗑 Deleted '{name}'")
        self.refresh()

    def _on_modified(self, _event: Any = None) -> None:
        # 简化判断：KeyRelease 即视为 dirty
        self._set_dirty(True)

    # ------------------------------------------------------------------
    # dirty / toast
    # ------------------------------------------------------------------
    def _set_dirty(self, value: bool) -> None:
        self._dirty = bool(value)
        try:
            self._dirty_label.configure(text="● unsaved" if self._dirty else "")
        except Exception:
            pass

    def show_toast(self, message: str, *, error: bool = False) -> None:
        if self._toast is None:
            return
        if self._toast_after_id is not None:
            try:
                self.frame.after_cancel(self._toast_after_id)
            except Exception:
                pass
            self._toast_after_id = None
        try:
            self._toast.configure(
                text=message,
                fg_color="#e74c3c" if error else "#2ecc71",
            )
            self._toast.place(relx=0.5, rely=0.95, anchor="s")
        except Exception:  # pragma: no cover
            return
        try:
            self._toast_after_id = self.frame.after(2000, self._hide_toast)
        except Exception:
            pass

    def _hide_toast(self) -> None:
        if self._toast is not None:
            try:
                self._toast.place_forget()
            except Exception:
                pass
        self._toast_after_id = None

    def _fire_active_cb(self, name: Optional[str]) -> None:
        if self._on_active_cb is None:
            return
        try:
            self._on_active_cb(name)
        except Exception:  # pragma: no cover
            logger.exception("on_active_change callback failed")

    # ------------------------------------------------------------------
    # Stage 3 (v1.3.0): 骨架屏
    # ------------------------------------------------------------------
    def _show_skeleton(self) -> None:
        """显示 Prompt 列表骨架屏（覆盖列表区域）。"""
        if self._skeleton_visible:
            return
        self._skeleton_visible = True
        # list_frame 占 body 的 1/4（uniform="prompts_split" 权重 1:3）
        self._skeleton_frame.place(
            relx=0, rely=0, relwidth=0.25, relheight=1,
        )
        self._skeleton_frame.lift()

    def _hide_skeleton(self) -> None:
        """隐藏 Prompt 列表骨架屏。"""
        if not self._skeleton_visible:
            return
        self._skeleton_visible = False
        self._skeleton_frame.place_forget()


__all__ = ["PromptsTab"]
