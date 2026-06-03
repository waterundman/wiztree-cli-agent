from abc import ABC, abstractmethod
from typing import List, Optional
try:
    from ..models.file_info import FileInfo
    from ..models.analysis_result import AnalysisResult
except ImportError:
    from models.file_info import FileInfo
    from models.analysis_result import AnalysisResult


class AnalyzerInterface(ABC):
    """
    分析器抽象基类
    定义分析器的标准接口
    """
    
    @abstractmethod
    def analyze(self, files: List[FileInfo]) -> AnalysisResult:
        """
        分析文件列表并返回分析结果
        
        Args:
            files: 文件信息列表
            
        Returns:
            AnalysisResult: 包含删除建议和统计信息的分析结果
        """
        pass
    
    @abstractmethod
    def get_analysis_rules(self) -> List[str]:
        """
        获取当前分析器使用的规则列表
        
        Returns:
            List[str]: 规则描述列表
        """
        pass
    
    def validate_files(self, files: List[FileInfo]) -> List[FileInfo]:
        """
        验证和过滤文件列表
        
        Args:
            files: 原始文件列表
            
        Returns:
            List[FileInfo]: 验证后的文件列表
        """
        # 默认实现：过滤掉目录和大小为0的文件
        return [
            f for f in files 
            if not f.is_directory and f.size > 0
        ]
    
    def calculate_total_savings(self, recommendations: List) -> int:
        """
        计算总潜在节省空间
        
        Args:
            recommendations: 删除建议列表
            
        Returns:
            int: 总潜在节省空间（字节）
        """
        return sum(r.potential_savings for r in recommendations)
    
    def create_empty_result(self, duration: float = 0.0) -> AnalysisResult:
        """
        创建空的分析结果
        
        Args:
            duration: 分析耗时（秒）
            
        Returns:
            AnalysisResult: 空的分析结果
        """
        from datetime import datetime
        from ..models.analysis_result import RiskLevel
        
        return AnalysisResult(
            recommendations=[],
            total_potential_savings=0,
            analysis_time=datetime.now(),
            duration_seconds=duration,
            risk_summary={level: 0 for level in RiskLevel},
            file_type_summary={},
            warnings=[]
        )