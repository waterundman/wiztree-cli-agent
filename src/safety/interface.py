from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from enum import Enum


class SafetyLevel(Enum):
    """安全级别枚举"""
    LOW = "low"          # 低风险
    MEDIUM = "medium"    # 中等风险
    HIGH = "high"        # 高风险
    CRITICAL = "critical"  # 关键风险


class SafetyCheckResult:
    """安全检查结果"""
    
    def __init__(self, is_safe: bool, level: SafetyLevel, 
                 message: str = "", details: Optional[Dict[str, Any]] = None):
        """
        初始化安全检查结果
        
        Args:
            is_safe: 是否安全
            level: 安全级别
            message: 消息
            details: 详细信息
        """
        self.is_safe = is_safe
        self.level = level
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'is_safe': self.is_safe,
            'level': self.level.value,
            'message': self.message,
            'details': self.details
        }


class SafetyInterface(ABC):
    """
    安全接口抽象基类
    
    所有安全相关的类都应该实现这个接口
    """
    
    @abstractmethod
    def validate_file(self, file_path: str) -> SafetyCheckResult:
        """
        验证单个文件的安全性
        
        Args:
            file_path: 文件路径
            
        Returns:
            SafetyCheckResult: 安全检查结果
        """
        pass
    
    @abstractmethod
    def validate_batch(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        批量验证文件安全性
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            验证结果字典，包含valid、invalid、warnings列表
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def is_path_blocked(self, file_path: str) -> bool:
        """
        检查路径是否被阻止
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否被阻止
        """
        pass
    
    @abstractmethod
    def log_deletion(self, file_path: str, success: bool, 
                    error_message: Optional[str] = None) -> None:
        """
        记录删除操作
        
        Args:
            file_path: 文件路径
            success: 是否成功
            error_message: 错误信息
        """
        pass
    
    @abstractmethod
    def get_safety_rules(self) -> List[str]:
        """
        获取安全规则列表
        
        Returns:
            List[str]: 安全规则描述列表
        """
        pass
    
    def check_system_critical(self, file_path: str) -> SafetyCheckResult:
        """
        检查是否为系统关键文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            SafetyCheckResult: 安全检查结果
        """
        # 默认实现，子类可以覆盖
        return SafetyCheckResult(
            is_safe=True,
            level=SafetyLevel.LOW,
            message="非系统关键文件"
        )
    
    def check_user_data(self, file_path: str) -> SafetyCheckResult:
        """
        检查是否为用户数据文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            SafetyCheckResult: 安全检查结果
        """
        # 默认实现，子类可以覆盖
        return SafetyCheckResult(
            is_safe=True,
            level=SafetyLevel.LOW,
            message="普通文件"
        )
    
    def get_risk_assessment(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        获取风险评估报告
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            风险评估报告
        """
        results = {
            'total_files': len(file_paths),
            'safe_files': 0,
            'risky_files': 0,
            'blocked_files': 0,
            'risk_level': SafetyLevel.LOW,
            'details': []
        }
        
        for file_path in file_paths:
            # 检查是否被阻止
            if self.is_path_blocked(file_path):
                results['blocked_files'] += 1
                results['details'].append({
                    'path': file_path,
                    'status': 'blocked',
                    'message': '路径被阻止'
                })
                continue
            
            # 验证文件
            check_result = self.validate_file(file_path)
            
            if check_result.is_safe:
                results['safe_files'] += 1
            else:
                results['risky_files'] += 1
                
                # 更新整体风险级别
                if check_result.level.value > results['risk_level'].value:
                    results['risk_level'] = check_result.level
            
            results['details'].append({
                'path': file_path,
                'status': 'safe' if check_result.is_safe else 'risky',
                'level': check_result.level.value,
                'message': check_result.message
            })
        
        return results
    
    def create_safety_report(self, file_paths: List[str]) -> str:
        """
        创建安全报告
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            格式化的安全报告
        """
        assessment = self.get_risk_assessment(file_paths)
        
        report_lines = [
            "安全风险评估报告",
            "=" * 50,
            f"评估时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"文件总数: {assessment['total_files']}",
            "",
            "风险统计:",
            f"  • 安全文件: {assessment['safe_files']}",
            f"  • 风险文件: {assessment['risky_files']}",
            f"  • 被阻止文件: {assessment['blocked_files']}",
            f"  • 整体风险级别: {assessment['risk_level'].value}",
            "",
            "详细信息:",
        ]
        
        for detail in assessment['details']:
            status_icon = "✓" if detail['status'] == 'safe' else "✗" if detail['status'] == 'blocked' else "⚠"
            report_lines.append(f"  {status_icon} {detail['path']}")
            if detail.get('message'):
                report_lines.append(f"    {detail['message']}")
        
        return "\n".join(report_lines)