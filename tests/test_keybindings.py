"""
KeyBindings 单元测试 (v1.2.0 / Stage 4)
=======================================

测试目标：
    1. SHORTCUTS 列表含 5 个快捷键
    2. bind_all 注册正确数量
    3. 优雅 fallback：方法不存在时跳过该快捷键
    4. 绑定后 handler 触发对应方法
    5. window.bind() 抛异常时不中断其他快捷键

策略：使用 importlib 直接加载 keybindings.py，绕过 src.ui.__init__
（后者会触发 MainWindow 导入，而 MainWindow 依赖 customtkinter/tkinter）。
所有测试基于 MagicMock window，零 GUI 依赖。
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def kb():
    """加载 keybindings 模块（绕过 src.ui.__init__）"""
    spec = importlib.util.spec_from_file_location(
        "_keybindings_test",
        Path(__file__).parent.parent / "src" / "ui" / "keybindings.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_full_window():
    """
    构造一个拥有所有快捷键方法 + tabview 的 mock window。

    用 spec= 限制属性，避免 hasattr() 误判。
    """
    window = MagicMock(spec=[
        "_start_scan", "_clear_results", "_cancel_operation",
        "open_settings", "tabview", "bind",
    ])
    # tabview.get() 返回一个带 refresh 的对象
    tab = MagicMock(spec=["refresh"])
    window.tabview.get.return_value = tab
    return window


# ---------------------------------------------------------------------------
# Test: SHORTCUTS 映射
# ---------------------------------------------------------------------------
class TestShortcuts:
    def test_has_5_shortcuts(self, kb):
        assert len(kb.KeyBindings.SHORTCUTS) == 5

    def test_shortcut_keys_present(self, kb):
        keys = [s[0] for s in kb.KeyBindings.SHORTCUTS]
        assert "<Control-s>" in keys
        assert "<Control-r>" in keys
        assert "<Control-l>" in keys
        assert "<Control-comma>" in keys
        assert "<Escape>" in keys

    def test_shortcut_keys_unique(self, kb):
        keys = [s[0] for s in kb.KeyBindings.SHORTCUTS]
        assert len(set(keys)) == len(keys)

    def test_shortcut_tuple_shape(self, kb):
        """每条 SHORTCUTS 是 (event_seq, existence_attr, handler_id)"""
        for item in kb.KeyBindings.SHORTCUTS:
            assert isinstance(item, tuple)
            assert len(item) == 3
            event_seq, existence_attr, handler_id = item
            assert event_seq.startswith("<")
            assert isinstance(existence_attr, str)
            assert isinstance(handler_id, str)


# ---------------------------------------------------------------------------
# Test: bind_all 注册数量
# ---------------------------------------------------------------------------
class TestBindAll:
    def test_all_methods_present_registers_5(self, kb):
        window = _make_full_window()
        kb.KeyBindings.bind_all(window)
        assert window.bind.call_count == 5

    def test_no_methods_registers_0(self, kb):
        """window 只有 bind，没有任何快捷键方法 → 全部跳过，0 次 bind"""
        window = MagicMock(spec=["bind"])
        kb.KeyBindings.bind_all(window)
        assert window.bind.call_count == 0

    def test_partial_methods_registers_partial(self, kb):
        """window 只有 _start_scan → 只有 Ctrl+S 绑定"""
        window = MagicMock(spec=["_start_scan", "bind"])
        kb.KeyBindings.bind_all(window)
        assert window.bind.call_count == 1
        window.bind.assert_called_with("<Control-s>", window.bind.call_args[0][1])

    def test_bind_called_with_correct_keys(self, kb):
        window = _make_full_window()
        kb.KeyBindings.bind_all(window)
        bound_keys = {c.args[0] for c in window.bind.call_args_list}
        for key in ("<Control-s>", "<Control-r>", "<Control-l>",
                    "<Control-comma>", "<Escape>"):
            assert key in bound_keys

    def test_each_handler_is_callable(self, kb):
        window = _make_full_window()
        kb.KeyBindings.bind_all(window)
        for call in window.bind.call_args_list:
            handler = call.args[1]
            assert callable(handler), f"handler for {call.args[0]} not callable"


# ---------------------------------------------------------------------------
# Test: 触发后调用正确方法
# ---------------------------------------------------------------------------
class TestHandlerInvocation:
    def test_ctrl_s_triggers_start_scan(self, kb):
        window = _make_full_window()
        kb.KeyBindings.bind_all(window)
        handler = self._get_handler(window.bind.call_args_list, "<Control-s>")
        handler(MagicMock())
        window._start_scan.assert_called_once()

    def test_ctrl_r_triggers_tabview_refresh(self, kb):
        window = _make_full_window()
        kb.KeyBindings.bind_all(window)
        handler = self._get_handler(window.bind.call_args_list, "<Control-r>")
        handler(MagicMock())
        window.tabview.get.return_value.refresh.assert_called_once()

    def test_ctrl_l_triggers_clear(self, kb):
        window = _make_full_window()
        kb.KeyBindings.bind_all(window)
        handler = self._get_handler(window.bind.call_args_list, "<Control-l>")
        handler(MagicMock())
        window._clear_results.assert_called_once()

    def test_ctrl_comma_triggers_open_settings(self, kb):
        window = _make_full_window()
        kb.KeyBindings.bind_all(window)
        handler = self._get_handler(window.bind.call_args_list, "<Control-comma>")
        handler(MagicMock())
        window.open_settings.assert_called_once()

    def test_escape_triggers_cancel(self, kb):
        window = _make_full_window()
        kb.KeyBindings.bind_all(window)
        handler = self._get_handler(window.bind.call_args_list, "<Escape>")
        handler(MagicMock())
        window._cancel_operation.assert_called_once()

    @staticmethod
    def _get_handler(call_args_list, key):
        for c in call_args_list:
            if c.args[0] == key:
                return c.args[1]
        raise AssertionError(f"No handler bound for {key}")


# ---------------------------------------------------------------------------
# Test: fallback 行为
# ---------------------------------------------------------------------------
class TestFallback:
    def test_missing_open_settings_skips_ctrl_comma(self, kb):
        """没有 open_settings → 跳过 Ctrl+, ；其他快捷键照常绑定"""
        window = MagicMock(spec=[
            "_start_scan", "_clear_results", "_cancel_operation",
            "tabview", "bind",
        ])
        tab = MagicMock(spec=["refresh"])
        window.tabview.get.return_value = tab
        # 故意不设置 open_settings

        kb.KeyBindings.bind_all(window)
        bound_keys = {c.args[0] for c in window.bind.call_args_list}
        assert "<Control-comma>" not in bound_keys
        assert "<Control-s>" in bound_keys  # 其他仍然绑定
        assert window.bind.call_count == 4

    def test_missing_tabview_skips_ctrl_r(self, kb):
        """没有 tabview → 跳过 Ctrl+R"""
        window = MagicMock(spec=[
            "_start_scan", "_clear_results", "_cancel_operation",
            "open_settings", "bind",
        ])
        kb.KeyBindings.bind_all(window)
        bound_keys = {c.args[0] for c in window.bind.call_args_list}
        assert "<Control-r>" not in bound_keys
        assert "<Control-s>" in bound_keys
        assert window.bind.call_count == 4

    def test_missing_all_skips_all(self, kb):
        """window 只有 bind → 全部跳过"""
        window = MagicMock(spec=["bind"])
        kb.KeyBindings.bind_all(window)
        assert window.bind.call_count == 0

    def test_window_bind_raises_does_not_propagate(self, kb):
        """如果 window.bind 本身抛异常，不应中断其他快捷键注册"""
        window = _make_full_window()
        call_count = [0]
        original_bind = window.bind

        def flaky_bind(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("simulated bind failure")
            return original_bind(*args, **kwargs)

        window.bind = flaky_bind
        # Should not raise
        kb.KeyBindings.bind_all(window)
        # 至少有一些 binding 成功
        assert call_count[0] >= 1

    def test_ctrl_r_no_refresh_method_no_op(self, kb):
        """如果当前 tab 没有 .refresh()，handler 应安全 no-op"""
        window = MagicMock(spec=[
            "_start_scan", "_clear_results", "_cancel_operation",
            "open_settings", "tabview", "bind",
        ])
        # tabview.get() 返回无 refresh 方法的对象
        window.tabview.get.return_value = "some_string_no_refresh"

        kb.KeyBindings.bind_all(window)
        handler = TestHandlerInvocation._get_handler(
            window.bind.call_args_list, "<Control-r>"
        )
        # Should not raise
        handler(MagicMock())

    def test_ctrl_r_tabview_get_raises_no_op(self, kb):
        """如果 tabview.get() 抛异常，handler 应安全 no-op"""
        window = MagicMock(spec=[
            "_start_scan", "_clear_results", "_cancel_operation",
            "open_settings", "tabview", "bind",
        ])
        window.tabview.get.side_effect = RuntimeError("boom")

        kb.KeyBindings.bind_all(window)
        handler = TestHandlerInvocation._get_handler(
            window.bind.call_args_list, "<Control-r>"
        )
        # Should not raise
        handler(MagicMock())


# ---------------------------------------------------------------------------
# Test: 私有辅助方法
# ---------------------------------------------------------------------------
class TestHelpers:
    def test_make_handler_returns_callable(self, kb):
        window = MagicMock()
        window._start_scan = MagicMock()
        handler = kb.KeyBindings._make_handler(window, "_start_scan")
        assert callable(handler)
        handler(None)
        window._start_scan.assert_called_once()

    def test_make_handler_returns_none_for_unknown(self, kb):
        window = MagicMock()
        handler = kb.KeyBindings._make_handler(window, "unknown_handler_id")
        assert handler is None

    def test_safe_refresh_tab_with_refresh(self, kb):
        tab = MagicMock()
        tab.refresh = MagicMock()
        window = MagicMock()
        window.tabview.get.return_value = tab
        kb.KeyBindings._safe_refresh_tab(window)
        tab.refresh.assert_called_once()

    def test_safe_refresh_tab_without_refresh(self, kb):
        tab = "string_no_refresh"  # 无 refresh 方法
        window = MagicMock()
        window.tabview.get.return_value = tab
        # Should not raise
        kb.KeyBindings._safe_refresh_tab(window)

    def test_safe_refresh_tab_get_raises(self, kb):
        window = MagicMock()
        window.tabview.get.side_effect = RuntimeError("boom")
        # Should not raise
        kb.KeyBindings._safe_refresh_tab(window)
