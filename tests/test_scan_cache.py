"""Stage 3: 扫描缓存测试"""
import json
import os
import time
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.scanner import WizTreeScanner
from src.scanner.options import ScanOptions
from src.models import FileInfo, ScanResult


def _has_tkinter():
    try:
        import tkinter
        return True
    except ImportError:
        return False


def _make_scan_result(target="C:\\", n_files=3):
    """辅助：构造 ScanResult"""
    files = []
    for i in range(n_files):
        files.append(FileInfo(
            path=Path(f"{target}file_{i}.txt"),
            size=1024 * (i + 1),
            modified_time=datetime(2025, 1, 1, 12, 0, i),
            created_time=None,
            is_directory=False,
            extension=".txt",
            depth=1,
            parent_path=Path(target),
        ))
    now = datetime.now()
    return ScanResult(
        target_path=Path(target),
        files=files,
        scan_time=now,
        duration_seconds=1.5,
        total_files=n_files,
        total_directories=0,
        total_size=sum(f.size for f in files),
        scan_options=ScanOptions().to_dict(),
        errors=[],
    )


class TestScanCacheKey:
    """缓存键生成测试"""

    def test_same_path_same_options_same_key(self):
        scanner = WizTreeScanner()
        opts = ScanOptions()
        k1 = scanner._get_cache_key("C:\\", opts)
        k2 = scanner._get_cache_key("C:\\", opts)
        assert k1 == k2

    def test_different_path_different_key(self):
        scanner = WizTreeScanner()
        opts = ScanOptions()
        k1 = scanner._get_cache_key("C:\\", opts)
        k2 = scanner._get_cache_key("D:\\", opts)
        assert k1 != k2

    def test_different_options_different_key(self):
        scanner = WizTreeScanner()
        opts1 = ScanOptions()
        opts2 = ScanOptions(min_size=1024)
        k1 = scanner._get_cache_key("C:\\", opts1)
        k2 = scanner._get_cache_key("C:\\", opts2)
        assert k1 != k2

    def test_key_is_sha256_hex(self):
        scanner = WizTreeScanner()
        key = scanner._get_cache_key("C:\\", ScanOptions())
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestScanCacheSerialization:
    """ScanResult 序列化/反序列化往返测试"""

    def test_roundtrip(self):
        original = _make_scan_result("C:\\test", n_files=5)
        serialized = WizTreeScanner._serialize_scan_result(original)
        restored = WizTreeScanner._deserialize_scan_result(serialized)

        assert restored.target_path == original.target_path
        assert restored.total_files == original.total_files
        assert restored.total_size == original.total_size
        assert restored.duration_seconds == original.duration_seconds
        assert len(restored.files) == len(original.files)
        for orig_f, rest_f in zip(original.files, restored.files):
            assert str(rest_f.path) == str(orig_f.path)
            assert rest_f.size == orig_f.size
            assert rest_f.extension == orig_f.extension

    def test_serialized_is_json_compatible(self):
        result = _make_scan_result()
        data = WizTreeScanner._serialize_scan_result(result)
        json_str = json.dumps(data, ensure_ascii=False)
        restored_data = json.loads(json_str)
        restored = WizTreeScanner._deserialize_scan_result(restored_data)
        assert restored.total_files == result.total_files


class TestScanCacheSaveLoad:
    """缓存文件读写测试"""

    def test_save_and_load_cache(self, tmp_path):
        scanner = WizTreeScanner()
        cache_file = str(tmp_path / "scan_cache.json")
        scanner._CACHE_FILE = cache_file

        result = _make_scan_result()
        key = scanner._get_cache_key("C:\\", ScanOptions())
        scanner._save_cache(key, result)

        assert os.path.exists(cache_file)
        loaded = scanner._load_cache(key)
        assert loaded is not None
        assert loaded.total_files == result.total_files
        assert loaded.total_size == result.total_size

    def test_load_nonexistent_key_returns_none(self, tmp_path):
        scanner = WizTreeScanner()
        scanner._CACHE_FILE = str(tmp_path / "scan_cache.json")
        assert scanner._load_cache("nonexistent_key") is None

    def test_load_missing_file_returns_none(self, tmp_path):
        scanner = WizTreeScanner()
        scanner._CACHE_FILE = str(tmp_path / "does_not_exist.json")
        assert scanner._load_cache("any_key") is None

    def test_expired_cache_returns_none(self, tmp_path):
        scanner = WizTreeScanner()
        cache_file = str(tmp_path / "scan_cache.json")
        scanner._CACHE_FILE = cache_file

        result = _make_scan_result()
        key = scanner._get_cache_key("C:\\", ScanOptions())
        scanner._save_cache(key, result)

        # 伪造 cached_at 为 2 小时前
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data[key]["cached_at"] = (datetime.now() - timedelta(hours=2)).isoformat()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        assert scanner._load_cache(key) is None

    def test_fresh_cache_returns_result(self, tmp_path):
        scanner = WizTreeScanner()
        cache_file = str(tmp_path / "scan_cache.json")
        scanner._CACHE_FILE = cache_file

        result = _make_scan_result()
        key = scanner._get_cache_key("C:\\", ScanOptions())
        scanner._save_cache(key, result)

        loaded = scanner._load_cache(key)
        assert loaded is not None

    def test_corrupted_json_returns_none(self, tmp_path):
        scanner = WizTreeScanner()
        cache_file = str(tmp_path / "scan_cache.json")
        scanner._CACHE_FILE = cache_file
        with open(cache_file, "w") as f:
            f.write("{invalid json!!!")

        assert scanner._load_cache("any_key") is None


