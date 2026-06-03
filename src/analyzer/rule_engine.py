import re
from typing import List, Dict, Tuple, Optional
from ..models.file_info import FileInfo
from ..models.analysis_result import DeletionRecommendation, RiskLevel


class RuleEngine:
    """
    规则引擎
    提供基于规则的文件分析降级方案
    """
    
    def __init__(self):
        self.rules = self._initialize_rules()
    
    def _initialize_rules(self) -> List[Dict]:
        """
        初始化预定义规则
        
        Returns:
            List[Dict]: 规则列表
        """
        return [
            {
                "name": "临时文件",
                "pattern": r"\.(tmp|temp|bak|old|log|cache)$",
                "risk": RiskLevel.LOW,
                "reason": "临时文件或备份文件，通常可安全删除",
                "confidence": 0.9,
                "size_threshold": 1024 * 1024  # 1MB
            },
            {
                "name": "安装包",
                "pattern": r"\.(msi|exe|setup|install)$",
                "risk": RiskLevel.MEDIUM,
                "reason": "安装程序文件，安装完成后可删除",
                "confidence": 0.8,
                "size_threshold": 10 * 1024 * 1024  # 10MB
            },
            {
                "name": "下载文件",
                "pattern": r"\\Downloads\\",
                "risk": RiskLevel.MEDIUM,
                "reason": "下载文件夹中的文件，可能不再需要",
                "confidence": 0.7,
                "size_threshold": 50 * 1024 * 1024  # 50MB
            },
            {
                "name": "缓存文件",
                "pattern": r"\\cache\\|\\Cache\\|\\AppData\\Local\\.*\\Cache",
                "risk": RiskLevel.LOW,
                "reason": "应用程序缓存，可安全清理",
                "confidence": 0.85,
                "size_threshold": 5 * 1024 * 1024  # 5MB
            },
            {
                "name": "日志文件",
                "pattern": r"\.(log|logs|txt)$",
                "risk": RiskLevel.LOW,
                "reason": "日志文件，通常可安全删除",
                "confidence": 0.75,
                "size_threshold": 2 * 1024 * 1024  # 2MB
            },
            {
                "name": "媒体文件",
                "pattern": r"\.(mp4|avi|mkv|mov|mp3|wav|flac)$",
                "risk": RiskLevel.HIGH,
                "reason": "媒体文件，可能包含重要内容",
                "confidence": 0.6,
                "size_threshold": 100 * 1024 * 1024  # 100MB
            },
            {
                "name": "文档文件",
                "pattern": r"\.(doc|docx|pdf|xls|xlsx|ppt|pptx)$",
                "risk": RiskLevel.HIGH,
                "reason": "文档文件，可能包含重要数据",
                "confidence": 0.7,
                "size_threshold": 10 * 1024 * 1024  # 10MB
            },
            {
                "name": "系统文件",
                "pattern": r"\\Windows\\|\\System32\\|\\Program Files\\",
                "risk": RiskLevel.CRITICAL,
                "reason": "系统文件，删除可能导致系统不稳定",
                "confidence": 0.95,
                "size_threshold": 0  # 任何大小都标记为关键风险
            },
            {
                "name": "游戏文件",
                "pattern": r"\\Steam\\|\\Epic Games\\|\\Games\\",
                "risk": RiskLevel.MEDIUM,
                "reason": "游戏文件，可重新下载但较大",
                "confidence": 0.65,
                "size_threshold": 500 * 1024 * 1024  # 500MB
            },
            {
                "name": "压缩文件",
                "pattern": r"\.(zip|rar|7z|tar|gz)$",
                "risk": RiskLevel.MEDIUM,
                "reason": "压缩文件，可能已解压或不再需要",
                "confidence": 0.7,
                "size_threshold": 20 * 1024 * 1024  # 20MB
            }
        ]
    
    def analyze_files(self, files: List[FileInfo]) -> Tuple[List[DeletionRecommendation], List[str]]:
        """
        使用规则引擎分析文件
        
        Args:
            files: 文件信息列表
            
        Returns:
            Tuple[List[DeletionRecommendation], List[str]]: (删除建议列表, 警告信息列表)
        """
        recommendations = []
        warnings = []
        
        for file_info in files:
            rule, score = self._match_rules(file_info)
            if rule and score > 0.5:  # 置信度阈值
                recommendation = self._create_recommendation(file_info, rule, score)
                recommendations.append(recommendation)
        
        # 按风险等级和分数排序
        recommendations.sort(
            key=lambda r: (self._risk_priority(r.risk_level), -r.confidence)
        )
        
        return recommendations, warnings
    
    def _match_rules(self, file_info: FileInfo) -> Tuple[Optional[Dict], float]:
        """
        为文件匹配最佳规则
        
        Args:
            file_info: 文件信息
            
        Returns:
            Tuple[Optional[Dict], float]: (匹配的规则, 匹配分数)
        """
        best_rule = None
        best_score = 0.0
        
        file_path = str(file_info.path).lower()
        file_size = file_info.size
        
        for rule in self.rules:
            score = self._calculate_rule_score(file_info, rule)
            if score > best_score:
                best_score = score
                best_rule = rule
        
        return best_rule, best_score
    
    def _calculate_rule_score(self, file_info: FileInfo, rule: Dict) -> float:
        """
        计算规则匹配分数
        
        Args:
            file_info: 文件信息
            rule: 规则
            
        Returns:
            float: 匹配分数 (0-1)
        """
        file_path = str(file_info.path).lower()
        pattern = rule["pattern"].lower()
        
        # 检查模式匹配
        if not re.search(pattern, file_path, re.IGNORECASE):
            return 0.0
        
        # 基础分数
        score = rule["confidence"]
        
        # 根据文件大小调整分数
        size_threshold = rule.get("size_threshold", 0)
        if size_threshold > 0:
            if file_info.size >= size_threshold * 5:
                # 文件非常大，增加分数
                score *= 1.2
            elif file_info.size < size_threshold * 0.5:
                # 文件较小，降低分数
                score *= 0.8
        
        # 根据文件年龄调整分数（如果有修改时间）
        if file_info.modified_time:
            from datetime import datetime
            age_days = (datetime.now() - file_info.modified_time).days
            if age_days > 365:  # 超过一年
                score *= 1.1
            elif age_days < 7:  # 最近一周
                score *= 0.9
        
        return min(score, 1.0)  # 确保不超过1.0
    
    def _create_recommendation(self, file_info: FileInfo, rule: Dict, score: float) -> DeletionRecommendation:
        """
        创建删除建议
        
        Args:
            file_info: 文件信息
            rule: 匹配的规则
            score: 匹配分数
            
        Returns:
            DeletionRecommendation: 删除建议
        """
        return DeletionRecommendation(
            file=file_info,
            reason=rule["reason"],
            risk_level=rule["risk"],
            confidence=score,
            potential_savings=file_info.size
        )
    
    def _risk_priority(self, risk: RiskLevel) -> int:
        """
        获取风险等级优先级（用于排序）
        
        Args:
            risk: 风险等级
            
        Returns:
            int: 优先级数值（越小优先级越高）
        """
        priority_map = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4
        }
        return priority_map.get(risk, 5)
    
    def get_rules(self) -> List[Dict]:
        """
        获取所有规则
        
        Returns:
            List[Dict]: 规则列表
        """
        return self.rules.copy()
    
    def add_rule(self, rule: Dict) -> bool:
        """
        添加新规则
        
        Args:
            rule: 规则字典，必须包含name, pattern, risk, reason, confidence
            
        Returns:
            bool: 是否添加成功
        """
        required_fields = ["name", "pattern", "risk", "reason", "confidence"]
        if not all(field in rule for field in required_fields):
            return False
        
        # 验证风险等级
        if not isinstance(rule["risk"], RiskLevel):
            try:
                rule["risk"] = RiskLevel(rule["risk"])
            except ValueError:
                return False
        
        # 验证置信度范围
        if not 0 <= rule["confidence"] <= 1:
            return False
        
        self.rules.append(rule)
        return True
    
    def clear_rules(self):
        """清空所有规则"""
        self.rules = []
    
    def reset_to_default(self):
        """重置为默认规则"""
        self.rules = self._initialize_rules()