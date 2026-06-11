from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum

from .file_info import FileInfo


class RiskLevel(Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DeletionRecommendation:
    """删除建议数据类"""
    file: FileInfo
    reason: str
    risk_level: RiskLevel
    confidence: float  # 0-1
    potential_savings: int  # 字节
    selected: bool = False
    
    @property
    def potential_savings_human_readable(self) -> str:
        """人类可读的潜在节省空间"""
        if self.potential_savings < 1024:
            return f"{self.potential_savings} B"
        elif self.potential_savings < 1024 ** 2:
            return f"{self.potential_savings / 1024:.2f} KB"
        elif self.potential_savings < 1024 ** 3:
            return f"{self.potential_savings / (1024 ** 2):.2f} MB"
        else:
            return f"{self.potential_savings / (1024 ** 3):.2f} GB"


@dataclass
class AnalysisResult:
    """分析结果数据类"""
    recommendations: List[DeletionRecommendation]
    total_potential_savings: int  # 字节
    analysis_time: datetime
    duration_seconds: float
    risk_summary: Dict[RiskLevel, int] = field(default_factory=dict)
    file_type_summary: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def total_potential_savings_human_readable(self) -> str:
        """人类可读的总潜在节省空间"""
        if self.total_potential_savings < 1024:
            return f"{self.total_potential_savings} B"
        elif self.total_potential_savings < 1024 ** 2:
            return f"{self.total_potential_savings / 1024:.2f} KB"
        elif self.total_potential_savings < 1024 ** 3:
            return f"{self.total_potential_savings / (1024 ** 2):.2f} MB"
        else:
            return f"{self.total_potential_savings / (1024 ** 3):.2f} GB"
    
    def get_recommendations_by_risk(self, risk_level: RiskLevel) -> List[DeletionRecommendation]:
        """按风险等级获取建议"""
        return [r for r in self.recommendations if r.risk_level == risk_level]
    
    def get_high_risk_recommendations(self) -> List[DeletionRecommendation]:
        """获取高风险建议"""
        return self.get_recommendations_by_risk(RiskLevel.HIGH)
    
    def get_critical_risk_recommendations(self) -> List[DeletionRecommendation]:
        """获取关键风险建议"""
        return self.get_recommendations_by_risk(RiskLevel.CRITICAL)
    
    def __str__(self) -> str:
        return (f"AnalysisResult: {len(self.recommendations)} recommendations, "
                f"Potential savings: {self.total_potential_savings_human_readable}")