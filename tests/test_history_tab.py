"""
HistoryTab 测试 (v1.2.0 / Stage 5)
==================================

覆盖：
    1. 构造 + UI 引用存在（search_entry / type_filter / refresh_btn / stats_btn / tree / restore_btn）
    2. ``refresh()`` 调用 ``AuditLogger.list_recent`` 并渲染到 tree
    3. type 过滤（All / file_delete / file_move 等）→ 传给 list_recent
    4. search 过滤（按 target_path 子串）
    5. 选中行 → 详情面板更新
    6. restore 按钮：仅在 file_delete / file_move 时可用
    7. restore 按钮触发 ``AuditLogger.restore`` 调用
    8. stats 按钮调用 ``AuditLogger.get_stats``

策略：mock 掉 ``AuditLogger``（不依赖真实 DB），用 ``ctk.CTk()`` 作为 root。
若 ctk/tkinter 不可用 → 全部 skip。
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import tkinter
    import customtkinter
    _CTK_OK = True
except ImportError:
    _CTK_OK = False

skip_no_ctk = pytest.mark.skipif(
    not _CTK_OK, reason="tkinter / customtkinter not available"
)


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
def mock_logger():
    """返回预设的 3 条样本数据，方法都是 MagicMock。"""
    al = MagicMock()
    al.list_recent.return_value = [
        {
            "id": 3, "timestamp": "2026-06-01T18:00:03",
            "action_type": "file_move", "target_path": "/dst/c.txt",
            "status": "success", "metadata": {"original_path": "/src/c.txt"},
            "user": "wxy",
        },
        {
            "id": 2, "timestamp": "2026-06-01T18:00:02",
            "action_type": "file_delete", "target_path": "/tmp/b.txt",
            "status": "success", "metadata": {"reason": "user"},
            "user": "wxy",
        },
        {
            "id": 1, "timestamp": "2026-06-01T18:00:01",
            "action_type": "scan", "target_path": "C:\\",
            "status": "success", "metadata": None, "user": "wxy",
        },
    ]
    al.get_stats.return_value = {
        "total_actions": 3, "by_type": {"file_move": 1, "file_delete": 1, "scan": 1},
        "by_status": {"success": 3}, "recent_24h": 3,
    }
    al.restore.return_value = True
    return al


# ---------------------------------------------------------------------------
# Test: import
# ---------------------------------------------------------------------------
class TestImport:
    @skip_no_ctk
    def test_module_imports(self):
        from src.ui.tabs.history_tab import HistoryTab, TYPE_FILTERS
        assert HistoryTab is not None
        assert "All" in TYPE_FILTERS
        assert "file_delete" in TYPE_FILTERS
        assert "file_move" in TYPE_FILTERS


# ---------------------------------------------------------------------------
# Test: 构造 + UI
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestConstruction:
    def test_constructs_with_mock_logger(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        assert tab.frame is not None
        assert tab._audit_logger is mock_logger
    
    def test_creates_required_widgets(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        # toolbar
        assert tab.search_entry is not None
        assert tab.type_filter is not None
        assert tab.refresh_btn is not None
        assert tab.stats_btn is not None
        # tree
        assert tab.tree is not None
        # bottom
        assert tab.restore_btn is not None
    
    def test_default_type_filter_is_all(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        assert tab._type_filter == "All"
    
    def test_construct_uses_audit_db_path(self, fake_master, tmp_path):
        from src.ui.tabs.history_tab import HistoryTab
        db = str(tmp_path / "audit.db")
        with patch("src.ui.tabs.history_tab.AuditLogger") as MockAL:
            MockAL.return_value = MagicMock(list_recent=MagicMock(return_value=[]))
            tab = HistoryTab(fake_master, audit_db_path=db)
            MockAL.assert_called_once_with(db)
            tab.refresh()


# ---------------------------------------------------------------------------
# Test: refresh + tree 渲染
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestRefresh:
    def test_refresh_calls_list_recent(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        mock_logger.list_recent.reset_mock()
        tab.refresh()
        mock_logger.list_recent.assert_called()
    
    def test_refresh_inserts_rows(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        rows = tab.tree.get_children()
        assert len(rows) == 3  # 3 mock records
    
    def test_refresh_default_limit_is_50(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        call_kwargs = mock_logger.list_recent.call_args.kwargs
        assert call_kwargs.get("limit") == 50
    
    def test_refresh_default_action_type_is_none(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        call_kwargs = mock_logger.list_recent.call_args.kwargs
        # action_type=None means "all"
        assert call_kwargs.get("action_type") is None
    
    def test_refresh_clears_old_rows(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()  # 3 rows
        # Now make list_recent return empty
        mock_logger.list_recent.return_value = []
        tab.refresh()
        assert tab.tree.get_children() == []
    
    def test_refresh_type_filter_passes_action_type(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        # 模拟选 file_delete
        tab._on_type_change("file_delete")
        mock_logger.list_recent.reset_mock()
        tab.refresh()
        kwargs = mock_logger.list_recent.call_args.kwargs
        assert kwargs.get("action_type") == "file_delete"
        # 还原
        tab._on_type_change("All")
    
    def test_refresh_uses_sort_desc(self, fake_master, mock_logger):
        """list_recent 自身负责 DESC 排序，UI 端只调用它"""
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        # The mock returns 3 rows pre-sorted (3, 2, 1)
        tab.refresh()
        ids = [tab.tree.item(c)["values"][0] for c in tab.tree.get_children()]
        assert ids == [3, 2, 1]
    
    def test_refresh_handles_exception(self, fake_master, mock_logger):
        """list_recent 抛异常时不应崩"""
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        mock_logger.list_recent.side_effect = RuntimeError("boom")
        # should not raise
        tab.refresh()
        assert tab.tree.get_children() == []  # empty after error


# ---------------------------------------------------------------------------
# Test: search 过滤
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestSearch:
    def test_search_filters_by_target_path(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()  # 3 rows visible
        # 模拟输入 "b.txt"
        tab._search_var.set("b.txt")
        tab._on_search_change()
        rows = tab.tree.get_children()
        assert len(rows) == 1
        # row 应该是 file_delete /tmp/b.txt
        vals = tab.tree.item(rows[0])["values"]
        assert vals[2] == "file_delete"
        assert "b.txt" in vals[3]
    
    def test_search_case_insensitive(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        tab._search_var.set("C:\\")
        tab._on_search_change()
        rows = tab.tree.get_children()
        # mock 数据中只有 scan row 的 path 是 "C:\\"
        assert len(rows) == 1
    
    def test_search_empty_shows_all(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        tab._search_var.set("xyz_no_match")
        tab._on_search_change()
        assert len(tab.tree.get_children()) == 0
        # 再清空
        tab._search_var.set("")
        tab._on_search_change()
        assert len(tab.tree.get_children()) == 3
    
    def test_search_no_match_returns_empty(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        tab._search_var.set("does_not_exist")
        tab._on_search_change()
        assert tab.tree.get_children() == []


# ---------------------------------------------------------------------------
# Test: 行选中 + 详情面板
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestSelection:
    def test_select_updates_detail(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        # 选中第一行
        first = tab.tree.get_children()[0]
        tab.tree.selection_set(first)
        tab._on_tree_select()
        # 详情框应含 id=3
        text = tab._detail_box.get("1.0", "end-1c")
        assert "id=3" in text
    
    def test_select_file_delete_enables_restore(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        # 找 file_delete 行（id=2）
        for row in tab.tree.get_children():
            vals = tab.tree.item(row)["values"]
            if vals[2] == "file_delete":
                tab.tree.selection_set(row)
                tab._on_tree_select()
                assert str(tab.restore_btn.cget("state")) == "normal"
                return
        pytest.fail("file_delete row not found")
    
    def test_select_file_move_enables_restore(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        for row in tab.tree.get_children():
            vals = tab.tree.item(row)["values"]
            if vals[2] == "file_move":
                tab.tree.selection_set(row)
                tab._on_tree_select()
                assert str(tab.restore_btn.cget("state")) == "normal"
                return
        pytest.fail("file_move row not found")
    
    def test_select_scan_disables_restore(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        for row in tab.tree.get_children():
            vals = tab.tree.item(row)["values"]
            if vals[2] == "scan":
                tab.tree.selection_set(row)
                tab._on_tree_select()
                assert str(tab.restore_btn.cget("state")) == "disabled"
                return
        pytest.fail("scan row not found")
    
    def test_select_none_disables_restore(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        # 直接调 _on_tree_select 不带选中
        tab.tree.selection_remove(*tab.tree.selection())
        tab._on_tree_select()
        assert str(tab.restore_btn.cget("state")) == "disabled"
    
    def test_select_shows_metadata(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        for row in tab.tree.get_children():
            vals = tab.tree.item(row)["values"]
            if vals[2] == "file_move":
                tab.tree.selection_set(row)
                tab._on_tree_select()
                text = tab._detail_box.get("1.0", "end-1c")
                assert "original_path" in text
                return
        pytest.fail("file_move row not found")


# ---------------------------------------------------------------------------
# Test: 还原按钮
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestRestore:
    def test_restore_calls_logger(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        # 选中 file_delete 行
        for row in tab.tree.get_children():
            if tab.tree.item(row)["values"][2] == "file_delete":
                tab.tree.selection_set(row)
                tab._on_tree_select()
                mock_logger.restore.reset_mock()
                tab._on_restore_click()
                mock_logger.restore.assert_called_once_with(2)  # id=2
                return
        pytest.fail("file_delete row not found")
    
    def test_restore_without_selection_no_op(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        mock_logger.restore.reset_mock()
        tab._on_restore_click()
        mock_logger.restore.assert_not_called()
    
    def test_restore_failure_shows_error_toast(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        mock_logger.restore.return_value = False
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        for row in tab.tree.get_children():
            if tab.tree.item(row)["values"][2] == "file_delete":
                tab.tree.selection_set(row)
                tab._on_tree_select()
                tab._on_restore_click()
                # toast 应有内容（"✗ Could not restore"）
                assert "Could not restore" in tab._toast.cget("text")
                return
        pytest.fail("file_delete row not found")
    
    def test_restore_exception_caught(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        mock_logger.restore.side_effect = RuntimeError("boom")
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        for row in tab.tree.get_children():
            if tab.tree.item(row)["values"][2] == "file_delete":
                tab.tree.selection_set(row)
                tab._on_tree_select()
                # should not raise
                tab._on_restore_click()
                assert "Restore failed" in tab._toast.cget("text")
                return
        pytest.fail("file_delete row not found")
    
    def test_restore_triggers_refresh(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab.refresh()
        for row in tab.tree.get_children():
            if tab.tree.item(row)["values"][2] == "file_delete":
                tab.tree.selection_set(row)
                tab._on_tree_select()
                mock_logger.list_recent.reset_mock()
                tab._on_restore_click()
                # refresh 后会再调 list_recent
                mock_logger.list_recent.assert_called()
                return
        pytest.fail("file_delete row not found")


# ---------------------------------------------------------------------------
# Test: stats 按钮
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestStats:
    def test_stats_button_calls_get_stats(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        mock_logger.get_stats.reset_mock()
        tab._show_stats()
        mock_logger.get_stats.assert_called_once()
    
    def test_stats_button_handles_exception(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        mock_logger.get_stats.side_effect = RuntimeError("boom")
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        # messagebox 屏蔽
        import src.ui.tabs.history_tab as mod
        mod.messagebox = MagicMock()
        mod.messagebox.showerror = MagicMock()
        tab._show_stats()
        mod.messagebox.showerror.assert_called()
    
    def test_stats_window_replaced_on_repeated_click(self, fake_master, mock_logger):
        from src.ui.tabs.history_tab import HistoryTab
        tab = HistoryTab(fake_master, audit_logger=mock_logger)
        tab._show_stats()
        first_win = tab._stats_window
        assert first_win is not None
        # 再点一次 — 旧 window 销毁
        tab._show_stats()
        assert tab._stats_window is not first_win
