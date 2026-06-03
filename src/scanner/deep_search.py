"""深度检索模块"""
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .path_validator import PathValidator
from .wiztree_scanner import WizTreeScanner
from .options import ScanOptions
from ..models.scan_result import ScanResult
from ..models.file_info import FileInfo


class DeepSearchError(Exception):
    """深度检索异常基类"""
    pass


class PathValidationError(DeepSearchError):
    """路径验证异常"""
    pass


class ScanExecutionError(DeepSearchError):
    """扫描执行异常"""
    pass


class DeepSearcher:
    """深度检索类"""
    
    def __init__(self, scanner: WizTreeScanner):
        """
        初始化深度检索器
        
        Args:
            scanner: WizTree扫描器实例
        """
        self.scanner = scanner
        self.validator = PathValidator()
        
    def search(self, folder_path: str, options: Optional[ScanOptions] = None) -> ScanResult:
        """
        深度检索文件夹
        
        Args:
            folder_path: 文件夹路径
            options: 扫描选项
            
        Returns:
            ScanResult: 扫描结果
            
        Raises:
            PathValidationError: 路径验证失败
            ScanExecutionError: 扫描执行失败
        """
        # 验证路径
        validation_result = self._validate_path(folder_path)
        if not validation_result['is_valid']:
            raise PathValidationError(validation_result['error_message'])
            
        # 使用默认选项（如果未提供）
        if options is None:
            options = ScanOptions()
            
        # 执行扫描
        try:
            return self.scanner.scan(folder_path, options)
        except Exception as e:
            raise ScanExecutionError(f"扫描执行失败: {str(e)}")
        
    def _validate_path(self, path: str) -> Dict[str, Any]:
        """
        验证路径
        
        Args:
            path: 要验证的路径
            
        Returns:
            Dict: 验证结果，包含 is_valid 和 error_message
        """
        # 基础验证
        is_valid, error_msg = self.validator.validate(path)
        if not is_valid:
            return {
                'is_valid': False,
                'error_message': error_msg,
                'error_code': 'BASIC_VALIDATION_FAILED'
            }
        
        # 检查是否为目录
        path_obj = Path(path)
        if not path_obj.is_dir():
            return {
                'is_valid': False,
                'error_message': f"路径不是目录: {path}",
                'error_code': 'NOT_DIRECTORY'
            }
            
        # 检查读取权限
        if not os.access(path, os.R_OK):
            return {
                'is_valid': False,
                'error_message': f"没有读取权限: {path}",
                'error_code': 'NO_READ_PERMISSION'
            }
            
        return {
            'is_valid': True,
            'error_message': None,
            'error_code': None
        }
        
    def get_folder_stats(self, folder_path: str) -> Dict[str, Any]:
        """
        获取文件夹统计信息
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            Dict: 统计信息，包含 total_size, file_count, dir_count
        """
        path = Path(folder_path)
        if not path.exists():
            return {
                'error': '路径不存在',
                'error_code': 'PATH_NOT_FOUND'
            }
            
        if not path.is_dir():
            return {
                'error': '路径不是目录',
                'error_code': 'NOT_DIRECTORY'
            }
            
        total_size = 0
        file_count = 0
        dir_count = 0
        errors = []
        
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    try:
                        total_size += item.stat().st_size
                        file_count += 1
                    except (PermissionError, OSError) as e:
                        errors.append(f"无法访问: {item} - {str(e)}")
                elif item.is_dir():
                    dir_count += 1
        except PermissionError:
            return {
                'error': '权限不足',
                'error_code': 'PERMISSION_DENIED'
            }
            
        return {
            'total_size': total_size,
            'total_size_human_readable': self._format_size(total_size),
            'file_count': file_count,
            'dir_count': dir_count,
            'errors': errors
        }
    
    def search_files_by_pattern(
        self, 
        folder_path: str, 
        pattern: str,
        options: Optional[ScanOptions] = None
    ) -> ScanResult:
        """
        按模式搜索文件
        
        Args:
            folder_path: 文件夹路径
            pattern: 文件名模式（支持通配符）
            options: 扫描选项
            
        Returns:
            ScanResult: 扫描结果
        """
        # 验证路径
        validation_result = self._validate_path(folder_path)
        if not validation_result['is_valid']:
            raise PathValidationError(validation_result['error_message'])
            
        # 使用默认选项（如果未提供）
        if options is None:
            options = ScanOptions()
            
        # 执行扫描
        try:
            result = self.scanner.scan(folder_path, options)
            
            # 按模式过滤文件
            filtered_files = [
                f for f in result.files 
                if self._match_pattern(f.path.name, pattern)
            ]
            
            # 构建新的结果
            return ScanResult(
                target_path=result.target_path,
                files=filtered_files,
                scan_time=result.scan_time,
                duration_seconds=result.duration_seconds,
                total_files=len(filtered_files),
                total_directories=sum(1 for f in filtered_files if f.is_directory),
                total_size=sum(f.size for f in filtered_files),
                scan_options=result.scan_options,
                errors=result.errors
            )
        except Exception as e:
            raise ScanExecutionError(f"文件搜索失败: {str(e)}")
    
    def search_large_files(
        self,
        folder_path: str,
        min_size_mb: float = 100.0,
        options: Optional[ScanOptions] = None
    ) -> ScanResult:
        """
        搜索大文件
        
        Args:
            folder_path: 文件夹路径
            min_size_mb: 最小文件大小（MB）
            options: 扫描选项
            
        Returns:
            ScanResult: 扫描结果
        """
        # 验证路径
        validation_result = self._validate_path(folder_path)
        if not validation_result['is_valid']:
            raise PathValidationError(validation_result['error_message'])
            
        # 使用默认选项（如果未提供）
        if options is None:
            options = ScanOptions()
            
        # 设置最小大小过滤
        min_size_bytes = int(min_size_mb * 1024 * 1024)
        options.min_size = min_size_bytes
            
        # 执行扫描
        try:
            return self.scanner.scan(folder_path, options)
        except Exception as e:
            raise ScanExecutionError(f"大文件搜索失败: {str(e)}")
    
    def _match_pattern(self, filename: str, pattern: str) -> bool:
        """
        匹配文件名模式
        
        Args:
            filename: 文件名
            pattern: 模式（支持 * 和 ?）
            
        Returns:
            bool: 是否匹配
        """
        import fnmatch
        return fnmatch.fnmatch(filename.lower(), pattern.lower())
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 大小（字节）
            
        Returns:
            str: 格式化后的大小字符串
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.2f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"
