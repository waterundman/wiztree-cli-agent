"""UI模块测试"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import FileInfo, ScanResult, RiskLevel, DeletionRecommendation

# 检查tkinter是否可用
try:
    import tkinter
    import customtkinter
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

# 跳过需要tkinter的测试
skip_if_no_tkinter = pytest.mark.skipif(
    not TKINTER_AVAILABLE,
    reason="tkinter not available"
)


class TestMainWindowInit:
    """测试MainWindow初始化"""

    @skip_if_no_tkinter
    def test_main_window_class_exists(self):
        """测试MainWindow类存在"""
        from src.ui.main_window import MainWindow
        assert MainWindow is not None

    @skip_if_no_tkinter
    def test_format_size_bytes(self):
        """测试字节大小格式化"""
        from src.ui.main_window import MainWindow
        window = MainWindow.__new__(MainWindow)
        assert window.format_size(500) == "500 B"

    @skip_if_no_tkinter
    def test_format_size_kb(self):
        """测试KB大小格式化"""
        from src.ui.main_window import MainWindow
        window = MainWindow.__new__(MainWindow)
        result = window.format_size(1024)
        assert "KB" in result

    @skip_if_no_tkinter
    def test_format_size_mb(self):
        """测试MB大小格式化"""
        from src.ui.main_window import MainWindow
        window = MainWindow.__new__(MainWindow)
        result = window.format_size(1024 * 1024)
        assert "MB" in result

    @skip_if_no_tkinter
    def test_format_size_gb(self):
        """测试GB大小格式化"""
        from src.ui.main_window import MainWindow
        window = MainWindow.__new__(MainWindow)
        result = window.format_size(1024 * 1024 * 1024)
        assert "GB" in result


class TestScanResultsUpdate:
    """测试扫描结果更新"""

    def test_scan_result_creation(self):
        """测试扫描结果创建"""
        files = [
            FileInfo(
                path=Path(f"test_{i}.txt"),
                size=1024 * (i + 1),
                modified_time=datetime.now()
            )
            for i in range(3)
        ]
        result = ScanResult(
            target_path=Path("."),
            files=files,
            scan_time=datetime.now(),
            duration_seconds=2.5,
            total_files=3,
            total_directories=0,
            total_size=sum(f.size for f in files)
        )
        assert result.total_files == 3
        assert result.total_size == sum(f.size for f in files)

    def test_scan_result_files(self):
        """测试扫描结果文件列表"""
        files = [
            FileInfo(path=Path("a.txt"), size=100, modified_time=datetime.now()),
            FileInfo(path=Path("b.txt"), size=200, modified_time=datetime.now()),
        ]
        result = ScanResult(
            target_path=Path("."),
            files=files,
            scan_time=datetime.now(),
            duration_seconds=1.0,
            total_files=2,
            total_directories=0,
            total_size=300
        )
        assert len(result.files) == 2
        assert result.files[0].name == "a.txt"

    def test_scan_result_get_largest_files(self):
        """测试获取最大文件"""
        files = [
            FileInfo(path=Path("small.txt"), size=100, modified_time=datetime.now()),
            FileInfo(path=Path("large.txt"), size=1000, modified_time=datetime.now()),
            FileInfo(path=Path("medium.txt"), size=500, modified_time=datetime.now()),
        ]
        result = ScanResult(
            target_path=Path("."),
            files=files,
            scan_time=datetime.now(),
            duration_seconds=1.0,
            total_files=3,
            total_directories=0,
            total_size=1600
        )
        largest = result.get_largest_files(2)
        assert len(largest) == 2
        assert largest[0].name == "large.txt"


class TestAIAnalysisUpdate:
    """测试AI分析更新"""

    def test_deletion_recommendation_creation(self):
        """测试删除推荐创建"""
        file_info = FileInfo(
            path=Path("temp.tmp"),
            size=1024,
            modified_time=datetime.now()
        )
        rec = DeletionRecommendation(
            file=file_info,
            reason="Temporary file",
            risk_level=RiskLevel.LOW,
            confidence=0.8,
            potential_savings=1024
        )
        assert rec.file.name == "temp.tmp"
        assert rec.risk_level == RiskLevel.LOW
        assert rec.confidence == 0.8

    def test_risk_levels(self):
        """测试风险等级"""
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.LOW.value == "low"

    def test_multiple_recommendations(self):
        """测试多个推荐"""
        recommendations = []
        for i in range(3):
            file_info = FileInfo(
                path=Path(f"file_{i}.tmp"),
                size=1024 * (i + 1),
                modified_time=datetime.now()
            )
            rec = DeletionRecommendation(
                file=file_info,
                reason=f"Reason {i}",
                risk_level=RiskLevel.LOW,
                confidence=0.7,
                potential_savings=file_info.size
            )
            recommendations.append(rec)
        assert len(recommendations) == 3
        assert all(r.risk_level == RiskLevel.LOW for r in recommendations)

    def test_analysis_result_creation(self):
        """测试分析结果创建"""
        from src.models import AnalysisResult
        file_info = FileInfo(
            path=Path("test.txt"),
            size=1024,
            modified_time=datetime.now()
        )
        rec = DeletionRecommendation(
            file=file_info,
            reason="test",
            risk_level=RiskLevel.LOW,
            confidence=0.9,
            potential_savings=1024
        )
        result = AnalysisResult(
            recommendations=[rec],
            total_potential_savings=1024,
            analysis_time=datetime.now(),
            duration_seconds=0.5
        )
        assert len(result.recommendations) == 1
        assert result.total_potential_savings == 1024


class TestFileActionTable:
    """测试文件操作表格"""

    def test_file_info_properties(self):
        """测试文件信息属性"""
        file_info = FileInfo(
            path=Path("test.txt"),
            size=1024,
            modified_time=datetime.now(),
            extension=".txt"
        )
        assert file_info.name == "test.txt"
        assert file_info.extension == ".txt"
        assert file_info.size == 1024

    def test_file_info_size_formats(self):
        """测试文件大小格式"""
        file_info = FileInfo(
            path=Path("test.txt"),
            size=500,
            modified_time=datetime.now()
        )
        assert "B" in file_info.size_human_readable

        file_info.size = 1024 * 1024
        assert "MB" in file_info.size_human_readable

    def test_file_info_from_path(self):
        """测试从路径创建FileInfo"""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode='w') as f:
            f.write("test content")
            temp_path = f.name
        try:
            path = Path(temp_path)
            file_info = FileInfo.from_path(path)
            assert file_info.path == path
            assert file_info.extension == ".txt"
            assert file_info.size > 0
        finally:
            os.unlink(temp_path)

    def test_recommendation_with_high_risk(self):
        """测试高风险推荐"""
        file_info = FileInfo(
            path=Path("important.dll"),
            size=1024 * 100,
            modified_time=datetime.now()
        )
        rec = DeletionRecommendation(
            file=file_info,
            reason="System file",
            risk_level=RiskLevel.HIGH,
            confidence=0.9,
            potential_savings=file_info.size
        )
        assert rec.risk_level == RiskLevel.HIGH

    def test_recommendation_with_medium_risk(self):
        """测试中风险推荐"""
        file_info = FileInfo(
            path=Path("cache.dat"),
            size=1024 * 50,
            modified_time=datetime.now()
        )
        rec = DeletionRecommendation(
            file=file_info,
            reason="Cache file",
            risk_level=RiskLevel.MEDIUM,
            confidence=0.6,
            potential_savings=file_info.size
        )
        assert rec.risk_level == RiskLevel.MEDIUM


class TestFileTable:
    """测试FileTable组件"""

    @skip_if_no_tkinter
    def test_file_table_class_exists(self):
        """测试FileTable类存在"""
        from src.ui.file_table import FileTable
        assert FileTable is not None

    @skip_if_no_tkinter
    def test_file_table_methods(self):
        """测试FileTable方法"""
        from src.ui.file_table import FileTable
        assert hasattr(FileTable, 'add_files')
        assert hasattr(FileTable, 'get_selected_files')
        assert hasattr(FileTable, 'clear')


class TestResultsView:
    """测试ResultsView组件"""

    @skip_if_no_tkinter
    def test_results_view_class_exists(self):
        """测试ResultsView类存在"""
        from src.ui.results_view import ResultsView
        assert ResultsView is not None

    @skip_if_no_tkinter
    def test_results_view_methods(self):
        """测试ResultsView方法"""
        from src.ui.results_view import ResultsView
        assert hasattr(ResultsView, 'populate_results')
        assert hasattr(ResultsView, 'clear_results')


class TestSmoothProgressBar:
    """测试平滑进度条"""

    @skip_if_no_tkinter
    def test_smooth_progress_bar_class_exists(self):
        """测试SmoothProgressBar类存在"""
        from src.ui.animations.smooth_progress import SmoothProgressBar
        assert SmoothProgressBar is not None

    @skip_if_no_tkinter
    def test_smooth_progress_bar_methods(self):
        """测试SmoothProgressBar方法"""
        from src.ui.animations.smooth_progress import SmoothProgressBar
        assert hasattr(SmoothProgressBar, 'set_smooth')
        assert hasattr(SmoothProgressBar, 'animate')


class TestSpinnerLabel:
    """测试旋转器标签"""

    @skip_if_no_tkinter
    def test_spinner_label_class_exists(self):
        """测试SpinnerLabel类存在"""
        from src.ui.animations.smooth_progress import SpinnerLabel
        assert SpinnerLabel is not None

    @skip_if_no_tkinter
    def test_spinner_frames(self):
        """测试旋转器帧"""
        from src.ui.animations.smooth_progress import SpinnerLabel
        assert len(SpinnerLabel.FRAMES) == 8
        assert "⣾" in SpinnerLabel.FRAMES

    @skip_if_no_tkinter
    def test_spinner_methods(self):
        """测试SpinnerLabel方法"""
        from src.ui.animations.smooth_progress import SpinnerLabel
        assert hasattr(SpinnerLabel, 'start')
        assert hasattr(SpinnerLabel, 'stop')
        assert hasattr(SpinnerLabel, 'animate')


class TestFadeInEffect:
    """测试淡入效果"""

    @skip_if_no_tkinter
    def test_fade_in_effect_class_exists(self):
        """测试FadeInEffect类存在"""
        from src.ui.animations.smooth_progress import FadeInEffect
        assert FadeInEffect is not None

    @skip_if_no_tkinter
    def test_fade_in_effect_methods(self):
        """测试FadeInEffect方法"""
        from src.ui.animations.smooth_progress import FadeInEffect
        assert hasattr(FadeInEffect, 'apply')
        assert hasattr(FadeInEffect, 'fade_in')


class TestUIIntegration:
    """UI集成测试"""

    @skip_if_no_tkinter
    def test_ui_module_imports(self):
        """测试UI模块导入"""
        from src.ui import MainWindow, ConfigPanel, ResultsView, FileTable
        assert MainWindow is not None
        assert ConfigPanel is not None
        assert ResultsView is not None
        assert FileTable is not None

    def test_models_imports(self):
        """测试模型导入"""
        from src.models import FileInfo, ScanResult, AnalysisResult, DeletionRecommendation, RiskLevel
        assert FileInfo is not None
        assert ScanResult is not None
        assert AnalysisResult is not None
        assert DeletionRecommendation is not None
        assert RiskLevel is not None

    def test_scanner_imports(self):
        """测试扫描器导入"""
        from src.scanner import WizTreeScanner, PathValidator, ScanOptions
        assert WizTreeScanner is not None
        assert PathValidator is not None
        assert ScanOptions is not None

    def test_analyzer_imports(self):
        """测试分析器导入"""
        from src.analyzer import RuleEngine
        assert RuleEngine is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
