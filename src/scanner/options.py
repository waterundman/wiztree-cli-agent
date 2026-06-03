from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ScanOptions:
    """扫描选项数据类"""
    max_depth: Optional[int] = None  # 最大扫描深度
    include_hidden: bool = False  # 是否包含隐藏文件
    file_extensions: Optional[List[str]] = None  # 只扫描特定扩展名
    exclude_patterns: Optional[List[str]] = None  # 排除模式
    min_size: Optional[int] = None  # 最小文件大小（字节）
    max_size: Optional[int] = None  # 最大文件大小（字节）
    follow_symlinks: bool = False  # 是否跟随符号链接
    
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
        }