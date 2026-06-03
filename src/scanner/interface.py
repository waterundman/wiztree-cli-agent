from abc import ABC, abstractmethod
from typing import List

try:
    from ..models.scan_result import ScanResult
    from .options import ScanOptions
except ImportError:
    from models.scan_result import ScanResult
    from scanner.options import ScanOptions


class ScannerInterface(ABC):
    """扫描器接口"""
    
    @abstractmethod
    def scan(self, target: str, options: ScanOptions) -> ScanResult:
        pass
    
    @abstractmethod
    def get_supported_options(self) -> List[str]:
        pass