"""深度检索模块测试"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.scanner.deep_search import (
    DeepSearcher, 
    DeepSearchError, 
    PathValidationError, 
    ScanExecutionError
)
from src.scanner.path_validator import PathValidator
from src.scanner.wiztree_scanner import WizTreeScanner
from src.scanner.options import ScanOptions
from src.models.scan_result import ScanResult
from src.models.file_info import FileInfo
from datetime import datetime


class TestDeepSearcher:
    """深度检索器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.mock_scanner = MagicMock(spec=WizTreeScanner)
        self.searcher = DeepSearcher(self.mock_scanner)
        
    def test_validate_path_valid_directory(self):
        """测试有效目录路径验证"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.searcher._validate_path(tmpdir)
            assert result['is_valid'] is True
            assert result['error_message'] is None
            assert result['error_code'] is None
            
    def test_validate_path_nonexistent(self):
        """测试不存在的路径"""
        result = self.searcher._validate_path("Z:\\nonexistent_path_12345")
        assert result['is_valid'] is False
        assert result['error_code'] == 'BASIC_VALIDATION_FAILED'
        
    def test_validate_path_file_not_directory(self):
        """测试文件路径（不是目录）"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmpfile:
            tmpfile_path = tmpfile.name
        try:
            result = self.searcher._validate_path(tmpfile_path)
            assert result['is_valid'] is False
            # 文件在基础验证阶段就会被拒绝
            assert result['error_code'] in ['BASIC_VALIDATION_FAILED', 'NOT_DIRECTORY']
        finally:
            try:
                os.unlink(tmpfile_path)
            except PermissionError:
                pass
                
    def test_search_success(self):
        """测试成功搜索"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")
            
            # 模拟扫描结果
            mock_result = ScanResult(
                target_path=Path(tmpdir),
                files=[FileInfo(
                    path=test_file,
                    size=12,
                    modified_time=datetime.now(),
                    is_directory=False,
                    extension='.txt',
                    depth=0,
                    parent_path=Path(tmpdir)
                )],
                scan_time=datetime.now(),
                duration_seconds=1.0,
                total_files=1,
                total_directories=0,
                total_size=12,
                scan_options=None,
                errors=[]
            )
            self.mock_scanner.scan.return_value = mock_result
            
            # 执行搜索
            result = self.searcher.search(tmpdir)
            
            assert result.total_files == 1
            assert result.total_size == 12
            self.mock_scanner.scan.assert_called_once()
            
    def test_search_invalid_path_raises_error(self):
        """测试无效路径抛出异常"""
        with pytest.raises(PathValidationError):
            self.searcher.search("Z:\\nonexistent_path_12345")
            
    def test_get_folder_stats(self):
        """测试获取文件夹统计"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            (Path(tmpdir) / "file1.txt").write_text("content1")
            (Path(tmpdir) / "file2.txt").write_text("content2 longer")
            (Path(tmpdir) / "subdir").mkdir()
            
            stats = self.searcher.get_folder_stats(tmpdir)
            
            assert stats['file_count'] == 2
            assert stats['dir_count'] == 1
            assert stats['total_size'] > 0
            assert 'total_size_human_readable' in stats
            
    def test_get_folder_stats_nonexistent(self):
        """测试不存在路径的统计"""
        stats = self.searcher.get_folder_stats("Z:\\nonexistent_path_12345")
        assert 'error' in stats
        assert stats['error_code'] == 'PATH_NOT_FOUND'
        
    def test_search_files_by_pattern(self):
        """测试按模式搜索文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            (Path(tmpdir) / "test.txt").write_text("content")
            (Path(tmpdir) / "test.py").write_text("content")
            (Path(tmpdir) / "other.log").write_text("content")
            
            # 模拟扫描结果
            mock_result = ScanResult(
                target_path=Path(tmpdir),
                files=[
                    FileInfo(
                        path=Path(tmpdir) / "test.txt",
                        size=7,
                        modified_time=datetime.now(),
                        is_directory=False,
                        extension='.txt',
                        depth=0,
                        parent_path=Path(tmpdir)
                    ),
                    FileInfo(
                        path=Path(tmpdir) / "test.py",
                        size=7,
                        modified_time=datetime.now(),
                        is_directory=False,
                        extension='.py',
                        depth=0,
                        parent_path=Path(tmpdir)
                    ),
                    FileInfo(
                        path=Path(tmpdir) / "other.log",
                        size=7,
                        modified_time=datetime.now(),
                        is_directory=False,
                        extension='.log',
                        depth=0,
                        parent_path=Path(tmpdir)
                    ),
                ],
                scan_time=datetime.now(),
                duration_seconds=1.0,
                total_files=3,
                total_directories=0,
                total_size=21,
                scan_options=None,
                errors=[]
            )
            self.mock_scanner.scan.return_value = mock_result
            
            # 搜索 .txt 文件
            result = self.searcher.search_files_by_pattern(tmpdir, "*.txt")
            assert len(result.files) == 1
            assert result.files[0].extension == '.txt'
            
    def test_search_large_files(self):
        """测试搜索大文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 模拟扫描结果
            mock_result = ScanResult(
                target_path=Path(tmpdir),
                files=[],
                scan_time=datetime.now(),
                duration_seconds=1.0,
                total_files=0,
                total_directories=0,
                total_size=0,
                scan_options=None,
                errors=[]
            )
            self.mock_scanner.scan.return_value = mock_result
            
            # 搜索大文件
            result = self.searcher.search_large_files(tmpdir, min_size_mb=100)
            
            # 验证选项被设置
            call_args = self.mock_scanner.scan.call_args
            options = call_args[0][1]
            assert options.min_size == 100 * 1024 * 1024
            
    def test_match_pattern(self):
        """测试模式匹配"""
        assert self.searcher._match_pattern("test.txt", "*.txt") is True
        assert self.searcher._match_pattern("test.py", "*.txt") is False
        assert self.searcher._match_pattern("test.txt", "test.*") is True
        assert self.searcher._match_pattern("TEST.TXT", "*.txt") is True  # 大小写不敏感
        
    def test_format_size(self):
        """测试大小格式化"""
        assert DeepSearcher._format_size(100) == "100 B"
        assert DeepSearcher._format_size(1024) == "1.00 KB"
        assert DeepSearcher._format_size(1024 * 1024) == "1.00 MB"
        assert DeepSearcher._format_size(1024 * 1024 * 1024) == "1.00 GB"


