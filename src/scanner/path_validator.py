import os
from pathlib import Path
from typing import Optional, Tuple
import ctypes
from ctypes import wintypes


class PathValidator:
    """路径验证器"""
    
    def __init__(self):
        self._kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        self._kernel32.GetVolumeInformationW.argtypes = [
            wintypes.LPWSTR, wintypes.LPWSTR, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD
        ]
        self._kernel32.GetVolumeInformationW.restype = wintypes.BOOL
    
    def validate(self, path: str) -> Tuple[bool, Optional[str]]:
        """
        验证路径
        
        Args:
            path: 要验证的路径
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        if not path:
            return False, "路径不能为空"
        
        # 规范化路径
        try:
            path = self._normalize_path(path)
        except Exception as e:
            return False, f"路径格式错误: {e}"
        
        # 检查路径是否存在
        if not os.path.exists(path):
            return False, f"路径不存在: {path}"
        
        # 检查路径权限
        if not self._check_permissions(path):
            return False, f"没有访问权限: {path}"
        
        # 检查是否为有效的扫描目标
        if not self._is_valid_scan_target(path):
            return False, f"不是有效的扫描目标: {path}"
        
        return True, None
    
    def _normalize_path(self, path: str) -> str:
        """
        规范化路径
        
        Args:
            path: 原始路径
            
        Returns:
            str: 规范化后的路径
        """
        # 处理Windows路径格式
        path = path.replace('/', '\\')
        
        # 处理相对路径
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        
        # 处理驱动器号
        if len(path) >= 2 and path[1] == ':':
            # 确保驱动器号大写
            path = path[0].upper() + path[1:]
        
        return path
    
    def _check_permissions(self, path: str) -> bool:
        """
        检查路径权限
        
        Args:
            path: 要检查的路径
            
        Returns:
            bool: 是否有权限
        """
        try:
            # 检查读取权限
            if os.path.isfile(path):
                return os.access(path, os.R_OK)
            elif os.path.isdir(path):
                # 尝试列出目录内容
                try:
                    next(os.scandir(path), None)
                    return True
                except PermissionError:
                    return False
                except StopIteration:
                    # 空目录也是有效的
                    return True
            return False
        except Exception:
            return False
    
    def _is_valid_scan_target(self, path: str) -> bool:
        """
        检查是否为有效的扫描目标
        
        Args:
            path: 要检查的路径
            
        Returns:
            bool: 是否为有效扫描目标
        """
        # 检查是否为驱动器根目录
        if self._is_drive_root(path):
            return self._is_valid_drive(path)
        
        # 检查是否为目录
        if not os.path.isdir(path):
            return False
        
        # 检查目录是否可访问
        try:
            # 尝试获取目录的统计信息
            os.stat(path)
            return True
        except OSError:
            return False
    
    def _is_drive_root(self, path: str) -> bool:
        """
        检查是否为驱动器根目录
        
        Args:
            path: 要检查的路径
            
        Returns:
            bool: 是否为驱动器根目录
        """
        # Windows驱动器根目录格式: C:\, D:\, etc.
        if len(path) == 3 and path[1] == ':' and path[2] == '\\':
            return True
        # 也支持 C: 格式
        if len(path) == 2 and path[1] == ':':
            return True
        return False
    
    def _is_valid_drive(self, path: str) -> bool:
        """
        检查是否为有效驱动器
        
        Args:
            path: 驱动器路径
            
        Returns:
            bool: 是否为有效驱动器
        """
        try:
            # 获取驱动器号
            drive = path[0].upper()
            if not drive.isalpha():
                return False
            
            # 检查驱动器是否存在
            drive_path = f"{drive}:\\"
            return os.path.exists(drive_path)
        except Exception:
            return False
    
    def get_drive_type(self, path: str) -> Optional[str]:
        """
        获取驱动器类型
        
        Args:
            path: 驱动器路径
            
        Returns:
            Optional[str]: 驱动器类型
        """
        if not self._is_drive_root(path):
            return None
        
        try:
            drive = path[0].upper()
            drive_path = f"{drive}:\\"
            
            # 使用Windows API获取驱动器类型
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_path)
            
            drive_types = {
                0: "未知",
                1: "无效",
                2: "可移动",
                3: "固定",
                4: "网络",
                5: "CD-ROM",
                6: "RAM磁盘"
            }
            
            return drive_types.get(drive_type, "未知")
        except Exception:
            return "未知"
    
    def get_available_drives(self) -> list:
        """
        获取可用驱动器列表
        
        Returns:
            list: 可用驱动器列表
        """
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            if bitmask & 1:
                drive_path = f"{letter}:\\"
                try:
                    # 检查驱动器是否可访问
                    os.stat(drive_path)
                    drives.append(drive_path)
                except OSError:
                    pass
            bitmask >>= 1
        
        return drives

    def validate_deep_search(self, path: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        深度检索路径验证
        
        Args:
            path: 要验证的路径
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (是否有效, 错误信息, 错误代码)
        """
        # 基础验证
        is_valid, error_msg = self.validate(path)
        if not is_valid:
            return is_valid, error_msg, 'BASIC_VALIDATION_FAILED'
        
        # 检查是否为目录
        path_obj = Path(path)
        if not path_obj.is_dir():
            return False, f"路径不是目录: {path}", 'NOT_DIRECTORY'
        
        # 检查读取权限
        if not os.access(path, os.R_OK):
            return False, f"没有读取权限: {path}", 'NO_READ_PERMISSION'
        
        # 检查是否为系统目录（可选警告）
        if self._is_system_directory(path):
            return True, "警告: 该目录为系统目录，扫描可能需要较长时间", 'SYSTEM_DIRECTORY_WARNING'
        
        return True, None, None

    def _is_system_directory(self, path: str) -> bool:
        """
        检查是否为系统目录
        
        Args:
            path: 要检查的路径
            
        Returns:
            bool: 是否为系统目录
        """
        system_dirs = [
            'C:\\Windows',
            'C:\\Program Files',
            'C:\\Program Files (x86)',
            'C:\\ProgramData',
        ]
        path_upper = path.upper()
        for sys_dir in system_dirs:
            if path_upper.startswith(sys_dir.upper()):
                return True
        return False

    def get_path_info(self, path: str) -> dict:
        """
        获取路径详细信息
        
        Args:
            path: 要检查的路径
            
        Returns:
            dict: 路径信息
        """
        info = {
            'path': path,
            'exists': False,
            'is_directory': False,
            'is_file': False,
            'is_readable': False,
            'is_writable': False,
            'is_drive_root': False,
            'drive_type': None,
        }
        
        try:
            path_obj = Path(path)
            info['exists'] = path_obj.exists()
            info['is_directory'] = path_obj.is_dir()
            info['is_file'] = path_obj.is_file()
            info['is_readable'] = os.access(path, os.R_OK)
            info['is_writable'] = os.access(path, os.W_OK)
            info['is_drive_root'] = self._is_drive_root(path)
            
            if info['is_drive_root']:
                info['drive_type'] = self.get_drive_type(path)
                
        except Exception as e:
            info['error'] = str(e)
            
        return info