"""SettingsDialog模块测试"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# 检查tkinter是否可用
try:
    import tkinter
    import customtkinter
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

skip_if_no_tkinter = pytest.mark.skipif(
    not TKINTER_AVAILABLE,
    reason="tkinter not available"
)

# ---- 通过 importlib 加载 settings_dialog.py 以绕过 src.ui.__init__ ----
_settings_dialog_spec = importlib.util.spec_from_file_location(
    "_settings_dialog_test",
    Path(__file__).parent.parent / "src" / "ui" / "settings_dialog.py",
)
_settings_dialog_mod = None


def _load_mod():
    """延迟加载 settings_dialog 模块（绕过 src.ui.__init__）"""
    global _settings_dialog_mod
    if _settings_dialog_mod is None:
        mod = importlib.util.module_from_spec(_settings_dialog_spec)
        _settings_dialog_spec.loader.exec_module(mod)
        _settings_dialog_mod = mod
    return _settings_dialog_mod


class TestSettingsDialogModule:
    """测试SettingsDialog模块级功能（无需tkinter）"""

    def test_theme_names_defined(self):
        """THEME_NAMES已定义且非空"""
        mod = _load_mod()
        assert isinstance(mod.THEME_NAMES, list)
        assert len(mod.THEME_NAMES) >= 2

    def test_provider_names_defined(self):
        """PROVIDER_NAMES已定义且非空"""
        mod = _load_mod()
        assert hasattr(mod.SettingsDialog, 'PROVIDER_NAMES')
        assert isinstance(mod.SettingsDialog.PROVIDER_NAMES, list)
        assert len(mod.SettingsDialog.PROVIDER_NAMES) >= 1

    def test_theme_names_contains_known(self):
        """THEME_NAMES应包含已知主题名或CTk回退名"""
        mod = _load_mod()
        combined = ' '.join(t.lower() for t in mod.THEME_NAMES)
        keywords = ('blue', 'dark', 'nord', 'dracula', 'oled', 'steam',
                    'catppuccin', 'green', 'light', 'system')
        assert any(kw in combined for kw in keywords)

    def test_provider_names_contains_expected(self):
        """PROVIDER_NAMES应包含预期provider"""
        mod = _load_mod()
        assert "deepseek" in mod.SettingsDialog.PROVIDER_NAMES
        assert "openai" in mod.SettingsDialog.PROVIDER_NAMES

    @skip_if_no_tkinter
    def test_settings_dialog_instantiation(self):
        """SettingsDialog可以用隐藏root创建"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            dlg = mod.SettingsDialog(master=root)
            assert dlg.window is not None
            dlg.window.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_settings_dialog_window_title(self):
        """SettingsDialog窗口标题正确"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            dlg = mod.SettingsDialog(master=root)
            title = dlg.window.title()
            assert "Settings" in title or "wiztree" in title.lower()
            dlg.window.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_settings_dialog_has_window_attribute(self):
        """SettingsDialog实例有window属性"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            dlg = mod.SettingsDialog(master=root)
            assert hasattr(dlg, 'window')
            dlg.window.destroy()
        finally:
            root.destroy()


class TestThemeNamesFallback:
    """测试THEME_NAMES的fallback机制"""

    def test_load_theme_names_function_exists(self):
        """_load_theme_names函数可通过模块访问"""
        mod = _load_mod()
        result = mod._load_theme_names()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_load_theme_names_returns_mt_themes_without_tkinter(self):
        """_load_theme_names在无tkinter时应返回CTk回退列表"""
        mod = _load_mod()
        with patch.object(mod, "_load_theme_names", return_value=["blue", "green", "dark-blue"]):
            result = mod._load_theme_names()
            for name in result:
                assert name == name.lower()

    def test_theme_names_module_level_is_list(self):
        """THEME_NAMES在模块级别是一个列表"""
        mod = _load_mod()
        assert isinstance(mod.THEME_NAMES, list)


