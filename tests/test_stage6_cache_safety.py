"""
Stage 6: 扫描缓存安全测试

测试BatchCache和BatchCacheManager的线程安全机制，确保多线程环境下的缓存安全。
"""

import threading
import time
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.scanner.cache import BatchCache, BatchCacheManager
from src.scanner import WizTreeScanner
from src.scanner.options import ScanOptions
from src.models.file_info import FileInfo
from src.models.scan_result import ScanResult


def _make_file_info(path: str = "test.txt", size: int = 1024) -> FileInfo:
    """辅助：构造 FileInfo"""
    return FileInfo(
        path=Path(path),
        size=size,
        modified_time=datetime.now(),
        created_time=None,
        is_directory=False,
        extension=".txt",
        depth=1,
        parent_path=Path("C:\\"),
    )


def _make_file_list(n_files: int = 3) -> list:
    """辅助：构造 FileInfo 列表"""
    return [_make_file_info(f"file_{i}.txt", 1024 * (i + 1)) for i in range(n_files)]


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


class TestBatchCacheThreadSafety:
    """BatchCache 线程安全测试"""

    def test_concurrent_get_put(self):
        """测试并发get和put操作"""
        cache = BatchCache(max_size=100)
        errors = []
        iterations = 100

        def worker(thread_id):
            try:
                for i in range(iterations):
                    key = f"key_{thread_id}_{i}"
                    data = _make_file_list(3)
                    
                    # Put操作
                    cache.put(key, data)
                    
                    # Get操作
                    retrieved = cache.get(key)
                    if retrieved is None:
                        errors.append(f"Thread {thread_id}: Failed to get key {key}")
                    
                    # Contains操作
                    if not cache.contains(key):
                        errors.append(f"Thread {thread_id}: Key {key} not found in contains")
            except Exception as e:
                errors.append(f"Thread {thread_id}: Exception {e}")

        # 创建多个线程
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证没有错误
        assert len(errors) == 0, f"Errors occurred: {errors}"

    def test_concurrent_resize(self):
        """测试并发resize操作"""
        cache = BatchCache(max_size=50)
        errors = []

        def writer(thread_id):
            try:
                for i in range(50):
                    key = f"key_{thread_id}_{i}"
                    cache.put(key, _make_file_list(2))
            except Exception as e:
                errors.append(f"Writer {thread_id}: Exception {e}")

        def resizer():
            try:
                for size in [10, 20, 30, 40, 50]:
                    cache.resize(size)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Resizer: Exception {e}")

        # 创建写入线程和调整大小线程
        threads = []
        for i in range(3):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
            t.start()
        
        resize_thread = threading.Thread(target=resizer)
        threads.append(resize_thread)
        resize_thread.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证没有错误
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # 验证缓存大小不超过当前max_size
        assert cache.size() <= cache.max_size

    def test_concurrent_cleanup_expired(self):
        """测试并发清理过期条目"""
        cache = BatchCache(max_size=100, ttl=0.1)  # 100ms TTL
        errors = []
        results = []

        def writer(thread_id):
            try:
                for i in range(20):
                    key = f"key_{thread_id}_{i}"
                    cache.put(key, _make_file_list(2))
                    time.sleep(0.05)  # 等待部分过期
            except Exception as e:
                errors.append(f"Writer {thread_id}: Exception {e}")

        def cleaner():
            try:
                for _ in range(10):
                    cleaned = cache.cleanup_expired()
                    results.append(cleaned)
                    time.sleep(0.05)
            except Exception as e:
                errors.append(f"Cleaner: Exception {e}")

        # 创建写入线程和清理线程
        threads = []
        for i in range(3):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
            t.start()
        
        clean_thread = threading.Thread(target=cleaner)
        threads.append(clean_thread)
        clean_thread.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证没有错误
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # 验证清理了过期条目
        assert len(results) > 0


