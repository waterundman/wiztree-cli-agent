from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

try:
    from ..models.file_info import FileInfo
except ImportError:
    from models.file_info import FileInfo

# 导入新创建的模块
from .blocklist import Blocklist
from .audit_logger import AuditLogger
from .file_validator import FileValidator, ValidationResult as FileValidationResult
from .confirm_dialog import ConfirmDialog
from .interface import SafetyInterface as NewSafetyInterface, SafetyLevel, SafetyCheckResult


# 保持向后兼容的旧接口
class SafetyInterface(ABC):
    """安全接口（旧版本，保持向后兼容）"""
    
    @abstractmethod
    def validate_file(self, file: FileInfo) -> 'SafetyCheckResult':
        """
        验证文件安全性

        Args:
            file: 文件信息

        Returns:
            SafetyCheckResult: 验证结果
        """
        pass

    @abstractmethod
    def confirm_deletion(self, files: List[FileInfo]) -> bool:
        """
        确认删除文件

        Args:
            files: 要删除的文件列表

        Returns:
            bool: 是否确认删除
        """
        pass

    @abstractmethod
    def get_safety_rules(self) -> List[str]:
        """
        获取安全规则列表

        Returns:
            List[str]: 安全规则名称列表
        """
        pass


class ComprehensiveSafetyManager(NewSafetyInterface):
    """
    综合安全管理器
    
    整合所有安全功能的管理器
    """
    
    def __init__(self, db_path: Optional[str] = None, 
                 custom_blocked_paths: Optional[List[str]] = None):
        """
        初始化综合安全管理器
        
        Args:
            db_path: 审计日志数据库路径
            custom_blocked_paths: 自定义黑名单路径
        """
        self.blocklist = Blocklist(custom_blocked_paths)
        self.audit_logger = AuditLogger(db_path)
        self.file_validator = FileValidator()
        self.confirm_dialog = ConfirmDialog()
    
    def validate_file(self, file_path: str) -> SafetyCheckResult:
        """
        验证单个文件的安全性
        
        Args:
            file_path: 文件路径
            
        Returns:
            SafetyCheckResult: 安全检查结果
        """
        # 检查黑名单
        if self.blocklist.is_blocked(file_path):
            return SafetyCheckResult(
                is_safe=False,
                level=SafetyLevel.CRITICAL,
                message=f"路径被阻止: {file_path}",
                details={'reason': 'blacklisted'}
            )
        
        # 验证文件
        result, message = self.file_validator.validate(file_path)
        
        if result == FileValidationResult.VALID:
            return SafetyCheckResult(
                is_safe=True,
                level=SafetyLevel.LOW,
                message="文件安全"
            )
        elif result == FileValidationResult.NOT_FOUND:
            return SafetyCheckResult(
                is_safe=False,
                level=SafetyLevel.MEDIUM,
                message=message,
                details={'reason': 'not_found'}
            )
        elif result == FileValidationResult.LOCKED:
            return SafetyCheckResult(
                is_safe=False,
                level=SafetyLevel.HIGH,
                message=message,
                details={'reason': 'locked'}
            )
        elif result == FileValidationResult.SYSTEM_FILE:
            return SafetyCheckResult(
                is_safe=False,
                level=SafetyLevel.CRITICAL,
                message=message,
                details={'reason': 'system_file'}
            )
        else:
            return SafetyCheckResult(
                is_safe=False,
                level=SafetyLevel.HIGH,
                message=message,
                details={'reason': result.value}
            )
    
    def validate_batch(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        批量验证文件安全性
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            验证结果字典
        """
        return self.file_validator.validate_batch(file_paths)
    
    def confirm_deletion(self, file_paths: List[str], 
                        custom_message: Optional[str] = None) -> bool:
        """
        确认删除文件
        
        Args:
            file_paths: 要删除的文件列表
            custom_message: 自定义确认消息
            
        Returns:
            bool: 是否确认删除
        """
        return self.confirm_dialog.get_confirmation(file_paths, custom_message)
    
    def is_path_blocked(self, file_path: str) -> bool:
        """
        检查路径是否被阻止
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否被阻止
        """
        return self.blocklist.is_blocked(file_path)
    
    def log_deletion(self, file_path: str, success: bool, 
                    error_message: Optional[str] = None) -> None:
        """
        记录删除操作
        
        Args:
            file_path: 文件路径
            success: 是否成功
            error_message: 错误信息
        """
        import os
        
        file_name = os.path.basename(file_path)
        file_size = None
        file_type = None
        parent_directory = os.path.dirname(file_path)
        
        try:
            if os.path.exists(file_path):
                stat_result = os.stat(file_path)
                file_size = stat_result.st_size
                _, ext = os.path.splitext(file_path)
                file_type = ext.upper()[1:] if ext else None
        except (OSError, PermissionError):
            pass
        
        status = "success" if success else "failed"
        
        self.audit_logger.log_deletion(
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
            parent_directory=parent_directory,
            deletion_status=status,
            error_message=error_message
        )
        
        self.audit_logger.log(
            action_type="file_delete",
            target_path=file_path,
            status=status,
            metadata={
                "file_name": file_name,
                "file_size": file_size,
                "file_type": file_type,
                "parent_directory": parent_directory,
                "error_message": error_message,
            },
        )
    
    def get_safety_rules(self) -> List[str]:
        """
        获取安全规则列表
        
        Returns:
            List[str]: 安全规则描述列表
        """
        return [
            "系统关键路径被阻止",
            "系统文件不允许删除",
            "锁定文件需要先解锁",
            "只读文件需要修改权限",
            "删除操作需要二次确认",
            "所有删除操作被记录到审计日志"
        ]
    
    def add_blocked_path(self, path: str):
        """
        添加路径到黑名单
        
        Args:
            path: 要添加的路径
        """
        self.blocklist.add_path(path)
    
    def remove_blocked_path(self, path: str) -> bool:
        """
        从黑名单移除路径
        
        Args:
            path: 要移除的路径
            
        Returns:
            是否成功移除
        """
        return self.blocklist.remove_path(path)
    
    def get_audit_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        获取审计统计信息
        
        Args:
            days: 统计天数
            
        Returns:
            统计信息字典
        """
        return self.audit_logger.get_statistics(days)
    
    def export_audit_log(self, output_path: str, format: str = "json") -> bool:
        """
        导出审计日志
        
        Args:
            output_path: 输出文件路径
            format: 输出格式（json/csv）
            
        Returns:
            是否成功导出
        """
        if format.lower() == "json":
            return self.audit_logger.export_to_json(output_path)
        elif format.lower() == "csv":
            return self.audit_logger.export_to_csv(output_path)
        else:
            return False


# 导出所有类
__all__ = [
    'SafetyInterface',
    'NewSafetyInterface',
    'ComprehensiveSafetyManager',
    'Blocklist',
    'AuditLogger',
    'FileValidator',
    'ConfirmDialog',
    'SafetyLevel',
    'SafetyCheckResult',
    'FileValidationResult'
]