"""
Stage 4: 批次缓存和LRU策略测试

测试BatchCache类的LRU缓存策略、批次缓存、内存优化等功能。
"""

import time
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.scanner.cache import BatchCache, BatchCacheManager
from src.models.file_info import FileInfo


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


class TestBatchCacheBasic:
    """BatchCache 基本功能测试"""

    def test_cache_initialization(self):
        """测试缓存初始化"""
        cache = BatchCache(max_size=5, ttl=60)
        assert cache.max_size == 5
        assert cache.ttl == 60
        assert cache.size() == 0

    def test_put_and_get(self):
        """测试存储和获取"""
        cache = BatchCache()
        data = _make_file_list(3)
        
        cache.put("key1", data)
        retrieved = cache.get("key1")
        
        assert retrieved is not None
        assert len(retrieved) == 3
        assert retrieved[0].path == Path("file_0.txt")

    def test_get_nonexistent_key(self):
        """测试获取不存在的键"""
        cache = BatchCache()
        assert cache.get("nonexistent") is None

    def test_contains(self):
        """测试包含检查"""
        cache = BatchCache()
        data = _make_file_list(2)
        
        cache.put("key1", data)
        assert cache.contains("key1") is True
        assert cache.contains("key2") is False

    def test_size(self):
        """测试大小计算"""
        cache = BatchCache()
        assert cache.size() == 0
        
        cache.put("key1", _make_file_list())
        assert cache.size() == 1
        
        cache.put("key2", _make_file_list())
        assert cache.size() == 2

    def test_clear(self):
        """测试清空缓存"""
        cache = BatchCache()
        cache.put("key1", _make_file_list())
        cache.put("key2", _make_file_list())
        
        assert cache.size() == 2
        cache.clear()
        assert cache.size() == 0
        assert cache.get("key1") is None


class TestBatchCacheLRU:
    """BatchCache LRU策略测试"""

    def test_lru_eviction(self):
        """测试LRU淘汰策略"""
        cache = BatchCache(max_size=2)
        
        # 添加两个条目
        cache.put("key1", _make_file_list())
        cache.put("key2", _make_file_list())
        assert cache.size() == 2
        
        # 添加第三个条目，应该淘汰最久未使用的
        cache.put("key3", _make_file_list())
        assert cache.size() == 2
        
        # key1应该被淘汰
        assert cache.get("key1") is None
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None

    def test_lru_access_updates_position(self):
        """测试LRU访问更新位置"""
        cache = BatchCache(max_size=2)
        
        # 添加两个条目
        cache.put("key1", _make_file_list())
        cache.put("key2", _make_file_list())
        
        # 访问key1，使其成为最近使用
        cache.get("key1")
        
        # 添加第三个条目，应该淘汰key2（最久未使用）
        cache.put("key3", _make_file_list())
        
        # key1应该仍然存在，key2应该被淘汰
        assert cache.get("key1") is not None
        assert cache.get("key2") is None
        assert cache.get("key3") is not None

    def test_lru_with_multiple_accesses(self):
        """测试多次访问的LRU行为"""
        cache = BatchCache(max_size=3)
        
        # 添加三个条目
        cache.put("key1", _make_file_list())
        cache.put("key2", _make_file_list())
        cache.put("key3", _make_file_list())
        
        # 按顺序访问：key1, key2, key3
        cache.get("key1")
        cache.get("key2")
        cache.get("key3")
        
        # 添加第四个条目，应该淘汰key1（最久未访问）
        cache.put("key4", _make_file_list())
        
        assert cache.get("key1") is None
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None
        assert cache.get("key4") is not None

    def test_update_existing_key(self):
        """测试更新已存在的键"""
        cache = BatchCache(max_size=2)
        
        # 添加初始数据
        data1 = _make_file_list(2)
        cache.put("key1", data1)
        
        # 更新数据
        data2 = _make_file_list(5)
        cache.put("key1", data2)
        
        # 应该返回新数据
        retrieved = cache.get("key1")
        assert retrieved is not None
        assert len(retrieved) == 5
        
        # 大小应该仍然是1
        assert cache.size() == 1


