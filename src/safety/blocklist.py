import os
import re
from typing import List, Set, Optional
from pathlib import Path


class Blocklist:
    """系统路径黑名单管理器"""
    
    # 硬编码的系统关键路径黑名单
    DEFAULT_BLOCKED_PATHS = {
        # Windows系统目录
        "C:\\Windows",
        "C:\\Windows\\System32",
        "C:\\Windows\\SysWOW64",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
        "C:\\Recovery",
        "C:\\$Recycle.Bin",
        "C:\\System Volume Information",
        "C:\\Boot",
        "C:\\bootmgr",
        "C:\\pagefile.sys",
        "C:\\swapfile.sys",
        "C:\\hiberfil.sys",
        
        # 用户目录
        "C:\\Users\\*\\AppData",
        "C:\\Users\\*\\NTUSER.DAT",
        "C:\\Users\\*\\ntuser.dat.log",
        
        # Linux/macOS系统目录
        "/bin",
        "/sbin",
        "/usr",
        "/etc",
        "/var",
        "/boot",
        "/dev",
        "/proc",
        "/sys",
        "/root",
        "/lib",
        "/lib64",
        "/opt",
        
        # macOS特定
        "/System",
        "/Library",
        "/Applications",
        
        # 关键配置文件
        "*.sys",
        "*.dll",
        "*.exe",
        "*.so",
        "*.dylib",
    }
    
    # 通配符模式
    WILDCARD_PATTERNS = [
        r"^C:\\Windows\\.*",  # Windows目录下的所有文件
        r"^C:\\Program Files\\.*",  # Program Files下的所有文件
        r"^C:\\Users\\.*\\AppData\\.*",  # 用户AppData
        r"^/usr/.*",  # /usr下的所有文件
        r"^/etc/.*",  # /etc下的所有文件
        r"^.*\\.sys$",  # 所有.sys文件
        r"^.*\\.dll$",  # 所有.dll文件
        r"^.*\\.exe$",  # 所有.exe文件
        r"^.*\\.so$",  # 所有.so文件
        r"^.*\\.dylib$",  # 所有.dylib文件
    ]
    
    def __init__(self, custom_blocked_paths: Optional[List[str]] = None):
        """
        初始化黑名单管理器
        
        Args:
            custom_blocked_paths: 自定义的额外黑名单路径
        """
        self._blocked_paths: Set[str] = set()
        self._compiled_patterns: List[re.Pattern] = []
        
        # 加载默认黑名单
        self._load_default_blocklist()
        
        # 加载自定义黑名单
        if custom_blocked_paths:
            self.add_paths(custom_blocked_paths)
        
        # 编译通配符模式
        self._compile_patterns()
    
    def _load_default_blocklist(self):
        """加载默认黑名单"""
        for path in self.DEFAULT_BLOCKED_PATHS:
            normalized = self._normalize_path(path)
            self._blocked_paths.add(normalized)
    
    def _compile_patterns(self):
        """编译通配符模式"""
        for pattern in self.WILDCARD_PATTERNS:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self._compiled_patterns.append(compiled)
            except re.error:
                # 忽略无效的正则表达式
                pass
    
    def _normalize_path(self, path: str) -> str:
        """
        规范化路径
        
        Args:
            path: 原始路径
            
        Returns:
            规范化后的路径
        """
        # 移除引号
        path = path.strip('"\'')
        
        # 转换为Path对象进行规范化
        try:
            normalized = Path(path).resolve()
            return str(normalized).lower()
        except (OSError, ValueError):
            # 如果路径无法解析，返回小写版本
            return path.lower().replace('/', '\\')
    
    def add_path(self, path: str):
        """
        添加单个路径到黑名单
        
        Args:
            path: 要添加的路径
        """
        normalized = self._normalize_path(path)
        self._blocked_paths.add(normalized)
    
    def add_paths(self, paths: List[str]):
        """
        批量添加路径到黑名单
        
        Args:
            paths: 要添加的路径列表
        """
        for path in paths:
            self.add_path(path)
    
    def remove_path(self, path: str) -> bool:
        """
        从黑名单中移除路径
        
        Args:
            path: 要移除的路径
            
        Returns:
            是否成功移除
        """
        normalized = self._normalize_path(path)
        if normalized in self._blocked_paths:
            self._blocked_paths.remove(normalized)
            return True
        return False
    
    def is_blocked(self, path: str) -> bool:
        """
        检查路径是否被阻止
        
        Args:
            path: 要检查的路径
            
        Returns:
            是否被阻止
        """
        normalized = self._normalize_path(path)
        
        # 精确匹配
        if normalized in self._blocked_paths:
            return True
        
        # 检查是否在黑名单目录下
        for blocked in self._blocked_paths:
            if '*' in blocked:
                # 通配符匹配 - 将通配符转换为正则表达式
                pattern = blocked.replace('\\', '\\\\')
                pattern = pattern.replace('*', '[^\\\\]*')
                pattern = f'^{pattern}$'
                try:
                    if re.match(pattern, normalized, re.IGNORECASE):
                        return True
                except re.error:
                    pass
            elif normalized.startswith(blocked + '\\') or normalized.startswith(blocked + '/'):
                return True
        
        # 通配符模式匹配
        for pattern in self._compiled_patterns:
            if pattern.match(normalized):
                return True
        
        return False
    
    def get_blocked_paths(self) -> List[str]:
        """
        获取所有黑名单路径
        
        Returns:
            黑名单路径列表
        """
        return list(self._blocked_paths)
    
    def clear(self):
        """清空黑名单"""
        self._blocked_paths.clear()
        self._compiled_patterns.clear()
    
    def __len__(self) -> int:
        """获取黑名单长度"""
        return len(self._blocked_paths)
    
    def __contains__(self, path: str) -> bool:
        """支持 in 操作符"""
        return self.is_blocked(path)