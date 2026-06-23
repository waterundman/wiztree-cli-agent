"""StreamingScanner模块测试"""
import pytest
import tempfile
import os
import csv
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.scanner import StreamingScanner, WizTreeScanner
from src.scanner.options import ScanOptions
from src.models import FileInfo, ScanResult


def _write_test_csv(rows):
    """创建临时CSV文件并返回路径"""
    f = tempfile.NamedTemporaryFile(
        mode='w', suffix='.csv', delete=False, encoding='utf-8-sig'
    )
    writer = csv.writer(f)
    writer.writerows(rows)
    f.close()
    return f.name


def _make_scanner_with_mocks(test_csv_path):
    """创建扫描器，注入模拟的 _execute_scan 和 isfile 检查。

    _execute_scan 会在被调用时将 test_csv_path 复制到 cmd 参数指定的
    csv_path（即 scan_batch 内部生成的临时目标路径）。
    """
    scanner = StreamingScanner("dummy_wiztree.exe")

    def mock_execute_scan(cmd, dest_csv_path):
        shutil.copy2(test_csv_path, dest_csv_path)

    scanner._execute_scan = mock_execute_scan
    return scanner


# ---- 标准CSV测试数据 ----
STANDARD_CSV_ROWS = [
    ['文件名', '大小', '修改时间', '创建时间', '属性', '路径'],
    ['C:\\test\\file1.txt', '1024', '2024-01-01 10:00:00', '2024-01-01 10:00:00', '32', 'C:\\test'],
    ['C:\\test\\file2.txt', '2048', '2024-01-01 11:00:00', '2024-01-01 11:00:00', '32', 'C:\\test'],
    ['C:\\test\\file3.txt', '4096', '2024-01-01 12:00:00', '2024-01-01 12:00:00', '32', 'C:\\test'],
    ['C:\\test\\file4.txt', '512', '2024-01-01 13:00:00', '2024-01-01 13:00:00', '32', 'C:\\test'],
    ['C:\\test\\file5.txt', '100', '2024-01-01 14:00:00', '2024-01-01 14:00:00', '32', 'C:\\test'],
]


class TestStreamingScanner:
    """StreamingScanner测试类"""

    def test_streaming_scanner_inherits_wiztree_scanner(self):
        scanner = StreamingScanner()
        assert isinstance(scanner, WizTreeScanner)

    def test_streaming_scanner_has_scan_batch_method(self):
        scanner = StreamingScanner()
        assert hasattr(scanner, 'scan_batch')
        assert callable(scanner.scan_batch)

    def test_streaming_scanner_has_scan_streaming_method(self):
        scanner = StreamingScanner()
        assert hasattr(scanner, 'scan_streaming')
        assert callable(scanner.scan_streaming)

    def test_streaming_scanner_has_get_total_files_count(self):
        scanner = StreamingScanner()
        assert hasattr(scanner, 'get_total_files_count')
        assert callable(scanner.get_total_files_count)

    def test_streaming_scanner_has_get_batch_info(self):
        scanner = StreamingScanner()
        assert hasattr(scanner, 'get_batch_info')
        assert callable(scanner.get_batch_info)

    def test_streaming_scanner_has_clear_cache(self):
        scanner = StreamingScanner()
        assert hasattr(scanner, 'clear_cache')
        assert callable(scanner.clear_cache)

    @patch('os.path.isfile', return_value=True)
    def test_scan_batch_first_batch(self, _mock_isfile, tmp_path):
        test_csv = _write_test_csv(STANDARD_CSV_ROWS)
        try:
            scanner = _make_scanner_with_mocks(test_csv)
            options = ScanOptions()
            result = scanner.scan_batch(str(tmp_path), options, batch_size=2, batch_index=0)

            assert result is not None
            assert result.total_files == 5
            assert len(result.files) == 2
            assert result.files[0].path.name == 'file1.txt'
            assert result.files[1].path.name == 'file2.txt'
        finally:
            os.remove(test_csv)

    @patch('os.path.isfile', return_value=True)
    def test_scan_batch_second_batch(self, _mock_isfile, tmp_path):
        test_csv = _write_test_csv(STANDARD_CSV_ROWS)
        try:
            scanner = _make_scanner_with_mocks(test_csv)
            options = ScanOptions()
            result = scanner.scan_batch(str(tmp_path), options, batch_size=2, batch_index=1)

            assert result is not None
            assert result.total_files == 5
            assert len(result.files) == 2
            assert result.files[0].path.name == 'file3.txt'
            assert result.files[1].path.name == 'file4.txt'
        finally:
            os.remove(test_csv)

    @patch('os.path.isfile', return_value=True)
    def test_scan_batch_last_batch(self, _mock_isfile, tmp_path):
        test_csv = _write_test_csv(STANDARD_CSV_ROWS)
        try:
            scanner = _make_scanner_with_mocks(test_csv)
            options = ScanOptions()
            result = scanner.scan_batch(str(tmp_path), options, batch_size=2, batch_index=2)

            assert result is not None
            assert result.total_files == 5
            assert len(result.files) == 1
            assert result.files[0].path.name == 'file5.txt'
        finally:
            os.remove(test_csv)

    @patch('os.path.isfile', return_value=True)
    def test_get_total_files_count(self, _mock_isfile, tmp_path):
        rows = [
            ['文件名', '大小', '修改时间', '创建时间', '属性', '路径'],
            ['C:\\test\\file1.txt', '1024', '2024-01-01 10:00:00', '2024-01-01 10:00:00', '32', 'C:\\test'],
            ['C:\\test\\file2.txt', '2048', '2024-01-01 11:00:00', '2024-01-01 11:00:00', '32', 'C:\\test'],
            ['C:\\test\\file3.txt', '4096', '2024-01-01 12:00:00', '2024-01-01 12:00:00', '32', 'C:\\test'],
            ['C:\\test\\dir1\\', '0', '2024-01-01 10:00:00', '2024-01-01 10:00:00', '16', 'C:\\test'],
            ['C:\\test\\file4.txt', '0', '2024-01-01 13:00:00', '2024-01-01 13:00:00', '32', 'C:\\test'],
        ]
        test_csv = _write_test_csv(rows)
        try:
            scanner = _make_scanner_with_mocks(test_csv)
            options = ScanOptions()
            total_files = scanner.get_total_files_count(str(tmp_path), options)
            assert total_files == 3
        finally:
            os.remove(test_csv)

    @patch('os.path.isfile', return_value=True)
    def test_get_batch_info(self, _mock_isfile, tmp_path):
        test_csv = _write_test_csv(STANDARD_CSV_ROWS)
        try:
            scanner = _make_scanner_with_mocks(test_csv)
            options = ScanOptions()
            batch_info = scanner.get_batch_info(str(tmp_path), options, batch_size=2)

            assert batch_info['total_files'] == 5
            assert batch_info['batch_size'] == 2
            assert batch_info['total_batches'] == 3
            assert batch_info['last_batch_size'] == 1
        finally:
            os.remove(test_csv)

    def test_clear_cache(self):
        scanner = StreamingScanner()
        scanner._batch_cache = {'test': [FileInfo(
            path=Path('test.txt'),
            size=1024,
            modified_time=datetime.now()
        )]}
        scanner._total_files_cache = 100

        scanner.clear_cache()

        assert len(scanner._batch_cache) == 0
        assert scanner._total_files_cache is None


