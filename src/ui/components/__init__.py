"""UI components module.

Stage 3 — exports the upgraded TreemapView, the new pure-Python
``squarify`` layout, the bottom :class:`StatusBar` and the
:class:`DrillDownController`.

Custom-tkinter based widgets (StatusBar, TreemapView) are imported
defensively so that pulling :mod:`src.ui.components` from a test
that does not need a real Tk root does not blow up.
"""
from __future__ import annotations

from .squarify import Rect, plot as squarify_plot, squarify

# These modules depend on customtkinter/tkinter at import time.  We
# try to import them eagerly — when the user is on a machine with a
# working display the public names are bound immediately.  When
# customtkinter is missing (e.g. headless CI) the names fall back
# to ``None`` and consumers can import them lazily.
try:
    from .drill_down import DrillDownController
except Exception:  # pragma: no cover - defensive
    DrillDownController = None  # type: ignore[misc,assignment]

try:
    from .status_bar import StatusBar
except Exception:  # pragma: no cover - defensive
    StatusBar = None  # type: ignore[misc,assignment]

try:
    from .treemap_view import TreemapView
except Exception:  # pragma: no cover - defensive
    TreemapView = None  # type: ignore[misc,assignment]

try:
    from .skeleton import SkeletonWidget, SkeletonLine
except Exception:  # pragma: no cover - defensive
    SkeletonWidget = None  # type: ignore[misc,assignment]
    SkeletonLine = None  # type: ignore[misc,assignment]

try:
    from .virtual_treeview import VirtualTreeview
except Exception:  # pragma: no cover - defensive
    VirtualTreeview = None  # type: ignore[misc,assignment]


def __getattr__(name):
    """Lazy re-export hook.

    Allows ``from src.ui.components import StatusBar`` to succeed
    even when :data:`StatusBar` was ``None`` at import time, by
    attempting a deferred import.
    """
    if name in {"DrillDownController", "StatusBar", "TreemapView",
                 "SkeletonWidget", "SkeletonLine", "VirtualTreeview"}:
        import importlib
        return importlib.import_module(
            "src.ui.components." + {
                "DrillDownController": "drill_down",
                "StatusBar": "status_bar",
                "TreemapView": "treemap_view",
                "SkeletonWidget": "skeleton",
                "SkeletonLine": "skeleton",
                "VirtualTreeview": "virtual_treeview",
            }[name]
        ).__dict__[name]
    raise AttributeError(name)


__all__ = [
    'DrillDownController',
    'Rect',
    'SkeletonLine',
    'SkeletonWidget',
    'StatusBar',
    'TreemapView',
    'VirtualTreeview',
    'squarify',
    'squarify_plot',
]
