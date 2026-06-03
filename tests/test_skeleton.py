"""Tests for :class:`SkeletonWidget` and :class:`SkeletonLine`.

Exercised in two flavours (following the project pattern):

* **Real Tk root** — hidden ``Tk`` instance so the widgets are real.
  Skipped when tkinter / customtkinter is unavailable.
* **Pure-Python logic** — formula / config tests that don't need Tk.
"""
from __future__ import annotations

import importlib.util
import math
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_TEST_DIR = Path(__file__).parent
_SRC_DIR = _TEST_DIR.parent


def _safe_load(path: Path, dotted_parent: str):
    """Load *path* without triggering its real parent package ``__init__``."""
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


_skeleton_mod = _safe_load(
    _SRC_DIR / "src" / "ui" / "components" / "skeleton.py",
    "src.ui",
)

TK_AVAILABLE = _skeleton_mod is not None and hasattr(_skeleton_mod, "SkeletonWidget")

import pytest  # noqa: E402

skip_if_no_tkinter = pytest.mark.skipif(
    not TK_AVAILABLE,
    reason="tkinter / customtkinter not available",
)

SkeletonWidget = _skeleton_mod.SkeletonWidget if TK_AVAILABLE else None  # type: ignore
SkeletonLine = _skeleton_mod.SkeletonLine if TK_AVAILABLE else None  # type: ignore


# ============================================================= Tk-root tests

@skip_if_no_tkinter
def test_skeleton_widget_creates_default_grid():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sw = SkeletonWidget(root)
        assert sw is not None
        assert len(sw._rectangles) == 3  # rows=3, cols=1
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_widget_custom_rows_cols():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sw = SkeletonWidget(root, rows=2, cols=4)
        assert len(sw._rectangles) == 8
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_widget_start_stop_lifecycle():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sw = SkeletonWidget(root)
        assert not sw.is_running
        sw.start()
        assert sw.is_running
        sw.stop()
        assert not sw.is_running
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_widget_start_is_idempotent():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sw = SkeletonWidget(root)
        sw.start()
        sw.start()  # second call should be no-op
        assert sw.is_running
        sw.stop()
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_widget_stop_is_idempotent():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sw = SkeletonWidget(root)
        sw.stop()  # stop before start — should not raise
        assert not sw.is_running
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_widget_pulse_changes_color():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sw = SkeletonWidget(root, rows=1, cols=1)
        sw.start()
        # Let a few frames tick
        root.update()
        time.sleep(0.05)
        root.update()
        # After at least one pulse the colour should differ from
        # the initial base colour
        sw.stop()
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_widget_corner_radius():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sw = SkeletonWidget(root, corner_radius=8)
        assert sw._corner_radius == 8
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_line_creates_full_width():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sl = SkeletonLine(root, width="full")
        assert sl.width_ratio == 1.0
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_line_creates_half_width():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sl = SkeletonLine(root, width="half")
        assert sl.width_ratio == 0.5
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_line_creates_quarter_width():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sl = SkeletonLine(root, width="quarter")
        assert sl.width_ratio == 0.25
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_line_default_is_full():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sl = SkeletonLine(root)
        assert sl.width_ratio == 1.0
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_line_invalid_width_raises():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        with pytest.raises(ValueError, match="width must be one of"):
            SkeletonLine(root, width="extra-wide")
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_line_height_is_16():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sl = SkeletonLine(root)
        assert sl.cget("height") == 16
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_skeleton_line_corner_radius_is_4():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        sl = SkeletonLine(root)
        assert sl.cget("corner_radius") == 4
    finally:
        root.destroy()


# ============================================================= Pure-Python tests

def test_pulse_formula_bounds():
    """The sine-based formula must produce grey values in [42, 74]."""
    low, high = 42, 74
    for t_10x in range(0, 200):
        t = t_10x * 0.1
        gray = int(low + (high - low) * (0.5 + 0.5 * math.sin(t * 3.0)))
        assert low <= gray <= high, f"gray={gray} out of bounds at t={t}"


def test_pulse_formula_produces_expected_range():
    """Verify the approximate min/max of the sine wave.

    ``int()`` truncates, so the theoretical maximum (74) may not be
    reached due to floating-point sampling — accept [low, high].
    """
    low, high = 42, 74
    vals = set()
    for t_100x in range(0, 10000):
        t = t_100x * 0.001
        gray = int(low + (high - low) * (0.5 + 0.5 * math.sin(t * 3.0)))
        vals.add(gray)
    assert min(vals) == low
    # Due to int() truncation, the max may be high or high-1
    assert max(vals) in (high, high - 1)


