"""ScanOptions 扩展参数测试"""
import pytest
from src.scanner.options import ScanOptions


class TestScanOptionsExtended:
    """测试 ScanOptions 扩展参数"""
    
    def test_default_options(self):
        """测试默认选项包含所有新参数"""
        options = ScanOptions()
        
        # 原有参数
        assert options.max_depth is None
        assert options.include_hidden == False
        assert options.file_extensions is None
        assert options.exclude_patterns is None
        assert options.min_size is None
        assert options.max_size is None
        assert options.follow_symlinks == False
        
        # 新增参数
        assert options.max_files == 1000
        assert options.batch_size == 50
        assert options.streaming == True
        assert options.cache_batches == 3
        assert options.lazy_load == True
    
    def test_custom_options(self):
        """测试自定义参数值"""
        options = ScanOptions(
            max_depth=5,
            include_hidden=True,
            max_files=500,
            batch_size=100,
            streaming=False,
            cache_batches=5,
            lazy_load=False
        )
        
        assert options.max_depth == 5
        assert options.include_hidden == True
        assert options.max_files == 500
        assert options.batch_size == 100
        assert options.streaming == False
        assert options.cache_batches == 5
        assert options.lazy_load == False
    
    def test_to_dict(self):
        """测试 to_dict 方法包含所有新参数"""
        options = ScanOptions()
        d = options.to_dict()
        
        assert isinstance(d, dict)
        
        # 检查原有键
        assert 'max_depth' in d
        assert 'include_hidden' in d
        assert 'file_extensions' in d
        assert 'exclude_patterns' in d
        assert 'min_size' in d
        assert 'max_size' in d
        assert 'follow_symlinks' in d
        
        # 检查新增键
        assert 'max_files' in d
        assert 'batch_size' in d
        assert 'streaming' in d
        assert 'cache_batches' in d
        assert 'lazy_load' in d
        
        # 检查值
        assert d['max_files'] == 1000
        assert d['batch_size'] == 50
        assert d['streaming'] == True
        assert d['cache_batches'] == 3
        assert d['lazy_load'] == True
    
    def test_to_dict_custom_values(self):
        """测试自定义值的 to_dict"""
        options = ScanOptions(
            max_files=2000,
            batch_size=25,
            streaming=False,
            cache_batches=2,
            lazy_load=False
        )
        d = options.to_dict()
        
        assert d['max_files'] == 2000
        assert d['batch_size'] == 25
        assert d['streaming'] == False
        assert d['cache_batches'] == 2
        assert d['lazy_load'] == False
    
    def test_backward_compatibility(self):
        """测试向后兼容性 - 使用原有参数创建"""
        options = ScanOptions(
            max_depth=3,
            include_hidden=True,
            file_extensions=['.txt', '.py'],
            exclude_patterns=['*.tmp'],
            min_size=1024,
            max_size=1024*1024,
            follow_symlinks=True
        )
        
        # 原有参数应正确设置
        assert options.max_depth == 3
        assert options.include_hidden == True
        assert options.file_extensions == ['.txt', '.py']
        assert options.exclude_patterns == ['*.tmp']
        assert options.min_size == 1024
        assert options.max_size == 1024*1024
        assert options.follow_symlinks == True
        
        # 新参数应使用默认值
        assert options.max_files == 1000
        assert options.batch_size == 50
        assert options.streaming == True
        assert options.cache_batches == 3
        assert options.lazy_load == True
        
        # to_dict 应包含所有参数
        d = options.to_dict()
        assert len(d) == 12  # 7 original + 5 new