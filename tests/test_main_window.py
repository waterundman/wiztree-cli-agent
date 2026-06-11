"""MainWindow模块测试"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from datetime import datetime

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


class TestMainWindowModule:
    """测试MainWindow模块级功能 — 导入main_window需要tkinter"""

    @skip_if_no_tkinter
    def test_import_main_window(self):
        """MainWindow类可以导入"""
        from src.ui.main_window import MainWindow
        assert MainWindow is not None

    @skip_if_no_tkinter
    def test_max_scan_files_defined(self):
        """MAX_SCAN_FILES和MAX_DISPLAY_FILES已定义且为正值"""
        from src.ui.main_window import MainWindow
        assert MainWindow.MAX_SCAN_FILES > 0
        assert MainWindow.MAX_DISPLAY_FILES > 0

    @skip_if_no_tkinter
    def test_max_scan_files_greater_than_display(self):
        """MAX_SCAN_FILES应大于等于MAX_DISPLAY_FILES"""
        from src.ui.main_window import MainWindow
        assert MainWindow.MAX_SCAN_FILES >= MainWindow.MAX_DISPLAY_FILES

    @skip_if_no_tkinter
    def test_format_size_static_method(self):
        """format_size是一个实例方法"""
        from src.ui.main_window import MainWindow
        assert hasattr(MainWindow, 'format_size')

    @skip_if_no_tkinter
    def test_format_size_bytes(self):
        """format_size格式化字节"""
        from src.ui.main_window import MainWindow
        mw = object.__new__(MainWindow)
        assert mw.format_size(500) == "500 B"

    @skip_if_no_tkinter
    def test_format_size_kb(self):
        """format_size格式化KB"""
        from src.ui.main_window import MainWindow
        mw = object.__new__(MainWindow)
        result = mw.format_size(1024)
        assert "KB" in result

    @skip_if_no_tkinter
    def test_format_size_mb(self):
        """format_size格式化MB"""
        from src.ui.main_window import MainWindow
        mw = object.__new__(MainWindow)
        result = mw.format_size(1024 * 1024)
        assert "MB" in result

    @skip_if_no_tkinter
    def test_format_size_gb(self):
        """format_size格式化GB"""
        from src.ui.main_window import MainWindow
        mw = object.__new__(MainWindow)
        result = mw.format_size(1024 * 1024 * 1024)
        assert "GB" in result

    @skip_if_no_tkinter
    def test_format_size_zero(self):
        """format_size格式化0字节"""
        from src.ui.main_window import MainWindow
        mw = object.__new__(MainWindow)
        assert mw.format_size(0) == "0 B"

    @skip_if_no_tkinter
    def test_format_size_kb_boundary(self):
        """format_size在KB边界正确格式化"""
        from src.ui.main_window import MainWindow
        mw = object.__new__(MainWindow)
        assert mw.format_size(1023) == "1023 B"
        assert "KB" in mw.format_size(1024)

    @skip_if_no_tkinter
    def test_format_size_mb_boundary(self):
        """format_size在MB边界正确格式化"""
        from src.ui.main_window import MainWindow
        mw = object.__new__(MainWindow)
        result = mw.format_size(1024 * 1024 - 1)
        assert "KB" in result
        result = mw.format_size(1024 * 1024)
        assert "MB" in result

    @skip_if_no_tkinter
    def test_format_size_gb_boundary(self):
        """format_size在GB边界正确格式化"""
        from src.ui.main_window import MainWindow
        mw = object.__new__(MainWindow)
        result = mw.format_size(1024 * 1024 * 1024 - 1)
        assert "MB" in result
        result = mw.format_size(1024 * 1024 * 1024)
        assert "GB" in result


class TestMainWindowImports:
    """测试MainWindow模块从src.ui导入"""

    @skip_if_no_tkinter
    def test_main_window_in_ui_package(self):
        """MainWindow可通过src.ui导入"""
        from src.ui import MainWindow
        assert MainWindow is not None

    @skip_if_no_tkinter
    def test_main_window_has_expected_methods(self):
        """MainWindow具有预期的核心方法"""
        from src.ui.main_window import MainWindow
        assert hasattr(MainWindow, 'setup_ui')
        assert hasattr(MainWindow, 'format_size')
        assert hasattr(MainWindow, 'update_scan_results')
        assert hasattr(MainWindow, 'update_status')


class TestRiskLevelDisplay:
    """测试RiskLevel显示相关功能 — 不需要tkinter"""

    def test_risk_level_values_are_lowercase(self):
        """RiskLevel枚举值均为小写"""
        from src.models.analysis_result import RiskLevel
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_level_comparison_lowercase(self):
        """风险等级比较应使用小写值"""
        from src.models.analysis_result import RiskLevel
        risk = RiskLevel.HIGH
        assert risk.value == "high"

    def test_risk_level_not_uppercase(self):
        """风险等级值不应为大写（防止显示Bug）"""
        from src.models.analysis_result import RiskLevel
        for level in RiskLevel:
            assert level.value == level.value.lower()

    def test_risk_level_list(self):
        """RiskLevel应有4个级别"""
        from src.models.analysis_result import RiskLevel
        levels = list(RiskLevel)
        assert len(levels) == 4
        names = [r.name for r in levels]
        assert "LOW" in names
        assert "MEDIUM" in names
        assert "HIGH" in names
        assert "CRITICAL" in names


class TestVirtualTreeviewImport:
    """测试VirtualTreeview组件导入"""

    @skip_if_no_tkinter
    def test_virtual_treeview_class_exists(self):
        """VirtualTreeview类存在"""
        from src.ui.components.virtual_treeview import VirtualTreeview
        assert VirtualTreeview is not None

    @skip_if_no_tkinter
    def test_virtual_treeview_methods(self):
        """VirtualTreeview具有预期方法"""
        from src.ui.components.virtual_treeview import VirtualTreeview
        assert hasattr(VirtualTreeview, 'insert')
        assert hasattr(VirtualTreeview, 'delete')
        assert hasattr(VirtualTreeview, 'get_children')


class TestMainWindowConstants:
    """测试MainWindow常量配置"""

    @skip_if_no_tkinter
    def test_max_scan_files_value(self):
        """MAX_SCAN_FILES应为5000"""
        from src.ui.main_window import MainWindow
        assert MainWindow.MAX_SCAN_FILES == 5000

    @skip_if_no_tkinter
    def test_max_display_files_value(self):
        """MAX_DISPLAY_FILES应为500"""
        from src.ui.main_window import MainWindow
        assert MainWindow.MAX_DISPLAY_FILES == 500

    @skip_if_no_tkinter
    def test_display_not_exceed_scan(self):
        """显示数量不超过扫描上限"""
        from src.ui.main_window import MainWindow
        assert MainWindow.MAX_DISPLAY_FILES <= MainWindow.MAX_SCAN_FILES


# ============================================================
# Stage 4: 关键路径测试 — start_scan 按钮状态
# ============================================================

class TestStartScanButtonState:
    """测试 start_scan() 按钮状态变更和线程启动"""

    @skip_if_no_tkinter
    def test_start_scan_disables_button(self):
        """start_scan() 将 scan_button 状态设为 disabled"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from src.ui.main_window import MainWindow
            mw = MainWindow()

            # Mock 验证路径存在
            with patch("os.path.isfile", return_value=True):
                # Mock scanner 和线程避免实际扫描
                with patch("src.ui.main_window.WizTreeScanner"):
                    with patch("src.ui.main_window.threading.Thread") as mock_thread:
                        mock_thread_instance = MagicMock()
                        mock_thread.return_value = mock_thread_instance

                        mw.start_scan()

                        state = str(mw.scan_button.cget("state"))
                        assert state == "disabled"
                        assert "Scanning" in str(mw.scan_button.cget("text"))
                        mock_thread_instance.start.assert_called_once()

            mw.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_start_scan_starts_thread(self):
        """start_scan() 启动后台线程"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from src.ui.main_window import MainWindow
            mw = MainWindow()

            with patch("os.path.isfile", return_value=True):
                with patch("src.ui.main_window.WizTreeScanner"):
                    with patch("src.ui.main_window.threading.Thread") as mock_thread:
                        mock_thread_instance = MagicMock()
                        mock_thread.return_value = mock_thread_instance

                        mw.start_scan()

                        # 验证线程以 daemon=True 创建
                        call_kwargs = mock_thread.call_args
                        assert call_kwargs[1].get("daemon") is True or call_kwargs.kwargs.get("daemon") is True
                        mock_thread_instance.start.assert_called_once()

            mw.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_start_scan_invalid_path_shows_error(self):
        """start_scan() 无效路径时显示错误，不启动扫描"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from src.ui.main_window import MainWindow
            mw = MainWindow()

            # 设置无效路径
            mw.wiztree_path.delete(0, "end")
            mw.wiztree_path.insert(0, "Z:\\nonexistent\\wiztree.exe")

            with patch("os.path.isfile", return_value=False):
                with patch("src.ui.main_window.threading.Thread") as mock_thread:
                    with patch("tkinter.messagebox.showerror"):
                        mw.start_scan()

                        # 不应启动线程
                        mock_thread.assert_not_called()

            mw.destroy()
        finally:
            root.destroy()


