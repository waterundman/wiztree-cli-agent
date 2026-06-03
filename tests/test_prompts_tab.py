"""
PromptsTab 测试 (v1.2.0 / Stage 2)

策略：mock PromptStore + 不真正渲染 CTk 文本框（构造完后只验证 API 行为）。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import tkinter
    import customtkinter
    _CTK_OK = True
except ImportError:
    _CTK_OK = False

skip_no_ctk = pytest.mark.skipif(not _CTK_OK, reason="tkinter / customtkinter not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_master():
    if not _CTK_OK:
        pytest.skip("tkinter not available")
    import customtkinter as ctk
    root = ctk.CTk()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def mock_store():
    s = MagicMock()
    s.list.return_value = ["alpha", "beta"]
    s.get.side_effect = lambda n: {"alpha": "AA", "beta": "BB"}.get(n)
    return s


# ---------------------------------------------------------------------------
# Test: import
# ---------------------------------------------------------------------------
class TestImport:
    @skip_no_ctk
    def test_module_imports(self):
        from src.ui.tabs.prompts_tab import PromptsTab
        assert PromptsTab is not None


# ---------------------------------------------------------------------------
# Test: 构造 + 行为
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestPromptsTab:
    def test_constructs(self, fake_master, mock_store):
        from src.ui.tabs.prompts_tab import PromptsTab
        tab = PromptsTab(fake_master, store=mock_store)
        assert tab.frame is not None
        assert tab._store is mock_store

    def test_refresh_calls_store_list(self, fake_master, mock_store):
        from src.ui.tabs.prompts_tab import PromptsTab
        tab = PromptsTab(fake_master, store=mock_store)
        mock_store.list.reset_mock()
        tab.refresh()
        mock_store.list.assert_called()

    def test_active_set_calls_set_active(self, fake_master, mock_store):
        from src.ui.tabs.prompts_tab import PromptsTab
        mock_store.get_active.return_value = "alpha"
        tab = PromptsTab(fake_master, store=mock_store)
        # 触发 active 切换
        tab._on_active_select("alpha")
        mock_store.set_active.assert_called_with("alpha")

    def test_active_clear_calls_set_active_none(self, fake_master, mock_store):
        from src.ui.tabs.prompts_tab import PromptsTab
        tab = PromptsTab(fake_master, store=mock_store)
        tab._on_active_select("— select or create —")
        mock_store.set_active.assert_called_with(None)

    def test_save_calls_store_set(self, fake_master, mock_store):
        from src.ui.tabs.prompts_tab import PromptsTab
        tab = PromptsTab(fake_master, store=mock_store)
        tab._current_name = "alpha"
        # 模拟编辑器有内容
        tab._editor.get = MagicMock(return_value="new content")
        tab._on_save_click()
        mock_store.set.assert_called_with("alpha", "new content")

    def test_delete_calls_store_delete(self, fake_master, mock_store):
        from src.ui.tabs.prompts_tab import PromptsTab
        # 屏蔽 messagebox 二次确认
        import src.ui.tabs.prompts_tab as mod
        mod.messagebox.askyesno = lambda *a, **kw: True
        tab = PromptsTab(fake_master, store=mock_store)
        tab._current_name = "alpha"
        tab._on_delete_click()
        mock_store.delete.assert_called_with("alpha")

    def test_delete_missing_does_not_call(self, fake_master, mock_store):
        from src.ui.tabs.prompts_tab import PromptsTab
        import src.ui.tabs.prompts_tab as mod
        mod.messagebox.askyesno = lambda *a, **kw: True
        tab = PromptsTab(fake_master, store=mock_store)
        tab._current_name = None
        tab._on_delete_click()
        mock_store.delete.assert_not_called()

    def test_active_change_callback(self, fake_master, mock_store):
        from src.ui.tabs.prompts_tab import PromptsTab
        cb = MagicMock()
        tab = PromptsTab(fake_master, store=mock_store, on_active_change=cb)
        tab._on_active_select("alpha")
        cb.assert_called_once_with("alpha")

    def test_pick_loads_content(self, fake_master, mock_store):
        from src.ui.tabs.prompts_tab import PromptsTab
        import src.ui.tabs.prompts_tab as mod
        mod.messagebox.askyesno = lambda *a, **kw: True
        tab = PromptsTab(fake_master, store=mock_store)
        # 模拟编辑器接口
        captured = {}
        tab._editor.delete = lambda *a, **kw: None
        tab._editor.insert = lambda *a, **kw: captured.setdefault("insert", a)
        tab._name_label.configure = lambda **kw: captured.setdefault("name", kw)
        tab._on_pick("beta")
        mock_store.get.assert_called_with("beta")
        # 验证 set 了 current_name
        assert tab._current_name == "beta"
        assert captured.get("name", {}).get("text") == "beta"
