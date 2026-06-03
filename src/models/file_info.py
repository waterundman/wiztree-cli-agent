from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from pathlib import Path


@dataclass(slots=True)
class FileInfo:
    """文件信息数据类（使用 __slots__ 优化内存）"""
    path: Path
    size: int  # 字节
    modified_time: datetime
    created_time: Optional[datetime] = None
    is_directory: bool = False
    extension: Optional[str] = None
    depth: int = 0  # 目录深度
    parent_path: Optional[Path] = None
    
    @classmethod
    def from_path(cls, path: Path, depth: int = 0) -> 'FileInfo':
        """从路径创建FileInfo实例"""
        stat = path.stat()
        return cls(
            path=path,
            size=stat.st_size,
            modified_time=datetime.fromtimestamp(stat.st_mtime),
            created_time=datetime.fromtimestamp(stat.st_ctime),
            is_directory=path.is_dir(),
            extension=path.suffix.lower() if path.suffix else None,
            depth=depth,
            parent_path=path.parent
        )
    
    @property
    def name(self) -> str:
        """文件名"""
        return self.path.name
    
    @property
    def size_human_readable(self) -> str:
        """人类可读的文件大小"""
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 ** 2:
            return f"{self.size / 1024:.2f} KB"
        elif self.size < 1024 ** 3:
            return f"{self.size / (1024 ** 2):.2f} MB"
        else:
            return f"{self.size / (1024 ** 3):.2f} GB"
    
    def __str__(self) -> str:
        return f"{self.name} ({self.size_human_readable})"