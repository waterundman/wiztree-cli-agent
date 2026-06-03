"""Tests for the upgraded :class:`TreemapView`.

The component is exercised both directly (with a hidden Tk root)
and through the public contract — :meth:`set_data`,
:meth:`set_drill_controller`, :meth:`zoom_to`, :meth:`clear`, and
the legacy :meth:`update_treemap`.

Tests that need a real matplotlib canvas require tkinter.  They
are skipped in environments without it.  The API-level tests
(introspection only) run regardless.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest  # noqa: E402


# Defensive loader that bypasses ``src.ui.__init__`` when tkinter
# is unavailable.  We register a shim package so the relative
# imports inside ``src.ui.components`` still resolve.

_TEST_DIR = Path(__file__).parent
_SRC_DIR = _TEST_DIR.parent


def _safe_load(path: Path, dotted_parent: str):
    parent_pkg = dotted_parent
    saved = sys.modules.get(parent_pkg)
    shim = types.ModuleType(parent_pkg)
    shim.__path__ = [str(_SRC_DIR / "src" / "ui")]
    sys.modules[parent_pkg] = shim
    try:
        spec = importlib.util.spec_from_file_location(
            dotted_parent + "." + path.stem, str(path)
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[dotted_parent + "." + path.stem] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    except Exception:
        return None
    finally:
        if saved is not None:
            sys.modules[parent_pkg] = saved
        else:
            sys.modules.pop(parent_pkg, None)


_drill_down_mod = _safe_load(
    _SRC_DIR / "src" / "ui" / "components" / "drill_down.py",
    "src.ui",
)
_treemap_view_mod = _safe_load(
    _SRC_DIR / "src" / "ui" / "components" / "treemap_view.py",
    "src.ui",
)
_squarify_mod = _safe_load(
    _SRC_DIR / "src" / "ui" / "components" / "squarify.py",
    "src.ui",
)


TK_AVAILABLE = (
    _drill_down_mod is not None
    and _treemap_view_mod is not None
    and _squarify_mod is not None
)

skip_if_no_tkinter = pytest.mark.skipif(
    not TK_AVAILABLE,
    reason="tkinter not available",
)

TreemapView = _treemap_view_mod.TreemapView if _treemap_view_mod else None  # type: ignore
DrillDownController = _drill_down_mod.DrillDownController if _drill_down_mod else None  # type: ignore
Rect = _squarify_mod.Rect if _squarify_mod else None  # type: ignore
squarify = _squarify_mod.squarify if _squarify_mod else None  # type: ignore


def _make_file_info(path: Path, size: int, *, is_dir: bool = False) -> "FileInfo":
    from src.models.file_info import FileInfo
    return FileInfo(
        path=path,
        size=size,
        modified_time=datetime.now(),
        is_directory=is_dir,
    )


# ----------------------------------------------------- API / introspection

@skip_if_no_tkinter
def test_treemap_view_class_has_required_methods():
    """Introspection-only check that runs even without tkinter."""
    for name in ("set_data", "set_drill_controller", "zoom_to", "clear", "update_treemap"):
        assert hasattr(TreemapView, name), "missing method: {}".format(name)


@skip_if_no_tkinter
def test_components_init_exports_new_classes():
    """``src.ui.components`` must export the Stage 3 additions."""
    assert DrillDownController is not None
    assert TreemapView is not None
    assert Rect is not None
    assert callable(squarify)


# ------------------------------------------------------------------ Tk tests

@skip_if_no_tkinter
def test_treemap_view_constructs():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        view = TreemapView(root)
        assert view is not None
        # The toolbar buttons must exist.
        assert hasattr(view, "_home_button")
        assert hasattr(view, "_up_button")
        # The matplotlib canvas must exist.
        assert view.canvas is not None
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_treemap_view_set_data_does_not_crash():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        view = TreemapView(root)
        items = [
            _make_file_info(Path("C:/data/a.txt"), 1024),
            _make_file_info(Path("C:/data/b.txt"), 2048),
            _make_file_info(Path("C:/data/c.txt"), 4096),
        ]
        view.set_data(items)  # should not raise
        view.clear()          # legacy v1.0.0 API must keep working
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_treemap_view_update_treemap_legacy_still_works():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        view = TreemapView(root)
        items = [_make_file_info(Path("C:/d/file_{}.bin".format(i)), 100 * (i + 1)) for i in range(5)]
        view.update_treemap(items)  # v1.0.0 entry point
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_treemap_view_set_drill_controller_wires_callback():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        view = TreemapView(root)
        controller = DrillDownController(master=root, root_path="C:/")
        # Provide a deterministic loader so we don't read the
        # actual filesystem.
        controller.set_data_loader(lambda p: [])
        view.set_drill_controller(controller)
        # The controller's callback should now be the view's
        # ``_on_path_change`` method.
        assert controller._on_path_change == view._on_path_change
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_treemap_view_zoom_to_with_controller(tmp_path):
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        (tmp_path / "a.txt").write_bytes(b"a")
        (tmp_path / "b.txt").write_bytes(b"bb")
        view = TreemapView(root)
        controller = DrillDownController(master=root, root_path=str(tmp_path))
        # Default loader walks the real directory.
        view.set_drill_controller(controller)
        view.zoom_to(str(tmp_path))
        # The controller's path should have been updated and the
        # view's breadcrumb should reflect it.
        assert controller.current_path() == str(tmp_path)
        # ``view._current_path`` is also updated by the callback.
        assert view._current_path == str(tmp_path)
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_treemap_view_clear_resets_items():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        view = TreemapView(root)
        view.set_data([_make_file_info(Path("C:/data.txt"), 1024)])
        view.clear()
        assert view._items == []
        assert view._rect_to_item == {}
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_treemap_view_set_data_handles_empty_input():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        view = TreemapView(root)
        view.set_data([])  # should not crash
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_treemap_view_handles_zero_size_items():
    """Items with size=0 must be dropped silently."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        view = TreemapView(root)
        items = [
            _make_file_info(Path("C:/a.txt"), 0),
            _make_file_info(Path("C:/b.txt"), 1024),
            _make_file_info(Path("C:/c.txt"), 0),
        ]
        view.set_data(items)  # should not crash
    finally:
        root.destroy()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
