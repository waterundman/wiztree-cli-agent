from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ScanOptions:
    """扫描选项数据类
    
    支持流式处理、批处理和缓存等高级功能
    """
    max_depth: Optional[int] = None  # 最大扫描深度
    include_hidden: bool = False  # 是否包含隐藏文件
    file_extensions: Optional[List[str]] = None  # 只扫描特定扩展名
    exclude_patterns: Optional[List[str]] = None  # 排除模式
    min_size: Optional[int] = None  # 最小文件大小（字节）
    max_size: Optional[int] = None  # 最大文件大小（字节）
    follow_symlinks: bool = False  # 是否跟随符号链接
    
    # 流式处理和批处理参数
    max_files: int = 1000  # 最大文件数量限制
    batch_size: int = 50  # 批处理大小
    streaming: bool = True  # 是否启用流式处理
    cache_batches: int = 3  # 缓存批次数
    lazy_load: bool = True  # 是否启用懒加载
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'max_depth': self.max_depth,
            'include_hidden': self.include_hidden,
            'file_extensions': self.file_extensions,
            'exclude_patterns': self.exclude_patterns,
            'min_size': self.min_size,
            'max_size': self.max_size,
            'follow_symlinks': self.follow_symlinks,
            'max_files': self.max_files,
            'batch_size': self.batch_size,
            'streaming': self.streaming,
            'cache_batches': self.cache_batches,
            'lazy_load': self.lazy_load,
        }