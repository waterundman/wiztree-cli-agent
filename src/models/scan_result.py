from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from .file_info import FileInfo


@dataclass
class ScanResult:
    """扫描结果数据类"""
    target_path: Path
    files: List[FileInfo]
    scan_time: datetime
    duration_seconds: float
    total_files: int
    total_directories: int
    total_size: int  # 字节
    scan_options: Optional[Dict] = None
    errors: List[str] = field(default_factory=list)
    
    @property
    def total_size_human_readable(self) -> str:
        """人类可读的总大小"""
        if self.total_size < 1024:
            return f"{self.total_size} B"
        elif self.total_size < 1024 ** 2:
            return f"{self.total_size / 1024:.2f} KB"
        elif self.total_size < 1024 ** 3:
            return f"{self.total_size / (1024 ** 2):.2f} MB"
        else:
            return f"{self.total_size / (1024 ** 3):.2f} GB"
    
    @property
    def average_file_size(self) -> int:
        """平均文件大小"""
        if self.total_files == 0:
            return 0
        return self.total_size // self.total_files
    
    def get_files_by_extension(self, extension: str) -> List[FileInfo]:
        """按扩展名过滤文件"""
        return [f for f in self.files if f.extension == extension]
    
    def get_largest_files(self, n: int = 10) -> List[FileInfo]:
        """获取最大的n个文件"""
        return sorted(self.files, key=lambda x: x.size, reverse=True)[:n]
    
    def get_oldest_files(self, n: int = 10) -> List[FileInfo]:
        """获取最旧的n个文件"""
        return sorted(self.files, key=lambda x: x.modified_time)[:n]
    
    def __str__(self) -> str:
        return (f"ScanResult: {self.total_files} files, {self.total_directories} directories, "
                f"Total: {self.total_size_human_readable}")