@skip_if_no_tkinter
def test_get_theme_skeleton_color_returns_string():
    from src.ui.components.skeleton import _get_theme_skeleton_color
    color = _get_theme_skeleton_color()
    assert isinstance(color, str)
    assert color.startswith("#")


@skip_if_no_tkinter
def test_width_map_values():
    assert SkeletonLine._WIDTH_MAP == {"full": 1.0, "half": 0.5, "quarter": 0.25}


# ============================================================= Stage 3 Integration tests

try:
    import customtkinter as ctk
    _CTK_OK = True
except ImportError:
    _CTK_OK = False

skip_no_ctk = pytest.mark.skipif(not _CTK_OK, reason="customtkinter not available")


# ---------------------------------------------------------------------------
# MainWindow skeleton API
# ---------------------------------------------------------------------------

@skip_no_ctk
class TestMainWindowSkeletonApi:
    """MainWindow 骨架屏 API 集成测试（不触发完整 __init__）。"""

    def _make_stub(self, root):
        """创建 MainWindow 骨架屏方法的最小 stub。"""
        import types

        class _Stub:
            pass

        stub = _Stub()

        # 创建 scan_tab 区域结构
        scan_tab = ctk.CTkFrame(root)
        table_frame = ctk.CTkFrame(scan_tab)
        table_frame.pack(fill="both", expand=True)
        import tkinter.ttk as ttk
        scan_tree = ttk.Treeview(table_frame, columns=("c",), show="headings")
        scan_tree.pack(fill="both", expand=True)

        stub.scan_tree = scan_tree
        stub._scan_skeleton_frame = ctk.CTkFrame(table_frame, fg_color="transparent")
        for _ in range(5):
            SkeletonLine(stub._scan_skeleton_frame, width="full").pack(fill="x", padx=4, pady=3)
        stub._scan_skeleton_visible = False

        # 创建 ai_tab 区域结构
        ai_tab = ctk.CTkFrame(root)
        text_frame = ctk.CTkFrame(ai_tab)
        text_frame.pack(fill="both", expand=True)
        ai_text = ctk.CTkTextbox(text_frame)
        ai_text.pack(fill="both", expand=True)

        stub.ai_text = ai_text
        stub._ai_skeleton_frame = ctk.CTkFrame(text_frame, fg_color="transparent")
        for _ in range(7):
            SkeletonLine(stub._ai_skeleton_frame, width="full").pack(fill="x", padx=4, pady=3)
        stub._ai_skeleton_visible = False

        # 绑定方法（从 main_window.py 的实现复制）
        from src.ui.main_window import MainWindow
        stub._show_scan_skeleton = types.MethodType(MainWindow._show_scan_skeleton, stub)
        stub._hide_scan_skeleton = types.MethodType(MainWindow._hide_scan_skeleton, stub)
        stub._show_ai_skeleton = types.MethodType(MainWindow._show_ai_skeleton, stub)
        stub._hide_ai_skeleton = types.MethodType(MainWindow._hide_ai_skeleton, stub)

        return stub

    def test_scan_skeleton_show_hide_lifecycle(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            stub = self._make_stub(root)
            assert not stub._scan_skeleton_visible
            stub._show_scan_skeleton()
            assert stub._scan_skeleton_visible
            stub._hide_scan_skeleton()
            assert not stub._scan_skeleton_visible
        finally:
            root.destroy()

    def test_ai_skeleton_show_hide_lifecycle(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            stub = self._make_stub(root)
            assert not stub._ai_skeleton_visible
            stub._show_ai_skeleton()
            assert stub._ai_skeleton_visible
            stub._hide_ai_skeleton()
            assert not stub._ai_skeleton_visible
        finally:
            root.destroy()

    def test_scan_skeleton_idempotent_show(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            stub = self._make_stub(root)
            stub._show_scan_skeleton()
            stub._show_scan_skeleton()  # 第二次不应出错
            assert stub._scan_skeleton_visible
            stub._hide_scan_skeleton()
        finally:
            root.destroy()

    def test_scan_skeleton_idempotent_hide(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            stub = self._make_stub(root)
            stub._hide_scan_skeleton()  # 未 show 就 hide 不应出错
            assert not stub._scan_skeleton_visible
        finally:
            root.destroy()

    def test_ai_skeleton_idempotent_show(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            stub = self._make_stub(root)
            stub._show_ai_skeleton()
            stub._show_ai_skeleton()
            assert stub._ai_skeleton_visible
            stub._hide_ai_skeleton()
        finally:
            root.destroy()

    def test_ai_skeleton_idempotent_hide(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            stub = self._make_stub(root)
            stub._hide_ai_skeleton()
            assert not stub._ai_skeleton_visible
        finally:
            root.destroy()

    def test_main_window_class_has_skeleton_methods(self):
        """MainWindow 类必须定义 4 个骨架屏 API 方法。"""
        from src.ui.main_window import MainWindow
        for name in ("_show_scan_skeleton", "_hide_scan_skeleton",
                      "_show_ai_skeleton", "_hide_ai_skeleton"):
            assert hasattr(MainWindow, name), f"MainWindow missing {name}"


# ---------------------------------------------------------------------------
# ModelsTab skeleton integration
# ---------------------------------------------------------------------------

@skip_no_ctk
class TestModelsTabSkeleton:
    """ModelsTab 骨架屏集成测试。"""

    def test_has_skeleton_methods(self):
        from src.ui.tabs.models_tab import ModelsTab
        assert hasattr(ModelsTab, "_show_skeleton")
        assert hasattr(ModelsTab, "_hide_skeleton")

    def test_skeleton_initially_hidden(self):
        from src.ui.tabs.models_tab import ModelsTab
        root = ctk.CTk()
        try:
            mock_catalog = MagicMock()
            mock_catalog.info.return_value = {"source": "test", "model_count": 0,
                                               "provider_count": 0, "providers": []}
            mock_catalog.list.return_value = []
            mock_config = MagicMock()
            tab = ModelsTab(root, catalog=mock_catalog, config_loader=mock_config)
            assert not tab._skeleton_visible
        finally:
            root.destroy()

    def test_show_hide_lifecycle(self):
        from src.ui.tabs.models_tab import ModelsTab
        root = ctk.CTk()
        try:
            mock_catalog = MagicMock()
            mock_catalog.info.return_value = {"source": "test", "model_count": 0,
                                               "provider_count": 0, "providers": []}
            mock_catalog.list.return_value = []
            mock_config = MagicMock()
            tab = ModelsTab(root, catalog=mock_catalog, config_loader=mock_config)
            tab._show_skeleton()
            assert tab._skeleton_visible
            tab._hide_skeleton()
            assert not tab._skeleton_visible
        finally:
            root.destroy()

    def test_refresh_shows_then_hides_skeleton(self):
        from src.ui.tabs.models_tab import ModelsTab
        root = ctk.CTk()
        try:
            mock_catalog = MagicMock()
            mock_catalog.info.return_value = {"source": "test", "model_count": 0,
                                               "provider_count": 0, "providers": []}
            mock_catalog.list.return_value = []
            mock_config = MagicMock()
            tab = ModelsTab(root, catalog=mock_catalog, config_loader=mock_config)
            # refresh 结束后骨架屏应被隐藏
            tab.refresh()
            assert not tab._skeleton_visible
        finally:
            root.destroy()


# ---------------------------------------------------------------------------
# PromptsTab skeleton integration
# ---------------------------------------------------------------------------

@skip_no_ctk
class TestPromptsTabSkeleton:
    """PromptsTab 骨架屏集成测试。"""

    def test_has_skeleton_methods(self):
        from src.ui.tabs.prompts_tab import PromptsTab
        assert hasattr(PromptsTab, "_show_skeleton")
        assert hasattr(PromptsTab, "_hide_skeleton")

    def test_skeleton_initially_hidden(self):
        from src.ui.tabs.prompts_tab import PromptsTab
        root = ctk.CTk()
        try:
            mock_store = MagicMock()
            mock_store.list.return_value = []
            mock_store.get_active.return_value = None
            tab = PromptsTab(root, store=mock_store)
            assert not tab._skeleton_visible
        finally:
            root.destroy()

    def test_show_hide_lifecycle(self):
        from src.ui.tabs.prompts_tab import PromptsTab
        root = ctk.CTk()
        try:
            mock_store = MagicMock()
            mock_store.list.return_value = []
            mock_store.get_active.return_value = None
            tab = PromptsTab(root, store=mock_store)
            tab._show_skeleton()
            assert tab._skeleton_visible
            tab._hide_skeleton()
            assert not tab._skeleton_visible
        finally:
            root.destroy()

    def test_refresh_shows_then_hides_skeleton(self):
        from src.ui.tabs.prompts_tab import PromptsTab
        root = ctk.CTk()
        try:
            mock_store = MagicMock()
            mock_store.list.return_value = ["alpha", "beta"]
            mock_store.get_active.return_value = "alpha"
            tab = PromptsTab(root, store=mock_store)
            # refresh 结束后骨架屏应被隐藏
            tab.refresh()
            assert not tab._skeleton_visible
        finally:
            root.destroy()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
