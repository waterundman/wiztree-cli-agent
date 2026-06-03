"""Skeleton loading widgets (Stage 1).

Provides two components:

* :class:`SkeletonWidget` — a grid of pulsing grey placeholder
  rectangles that simulate content being loaded.
* :class:`SkeletonLine` — a single-line placeholder bar with
  configurable width (``'full'``, ``'half'``, ``'quarter'``).

Both widgets inherit from ``ctk.CTkFrame`` and are designed to be
replaced by real content once loading completes.
"""
from __future__ import annotations

import math
import time
from typing import Optional

import customtkinter as ctk

# Default skeleton grey (used when no theme is available)
_DEFAULT_SKELETON_COLOR = "#3a3a3a"
_PULSE_LOW = 42   # hex 0x2a — darkest grey in the pulse cycle
_PULSE_HIGH = 74  # hex 0x4a — lightest grey in the pulse cycle
_PULSE_FPS_INTERVAL_MS = 33  # ~30 fps


def _get_theme_skeleton_color() -> str:
    """Try to derive a skeleton colour from the current theme.

    Falls back to ``_DEFAULT_SKELETON_COLOR`` when customtkinter is
    not available or no theme colour can be resolved.
    """
    try:
        fg = ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
        if isinstance(fg, (list, tuple)):
            fg = fg[1] if len(fg) > 1 else fg[0]
        return fg  # type: ignore[return-value]
    except Exception:
        return _DEFAULT_SKELETON_COLOR


# ---------------------------------------------------------------------------
# SkeletonWidget
# ---------------------------------------------------------------------------
class SkeletonWidget(ctk.CTkFrame):
    """Grid of pulsing grey placeholder rectangles.

    Parameters
    ----------
    rows : int
        Number of placeholder rows (default 3).
    cols : int
        Number of placeholder columns (default 1).
    corner_radius : int
        Rounded-corner radius for each rectangle (default 4).
    """

    def __init__(self, master=None, *, rows: int = 3, cols: int = 1,
                 corner_radius: int = 4, **kwargs):
        super().__init__(master, **kwargs)

        self._rows = rows
        self._cols = cols
        self._corner_radius = corner_radius
        self._running = False
        self._start_time: float = 0.0
        self._after_id: Optional[str] = None

        # Base colour from theme
        self._base_color = _get_theme_skeleton_color()

        # Create placeholder rectangles
        self._rectangles: list[ctk.CTkFrame] = []
        for r in range(rows):
            for c in range(cols):
                rect = ctk.CTkFrame(
                    self,
                    corner_radius=corner_radius,
                    fg_color=self._base_color,
                    height=20,
                )
                rect.grid(row=r, column=c, padx=4, pady=4, sticky="ew")
                self._rectangles.append(rect)

        # Make columns expand equally
        for c in range(cols):
            self.columnconfigure(c, weight=1)

    # -- public API --------------------------------------------------------

    def start(self) -> None:
        """Start the pulse animation."""
        if self._running:
            return
        self._running = True
        self._start_time = time.monotonic()
        self._pulse()

    def stop(self) -> None:
        """Stop the animation and hide the widget."""
        self._running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:  # pragma: no cover — defensive
                pass
            self._after_id = None
        # Hide using whichever geometry manager was used
        try:
            self.pack_forget()
        except Exception:
            pass
        try:
            self.grid_forget()
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the pulse animation is active."""
        return self._running

    # -- internal ----------------------------------------------------------

    def _pulse(self) -> None:
        if not self._running:
            return
        elapsed = time.monotonic() - self._start_time
        # Smooth sine-wave pulse between _PULSE_LOW and _PULSE_HIGH
        gray = int(_PULSE_LOW + (_PULSE_HIGH - _PULSE_LOW) *
                   (0.5 + 0.5 * math.sin(elapsed * 3.0)))
        color = f"#{gray:02x}{gray:02x}{gray:02x}"
        for rect in self._rectangles:
            rect.configure(fg_color=color)
        self._after_id = self.after(_PULSE_FPS_INTERVAL_MS, self._pulse)


# ---------------------------------------------------------------------------
# SkeletonLine
# ---------------------------------------------------------------------------
class SkeletonLine(ctk.CTkFrame):
    """Single-line placeholder bar.

    Parameters
    ----------
    width : str
        One of ``'full'`` (100 %), ``'half'`` (50 %), ``'quarter'``
        (25 %).  Defaults to ``'full'``.
    """

    _WIDTH_MAP = {
        "full": 1.0,
        "half": 0.5,
        "quarter": 0.25,
    }

    def __init__(self, master=None, *, width: str = "full", **kwargs):
        ratio = self._WIDTH_MAP.get(width)
        if ratio is None:
            raise ValueError(
                f"width must be one of {list(self._WIDTH_MAP)}, got {width!r}"
            )

        kwargs.setdefault("height", 16)
        kwargs.setdefault("corner_radius", 4)
        kwargs.setdefault("fg_color", _get_theme_skeleton_color())

        super().__init__(master, **kwargs)

        self._width_ratio = ratio
        self._requested_width = width

        # Apply the proportional width after the widget is mapped
        self.after_idle(self._apply_width)

    # -- public API --------------------------------------------------------

    @property
    def width_ratio(self) -> float:
        """Return the configured width ratio (0.0 – 1.0)."""
        return self._width_ratio

    # -- internal ----------------------------------------------------------

    def _apply_width(self) -> None:
        """Scale to the requested fraction of the parent."""
        parent = self.master
        if parent is None:
            return
        try:
            parent_w = parent.winfo_width()
            if parent_w > 1:
                target = int(parent_w * self._width_ratio)
                self.configure(width=target)
        except Exception:  # pragma: no cover — defensive
            pass
