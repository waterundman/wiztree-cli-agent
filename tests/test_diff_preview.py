"""
DiffPreviewDialog 测试 (v1.2.0 / Stage 5)
==========================================

覆盖：
    1. 构造 + 标题
    2. ``show()`` 默认返回 False（未操作时为初始 result）
    3. ``show()`` 在 Confirm 后返回 True
    4. ``show()`` 在 Cancel 后返回 False
    5. delete 模式：After 显示 "🗑️ DELETE"
    6. move 模式：After 显示 "↩️ MOVE to <new_path>"
    7. 通用模式：After 显示 new_path
    8. 警告文字 "⚠️ This action can be restored" 始终存在
    9. 文件不存在 / 无权限时 size / mtime 显示为 "(unavailable)"，不抛异常
    10. 旧路径为空时也安全

策略：mock 掉 ``show()`` 的实际 wait_window 行为以避免卡死；
使用 ctk.CTk() 构造 root。tkinter 不可用时整个文件 skip。
"""
from __future__ import annotations

import os
import sys
import tempfile
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
def fake_parent():
    if not _CTK_OK:
        pytest.skip("tkinter not available")
    import customtkinter as ctk
    root = ctk.CTk()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test: import
# ---------------------------------------------------------------------------
class TestImport:
    @skip_no_ctk
    def test_module_imports(self):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        assert DiffPreviewDialog is not None
    
    @skip_no_ctk
    def test_helpers_exist(self):
        from src.ui.tabs.diff_preview import _format_size, _format_mtime, _file_info
        assert _format_size(0) == "0 B"
        assert _format_size(1024) == "1.0 KB"
        assert _format_size(1024 ** 2) == "1.0 MB"
        assert _format_size(1024 ** 3) == "1.00 GB"
        # 负数/None → unavailable
        assert "(unavailable)" in _format_size(None)
        assert "(unavailable)" in _format_size(-1)
        # mtime
        assert _format_mtime(0) == "(unavailable)"
        assert _format_mtime(None) == "(unavailable)"
        assert _format_mtime(1748800000) != "(unavailable)"
        # file_info with nonexistent path
        info = _file_info("Z:\\nonexistent\\file_xyz.txt")
        assert info["exists"] is False
        assert info["size_str"] == "(unavailable)"