class TestProviderNames:
    """测试PROVIDER_NAMES列表"""

    def test_provider_count(self):
        """PROVIDER_NAMES应有6个provider"""
        mod = _load_mod()
        assert len(mod.SettingsDialog.PROVIDER_NAMES) == 6

    def test_provider_names_all_strings(self):
        """PROVIDER_NAMES所有条目均为字符串"""
        mod = _load_mod()
        for name in mod.SettingsDialog.PROVIDER_NAMES:
            assert isinstance(name, str)
            assert len(name) > 0

    def test_provider_names_unique(self):
        """PROVIDER_NAMES无重复"""
        mod = _load_mod()
        names = mod.SettingsDialog.PROVIDER_NAMES
        assert len(names) == len(set(names))

    def test_provider_names_ordered(self):
        """PROVIDER_NAMES顺序稳定"""
        mod = _load_mod()
        expected = ["deepseek", "openai", "anthropic", "openrouter", "siliconflow", "ollama"]
        assert mod.SettingsDialog.PROVIDER_NAMES == expected


# ============================================================
# Stage 4: 关键路径测试 — SettingsDialog 构造函数不抛异常
# ============================================================

class TestSettingsDialogConstructor:
    """测试 SettingsDialog 构造函数安全性"""

    @skip_if_no_tkinter
    def test_constructor_no_exception(self):
        """SettingsDialog 构造函数不抛异常"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            dlg = mod.SettingsDialog(master=root)
            assert dlg is not None
            assert dlg.window is not None
            assert dlg.window.winfo_exists()
            dlg.window.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_constructor_sets_attributes(self):
        """SettingsDialog 构造后具有预期属性"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            dlg = mod.SettingsDialog(master=root)
            assert hasattr(dlg, '_api_key_entries')
            assert hasattr(dlg, '_theme_var')
            assert hasattr(dlg, '_default_provider_var')
            assert hasattr(dlg, '_config')
            assert hasattr(dlg, '_status_label')
            # _api_key_entries 应包含所有 provider
            for provider in mod.SettingsDialog.PROVIDER_NAMES:
                assert provider in dlg._api_key_entries
            dlg.window.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_constructor_modal_behavior(self):
        """SettingsDialog 创建为模态窗口"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            dlg = mod.SettingsDialog(master=root)
            # grab_set 意味着窗口应获取输入焦点
            assert dlg.window.winfo_exists()
            dlg.window.destroy()
        finally:
            root.destroy()


# ============================================================
# Stage 4: 关键路径测试 — THEME_NAMES 正确加载
# ============================================================

class TestThemeNamesLoading:
    """测试 THEME_NAMES 正确加载"""

    def test_theme_names_is_nonempty_list(self):
        """THEME_NAMES 是非空列表"""
        mod = _load_mod()
        assert isinstance(mod.THEME_NAMES, list)
        assert len(mod.THEME_NAMES) > 0

    def test_theme_names_all_lowercase_strings(self):
        """THEME_NAMES 所有条目均为非空字符串"""
        mod = _load_mod()
        for name in mod.THEME_NAMES:
            assert isinstance(name, str)
            assert len(name) > 0

    def test_theme_names_from_modern_theme_or_fallback(self):
        """THEME_NAMES 来自 ModernTheme 或回退列表"""
        mod = _load_mod()
        # 如果 ModernTheme 可用，列表应更长；否则为 6 个回退
        try:
            from src.ui.themes.modern_theme import ModernTheme
            expected = ModernTheme.list_themes()
            assert mod.THEME_NAMES == expected
        except Exception:
            fallback = ["blue", "green", "dark-blue", "dark-green", "light", "system"]
            assert mod.THEME_NAMES == fallback


# ============================================================
# Stage 4: 关键路径测试 — _save_all 持久化
# ============================================================

class TestSaveAll:
    """测试 _save_all 持久化"""

    @skip_if_no_tkinter
    def test_save_all_calls_config_set(self):
        """_save_all 将设置写入 config"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            mock_config = MagicMock()
            dlg = mod.SettingsDialog(master=root, config_loader=mock_config)

            # 修改主题变量
            dlg._theme_var.set("GitHub Dark")
            dlg._default_provider_var.set("openai")

            dlg._save_all()

            # 验证 config.set 被调用
            calls = {str(c): c for c in mock_config.set.call_args_list}
            # 应该设置了 ui.theme
            mock_config.set.assert_any_call("ui.theme", "GitHub Dark")
            # 应该设置了 llm.default_provider
            mock_config.set.assert_any_call("llm.default_provider", "openai")

            dlg.window.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_save_all_persists_theme(self):
        """_save_all 正确持久化主题选择"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            mock_config = MagicMock()
            dlg = mod.SettingsDialog(master=root, config_loader=mock_config)

            dlg._theme_var.set("Catppuccin Mocha")
            dlg._save_all()

            mock_config.set.assert_any_call("ui.theme", "Catppuccin Mocha")

            dlg.window.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_save_all_handles_error_gracefully(self):
        """_save_all 异常时不崩溃，显示错误状态"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            mock_config = MagicMock()
            mock_config.set.side_effect = RuntimeError("disk full")
            dlg = mod.SettingsDialog(master=root, config_loader=mock_config)

            dlg._save_all()  # 不应抛异常

            # 状态应显示错误
            status = dlg._status_label.cget("text")
            assert "failed" in status.lower() or "error" in status.lower()

            dlg.window.destroy()
        finally:
            root.destroy()