class TestClearCache:
    """clear_cache 测试"""

    def test_clear_cache_removes_file(self, tmp_path):
        scanner = WizTreeScanner()
        scanner._CACHE_FILE = str(tmp_path / "cache.json")
        scanner._save_cache("k1", _make_scan_result())
        assert os.path.exists(scanner._CACHE_FILE)
        assert scanner.clear_cache()
        assert not os.path.exists(scanner._CACHE_FILE)

    def test_clear_cache_nonexistent_file(self, tmp_path):
        scanner = WizTreeScanner()
        scanner._CACHE_FILE = str(tmp_path / "nope.json")
        assert scanner.clear_cache()


class TestScanWithCache:
    """scan_with_cache 集成测试"""

    def test_first_call_runs_scan(self, tmp_path):
        scanner = WizTreeScanner()
        scanner._CACHE_FILE = str(tmp_path / "cache.json")
        mock_result = _make_scan_result()

        with patch.object(scanner, "scan", return_value=mock_result) as mock_scan:
            result = scanner.scan_with_cache("C:\\", ScanOptions())
            mock_scan.assert_called_once()
            assert result.total_files == mock_result.total_files

    def test_second_call_returns_cache(self, tmp_path):
        scanner = WizTreeScanner()
        scanner._CACHE_FILE = str(tmp_path / "cache.json")
        mock_result = _make_scan_result()

        with patch.object(scanner, "scan", return_value=mock_result) as mock_scan:
            scanner.scan_with_cache("C:\\", ScanOptions())
            scanner.scan_with_cache("C:\\", ScanOptions())
            # scan 只应被调用一次
            assert mock_scan.call_count == 1

    def test_different_target_runs_again(self, tmp_path):
        scanner = WizTreeScanner()
        scanner._CACHE_FILE = str(tmp_path / "cache.json")
        mock_result = _make_scan_result()

        with patch.object(scanner, "scan", return_value=mock_result) as mock_scan:
            scanner.scan_with_cache("C:\\", ScanOptions())
            scanner.scan_with_cache("D:\\", ScanOptions())
            assert mock_scan.call_count == 2

    def test_cache_hit_fires_progress_callback(self, tmp_path):
        callback = MagicMock()
        scanner = WizTreeScanner(progress_callback=callback)
        scanner._CACHE_FILE = str(tmp_path / "cache.json")
        mock_result = _make_scan_result()

        with patch.object(scanner, "scan", return_value=mock_result):
            scanner.scan_with_cache("C:\\", ScanOptions())

        callback.reset_mock()
        # 第二次调用应命中缓存
        with patch.object(scanner, "scan") as mock_scan:
            scanner.scan_with_cache("C:\\", ScanOptions())
            mock_scan.assert_not_called()
        callback.assert_called()


class TestMainWindowProgressCallback:
    """MainWindow 进度回调测试（纯逻辑，不创建 UI）"""

    @pytest.mark.skipif(
        os.environ.get("CI") == "true" or not _has_tkinter(),
        reason="tkinter not available in this environment",
    )
    def test_apply_progress_with_files(self):
        from src.ui.main_window import MainWindow
        mw = MainWindow.__new__(MainWindow)
        mock_status = MagicMock()
        mw.update_status = mock_status
        mw._apply_progress("Scanning...", 500)
        mock_status.assert_called_once_with("Scanning... (500 files)", "yellow")

    @pytest.mark.skipif(
        os.environ.get("CI") == "true" or not _has_tkinter(),
        reason="tkinter not available in this environment",
    )
    def test_apply_progress_no_files(self):
        from src.ui.main_window import MainWindow
        mw = MainWindow.__new__(MainWindow)
        mock_status = MagicMock()
        mw.update_status = mock_status
        mw._apply_progress("Starting...", 0)
        mock_status.assert_called_once_with("Starting...", "yellow")
