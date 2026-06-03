"""
ModernTheme 单元测试 (v1.2.0 / Stage 4)
========================================

测试目标：
    1. 6 主题注册（THEMES / THEME_ORDER 各 6 项 + 6-key 完整性）
    2. list_themes() 返回 6 个固定顺序的主题
    3. get_current() 返回持久化值 / 内建默认
    4. apply(name) 调用 ctk.set_default_color_theme + ConfigLoader.set
    5. apply(未知名) 抛 ValueError
    6. v1.1.0 实例 API 兼容（apply_theme / get_color / toggle_mode）
    7. ctk theme JSON 包含所有 widget 类 + 进度条颜色

策略：使用 importlib 直接加载 modern_theme.py，绕过 src.ui.__init__
（后者会触发 MainWindow 导入，而 MainWindow 依赖 customtkinter/tkinter）。
这样测试可以在无 GUI 环境的 CI 中运行。

注意：使用 patch.object(mt, "ctk", ...) 修补加载后模块的 ctk 属性，
而不是 ``src.ui.themes.modern_theme.ctk``（后者指向 sys.modules 中
可能未注册的原始模块引用）。
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Fixtures / helpers
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
def _reset_modern_theme_state(mt):
    """每个测试前后重置 ModernTheme._current 类状态"""
    mt.ModernTheme._current = None
    yield
    mt.ModernTheme._current = None


# ---------------------------------------------------------------------------
# Test: 6 主题注册
# ---------------------------------------------------------------------------
class TestThemeRegistration:
    def test_themes_dict_has_6_entries(self, mt):
        assert len(mt.THEMES) == 6

    def test_theme_order_has_6_entries(self, mt):
        assert len(mt.THEME_ORDER) == 6

    def test_theme_order_matches_spec(self, mt):
        expected = [
            "Steam Dark",
            "Catppuccin Mocha",
            "OLED Black",
            "GitHub Dark",
            "Nord",
            "Dracula",
        ]
        assert mt.THEME_ORDER == expected

    def test_themes_dict_keys_match_order(self, mt):
        for name in mt.THEME_ORDER:
            assert name in mt.THEMES, f"{name} missing from THEMES"

    def test_each_theme_has_6_required_keys(self, mt):
        for name, palette in mt.THEMES.items():
            missing = set(mt.REQUIRED_KEYS) - set(palette.keys())
            assert not missing, f"{name} missing keys: {missing}"

    def test_each_color_is_hex_string(self, mt):
        for name, palette in mt.THEMES.items():
            for key, val in palette.items():
                assert isinstance(val, str), f"{name}.{key} not str"
                assert val.startswith("#"), f"{name}.{key}={val} is not hex"
                assert len(val) == 7, f"{name}.{key}={val} length != 7"

    def test_no_duplicate_themes(self, mt):
        assert len(set(mt.THEME_ORDER)) == len(mt.THEME_ORDER)


# ---------------------------------------------------------------------------
# Test: 6 主题色板 spot check (每主题至少一个 key color 验证)
# ---------------------------------------------------------------------------
class TestThemeColorPalette:
    def test_steam_dark_palette(self, mt):
        p = mt.THEMES["Steam Dark"]
        assert p["fg_color"] == "#1e2837"
        assert p["button_color"] == "#2a475e"
        assert p["progressbar_color"] == "#66c0f4"

    def test_catppuccin_mocha_palette(self, mt):
        p = mt.THEMES["Catppuccin Mocha"]
        assert p["fg_color"] == "#1e1e2e"
        assert p["button_color"] == "#89b4fa"

    def test_oled_black_palette(self, mt):
        p = mt.THEMES["OLED Black"]
        assert p["fg_color"] == "#000000"
        assert p["text_color"] == "#e0e0e0"

    def test_github_dark_palette(self, mt):
        p = mt.THEMES["GitHub Dark"]
        assert p["fg_color"] == "#0d1117"
        assert p["button_color"] == "#21262d"
        assert p["progressbar_color"] == "#58a6ff"

    def test_nord_palette(self, mt):
        p = mt.THEMES["Nord"]
        assert p["fg_color"] == "#2e3440"
        assert p["text_color"] == "#eceff4"

    def test_dracula_palette(self, mt):
        p = mt.THEMES["Dracula"]
        assert p["fg_color"] == "#282a36"
        assert p["progressbar_color"] == "#bd93f9"


# ---------------------------------------------------------------------------
# Test: list_themes()
# ---------------------------------------------------------------------------
class TestListThemes:
    def test_returns_list(self, mt):
        result = mt.ModernTheme.list_themes()
        assert isinstance(result, list)

    def test_returns_6_themes(self, mt):
        assert len(mt.ModernTheme.list_themes()) == 6

    def test_returns_in_fixed_order(self, mt):
        expected = [
            "Steam Dark",
            "Catppuccin Mocha",
            "OLED Black",
            "GitHub Dark",
            "Nord",
            "Dracula",
        ]
        assert mt.ModernTheme.list_themes() == expected

    def test_list_themes_returns_new_list(self, mt):
        """返回的 list 不应是内部 THEME_ORDER 的引用（避免外部修改污染）"""
        result1 = mt.ModernTheme.list_themes()
        result1.append("Hacked")
        result2 = mt.ModernTheme.list_themes()
        assert "Hacked" not in result2


# ---------------------------------------------------------------------------
# Test: get_current()
# ---------------------------------------------------------------------------
class TestGetCurrent:
    def test_default_when_no_saved(self, mt):
        with patch("src.utils.config_loader.ConfigLoader.get_instance") as mock_get:
            mock_cfg = MagicMock()
            mock_cfg.get.return_value = None
            mock_get.return_value = mock_cfg
            assert mt.ModernTheme.get_current() == mt.DEFAULT_THEME

    def test_returns_saved_theme(self, mt):
        with patch("src.utils.config_loader.ConfigLoader.get_instance") as mock_get:
            mock_cfg = MagicMock()
            mock_cfg.get.return_value = "Nord"
            mock_get.return_value = mock_cfg
            assert mt.ModernTheme.get_current() == "Nord"

    def test_ignores_invalid_saved(self, mt):
        with patch("src.utils.config_loader.ConfigLoader.get_instance") as mock_get:
            mock_cfg = MagicMock()
            mock_cfg.get.return_value = "InvalidTheme"
            mock_get.return_value = mock_cfg
            # invalid saved value → fall back to default
            assert mt.ModernTheme.get_current() == mt.DEFAULT_THEME

    def test_returns_class_state_first(self, mt):
        mt.ModernTheme._current = "Dracula"
        with patch("src.utils.config_loader.ConfigLoader.get_instance") as mock_get:
            # 即使 ConfigLoader 返回不同值，class state 优先
            mock_cfg = MagicMock()
            mock_cfg.get.return_value = "Nord"
            mock_get.return_value = mock_cfg
            assert mt.ModernTheme.get_current() == "Dracula"

    def test_ignores_invalid_class_state(self, mt):
        mt.ModernTheme._current = "Garbage"
        with patch("src.utils.config_loader.ConfigLoader.get_instance") as mock_get:
            mock_cfg = MagicMock()
            mock_cfg.get.return_value = "Nord"
            mock_get.return_value = mock_cfg
            # class state 无效 → fall through 到 ConfigLoader
            assert mt.ModernTheme.get_current() == "Nord"

    def test_default_theme_is_github_dark(self, mt):
        assert mt.DEFAULT_THEME == "GitHub Dark"


# ---------------------------------------------------------------------------
# Test: apply()
# ---------------------------------------------------------------------------
class TestApply:
    def _apply_with_mocks(self, mt, theme_name, *, ctk_value=None,
                          theme_file="/tmp/fake.json", cfg_value=None):
        """
        在 mock 环境中执行 mt.ModernTheme.apply(theme_name)。

        - ctk_value:     替换模块 ctk 属性的值（默认 MagicMock）
        - theme_file:    _ensure_theme_file 返回的路径
        - cfg_value:     ConfigLoader.get_instance() 返回值
        """
        if ctk_value is None:
            ctk_value = MagicMock()
        with patch.object(mt, "ctk", ctk_value, create=True):
            with patch.object(mt, "_ensure_theme_file", return_value=theme_file):
                with patch(
                    "src.utils.config_loader.ConfigLoader.get_instance",
                    return_value=cfg_value,
                ):
                    mt.ModernTheme.apply(theme_name)
        return ctk_value

    def test_apply_sets_class_state(self, mt):
        self._apply_with_mocks(mt, "Nord")
        assert mt.ModernTheme._current == "Nord"

    def test_apply_calls_ctk_set_appearance(self, mt):
        mock_ctk = MagicMock()
        self._apply_with_mocks(mt, "Dracula", ctk_value=mock_ctk)
        mock_ctk.set_appearance_mode.assert_called_with("dark")

    def test_apply_calls_ctk_set_default_color_theme(self, mt):
        mock_ctk = MagicMock()
        self._apply_with_mocks(
            mt, "Catppuccin Mocha",
            ctk_value=mock_ctk, theme_file="/tmp/custom.json",
        )
        mock_ctk.set_default_color_theme.assert_called_with("/tmp/custom.json")

    def test_apply_persists_to_config(self, mt):
        mock_cfg = MagicMock()
        self._apply_with_mocks(mt, "Steam Dark", cfg_value=mock_cfg)
        mock_cfg.set.assert_called_with("ui.theme", "Steam Dark")

    def test_apply_unknown_raises_value_error(self, mt):
        with pytest.raises(ValueError) as excinfo:
            mt.ModernTheme.apply("InvalidTheme")
        assert "Unknown theme" in str(excinfo.value)
        assert "InvalidTheme" in str(excinfo.value)

    def test_apply_unknown_does_not_set_state(self, mt):
        with pytest.raises(ValueError):
            mt.ModernTheme.apply("NotATheme")
        assert mt.ModernTheme._current is None

    def test_apply_all_6_themes_succeed(self, mt):
        for name in mt.THEME_ORDER:
            self._apply_with_mocks(mt, name)
            assert mt.ModernTheme._current == name

    def test_apply_works_when_ctk_unavailable(self, mt):
        """customtkinter 不可用（ctk=None）时 apply() 仍然能持久化"""
        mock_cfg = MagicMock()
        # ctk_value=None 触发 ImportError 保护分支
        self._apply_with_mocks(mt, "OLED Black", ctk_value=None, cfg_value=mock_cfg)
        assert mt.ModernTheme._current == "OLED Black"
        mock_cfg.set.assert_called_with("ui.theme", "OLED Black")


# ---------------------------------------------------------------------------
# Test: 持久化 round-trip
# ---------------------------------------------------------------------------
class TestPersistence:
    def test_apply_then_get_current_round_trip(self, mt):
        for name in mt.ModernTheme.list_themes():
            with patch.object(mt, "ctk", MagicMock(), create=True):
                with patch.object(mt, "_ensure_theme_file", return_value="/tmp/x.json"):
                    with patch("src.utils.config_loader.ConfigLoader.get_instance"):
                        mt.ModernTheme.apply(name)
            assert mt.ModernTheme.get_current() == name


# ---------------------------------------------------------------------------
# Test: _build_ctk_theme_json
# ---------------------------------------------------------------------------
class TestBuildCtkThemeJson:
    def test_returns_dict(self, mt):
        data = mt._build_ctk_theme_json("Nord")
        assert isinstance(data, dict)

    def test_contains_core_widget_classes(self, mt):
        data = mt._build_ctk_theme_json("Nord")
        for cls in ("CTk", "CTkButton", "CTkLabel", "CTkFrame", "CTkProgressBar"):
            assert cls in data, f"Missing widget class {cls}"

    def test_progressbar_uses_theme_color(self, mt):
        data = mt._build_ctk_theme_json("Dracula")
        purple = mt.THEMES["Dracula"]["progressbar_color"]
        # 进度条颜色必须出现在 CTkProgressBar 的 progress_color 中
        assert purple in str(data["CTkProgressBar"])

    def test_unknown_theme_raises(self, mt):
        with pytest.raises(ValueError):
            mt._build_ctk_theme_json("InvalidTheme")

    def test_button_uses_button_color(self, mt):
        data = mt._build_ctk_theme_json("Catppuccin Mocha")
        blue = mt.THEMES["Catppuccin Mocha"]["button_color"]
        assert blue in str(data["CTkButton"])

    def test_fg_color_appears_in_frame(self, mt):
        data = mt._build_ctk_theme_json("GitHub Dark")
        fg = mt.THEMES["GitHub Dark"]["fg_color"]
        assert fg in str(data["CTkFrame"])


# ---------------------------------------------------------------------------
# Test: v1.1.0 兼容 API
# ---------------------------------------------------------------------------
class TestV110Compatibility:
    def test_constructor_default_mode(self, mt):
        m = mt.ModernTheme()
        assert m.mode == "dark"
        assert m.colors is mt.ModernTheme.DARK_COLORS

    def test_constructor_with_dark(self, mt):
        m = mt.ModernTheme(mode="dark")
        assert m.mode == "dark"

    def test_constructor_with_light(self, mt):
        m = mt.ModernTheme(mode="light")
        assert m.mode == "light"
        assert m.colors is mt.ModernTheme.LIGHT_COLORS

    def test_get_color_known(self, mt):
        m = mt.ModernTheme()
        assert m.get_color("bg") == "#1e1e2e"
        assert m.get_color("accent") == "#89b4fa"

    def test_get_color_default(self, mt):
        m = mt.ModernTheme()
        assert m.get_color("nonexistent") == "#000000"

    def test_toggle_mode_dark_to_light(self, mt):
        m = mt.ModernTheme()
        m.toggle_mode()
        assert m.mode == "light"
        assert m.colors is mt.ModernTheme.LIGHT_COLORS

    def test_toggle_mode_light_to_dark(self, mt):
        m = mt.ModernTheme(mode="light")
        m.toggle_mode()
        assert m.mode == "dark"
        assert m.colors is mt.ModernTheme.DARK_COLORS

    def test_dark_colors_has_8_keys(self, mt):
        assert len(mt.ModernTheme.DARK_COLORS) == 8

    def test_light_colors_has_8_keys(self, mt):
        assert len(mt.ModernTheme.LIGHT_COLORS) == 8
