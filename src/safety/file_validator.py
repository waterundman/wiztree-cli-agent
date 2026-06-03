import os
import stat
import ctypes
from typing import Optional, Tuple
from pathlib import Path
from enum import Enum


class ValidationResult(Enum):
    """验证结果枚举"""
    VALID = "valid"
    NOT_FOUND = "not_found"
    LOCKED = "locked"
    PERMISSION_DENIED = "permission_denied"
    SYSTEM_FILE = "system_file"
    IN_USE = "in_use"
    READ_ONLY = "read_only"
    HIDDEN = "hidden"
    SYSTEM = "system"


class FileInfo:
    """文件信息类"""
    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path)
        self.directory = os.path.dirname(path)
        self.exists = False
        self.is_file = False
        self.is_dir = False
        self.size = 0
        self.is_readable = False
        self.is_writable = False
        self.is_executable = False
        self.is_hidden = False
        self.is_system = False
        self.is_locked = False
        self.permissions = ""
        self.last_modified = None
        
        self._analyze()
    
    def _analyze(self):
        """分析文件信息"""
        try:
            path_obj = Path(self.path)
            
            # 检查存在性
            self.exists = path_obj.exists()
            
            if self.exists:
                # 获取文件状态
                stat_result = path_obj.stat()
                
                # 文件类型
                self.is_file = path_obj.is_file()
                self.is_dir = path_obj.is_dir()
                
                # 文件大小
                if self.is_file:
                    self.size = stat_result.st_size
                
                # 权限检查
                self.is_readable = os.access(self.path, os.R_OK)
                self.is_writable = os.access(self.path, os.W_OK)
                self.is_executable = os.access(self.path, os.X_OK)
                
                # 隐藏文件检查
                self.is_hidden = self._is_hidden()
                
                # 系统文件检查
                self.is_system = self._is_system_file()
                
                # 锁定文件检查
                self.is_locked = self._is_locked()
                
                # 权限字符串
                self.permissions = stat.filemode(stat_result.st_mode)
                
                # 修改时间
                self.last_modified = stat_result.st_mtime
                
        except (OSError, PermissionError):
            # 文件无法访问
            pass
    
    def _is_hidden(self) -> bool:
        """检查是否为隐藏文件"""
        try:
            # Windows隐藏文件检查
            if os.name == 'nt':
                attrs = ctypes.windll.kernel32.GetFileAttributesW(self.path)
                if attrs != -1:
                    return bool(attrs & 2)  # FILE_ATTRIBUTE_HIDDEN
            
            # Unix隐藏文件检查（以.开头）
            return self.name.startswith('.')
        except:
            return False
    
    def _is_system_file(self) -> bool:
        """检查是否为系统文件"""
        try:
            # Windows系统文件检查
            if os.name == 'nt':
                attrs = ctypes.windll.kernel32.GetFileAttributesW(self.path)
                if attrs != -1:
                    return bool(attrs & 4)  # FILE_ATTRIBUTE_SYSTEM
            
            # 系统目录检查
            system_paths = [
                '/bin', '/sbin', '/usr', '/etc', '/var', '/boot', '/dev',
                'C:\\Windows', 'C:\\Program Files', 'C:\\Program Files (x86)'
            ]
            
            for sys_path in system_paths:
                if self.path.lower().startswith(sys_path.lower()):
                    return True
            
            return False
        except:
            return False
    
    def _is_locked(self) -> bool:
        """检查文件是否被锁定"""
        try:
            # 尝试以独占方式打开文件
            if self.is_file:
                with open(self.path, 'rb') as f:
                    # 尝试获取文件锁
                    if os.name == 'nt':
                        import msvcrt
                        try:
                            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                            return False
                        except:
                            return True
                    else:
                        import fcntl
                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                            return False
                        except:
                            return True
            return False
        except:
            return False
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'path': self.path,
            'name': self.name,
            'directory': self.directory,
            'exists': self.exists,
            'is_file': self.is_file,
            'is_dir': self.is_dir,
            'size': self.size,
            'is_readable': self.is_readable,
            'is_writable': self.is_writable,
            'is_executable': self.is_executable,
            'is_hidden': self.is_hidden,
            'is_system': self.is_system,
            'is_locked': self.is_locked,
            'permissions': self.permissions,
            'last_modified': self.last_modified
        }


