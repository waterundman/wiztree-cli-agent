"""
批次缓存模块 - 实现LRU缓存策略优化内存使用

本模块提供BatchCache类，用于缓存扫描批次数据，采用LRU（最近最少使用）策略
自动管理缓存大小，只保留当前批次和相邻批次，避免内存无限增长。

Stage 6: 添加线程安全机制，确保多线程环境下的缓存安全。
"""

import logging
import threading
from collections import OrderedDict
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

from ..models.file_info import FileInfo

logger = logging.getLogger(__name__)


class BatchCache:
    """
    批次LRU缓存
    
    使用OrderedDict实现LRU缓存策略，限制缓存大小，自动清理旧批次。
    只缓存当前批次和相邻批次，优化内存使用。
    
    Stage 6: 添加线程安全机制，使用threading.Lock保护所有缓存操作。
    
    Attributes:
        max_size: 最大缓存条目数
        ttl: 缓存条目过期时间（秒）
    """
    
    def __init__(self, max_size: int = 10, ttl: int = 300):
        """
        初始化批次缓存
        
        Args:
            max_size: 最大缓存条目数，默认10个批次
            ttl: 缓存条目过期时间（秒），默认300秒（5分钟）
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, Tuple[datetime, List[FileInfo]]] = OrderedDict()
        self._access_times: Dict[str, datetime] = {}
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[List[FileInfo]]:
        """
        获取缓存的批次数据
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[List[FileInfo]]: 缓存的文件信息列表，如果不存在或已过期则返回None
        """
        with self._lock:
            if key not in self._cache:
                return None
            
            # 检查是否过期
            cached_at, data = self._cache[key]
            if datetime.now() - cached_at > timedelta(seconds=self.ttl):
                self._remove(key)
                return None
            
            # 更新访问时间（LRU核心）
            self._cache.move_to_end(key)
            self._access_times[key] = datetime.now()
            
            return data
    
    def put(self, key: str, data: List[FileInfo]) -> None:
        """
        存储批次数据到缓存
        
        Args:
            key: 缓存键
            data: 文件信息列表
        """
        with self._lock:
            # 如果已存在，先删除
            if key in self._cache:
                self._remove(key)
            
            # 检查缓存大小，如果已满则删除最久未使用的
            while len(self._cache) >= self.max_size:
                self._evict_oldest()
            
            # 存储新条目
            now = datetime.now()
            self._cache[key] = (now, data)
            self._access_times[key] = now
            
            logger.debug("Cached batch with key: %s", key[:16] + "...")
    
    def _remove(self, key: str) -> None:
        """删除指定缓存条目"""
        if key in self._cache:
            del self._cache[key]
            del self._access_times[key]
    
    def _evict_oldest(self) -> None:
        """淘汰最久未使用的缓存条目"""
        if not self._cache:
            return
        
        # OrderedDict的第一个元素是最久未使用的
        oldest_key = next(iter(self._cache))
        self._remove(oldest_key)
        logger.debug("Evicted oldest cache entry: %s", oldest_key[:16] + "...")
    
    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
            logger.debug("Cache cleared")
    
    def size(self) -> int:
        """获取当前缓存条目数"""
        with self._lock:
            return len(self._cache)
    
    def contains(self, key: str) -> bool:
        """检查缓存是否包含指定键（且未过期）"""
        with self._lock:
            if key not in self._cache:
                return False
            
            # 检查是否过期
            cached_at, _ = self._cache[key]
            if datetime.now() - cached_at > timedelta(seconds=self.ttl):
                self._remove(key)
                return False
            
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            Dict[str, Any]: 缓存统计信息
        """
        with self._lock:
            now = datetime.now()
            valid_entries = 0
            expired_entries = 0
            
            for key, (cached_at, _) in self._cache.items():
                if now - cached_at > timedelta(seconds=self.ttl):
                    expired_entries += 1
                else:
                    valid_entries += 1
            
            return {
                'total_entries': len(self._cache),
                'valid_entries': valid_entries,
                'expired_entries': expired_entries,
                'max_size': self.max_size,
                'ttl_seconds': self.ttl,
                'usage_percent': (len(self._cache) / self.max_size * 100) if self.max_size > 0 else 0
            }
    
    def cleanup_expired(self) -> int:
        """
        清理所有过期的缓存条目
        
        Returns:
            int: 清理的条目数量
        """
        with self._lock:
            now = datetime.now()
            expired_keys = []
            
            for key, (cached_at, _) in self._cache.items():
                if now - cached_at > timedelta(seconds=self.ttl):
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove(key)
            
            if expired_keys:
                logger.debug("Cleaned up %d expired cache entries", len(expired_keys))
            
            return len(expired_keys)
    
    def get_batch_keys(self) -> List[str]:
        """获取所有缓存键（用于调试）"""
        with self._lock:
            return list(self._cache.keys())
    
    def resize(self, new_max_size: int) -> None:
        """
        调整缓存大小
        
        Args:
            new_max_size: 新的最大缓存条目数
        """
        with self._lock:
            if new_max_size < 0:
                raise ValueError("max_size must be non-negative")
            
            # 如果新大小更小，需要淘汰多余的条目
            while len(self._cache) > new_max_size:
                self._evict_oldest()
            
            self.max_size = new_max_size
            logger.debug("Cache resized to %d entries", new_max_size)


class BatchCacheManager:
    """
    批次缓存管理器
    
    管理多个BatchCache实例，支持为不同扫描目标维护独立的缓存。
    
    Stage 6: 添加线程安全机制，确保多线程环境下的缓存管理器安全。
    """
    
    def __init__(self, default_max_size: int = 10, default_ttl: int = 300):
        """
        初始化缓存管理器
        
        Args:
            default_max_size: 默认最大缓存条目数
            default_ttl: 默认缓存过期时间（秒）
        """
        self.default_max_size = default_max_size
        self.default_ttl = default_ttl
        self._caches: Dict[str, BatchCache] = {}
        self._lock = threading.Lock()
    
    def get_cache(self, target: str) -> BatchCache:
        """
        获取指定目标的缓存实例
        
        Args:
            target: 扫描目标路径
            
        Returns:
            BatchCache: 缓存实例
        """
        with self._lock:
            if target not in self._caches:
                self._caches[target] = BatchCache(
                    max_size=self.default_max_size,
                    ttl=self.default_ttl
                )
            return self._caches[target]
    
    def clear_all(self) -> None:
        """清空所有缓存"""
        with self._lock:
            for cache in self._caches.values():
                cache.clear()
            self._caches.clear()
            logger.debug("All caches cleared")
    
    def cleanup_all_expired(self) -> int:
        """
        清理所有缓存中的过期条目
        
        Returns:
            int: 清理的总条目数量
        """
        with self._lock:
            total_cleaned = 0
            for cache in self._caches.values():
                total_cleaned += cache.cleanup_expired()
            return total_cleaned
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取所有缓存的统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        with self._lock:
            stats = {
                'total_caches': len(self._caches),
                'caches': {}
            }
            
            for target, cache in self._caches.items():
                stats['caches'][target] = cache.get_stats()
            
            return stats