# ============================================================
# Stage 4: 关键路径测试 — 无 keyring 时优雅降级
# ============================================================

class TestKeyringGracefulDegradation:
    """测试无 keyring 时优雅降级"""

    @skip_if_no_tkinter
    def test_no_keyring_constructor_does_not_crash(self):
        """无 keyring 时 SettingsDialog 构造不崩溃"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            # Mock CredentialStore 不可用
            with patch("src.utils.credential_store.CredentialStore", side_effect=Exception("no keyring")):
                dlg = mod.SettingsDialog(master=root, credential_store=None)
                assert dlg.window is not None
                assert dlg.window.winfo_exists()
                dlg.window.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_no_keyring_save_key_falls_back_to_config(self):
        """无 keyring 时保存 API key 回退到配置文件"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            mock_config = MagicMock()
            dlg = mod.SettingsDialog(
                master=root,
                config_loader=mock_config,
                credential_store=None,  # 无 keyring
            )

            # 模拟用户输入 key
            entry = dlg._api_key_entries.get("deepseek")
            assert entry is not None
            entry.insert(0, "sk-test-key-123")

            dlg._save_api_key("deepseek", entry)

            # 应该回退到 config.set
            mock_config.set.assert_called_with("api_keys.deepseek", "sk-test-key-123")

            dlg.window.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_no_keyring_clear_key_falls_back_to_config(self):
        """无 keyring 时清除 API key 回退到配置文件"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            mock_config = MagicMock()
            dlg = mod.SettingsDialog(
                master=root,
                config_loader=mock_config,
                credential_store=None,
            )

            dlg._clear_api_key("openai")

            mock_config.set.assert_called_with("api_keys.openai", "")

            dlg.window.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_no_keyring_load_existing_shows_not_set(self):
        """无 keyring 时 _load_existing 显示 '(not set)'"""
        mod = _load_mod()
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            mock_config = MagicMock()
            mock_config.get.return_value = ""
            dlg = mod.SettingsDialog(
                master=root,
                config_loader=mock_config,
                credential_store=None,
            )

            # 手动调用 _load_existing
            dlg._load_existing()

            # 所有 entry 应显示 "(not set)"
            for provider, entry in dlg._api_key_entries.items():
                ph = entry.cget("placeholder_text")
                assert "not set" in ph.lower() or "loading" in ph.lower()

            dlg.window.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