class TestPathValidatorDeepSearch:
    """路径验证器深度检索测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.validator = PathValidator()
        
    def test_validate_deep_search_valid_directory(self):
        """测试有效目录深度验证"""
        with tempfile.TemporaryDirectory() as tmpdir:
            is_valid, error_msg, error_code = self.validator.validate_deep_search(tmpdir)
            assert is_valid is True
            assert error_msg is None
            assert error_code is None
            
    def test_validate_deep_search_file(self):
        """测试文件深度验证"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmpfile:
            tmpfile_path = tmpfile.name
        try:
            is_valid, error_msg, error_code = self.validator.validate_deep_search(tmpfile_path)
            assert is_valid is False
            # 文件在基础验证阶段就会被拒绝
            assert error_code in ['BASIC_VALIDATION_FAILED', 'NOT_DIRECTORY']
        finally:
            try:
                os.unlink(tmpfile_path)
            except PermissionError:
                pass
                
    def test_validate_deep_search_nonexistent(self):
        """测试不存在路径深度验证"""
        is_valid, error_msg, error_code = self.validator.validate_deep_search("Z:\\nonexistent_path_12345")
        assert is_valid is False
        assert error_code == 'BASIC_VALIDATION_FAILED'
        
    def test_get_path_info(self):
        """测试获取路径信息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            info = self.validator.get_path_info(tmpdir)
            assert info['exists'] is True
            assert info['is_directory'] is True
            assert info['is_file'] is False
            assert info['is_readable'] is True
            
    def test_get_path_info_nonexistent(self):
        """测试不存在路径信息"""
        info = self.validator.get_path_info("Z:\\nonexistent_path_12345")
        assert info['exists'] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