class FileValidator:
    """文件验证器"""
    
    def __init__(self, check_locks: bool = True, check_permissions: bool = True):
        """
        初始化文件验证器
        
        Args:
            check_locks: 是否检查文件锁定
            check_permissions: 是否检查权限
        """
        self.check_locks = check_locks
        self.check_permissions = check_permissions
    
    def validate(self, file_path: str) -> Tuple[ValidationResult, str]:
        """
        验证文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            (验证结果, 错误信息)
        """
        try:
            # 获取文件信息
            file_info = FileInfo(file_path)
            
            # 检查文件是否存在
            if not file_info.exists:
                return ValidationResult.NOT_FOUND, f"文件不存在: {file_path}"
            
            # 检查系统文件
            if file_info.is_system:
                return ValidationResult.SYSTEM_FILE, f"系统文件不允许删除: {file_path}"
            
            # 检查隐藏文件
            if file_info.is_hidden:
                return ValidationResult.HIDDEN, f"隐藏文件: {file_path}"
            
            # 检查文件锁定
            if self.check_locks and file_info.is_locked:
                return ValidationResult.LOCKED, f"文件被锁定: {file_path}"
            
            # 检查权限
            if self.check_permissions:
                if not file_info.is_readable:
                    return ValidationResult.PERMISSION_DENIED, f"没有读取权限: {file_path}"
                
                if not file_info.is_writable:
                    return ValidationResult.READ_ONLY, f"文件只读: {file_path}"
            
            return ValidationResult.VALID, ""
            
        except Exception as e:
            return ValidationResult.PERMISSION_DENIED, f"验证文件时出错: {str(e)}"
    
    def validate_batch(self, file_paths: list) -> dict:
        """
        批量验证文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            验证结果字典
        """
        results = {
            'valid': [],
            'invalid': [],
            'warnings': []
        }
        
        for file_path in file_paths:
            result, message = self.validate(file_path)
            
            if result == ValidationResult.VALID:
                results['valid'].append(file_path)
            elif result in [ValidationResult.HIDDEN, ValidationResult.READ_ONLY]:
                results['warnings'].append({
                    'path': file_path,
                    'result': result.value,
                    'message': message
                })
            else:
                results['invalid'].append({
                    'path': file_path,
                    'result': result.value,
                    'message': message
                })
        
        return results
    
    def get_file_info(self, file_path: str) -> FileInfo:
        """
        获取文件详细信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息对象
        """
        return FileInfo(file_path)
    
    def is_safe_to_delete(self, file_path: str) -> bool:
        """
        检查文件是否可以安全删除
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否可以安全删除
        """
        result, _ = self.validate(file_path)
        return result == ValidationResult.VALID
    
    def get_detailed_report(self, file_path: str) -> dict:
        """
        获取详细的验证报告
        
        Args:
            file_path: 文件路径
            
        Returns:
            详细报告字典
        """
        file_info = FileInfo(file_path)
        result, message = self.validate(file_path)
        
        report = {
            'file_info': file_info.to_dict(),
            'validation_result': result.value,
            'message': message,
            'is_safe': result == ValidationResult.VALID,
            'warnings': [],
            'recommendations': []
        }
        
        # 添加警告
        if file_info.is_hidden:
            report['warnings'].append("文件是隐藏的")
        
        if file_info.is_system:
            report['warnings'].append("文件是系统文件")
            report['recommendations'].append("不要删除系统文件")
        
        if file_info.is_locked:
            report['warnings'].append("文件被锁定")
            report['recommendations'].append("关闭使用此文件的程序")
        
        if not file_info.is_writable:
            report['warnings'].append("文件只读")
            report['recommendations'].append("检查文件权限")
        
        return report