class TestBatchCacheTTL:
    """BatchCache TTL过期测试"""

    def test_expired_entry_not_returned(self):
        """测试过期条目不返回"""
        cache = BatchCache(ttl=1)  # 1秒过期
        
        cache.put("key1", _make_file_list())
        assert cache.get("key1") is not None
        
        # 等待过期
        time.sleep(1.1)
        
        assert cache.get("key1") is None
        assert cache.size() == 0

    def test_cleanup_expired(self):
        """测试清理过期条目"""
        cache = BatchCache(ttl=1)
        
        cache.put("key1", _make_file_list())
        cache.put("key2", _make_file_list())
        
        # 等待过期
        time.sleep(1.1)
        
        cleaned = cache.cleanup_expired()
        assert cleaned == 2
        assert cache.size() == 0

    def test_contains_expired(self):
        """测试检查过期条目"""
        cache = BatchCache(ttl=1)
        
        cache.put("key1", _make_file_list())
        assert cache.contains("key1") is True
        
        # 等待过期
        time.sleep(1.1)
        
        assert cache.contains("key1") is False


class TestBatchCacheStats:
    """BatchCache 统计信息测试"""

    def test_get_stats_empty_cache(self):
        """测试空缓存的统计信息"""
        cache = BatchCache(max_size=10, ttl=60)
        stats = cache.get_stats()
        
        assert stats['total_entries'] == 0
        assert stats['valid_entries'] == 0
        assert stats['expired_entries'] == 0
        assert stats['max_size'] == 10
        assert stats['ttl_seconds'] == 60
        assert stats['usage_percent'] == 0.0

    def test_get_stats_with_entries(self):
        """测试有条目的统计信息"""
        cache = BatchCache(max_size=5, ttl=60)
        
        cache.put("key1", _make_file_list())
        cache.put("key2", _make_file_list())
        
        stats = cache.get_stats()
        
        assert stats['total_entries'] == 2
        assert stats['valid_entries'] == 2
        assert stats['expired_entries'] == 0
        assert stats['usage_percent'] == 40.0

    def test_get_stats_with_expired_entries(self):
        """测试包含过期条目的统计信息"""
        cache = BatchCache(max_size=5, ttl=1)
        
        cache.put("key1", _make_file_list())
        cache.put("key2", _make_file_list())
        
        # 等待过期
        time.sleep(1.1)
        
        stats = cache.get_stats()
        
        assert stats['total_entries'] == 2
        assert stats['valid_entries'] == 0
        assert stats['expired_entries'] == 2


class TestBatchCacheResize:
    """BatchCache 大小调整测试"""

    def test_resize_to_smaller(self):
        """测试调整为更小的大小"""
        cache = BatchCache(max_size=5)
        
        # 添加5个条目
        for i in range(5):
            cache.put(f"key{i}", _make_file_list())
        
        assert cache.size() == 5
        
        # 调整为更小的大小
        cache.resize(3)
        assert cache.max_size == 3
        assert cache.size() == 3

    def test_resize_to_larger(self):
        """测试调整为更大的大小"""
        cache = BatchCache(max_size=2)
        
        cache.put("key1", _make_file_list())
        cache.put("key2", _make_file_list())
        
        # 调整为更大的大小
        cache.resize(5)
        assert cache.max_size == 5
        assert cache.size() == 2

    def test_resize_invalid_size(self):
        """测试调整为无效大小"""
        cache = BatchCache()
        
        with pytest.raises(ValueError):
            cache.resize(-1)