class TestStreamingScannerEdgeCases:
    """StreamingScanner边界情况测试"""

    @patch('os.path.isfile', return_value=True)
    def test_scan_batch_empty_csv(self, _mock_isfile, tmp_path):
        rows = [['文件名', '大小', '修改时间', '创建时间', '属性', '路径']]
        test_csv = _write_test_csv(rows)
        try:
            scanner = _make_scanner_with_mocks(test_csv)
            options = ScanOptions()
            result = scanner.scan_batch(str(tmp_path), options, batch_size=2, batch_index=0)

            assert result is not None
            assert result.total_files == 0
            assert len(result.files) == 0
        finally:
            os.remove(test_csv)

    @patch('os.path.isfile', return_value=True)
    def test_scan_batch_batch_index_out_of_range(self, _mock_isfile, tmp_path):
        rows = [
            ['文件名', '大小', '修改时间', '创建时间', '属性', '路径'],
            ['C:\\test\\file1.txt', '1024', '2024-01-01 10:00:00', '2024-01-01 10:00:00', '32', 'C:\\test'],
            ['C:\\test\\file2.txt', '2048', '2024-01-01 11:00:00', '2024-01-01 11:00:00', '32', 'C:\\test'],
        ]
        test_csv = _write_test_csv(rows)
        try:
            scanner = _make_scanner_with_mocks(test_csv)
            options = ScanOptions()
            result = scanner.scan_batch(str(tmp_path), options, batch_size=2, batch_index=5)

            assert result is not None
            assert result.total_files == 2
            assert len(result.files) == 0
        finally:
            os.remove(test_csv)

    @patch('os.path.isfile', return_value=True)
    def test_scan_batch_single_batch_all_files(self, _mock_isfile, tmp_path):
        """批次大小大于文件数时，一次取完"""
        test_csv = _write_test_csv(STANDARD_CSV_ROWS)
        try:
            scanner = _make_scanner_with_mocks(test_csv)
            options = ScanOptions()
            result = scanner.scan_batch(str(tmp_path), options, batch_size=10, batch_index=0)

            assert result is not None
            assert result.total_files == 5
            assert len(result.files) == 5
        finally:
            os.remove(test_csv)

    def test_scan_batch_invalid_target(self):
        scanner = StreamingScanner("dummy.exe")
        options = ScanOptions()
        with pytest.raises(ValueError, match="无效的扫描目标"):
            scanner.scan_batch("Z:\\nonexistent\\path", options)

    @patch('os.path.isfile', return_value=False)
    def test_scan_batch_missing_wiztree(self, _mock_isfile, tmp_path):
        scanner = StreamingScanner("nonexistent.exe")
        options = ScanOptions()
        with pytest.raises(FileNotFoundError, match="WizTree可执行文件不存在"):
            scanner.scan_batch(str(tmp_path), options)

    @patch('os.path.isfile', return_value=True)
    def test_scan_batch_result_builds_scan_result(self, _mock_isfile, tmp_path):
        """验证 ScanResult 字段正确"""
        test_csv = _write_test_csv(STANDARD_CSV_ROWS)
        try:
            scanner = _make_scanner_with_mocks(test_csv)
            options = ScanOptions()
            result = scanner.scan_batch(str(tmp_path), options, batch_size=3, batch_index=0)

            assert isinstance(result, ScanResult)
            assert result.target_path == Path(str(tmp_path))
            assert result.total_files == 5
            assert result.duration_seconds >= 0
            assert result.scan_options is not None
        finally:
            os.remove(test_csv)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
