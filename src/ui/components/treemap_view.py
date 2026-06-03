"""Treemap visualization component.

Stage 3 — upgraded with:

* Squarified Treemap layout (Bruls et al. 2000) via the pure-Python
  :mod:`src.ui.components.squarify` module.  No third-party
  ``squarify`` package is required any more for the layout itself.
* A breadcrumb toolbar with ``Up`` and ``Home`` buttons that
  delegate to a :class:`DrillDownController`.
* Matplotlib hover tooltips that display the full path and human
  readable size of the rectangle under the cursor.
* A double-click handler that asks the controller to enter the
  selected directory.

The v1.0.0 public API (:meth:`update_treemap`, :meth:`clear`) is
preserved verbatim so existing callers keep working.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import customtkinter as ctk

try:
    import tkinter as tk
except Exception:  # pragma: no cover - tkinter missing
    tk = None  # type: ignore[assignment]

import matplotlib
# Force the Tk-friendly backend before pyplot is touched anywhere.
matplotlib.use("TkAgg", force=False)
import matplotlib.pyplot as _plt  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402

from ...models.file_info import FileInfo
from .squarify import Rect, squarify as _squarify


_MAX_DRAW = 200  # how many rectangles to actually render (perf cap)


def _format_size(size: int) -> str:
    if size < 1024:
        return "{} B".format(size)
    if size < 1024 ** 2:
        return "{:.2f} KB".format(size / 1024)
    if size < 1024 ** 3:
        return "{:.2f} MB".format(size / (1024 ** 2))
    return "{:.2f} GB".format(size / (1024 ** 3))


class TreemapView(ctk.CTkFrame):
    """Treemap visualization component.

    The component is split into two vertical sections:

    1. A toolbar at the top with the current path, an ``Up`` button
       and a ``Home`` button.
    2. A matplotlib canvas that renders the squarified treemap.

    Public API
    ----------
    update_treemap(files)  — v1.0.0 legacy entry point
    set_data(items)        — Stage 3 entry point
    clear()                — v1.0.0 legacy entry point
    set_drill_controller(c) — Stage 3: wire up a DrillDownController
    zoom_to(path)          — Stage 3: jump to ``path`` programmatically
    """

    def __init__(self, master):
        super().__init__(master, corner_radius=10)
        self._items: List[FileInfo] = []
        self._rect_to_item: Dict[int, FileInfo] = {}
        self._current_path: str = ""
        self._controller = None  # type: ignore[var-annotated]
        self._tooltip: Optional[tk.Toplevel] = None  # type: ignore[name-defined]

        self.fig = None
        self.ax = None
        self.canvas = None
        self._setup_ui()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar: breadcrumb + Up + Home
        self._toolbar = ctk.CTkFrame(self, fg_color="transparent", height=32)
        self._toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        self._toolbar.grid_propagate(False)
        self._toolbar.grid_columnconfigure(0, weight=1)

        self._breadcrumb = ctk.CTkLabel(
            self._toolbar,
            text="(root)",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color="#cdd6f4",
        )
        self._breadcrumb.grid(row=0, column=0, sticky="ew", padx=(6, 8), pady=4)

        self._home_button = ctk.CTkButton(
            self._toolbar,
            text="\U0001F3E0",  # 🏠
            width=32,
            height=24,
            command=self._on_home,
        )
        self._home_button.grid(row=0, column=1, padx=2, pady=2)

        self._up_button = ctk.CTkButton(
            self._toolbar,
            text="\u2B06",  # ⬆
            width=32,
            height=24,
            command=self._on_up,
        )
        self._up_button.grid(row=0, column=2, padx=2, pady=2)

        # Matplotlib canvas
        self.fig, self.ax = _plt.subplots(1, 1, figsize=(8, 6))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        # Event bindings
        self._cid_press = self.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self._cid_motion = self.canvas.mpl_connect("motion_notify_event", self._on_canvas_motion)
        self._cid_leave = self.canvas.mpl_connect("figure_leave_event", self._hide_tooltip)

    # ----------------------------------------------------------- v1.0.0 API

    def update_treemap(self, files: List[FileInfo]) -> None:
        """Update Treemap (legacy v1.0.0 entry point)."""
        self.set_data(files)

    def clear(self) -> None:
        """Clear the chart (legacy v1.0.0 entry point)."""
        if self.ax is not None:
            self.ax.clear()
            self.ax.set_axis_off()
        if self.canvas is not None:
            self.canvas.draw()
        self._items = []
        self._rect_to_item = {}

    # ----------------------------------------------------------- Stage 3 API

    def set_data(self, items: List[FileInfo]) -> None:
        """Render ``items`` as a squarified treemap.

        ``items`` may be a mix of files and directories.  Items with
        size <= 0 are dropped.  Rendering is capped at
        :data:`_MAX_DRAW` rectangles to keep the canvas responsive on
        very large folders; the cap is applied after sorting by size
        descending so the most important rectangles survive.
        """
        self._items = list(items) if items else []
        if self.controller is not None and self._current_path:
            self._breadcrumb.configure(text=self._current_path)
        else:
            self._breadcrumb.configure(text="(root)" if not self._items else "(scanned)")
        self._render()

    def set_drill_controller(self, controller) -> None:
        """Wire up a :class:`DrillDownController`.

        The controller's path-change callback is overridden to call
        :meth:`set_data` with the new path's children.
        """
        self._controller = controller
        if controller is not None:
            try:
                controller.set_on_path_change(self._on_path_change)
            except Exception:
                pass
            # Push the initial render so the view is in sync with
            # the controller's current path.
            try:
                self._on_path_change(controller.current_path())
            except Exception:
                pass

    @property
    def controller(self):
        """Return the currently wired :class:`DrillDownController`."""
        return self._controller

    def zoom_to(self, path: str) -> None:
        """Programmatically navigate to ``path``.

        If a controller has been wired, delegates to
        :meth:`DrillDownController.enter`; otherwise re-renders the
        view from ``controller.get_children(path)`` (best effort).
        """
        if self._controller is not None:
            self._controller.enter(path)
            return
        # No controller — try to drive a controller-less re-render
        # by reading the path directly.
        self._current_path = path or ""
        self._breadcrumb.configure(text=self._current_path or "(root)")
        if self._controller is not None:
            items = self._controller.get_children(self._current_path)
        else:
            items = self._standalone_load(self._current_path)
        self.set_data(items)

    # ----------------------------------------------------------- internals

    def _on_home(self) -> None:
        if self._controller is not None:
            self._controller.home()

    def _on_up(self) -> None:
        if self._controller is not None:
            new_path = self._controller.up()
            # ``up`` returns None at the root; nothing to render.
            if new_path is None:
                return

    def _on_path_change(self, path: str) -> None:
        """Default :class:`DrillDownController` callback.

        Always called on the master thread (the controller schedules
        it via ``after(0, ...)``).  Re-renders the treemap with the
        children of ``path`` and updates the breadcrumb.
        """
        self._current_path = path or ""
        try:
            self._breadcrumb.configure(text=self._current_path or "(root)")
        except Exception:
            pass
        items: List[FileInfo] = []
        if self._controller is not None:
            try:
                items = self._controller.get_children(self._current_path)
            except Exception:
                items = []
        else:
            items = self._standalone_load(self._current_path)
        self.set_data(items)

    @staticmethod
    def _standalone_load(path: str) -> List[FileInfo]:
        """Best-effort loader used when no controller is wired."""
        if not path:
            return []
        p = Path(path)
        if not p.exists():
            return []
        if p.is_file():
            try:
                return [FileInfo.from_path(p, depth=0)]
            except Exception:
                return []
        try:
            children = list(p.iterdir())
        except (PermissionError, OSError):
            return []
        items: List[FileInfo] = []
        for child in children:
            try:
                items.append(FileInfo.from_path(child, depth=0))
            except Exception:
                continue
        items.sort(key=lambda f: -f.size)
        return items

    def _render(self) -> None:
        """Recompute the layout and redraw the matplotlib axes."""
        if self.ax is None or self.canvas is None:
            return
        self.ax.clear()

        # Drop non-positive sizes and pick the most important ones.
        positive = [it for it in self._items if it.size > 0]
        positive.sort(key=lambda it: -it.size)
        positive = positive[:_MAX_DRAW]
        self._rect_to_item = {}

        if not positive:
            self.ax.text(
                0.5, 0.5,
                "No data to display",
                ha="center", va="center",
                transform=self.ax.transAxes,
                fontsize=14, color="#888888",
            )
            self.ax.set_axis_off()
            self.canvas.draw_idle()
            return

        # Build (label, area) pairs.  We use the file's name as the
        # label and a small epsilon so the squarify step never has
        # to deal with zero areas.
        pairs: List[tuple] = []
        for it in positive:
            label = it.name or str(it.path)
            area = max(1, int(it.size))
            pairs.append((label, float(area)))
        rects: List[Rect] = _squarify(pairs, 100, 100)

        cmap = _plt.get_cmap('Spectral')
        n = len(rects)
        for idx, r in enumerate(rects):
            face = cmap(idx / max(1, n - 1)) if n > 1 else cmap(0.5)
            patch = matplotlib.patches.Rectangle(
                (r.x, r.y), r.w, r.h,
                facecolor=face, edgecolor='white',
                alpha=0.85, linewidth=1.5,
            )
            self.ax.add_patch(patch)
            self._rect_to_item[idx] = positive[idx]
            if r.w > 6 and r.h > 6:
                # Use id() as the lookup key in the click handler so
                # we never get confused by hash collisions.
                self.ax.text(
                    r.x + r.w / 2, r.y + r.h / 2,
                    positive[idx].name,
                    ha='center', va='center',
                    fontsize=max(6, min(12, int(min(r.w, r.h) / 6))),
                    color='black',
                )
        self.ax.set_xlim(0, 100)
        self.ax.set_ylim(100, 0)  # y origin at top-left
        self.ax.set_aspect('auto')
        self.ax.set_axis_off()
        self.canvas.draw_idle()

    # --------------------------------------------------- interaction hooks

    def _on_canvas_click(self, event) -> None:
        """Handle clicks on the canvas.

        Single click = nothing; double click on a directory tells
        the controller to enter it.
        """
        if event is None or event.inaxes is not self.ax:
            return
        if event.dblclick:
            rect = self._rect_at(event.xdata, event.ydata)
            if rect is None:
                return
            item = self._rect_to_item.get(id(rect))
            if item is None:
                return
            if not item.is_directory:
                return
            target = str(item.path)
            if self._controller is not None:
                self._controller.enter(target)
            else:
                self.zoom_to(target)

    def _rect_at(self, x: Optional[float], y: Optional[float]) -> Optional[Rect]:
        if x is None or y is None:
            return None
        # ``_render`` is the only place that populates the layout
        # so we recompute it on the fly — cheap because the input
        # is at most ``_MAX_DRAW`` rectangles.
        positive = [it for it in self._items if it.size > 0]
        positive.sort(key=lambda it: -it.size)
        positive = positive[:_MAX_DRAW]
        if not positive:
            return None
        pairs = [(it.name or str(it.path), float(max(1, int(it.size)))) for it in positive]
        rects = _squarify(pairs, 100, 100)
        for idx, r in enumerate(rects):
            if r.x <= x <= r.x + r.w and r.y <= y <= r.y + r.h:
                return r
        return None

    def _on_canvas_motion(self, event) -> None:
        if event is None or event.inaxes is not self.ax:
            self._hide_tooltip(event)
            return
        rect = self._rect_at(event.xdata, event.ydata)
        if rect is None:
            self._hide_tooltip(event)
            return
        # Find the matching item
        positive = [it for it in self._items if it.size > 0]
        positive.sort(key=lambda it: -it.size)
        positive = positive[:_MAX_DRAW]
        if not positive:
            self._hide_tooltip(event)
            return
        pairs = [(it.name or str(it.path), float(max(1, int(it.size)))) for it in positive]
        rects = _squarify(pairs, 100, 100)
        target = None
        for idx, r in enumerate(rects):
            if r is rect or (r.x == rect.x and r.y == rect.y and r.w == rect.w and r.h == rect.h):
                target = positive[idx]
                break
        if target is None:
            self._hide_tooltip(event)
            return
        self._show_tooltip(event, target)

    def _show_tooltip(self, event, item: FileInfo) -> None:
        if tk is None or self.canvas is None:
            return
        try:
            widget = self.canvas.get_tk_widget()
            x_root = widget.winfo_rootx() + int(event.x)
            y_root = widget.winfo_rooty() + int(event.y)
        except Exception:
            return
        text = "{}\n{}".format(item.path, _format_size(item.size))
        if item.is_directory:
            text += "  (folder — double-click to enter)"
        if self._tooltip is None:
            try:
                self._tooltip = tk.Toplevel(widget)
                self._tooltip.wm_overrideredirect(True)
                self._tooltip_label = tk.Label(
                    self._tooltip,
                    text=text,
                    justify='left',
                    background='#1e1e2e',
                    foreground='#cdd6f4',
                    relief='solid',
                    borderwidth=1,
                    font=('Consolas', 9),
                    padx=6, pady=3,
                )
                self._tooltip_label.pack()
            except Exception:
                self._tooltip = None
                return
        else:
            try:
                self._tooltip_label.configure(text=text)
            except Exception:
                return
        try:
            self._tooltip.wm_geometry("+{}+{}".format(x_root + 12, y_root + 12))
            self._tooltip.deiconify()
        except Exception:
            pass

    def _hide_tooltip(self, event=None) -> None:  # noqa: ARG002
        if self._tooltip is None:
            return
        try:
            self._tooltip.withdraw()
        except Exception:
            pass


__all__ = ['TreemapView']