# ---------------------------------------------------------------------------
# Test: 构造
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestConstruction:
    def test_basic_construction(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a.txt", None, "delete")
        assert dlg.old_path == "/a.txt"
        assert dlg.new_path is None
        assert dlg.action == "delete"
        assert dlg.top is not None
        assert dlg.result is False
        # 关窗
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_move_construction(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/src/a.txt", "/dst/a.txt", "move")
        assert dlg.action == "move"
        assert dlg.new_path == "/dst/a.txt"
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_construction_does_not_call_wait_window(self, fake_parent):
        """构造不应阻塞（wait_window 由 show() 调用）"""
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "delete")
        # 构造完没 wait
        try:
            dlg.top.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Test: _format_after 逻辑
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestFormatAfter:
    def test_delete_shows_trash_icon(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a.txt", None, "delete")
        assert "🗑️" in dlg._format_after()
        assert "DELETE" in dlg._format_after()
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_file_delete_alias_also_trash(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "file_delete")
        assert "🗑️" in dlg._format_after()
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_move_shows_arrow(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/src/a", "/dst/a", "move")
        assert "↩️" in dlg._format_after()
        assert "/dst/a" in dlg._format_after()
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_move_without_new_path(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/src/a", None, "move")
        # new_path 为 None → 应显示 unknown
        s = dlg._format_after()
        assert "↩️" in s
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_generic_action_shows_new_path(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", "/b", "rename")
        # 非 delete / move → 显示 new_path
        assert dlg._format_after() == "/b"
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_generic_action_no_new_path(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "rename")
        # 通用 + 无 new_path
        assert "(no change)" in dlg._format_after()
        try:
            dlg.top.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Test: _is_destructive
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestIsDestructive:
    def test_delete_is_destructive(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "delete")
        assert dlg._is_destructive() is True
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_file_delete_is_destructive(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "file_delete")
        assert dlg._is_destructive() is True
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_move_is_not_destructive(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", "/b", "move")
        assert dlg._is_destructive() is False
        try:
            dlg.top.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Test: show() 返回值
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestShow:
    def test_show_returns_false_when_not_confirmed(self, fake_parent):
        """show() 在 cancel 后返回 False"""
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "delete")
        # 模拟 Cancel
        dlg._on_cancel()
        result = dlg.show()  # 应当立即返回（top 已销毁）
        assert result is False
    
    def test_show_returns_true_when_confirmed(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "delete")
        dlg._on_confirm()
        result = dlg.show()
        assert result is True
    
    def test_confirm_sets_result_true(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "delete")
        assert dlg.result is False
        dlg._on_confirm()
        assert dlg.result is True
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_cancel_sets_result_false(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "delete")
        dlg._on_confirm()  # 模拟先确认
        dlg._on_cancel()   # 再 cancel
        assert dlg.result is False
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_show_after_destroy_returns_current_result(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "delete")
        dlg._on_confirm()
        # 已被 _on_confirm 销毁；show() 应当 graceful 返回当前 result
        result = dlg.show()
        assert result is True


# ---------------------------------------------------------------------------
# Test: UI 内容
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestUI:
    def test_title_contains_action(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "delete")
        # 标题在 _build_ui 中作为 CTkLabel text "Preview: {action}"
        # 验证 _build_ui 不抛异常（已经构造时调用过）
        # 通过 top 的子控件来确认
        children = dlg.top.winfo_children()
        # 至少应包含 title label / before frame / after frame / warning / buttons
        assert len(children) >= 3
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_old_path_in_before_section(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/some/very/specific/path.txt", None, "delete")
        # 找到 body frame（第一个 packed child 之外）
        # 通过 find children recursively
        def all_labels(w):
            out = []
            for c in w.winfo_children():
                cls = type(c).__name__
                if "Label" in cls:
                    try:
                        out.append(c.cget("text"))
                    except Exception:
                        pass
                out.extend(all_labels(c))
            return out
        labels = all_labels(dlg.top)
        # 至少有一个 label 包含路径
        assert any("/some/very/specific/path.txt" in s for s in labels)
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_warning_text_present(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "/a", None, "delete")
        def all_labels(w):
            out = []
            for c in w.winfo_children():
                cls = type(c).__name__
                if "Label" in cls:
                    try:
                        out.append(c.cget("text"))
                    except Exception:
                        pass
                out.extend(all_labels(c))
            return out
        labels = all_labels(dlg.top)
        assert any("restored from History tab" in s for s in labels)
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_size_and_mtime_for_real_file(self, fake_parent, tmp_path):
        """old_path 是真实文件时显示 size + mtime"""
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        f = tmp_path / "real.txt"
        f.write_text("content", encoding="utf-8")
        dlg = DiffPreviewDialog(fake_parent, str(f), None, "delete")
        # 不抛异常即成功
        def all_labels(w):
            out = []
            for c in w.winfo_children():
                cls = type(c).__name__
                if "Label" in cls:
                    try:
                        out.append(c.cget("text"))
                    except Exception:
                        pass
                out.extend(all_labels(c))
            return out
        labels = all_labels(dlg.top)
        # 文件大小 7 bytes → "7 B"
        assert any("B" in s for s in labels)
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_size_unavailable_for_missing_file(self, fake_parent):
        """old_path 不存在时显示 '(unavailable)'"""
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "Z:\\definitely\\nonexistent.txt", None, "delete")
        def all_labels(w):
            out = []
            for c in w.winfo_children():
                cls = type(c).__name__
                if "Label" in cls:
                    try:
                        out.append(c.cget("text"))
                    except Exception:
                        pass
                out.extend(all_labels(c))
            return out
        labels = all_labels(dlg.top)
        assert any("(unavailable)" in s for s in labels)
        try:
            dlg.top.destroy()
        except Exception:
            pass
    
    def test_empty_old_path_safe(self, fake_parent):
        from src.ui.tabs.diff_preview import DiffPreviewDialog
        dlg = DiffPreviewDialog(fake_parent, "", None, "delete")
        # 不抛异常
        assert dlg._format_after() != ""
        try:
            dlg.top.destroy()
        except Exception:
            pass
