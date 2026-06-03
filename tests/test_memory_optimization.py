"""Stage 2: 内存优化测试"""
import sys
import os
import csv
import tempfile
import pytest
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.file_info import FileInfo
from src.scanner.wiztree_scanner import WizTreeScanner


class TestFileInfoSlots:
    """测试 FileInfo __slots__ 实现"""
    
    def test_fileinfo_has_slots(self):
        """验证 FileInfo 使用 __slots__"""
        assert hasattr(FileInfo, '__slots__'), "FileInfo 应该定义 __slots__"
    
    def test_fileinfo_slots_contains_all_attributes(self):
        """验证 __slots__ 包含所有属性"""
        expected_slots = {
            'path', 'size', 'modified_time', 'created_time',
            'is_directory', 'extension', 'depth', 'parent_path'
        }
        actual_slots = set(FileInfo.__slots__)
        assert expected_slots == actual_slots, f"__slots__ 缺少属性: {expected_slots - actual_slots}"
    
    def test_fileinfo_no_dict(self):
        """使用 __slots__ 的实例不应该有 __dict__"""
        fi = FileInfo(
            path=Path("test.txt"),
            size=100,
            modified_time=datetime.now()
        )
        assert not hasattr(fi, '__dict__'), "使用 __slots__ 的实例不应有 __dict__"
    
    def test_fileinfo_properties_still_work(self):
        """验证属性方法仍然正常工作"""
        fi = FileInfo(
            path=Path("/some/path/test.txt"),
            size=1024,
            modified_time=datetime.now()
        )
        assert fi.name == "test.txt"
        assert "KB" in fi.size_human_readable
        assert str(fi) == "test.txt (1.00 KB)"
    
    def test_fileinfo_memory_reduction(self):
        """测试内存占用减少"""
        fi = FileInfo(
            path=Path("test.txt"),
            size=100,
            modified_time=datetime.now(),
            created_time=datetime.now(),
            is_directory=False,
            extension=".txt",
            depth=1,
            parent_path=Path("/some")
        )
        instance_size = sys.getsizeof(fi)
        # __slots__ 实例应该小于 200 字节（典型值约 64-128 字节）
        assert instance_size < 200, f"实例大小 {instance_size} 字节，预期 < 200"
    
    def test_fileinfo_cannot_add_dynamic_attribute(self):
        """使用 __slots__ 不能添加动态属性"""
        fi = FileInfo(
            path=Path("test.txt"),
            size=100,
            modified_time=datetime.now()
        )
        with pytest.raises(AttributeError):
            fi.dynamic_attr = "should fail"
    
    def test_fileinfo_from_path_classmethod(self):
        """验证 from_path 类方法仍然工作"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write(b"test content")
            temp_path = f.name
        
        try:
            fi = FileInfo.from_path(Path(temp_path))
            assert fi.path == Path(temp_path)
            assert fi.size > 0
            assert fi.modified_time is not None
            assert fi.is_directory is False
        finally:
            os.unlink(temp_path)


class TestCSVStreaming:
    """测试 CSV 流式解析"""
    
    def test_parse_csv_streaming_exists(self):
        """验证 _parse_csv_streaming 方法存在"""
        scanner = WizTreeScanner()
        assert hasattr(scanner, '_parse_csv_streaming')
    
    def test_parse_csv_streaming_is_generator(self):
        """验证 _parse_csv_streaming 返回生成器"""
        scanner = WizTreeScanner()
        
        # 创建临时 CSV 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Size', 'Allocated', 'Modified', 'Created', 'Entries'])
            writer.writerow(['C:\\test.txt', '1024', '1024', '2024-01-01 12:00:00', '', ''])
            csv_path = f.name
        
        try:
            result = scanner._parse_csv_streaming(csv_path)
            # 应该是生成器
            import types
            assert isinstance(result, types.GeneratorType), "应该返回生成器"
        finally:
            os.unlink(csv_path)
    
    def test_parse_csv_streaming_yields_fileinfo(self):
        """验证流式解析正确产出 FileInfo"""
        scanner = WizTreeScanner()
        
        # 创建临时 CSV 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Size', 'Allocated', 'Modified', 'Created', 'Entries'])
            writer.writerow(['C:\\test.txt', '1024', '1024', '2024-01-01 12:00:00', '', ''])
            writer.writerow(['C:\\data.csv', '2048', '2048', '2024-01-02 12:00:00', '', ''])
            csv_path = f.name
        
        try:
            files = list(scanner._parse_csv_streaming(csv_path))
            assert len(files) == 2
            assert all(isinstance(f, FileInfo) for f in files)
            assert files[0].size == 1024
            assert files[1].size == 2048
        finally:
            os.unlink(csv_path)
    
    def test_parse_csv_uses_streaming(self):
        """验证 _parse_csv 使用流式解析"""
        scanner = WizTreeScanner()
        
        # 创建临时 CSV 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Size', 'Allocated', 'Modified', 'Created', 'Entries'])
            writer.writerow(['C:\\b.txt', '512', '512', '2024-01-01 12:00:00', '', ''])
            writer.writerow(['C:\\a.txt', '1024', '1024', '2024-01-02 12:00:00', '', ''])
            csv_path = f.name
        
        try:
            files = scanner._parse_csv(csv_path)
            # 应该按大小降序排序
            assert len(files) == 2
            assert files[0].size >= files[1].size
        finally:
            os.unlink(csv_path)
    
    def test_parse_csv_streaming_skips_directories(self):
        """验证流式解析跳过目录"""
        scanner = WizTreeScanner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Size', 'Allocated', 'Modified', 'Created', 'Entries'])
            writer.writerow(['C:\\folder\\', '0', '0', '2024-01-01 12:00:00', '', ''])
            writer.writerow(['C:\\test.txt', '1024', '1024', '2024-01-01 12:00:00', '', ''])
            csv_path = f.name
        
        try:
            files = list(scanner._parse_csv_streaming(csv_path))
            assert len(files) == 1
            assert files[0].name == 'test.txt'
        finally:
            os.unlink(csv_path)
    
    def test_parse_csv_streaming_skips_zero_size(self):
        """验证流式解析跳过零大小文件"""
        scanner = WizTreeScanner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Size', 'Allocated', 'Modified', 'Created', 'Entries'])
            writer.writerow(['C:\\empty.txt', '0', '0', '2024-01-01 12:00:00', '', ''])
            writer.writerow(['C:\\test.txt', '1024', '1024', '2024-01-01 12:00:00', '', ''])
            csv_path = f.name
        
        try:
            files = list(scanner._parse_csv_streaming(csv_path))
            assert len(files) == 1
            assert files[0].size == 1024
        finally:
            os.unlink(csv_path)
    
    def test_parse_csv_streaming_handles_empty_csv(self):
        """验证流式解析处理空 CSV"""
        scanner = WizTreeScanner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Size', 'Allocated', 'Modified', 'Created', 'Entries'])
            csv_path = f.name
        
        try:
            files = list(scanner._parse_csv_streaming(csv_path))
            assert len(files) == 0
        finally:
            os.unlink(csv_path)
    
    def test_parse_csv_streaming_handles_no_header(self):
        """验证流式解析处理无标题 CSV"""
        scanner = WizTreeScanner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            # 空文件
            csv_path = f.name
        
        try:
            files = list(scanner._parse_csv_streaming(csv_path))
            assert len(files) == 0
        finally:
            os.unlink(csv_path)
    
    def test_parse_csv_streaming_cancellation(self):
        """验证流式解析支持取消"""
        scanner = WizTreeScanner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Size', 'Allocated', 'Modified', 'Created', 'Entries'])
            for i in range(100):
                writer.writerow([f'C:\\file{i}.txt', str(i * 100), str(i * 100), '2024-01-01 12:00:00', '', ''])
            csv_path = f.name
        
        try:
            # 模拟取消
            scanner._cancelled = True
            files = list(scanner._parse_csv_streaming(csv_path))
            assert len(files) == 0, "取消后应该没有文件"
        finally:
            os.unlink(csv_path)
            scanner._cancelled = False
    
    def test_parse_csv_streaming_memory_efficiency(self):
        """测试流式解析内存效率"""
        scanner = WizTreeScanner()
        
        # 创建较大的 CSV 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Size', 'Allocated', 'Modified', 'Created', 'Entries'])
            for i in range(1000):
                writer.writerow([f'C:\\path\\to\\file{i}.txt', str(i + 1), str(i + 1), '2024-01-01 12:00:00', '', ''])
            csv_path = f.name
        
        try:
            # 流式解析应该使用生成器
            gen = scanner._parse_csv_streaming(csv_path)
            import types
            assert isinstance(gen, types.GeneratorType)
            
            # 逐个获取，不应该一次性加载所有
            count = 0
            for fi in gen:
                assert isinstance(fi, FileInfo)
                count += 1
            
            assert count == 1000
        finally:
            os.unlink(csv_path)