class TestBatchCacheManager:
    """BatchCacheManager 测试"""

    def test_manager_initialization(self):
        """测试管理器初始化"""
        manager = BatchCacheManager(default_max_size=5, default_ttl=60)
        assert manager.default_max_size == 5
        assert manager.default_ttl == 60

    def test_get_cache_creates_new(self):
        """测试获取缓存创建新实例"""
        manager = BatchCacheManager()
        
        cache1 = manager.get_cache("C:\\")
        cache2 = manager.get_cache("D:\\")
        
        assert cache1 is not cache2
        assert len(manager._caches) == 2

    def test_get_cache_returns_same_instance(self):
        """测试获取缓存返回相同实例"""
        manager = BatchCacheManager()
        
        cache1 = manager.get_cache("C:\\")
        cache2 = manager.get_cache("C:\\")
        
        assert cache1 is cache2

    def test_clear_all(self):
        """测试清空所有缓存"""
        manager = BatchCacheManager()
        
        cache1 = manager.get_cache("C:\\")
        cache2 = manager.get_cache("D:\\")
        
        cache1.put("key1", _make_file_list())
        cache2.put("key2", _make_file_list())
        
        manager.clear_all()
        
        assert len(manager._caches) == 0

    def test_cleanup_all_expired(self):
        """测试清理所有过期条目"""
        manager = BatchCacheManager(default_ttl=1)
        
        cache1 = manager.get_cache("C:\\")
        cache2 = manager.get_cache("D:\\")
        
        cache1.put("key1", _make_file_list())
        cache2.put("key2", _make_file_list())
        
        # 等待过期
        time.sleep(1.1)
        
        cleaned = manager.cleanup_all_expired()
        assert cleaned == 2

    def test_get_stats(self):
        """测试获取统计信息"""
        manager = BatchCacheManager()
        
        cache1 = manager.get_cache("C:\\")
        cache2 = manager.get_cache("D:\\")
        
        cache1.put("key1", _make_file_list())
        cache2.put("key2", _make_file_list())
        
        stats = manager.get_stats()
        
        assert stats['total_caches'] == 2
        assert 'C:\\' in stats['caches']
        assert 'D:\\' in stats['caches']


class TestBatchCacheIntegration:
    """BatchCache 集成测试"""

    def test_cache_with_real_file_info(self):
        """测试使用真实FileInfo的缓存"""
        cache = BatchCache(max_size=3)
        
        # 创建不同大小的文件列表
        small_files = [_make_file_info("small.txt", 100)]
        medium_files = [_make_file_info("medium.txt", 1000)]
        large_files = [_make_file_info("large.txt", 10000)]
        
        # 缓存这些列表
        cache.put("small", small_files)
        cache.put("medium", medium_files)
        cache.put("large", large_files)
        
        # 验证可以正确获取
        assert len(cache.get("small")) == 1
        assert cache.get("small")[0].size == 100
        
        assert len(cache.get("medium")) == 1
        assert cache.get("medium")[0].size == 1000
        
        assert len(cache.get("large")) == 1
        assert cache.get("large")[0].size == 10000

    def test_cache_performance(self):
        """测试缓存性能"""
        cache = BatchCache(max_size=100)
        
        # 添加100个条目
        for i in range(100):
            cache.put(f"key{i}", _make_file_list(10))
        
        assert cache.size() == 100
        
        # 随机访问一些条目
        for i in range(0, 100, 10):
            assert cache.get(f"key{i}") is not None
        
        # 添加新条目，应该淘汰最久未使用的
        for i in range(100, 110):
            cache.put(f"key{i}", _make_file_list(5))
        
        assert cache.size() == 100
        
        # 最近访问的条目应该仍然存在
        for i in range(90, 100):
            assert cache.get(f"key{i}") is not None

    def test_batch_cache_with_scanner_pattern(self):
        """测试模拟扫描器使用模式的缓存"""
        cache = BatchCache(max_size=5)
        
        # 模拟扫描批次
        for batch_idx in range(10):
            batch_key = f"batch_{batch_idx}"
            batch_data = _make_file_info(f"file_{batch_idx}.txt", 1024 * batch_idx)
            
            # 检查缓存
            cached = cache.get(batch_key)
            if cached is None:
                # 模拟扫描
                scanned_data = [batch_data]
                cache.put(batch_key, scanned_data)
            else:
                # 使用缓存
                assert len(cached) == 1
        
        # 由于max_size=5，应该只有最后5个批次在缓存中
        assert cache.size() == 5
        
        # 最后5个批次应该存在
        for i in range(5, 10):
            assert cache.contains(f"batch_{i}") is True
        
        # 前5个批次应该被淘汰
        for i in range(5):
            assert cache.contains(f"batch_{i}") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])