class TestBatchCacheManagerThreadSafety:
    """BatchCacheManager 线程安全测试"""

    def test_concurrent_get_cache(self):
        """测试并发获取缓存实例"""
        manager = BatchCacheManager()
        errors = []
        caches = []

        def worker(thread_id):
            try:
                for i in range(10):
                    target = f"C:\\target_{thread_id}_{i}"
                    cache = manager.get_cache(target)
                    caches.append(cache)
                    
                    # 验证缓存实例可用
                    cache.put(f"key_{i}", _make_file_list(2))
                    assert cache.get(f"key_{i}") is not None
            except Exception as e:
                errors.append(f"Thread {thread_id}: Exception {e}")

        # 创建多个线程
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证没有错误
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # 验证缓存实例数量
        assert len(manager._caches) == 50  # 5 threads * 10 targets each

    def test_concurrent_clear_all(self):
        """测试并发清空所有缓存"""
        manager = BatchCacheManager()
        errors = []

        def worker(thread_id):
            try:
                cache = manager.get_cache(f"C:\\target_{thread_id}")
                for i in range(10):
                    cache.put(f"key_{i}", _make_file_list(2))
            except Exception as e:
                errors.append(f"Worker {thread_id}: Exception {e}")

        def clearer():
            try:
                time.sleep(0.1)
                manager.clear_all()
            except Exception as e:
                errors.append(f"Clearer: Exception {e}")

        # 创建写入线程和清理线程
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        clear_thread = threading.Thread(target=clearer)
        threads.append(clear_thread)
        clear_thread.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证没有错误
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # 验证缓存已清空
        assert len(manager._caches) == 0


class TestWizTreeScannerCacheThreadSafety:
    """WizTreeScanner 缓存线程安全测试"""

    def test_concurrent_scan_with_cache(self):
        """测试并发带缓存的扫描"""
        scanner = WizTreeScanner()
        errors = []
        results = []

        def worker(thread_id):
            try:
                for i in range(5):
                    target = f"C:\\target_{thread_id}_{i}"
                    options = ScanOptions()
                    
                    # 模拟扫描结果
                    mock_result = _make_scan_result(target, 3)
                    
                    with patch.object(scanner, "scan", return_value=mock_result):
                        result = scanner.scan_with_cache(target, options)
                        results.append(result)
                        
                        # 第二次调用应该命中缓存
                        result2 = scanner.scan_with_cache(target, options)
                        assert result2.total_files == result.total_files
            except Exception as e:
                errors.append(f"Thread {thread_id}: Exception {e}")

        # 创建多个线程
        threads = []
        for i in range(3):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证没有错误
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # 验证结果数量
        assert len(results) == 15  # 3 threads * 5 targets each

    def test_concurrent_clear_cache(self):
        """测试并发清除缓存"""
        scanner = WizTreeScanner()
        errors = []

        def worker(thread_id):
            try:
                for i in range(5):
                    target = f"C:\\target_{thread_id}_{i}"
                    options = ScanOptions()
                    
                    # 模拟扫描结果
                    mock_result = _make_scan_result(target, 3)
                    
                    with patch.object(scanner, "scan", return_value=mock_result):
                        scanner.scan_with_cache(target, options)
            except Exception as e:
                errors.append(f"Worker {thread_id}: Exception {e}")

        def clearer():
            try:
                time.sleep(0.1)
                scanner.clear_cache()
            except Exception as e:
                errors.append(f"Clearer: Exception {e}")

        # 创建写入线程和清理线程
        threads = []
        for i in range(3):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        clear_thread = threading.Thread(target=clearer)
        threads.append(clear_thread)
        clear_thread.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证没有错误
        assert len(errors) == 0, f"Errors occurred: {errors}"


class TestCacheLockImplementation:
    """缓存锁实现验证测试"""

    def test_batch_cache_has_lock(self):
        """测试BatchCache有锁属性"""
        cache = BatchCache()
        assert hasattr(cache, '_lock')
        assert isinstance(cache._lock, type(threading.Lock()))

    def test_batch_cache_manager_has_lock(self):
        """测试BatchCacheManager有锁属性"""
        manager = BatchCacheManager()
        assert hasattr(manager, '_lock')
        assert isinstance(manager._lock, type(threading.Lock()))

    def test_wiztree_scanner_has_cache_lock(self):
        """测试WizTreeScanner有缓存锁属性"""
        scanner = WizTreeScanner()
        assert hasattr(scanner, '_cache_lock')
        assert isinstance(scanner._cache_lock, type(threading.Lock()))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