# ============================================================
# Stage 4: 关键路径测试 — update_scan_results 截断逻辑
# ============================================================

class TestUpdateScanResultsTruncation:
    """测试 update_scan_results() 的 MAX_DISPLAY_FILES 截断逻辑"""

    @skip_if_no_tkinter
    def test_truncation_limits_display(self):
        """文件数超过 MAX_DISPLAY_FILES 时只显示前 MAX_DISPLAY_FILES 个"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from src.ui.main_window import MainWindow
            from src.models.file_info import FileInfo
            mw = MainWindow()

            # 创建超过 MAX_DISPLAY_FILES 的模拟文件
            max_display = MainWindow.MAX_DISPLAY_FILES
            total_files = max_display + 200
            files = []
            for i in range(total_files):
                fi = FileInfo(
                    path=Path(f"C:\\file_{i}.dat"),
                    size=(total_files - i) * 1024,
                    modified_time=datetime.now(),
                )
                files.append(fi)

            mock_result = MagicMock()
            mock_result.files = files
            mock_result.total_files = total_files
            mock_result.total_size = sum(f.size for f in files)
            mock_result.duration_seconds = 1.5

            mw.scan_result = mock_result
            mw.update_scan_results()

            # 验证 scan_tree 只有 MAX_DISPLAY_FILES 行
            children = mw.scan_tree.get_children()
            assert len(children) == max_display

            # 验证状态栏显示截断提示
            status_text = mw.status_label.cget("text")
            assert str(max_display) in status_text

            mw.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_no_truncation_when_under_limit(self):
        """文件数不超过 MAX_DISPLAY_FILES 时全部显示"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from src.ui.main_window import MainWindow
            from src.models.file_info import FileInfo
            mw = MainWindow()

            file_count = 10
            files = []
            for i in range(file_count):
                fi = FileInfo(
                    path=Path(f"C:\\file_{i}.dat"),
                    size=(i + 1) * 1024,
                    modified_time=datetime.now(),
                )
                files.append(fi)

            mock_result = MagicMock()
            mock_result.files = files
            mock_result.total_files = file_count
            mock_result.total_size = sum(f.size for f in files)
            mock_result.duration_seconds = 0.5

            mw.scan_result = mock_result
            mw.update_scan_results()

            children = mw.scan_tree.get_children()
            assert len(children) == file_count

            mw.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_update_scan_results_empty(self):
        """scan_result 为 None 时不崩溃"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from src.ui.main_window import MainWindow
            mw = MainWindow()

            mw.scan_result = None
            mw.update_scan_results()  # 不应抛异常

            children = mw.scan_tree.get_children()
            assert len(children) == 0

            mw.destroy()
        finally:
            root.destroy()


# ============================================================
# Stage 4: 关键路径测试 — update_action_table 数据填充
# ============================================================

class TestUpdateActionTable:
    """测试 update_action_table() 数据填充"""

    @skip_if_no_tkinter
    def test_action_table_populates_from_file_pool(self):
        """update_action_table 从 _file_pool 填充 action_tree"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from src.ui.main_window import MainWindow
            from src.models.file_info import FileInfo
            from src.models.analysis_result import DeletionRecommendation, RiskLevel
            mw = MainWindow()

            # 创建文件池
            files = []
            for i in range(5):
                fi = FileInfo(
                    path=Path(f"C:\\pool_file_{i}.tmp"),
                    size=(i + 1) * 2048,
                    modified_time=datetime.now(),
                )
                files.append(fi)
            mw._file_pool = files
            mw._current_batch = 0

            # 创建推荐（部分文件有推荐）
            rec = DeletionRecommendation(
                file=files[0],
                reason="Temporary file",
                risk_level=RiskLevel.LOW,
                confidence=0.9,
                potential_savings=files[0].size,
                selected=False,
            )
            mw.recommendations = [rec]

            mw.update_action_table()

            # 验证 action_tree 有数据
            children = mw.action_tree.get_children()
            assert len(children) == 5

            # 验证第一条有推荐信息
            first_values = mw.action_tree.item(children[0], "values")
            assert "Temporary file" in str(first_values[3])

            # 验证无推荐的文件显示默认文本
            second_values = mw.action_tree.item(children[1], "values")
            assert "Not recommended" in str(second_values[3])

            mw.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_action_table_empty_pool(self):
        """文件池为空时 update_action_table 不崩溃"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from src.ui.main_window import MainWindow
            mw = MainWindow()

            mw._file_pool = []
            mw._current_batch = 0
            mw.recommendations = []
            mw.update_action_table()

            children = mw.action_tree.get_children()
            assert len(children) == 0

            mw.destroy()
        finally:
            root.destroy()


# ============================================================
# Stage 4: 关键路径测试 — _refresh_model_selector 无 API key
# ============================================================

class TestRefreshModelSelector:
    """测试 _refresh_model_selector() 无 API key 时的显示"""

    @skip_if_no_tkinter
    def test_no_api_key_shows_fallback(self):
        """无 API key 时模型选择器显示 '(no API key configured)'"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from src.ui.main_window import MainWindow
            mw = MainWindow()

            # Mock CredentialStore 抛异常（模拟无 keyring）
            with patch("src.utils.credential_store.CredentialStore", side_effect=Exception("no keyring")):
                # 调用 _refresh_model_selector 并等待后台线程完成
                mw._refresh_model_selector()

                # 等待后台线程的 after(0, _update) 执行
                import time
                for _ in range(50):
                    mw.update_idletasks()
                    mw.update()
                    time.sleep(0.05)

                # 检查 model_dropdown 的值
                var_val = mw.model_var.get()
                assert var_val == "(no API key configured)"

                # 检查状态标签
                status_text = mw.model_status_label.cget("text")
                assert "No API keys" in status_text

            mw.destroy()
        finally:
            root.destroy()

    @skip_if_no_tkinter
    def test_with_api_keys_shows_models(self):
        """有 API key 时显示可用模型列表"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            from src.ui.main_window import MainWindow
            mw = MainWindow()

            mock_store = MagicMock()
            mock_store.get_api_key.return_value = "fake-key"

            mock_router = MagicMock()
            mock_router.get_provider_status.return_value = {
                "deepseek": {
                    "has_api_key": True,
                    "models": ["deepseek-chat", "deepseek-coder"],
                }
            }

            with patch("src.utils.credential_store.CredentialStore", return_value=mock_store):
                with patch("src.analyzer.llm_router.LLMRouter", return_value=mock_router):
                    mw._llm_router = None
                    mw._refresh_model_selector()

                    import time
                    for _ in range(50):
                        mw.update_idletasks()
                        mw.update()
                        time.sleep(0.05)

                    var_val = mw.model_var.get()
                    assert "deepseek" in var_val

            mw.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
