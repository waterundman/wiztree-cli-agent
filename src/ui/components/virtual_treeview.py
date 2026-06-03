"""Virtual Treeview 组件 — 支持大数据集虚拟滚动。

Stage 1 (v1.4.0): 实现虚拟滚动模式，只渲染可见行 + 缓冲区（前后各 10 行）。
"""
from __future__ import annotations

import logging
import tkinter.ttk as ttk
from typing import Any, Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


class VirtualTreeview(ttk.Treeview):
    """支持虚拟滚动的 Treeview 组件。

    只渲染可见行 + 缓冲区（前后各 10 行），拦截滚动事件动态加载/卸载行。
    """

    def __init__(
        self,
        master: Any,
        columns: Tuple[str, ...] = (),
        buffer_size: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, columns=columns, **kwargs)
        self._all_data: List[Tuple[Any, ...]] = []
        self._visible_start: int = 0
        self._visible_end: int = 0
        self._buffer_size: int = buffer_size
        self._row_height: int = 20  # 默认行高
        self._total_rows: int = 0
        self._sort_column: Optional[str] = None
        self._sort_reverse: bool = False
        self._columns: Tuple[str, ...] = columns

        # 拦截滚动事件
        self.bind("<Configure>", self._on_configure)
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", self._on_mousewheel)  # Linux scroll up
        self.bind("<Button-5>", self._on_mousewheel)  # Linux scroll down

        # 重写 yview 和 yview_moveto
        self._orig_yview = self.yview
        self._orig_yview_moveto = self.yview_moveto
        self.yview = self._yview_override  # type: ignore[assignment]
        self.yview_moveto = self._yview_moveto_override  # type: ignore[assignment]

    def set_data(self, data: List[Tuple[Any, ...]]) -> None:
        """设置全量数据（不立即渲染）。"""
        self._all_data = list(data)
        self._total_rows = len(self._all_data)
        self._visible_start = 0
        self._visible_end = 0
        # 清空 Treeview
        super().delete(*super().get_children())

    def refresh(self) -> None:
        """刷新可见区域。"""
        self._update_visible_range()
        self._render_visible_rows()

    def visible_range(self) -> Tuple[int, int]:
        """返回当前可见行范围 (start, end)。"""
        return (self._visible_start, self._visible_end)

    def sort_by(self, column: str, reverse: bool = False) -> None:
        """按列排序。"""
        if not self._all_data:
            return

        col_idx = list(self._columns).index(column) if column in self._columns else 0
        self._all_data.sort(key=lambda row: row[col_idx] if col_idx < len(row) else "", reverse=reverse)
        self._sort_column = column
        self._sort_reverse = reverse
        self.refresh()

    def _on_configure(self, event: Any) -> None:
        """窗口大小变化时刷新。"""
        self._update_visible_range()
        self._render_visible_rows()

    def _on_mousewheel(self, event: Any) -> None:
        """鼠标滚轮事件。"""
        # 计算滚动行数
        if event.num == 4:  # Linux scroll up
            delta = -3
        elif event.num == 5:  # Linux scroll down
            delta = 3
        else:
            delta = -1 * (event.delta // 120)

        new_start = max(0, min(self._total_rows - 1, self._visible_start + delta))
        if new_start != self._visible_start:
            self._visible_start = new_start
            self._update_visible_range()
            self._render_visible_rows()

    def _yview_override(self, *args: Any) -> Any:
        """重写 yview 方法。"""
        if not args:
            return self._orig_yview()

        action = args[0]
        if action == "moveto":
            fraction = float(args[1])
            self._visible_start = int(fraction * self._total_rows)
            self._update_visible_range()
            self._render_visible_rows()
            return None
        elif action == "scroll":
            number = int(args[1])
            new_start = max(0, min(self._total_rows - 1, self._visible_start + number))
            if new_start != self._visible_start:
                self._visible_start = new_start
                self._update_visible_range()
                self._render_visible_rows()
            return None

        return self._orig_yview(*args)

    def _yview_moveto_override(self, fraction: str) -> None:
        """重写 yview_moveto 方法。"""
        self._visible_start = int(float(fraction) * self._total_rows)
        self._update_visible_range()
        self._render_visible_rows()

    def _update_visible_range(self) -> None:
        """计算可见行范围。"""
        if self._total_rows == 0:
            self._visible_start = 0
            self._visible_end = 0
            return

        # 计算可见行数
        try:
            height = self.winfo_height()
            visible_rows = max(1, height // self._row_height)
        except Exception:
            visible_rows = 15  # 默认值

        # 计算带缓冲区的范围
        start = max(0, self._visible_start - self._buffer_size)
        end = min(self._total_rows, self._visible_start + visible_rows + self._buffer_size)

        self._visible_start = max(0, min(self._visible_start, self._total_rows - visible_rows))
        self._visible_end = end

    def _render_visible_rows(self) -> None:
        """渲染可见行。"""
        # 批量删除
        children = super().get_children()
        if children:
            super().delete(*children)

        # 批量插入
        for i in range(self._visible_start, min(self._visible_end, self._total_rows)):
            row = self._all_data[i]
            super().insert("", "end", values=row, iid=str(i))

    def get_children(self, item: str = "") -> Tuple[str, ...]:
        """返回当前渲染的子项。"""
        return super().get_children(item)

    def delete(self, *items: str) -> None:
        """删除指定项。"""
        if items:
            super().delete(*items)

    def insert(self, parent: str, index: str, iid: Optional[str] = None, **kwargs: Any) -> str:
        """插入项（虚拟模式下不直接使用）。"""
        return super().insert(parent, index, iid=iid, **kwargs)

    def item(self, item: str, option: Optional[str] = None, **kwargs: Any) -> Any:
        """获取/设置项属性。"""
        return super().item(item, option=option, **kwargs)
