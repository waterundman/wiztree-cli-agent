"""UI接口定义"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class UIInterface(ABC):
    """UI接口抽象基类"""
    
    @abstractmethod
    def show_results(self, results: Any) -> None:
        """显示结果"""
        pass
        
    @abstractmethod
    def update_progress(self, progress: float) -> None:
        """更新进度"""
        pass
        
    @abstractmethod
    def show_error(self, message: str) -> None:
        """显示错误"""
        pass
