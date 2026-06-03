"""
主题切换回调测试 (v1.3.0 / Stage 3)
====================================

测试目标：
    1. 6 主题切换不抛异常
    2. 切换后 ttk 样式变化
    3. 快速切换不崩溃
    4. 回调注册和触发

策略：使用 importlib 直接加载 modern_theme.py，
通过 mock 替换 ctk / ConfigLoader / ttk.Style。
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mt():
    """加载 modern_theme 模块（绕过 src.ui.__init__）"""
    spec = importlib.util.spec_from_file_location(
        "_modern_theme_test",
        Path(__file__).parent.parent / "src" / "ui" / "themes" / "modern_theme.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _reset_state(mt):
    """每个测试前后重置 ModernTheme 类状态"""
    mt.ModernTheme._current = None
    mt.ModernTheme._on_change_callbacks = []
    yield
    mt.ModernTheme._current = None
    mt.ModernTheme._on_change_callbacks = []


def _apply_with_mocks(mt, theme_name):
    """在 mock 环境中 apply 主题"""
    mock_ctk = MagicMock()
    mock_cfg = MagicMock()
    with patch.object(mt, "ctk", mock_ctk, create=True):
        with patch.object(mt, "_ensure_theme_file", return_value="/tmp/fake.json"):
            with patch(
                "src.utils.config_loader.ConfigLoader.get_instance",
                return_value=mock_cfg,
            ):
                mt.ModernTheme.apply(theme_name)


# ---------------------------------------------------------------------------
# Test: 6 主题切换不抛异常
# ---------------------------------------------------------------------------
class TestAllThemesSwitch:
    def test_switch_to_all_6_themes(self, mt):
        """依次切换到 6 个主题，不应抛异常"""
        for name in mt.THEME_ORDER:
            _apply_with_mocks(mt, name)
            assert mt.ModernTheme._current == name

    def test_switch_to_all_6_themes_with_callback(self, mt):
        """带回调注册时，6 主题切换均不抛异常"""
        cb = MagicMock()
        mt.ModernTheme.on_theme_change(cb)
        for name in mt.THEME_ORDER:
            _apply_with_mocks(mt, name)
        assert cb.call_count == 6


# ---------------------------------------------------------------------------
# Test: 切换后 ttk 样式变化
# ---------------------------------------------------------------------------
class TestTtkStyleUpdate:
    def test_apply_ttk_style_sets_treeview_colors(self, mt):
        """apply_ttk_style 应配置 Treeview 背景/前景色"""
        mock_style = MagicMock()
        _apply_with_mocks(mt, "Nord")
        mt.ModernTheme.apply_ttk_style(mock_style)

        # 验证 style.configure 被调用，且包含 Nord 的 fg_color
        treeview_calls = [
            c for c in mock_style.configure.call_args_list
            if c[0][0] == "Treeview"
        ]
        assert len(treeview_calls) >= 1
        bg = treeview_calls[0][1].get("background") or treeview_calls[0][0][1] if len(treeview_calls[0][0]) > 1 else None
        # Nord fg_color
        nord_fg = mt.THEMES["Nord"]["fg_color"]
        # 从 call 对象中提取 background 参数
        actual_bg = treeview_calls[0][1]["background"]
        assert actual_bg == nord_fg

    def test_ttk_style_changes_between_themes(self, mt):
        """不同主题切换后 ttk 样式颜色应不同"""
        mock_style = MagicMock()

        _apply_with_mocks(mt, "OLED Black")
        mt.ModernTheme.apply_ttk_style(mock_style)
        calls_oled = [
            c for c in mock_style.configure.call_args_list
            if c[0][0] == "Treeview"
        ]
        bg_oled = calls_oled[0][1]["background"]

        mock_style.reset_mock()

        _apply_with_mocks(mt, "Dracula")
        mt.ModernTheme.apply_ttk_style(mock_style)
        calls_dracula = [
            c for c in mock_style.configure.call_args_list
            if c[0][0] == "Treeview"
        ]
        bg_dracula = calls_dracula[0][1]["background"]

        # OLED Black (#000000) vs Dracula (#282a36)
        assert bg_oled != bg_dracula

    def test_apply_ttk_style_uses_clam_theme(self, mt):
        """apply_ttk_style 应切换到 clam 主题（ttk Treeview 兼容）"""
        mock_style = MagicMock()
        _apply_with_mocks(mt, "Steam Dark")
        mt.ModernTheme.apply_ttk_style(mock_style)
        mock_style.theme_use.assert_called_with("clam")


# ---------------------------------------------------------------------------
# Test: 快速切换不崩溃
# ---------------------------------------------------------------------------
class TestRapidSwitching:
    def test_rapid_switch_30_cycles(self, mt):
        """快速循环切换 30 次不抛异常"""
        cb = MagicMock()
        mt.ModernTheme.on_theme_change(cb)
        themes = mt.THEME_ORDER
        for i in range(30):
            name = themes[i % len(themes)]
            _apply_with_mocks(mt, name)
        assert cb.call_count == 30
        assert mt.ModernTheme._current == themes[(30 - 1) % len(themes)]

    def test_rapid_switch_with_ttk_style(self, mt):
        """快速切换并更新 ttk 样式不崩溃"""
        mock_style = MagicMock()
        cb = MagicMock()
        mt.ModernTheme.on_theme_change(cb)

        for i in range(20):
            name = mt.THEME_ORDER[i % len(mt.THEME_ORDER)]
            _apply_with_mocks(mt, name)
            mt.ModernTheme.apply_ttk_style(mock_style)

        assert cb.call_count == 20


# ---------------------------------------------------------------------------
# Test: 回调注册和触发
# ---------------------------------------------------------------------------
class TestCallbackRegistration:
    def test_on_theme_change_registers_callback(self, mt):
        """on_theme_change 应注册回调"""
        cb = MagicMock()
        mt.ModernTheme.on_theme_change(cb)
        assert cb in mt.ModernTheme._on_change_callbacks

    def test_callback_receives_theme_name(self, mt):
        """回调应接收主题名作为参数"""
        cb = MagicMock()
        mt.ModernTheme.on_theme_change(cb)
        _apply_with_mocks(mt, "Nord")
        cb.assert_called_once_with("Nord")

    def test_multiple_callbacks_all_triggered(self, mt):
        """多个回调在主题切换时均应被触发"""
        cb1 = MagicMock()
        cb2 = MagicMock()
        mt.ModernTheme.on_theme_change(cb1)
        mt.ModernTheme.on_theme_change(cb2)
        _apply_with_mocks(mt, "Dracula")
        cb1.assert_called_once_with("Dracula")
        cb2.assert_called_once_with("Dracula")

    def test_callback_exception_does_not_block_others(self, mt):
        """单个回调抛异常不应阻止其他回调执行"""
        def bad_cb(name):
            raise RuntimeError("boom")

        good_cb = MagicMock()
        mt.ModernTheme.on_theme_change(bad_cb)
        mt.ModernTheme.on_theme_change(good_cb)
        # 不应抛异常
        _apply_with_mocks(mt, "Steam Dark")
        good_cb.assert_called_once_with("Steam Dark")

    def test_no_callbacks_registered_still_works(self, mt):
        """无回调注册时 apply 不应失败"""
        _apply_with_mocks(mt, "Catppuccin Mocha")
        assert mt.ModernTheme._current == "Catppuccin Mocha"

    def test_callback_triggered_after_state_update(self, mt):
        """回调触发时 _current 应已更新"""
        captured = []
        def capture(name):
            captured.append(mt.ModernTheme._current)

        mt.ModernTheme.on_theme_change(capture)
        _apply_with_mocks(mt, "OLED Black")
        assert captured == ["OLED Black"]
