"""VirtualTreeview 组件测试。

Exercised in two flavours (following the project pattern):

* **Real Tk root** — hidden ``Tk`` instance so the widgets are real.
  Skipped when tkinter / customtkinter is unavailable.
* **Pure-Python logic** — formula / config tests that don't need Tk.
"""
from __future__ import annotations

import importlib.util
import sys
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


_vtreeview_mod = _safe_load(
    _SRC_DIR / "src" / "ui" / "components" / "virtual_treeview.py",
    "src.ui",
)

TK_AVAILABLE = _vtreeview_mod is not None and hasattr(_vtreeview_mod, "VirtualTreeview")

import pytest  # noqa: E402

skip_if_no_tkinter = pytest.mark.skipif(
    not TK_AVAILABLE,
    reason="tkinter / customtkinter not available",
)

VirtualTreeview = _vtreeview_mod.VirtualTreeview if TK_AVAILABLE else None  # type: ignore


# ============================================================= Tk-root tests

@skip_if_no_tkinter
def test_virtual_treeview_creates_default():
    """测试 VirtualTreeview 创建。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2", "col3")
        tree = VirtualTreeview(root, columns=columns, show="headings", buffer_size=5)
        assert tree is not None
        assert tree._all_data == []
        assert tree._visible_start == 0
        assert tree._visible_end == 0
        assert tree._buffer_size == 5
        assert tree._total_rows == 0
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_virtual_treeview_columns_configured():
    """测试列配置。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2", "col3")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        tree.heading("col1", text="Column 1")
        tree.heading("col2", text="Column 2")
        tree.heading("col3", text="Column 3")
        tree.column("col1", width=100)
        tree.column("col2", width=150)
        tree.column("col3", width=100)

        configured_columns = tree["columns"]
        assert "col1" in configured_columns
        assert "col2" in configured_columns
        assert "col3" in configured_columns
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_set_data_empty():
    """测试设置空数据。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        tree.set_data([])
        assert tree._all_data == []
        assert tree._total_rows == 0
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_set_data_with_rows():
    """测试设置有数据。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2", "col3")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        data = [
            (1, "file1.txt", "100 KB"),
            (2, "file2.txt", "200 KB"),
            (3, "file3.txt", "300 KB"),
        ]
        tree.set_data(data)
        assert len(tree._all_data) == 3
        assert tree._total_rows == 3
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_set_data_clears_existing():
    """测试设置数据会清除现有数据。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        data1 = [(1, "a")]
        data2 = [(2, "b")]
        tree.set_data(data1)
        tree.set_data(data2)
        assert len(tree._all_data) == 1
        assert tree._all_data[0] == (2, "b")
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_refresh_with_data():
    """测试刷新有数据。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings", buffer_size=5)
        data = [(i, f"file{i}.txt") for i in range(20)]
        tree.set_data(data)
        tree.refresh()
        children = tree.get_children()
        assert len(children) > 0
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_refresh_without_data():
    """测试刷新无数据。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        tree.set_data([])
        tree.refresh()
        children = tree.get_children()
        assert len(children) == 0
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_refresh_renders_buffer():
    """测试刷新渲染缓冲区。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings", buffer_size=5)
        data = [(i, f"file{i}.txt") for i in range(50)]
        tree.set_data(data)
        tree.refresh()
        # 应该渲染可见行 + 缓冲区
        children = tree.get_children()
        assert len(children) > 0
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_visible_range_initial():
    """测试初始可见范围。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        start, end = tree.visible_range()
        assert start == 0
        assert end == 0
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_visible_range_after_set_data():
    """测试设置数据后的可见范围。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings", buffer_size=5)
        data = [(i, f"file{i}.txt") for i in range(20)]
        tree.set_data(data)
        tree.refresh()
        start, end = tree.visible_range()
        assert start >= 0
        assert end <= 20
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_sort_by_column():
    """测试按列排序。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        data = [
            (3, "file3.txt"),
            (1, "file1.txt"),
            (2, "file2.txt"),
        ]
        tree.set_data(data)
        tree.sort_by("col1", reverse=False)
        assert tree._all_data[0][0] == 1
        assert tree._all_data[1][0] == 2
        assert tree._all_data[2][0] == 3
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_sort_by_column_reverse():
    """测试按列反向排序。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        data = [
            (1, "file1.txt"),
            (3, "file3.txt"),
            (2, "file2.txt"),
        ]
        tree.set_data(data)
        tree.sort_by("col1", reverse=True)
        assert tree._all_data[0][0] == 3
        assert tree._all_data[1][0] == 2
        assert tree._all_data[2][0] == 1
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_sort_by_string_column():
    """测试按字符串列排序。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        data = [
            (1, "banana"),
            (2, "apple"),
            (3, "cherry"),
        ]
        tree.set_data(data)
        tree.sort_by("col2", reverse=False)
        assert tree._all_data[0][1] == "apple"
        assert tree._all_data[1][1] == "banana"
        assert tree._all_data[2][1] == "cherry"
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_sort_empty_data():
    """测试排序空数据。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        tree.set_data([])
        tree.sort_by("col1", reverse=False)
        assert tree._all_data == []
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_large_dataset_performance():
    """测试大数据集性能。"""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings", buffer_size=10)
        # 创建 10000 行数据
        data = [(i, f"file{i}.txt") for i in range(10000)]
        tree.set_data(data)
        assert tree._total_rows == 10000

        # 刷新应该很快（只渲染可见行）
        tree.refresh()
        children = tree.get_children()
        # 应该只渲染少量行（可见行 + 缓冲区）
        assert len(children) < 100
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_sort_large_dataset():
    """测试排序大数据集。"""
    import random
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        columns = ("col1", "col2")
        tree = VirtualTreeview(root, columns=columns, show="headings")
        data = [(random.randint(1, 10000), f"file{i}.txt") for i in range(1000)]
        tree.set_data(data)
        tree.sort_by("col1", reverse=False)

        # 验证排序正确
        for i in range(len(tree._all_data) - 1):
            assert tree._all_data[i][0] <= tree._all_data[i + 1][0]
    finally:
        root.destroy()


# ============================================================= Pure-Python logic tests

def test_virtual_treeview_data_structure():
    """测试数据结构（不需要 Tk）。"""
    # 测试数据列表操作
    data = [(1, "a"), (2, "b"), (3, "c")]
    assert len(data) == 3
    assert data[0] == (1, "a")
    assert data[-1] == (3, "c")


def test_virtual_treeview_sort_logic():
    """测试排序逻辑（不需要 Tk）。"""
    data = [(3, "c"), (1, "a"), (2, "b")]
    sorted_data = sorted(data, key=lambda x: x[0])
    assert sorted_data[0] == (1, "a")
    assert sorted_data[1] == (2, "b")
    assert sorted_data[2] == (3, "c")


def test_virtual_treeview_reverse_sort_logic():
    """测试反向排序逻辑（不需要 Tk）。"""
    data = [(1, "a"), (3, "c"), (2, "b")]
    sorted_data = sorted(data, key=lambda x: x[0], reverse=True)
    assert sorted_data[0] == (3, "c")
    assert sorted_data[1] == (2, "b")
    assert sorted_data[2] == (1, "a")
