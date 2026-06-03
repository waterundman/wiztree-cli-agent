"""Unit tests for model layer"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import FileInfo, ScanResult, AnalysisResult, DeletionRecommendation, RiskLevel
from src.scanner.options import ScanOptions


class TestFileInfo:
    """Test FileInfo dataclass"""
    
    def test_creation(self):
        fi = FileInfo(
            path=Path("test.txt"),
            size=1024,
            modified_time=datetime.now(),
            is_directory=False,
            extension=".txt"
        )
        assert fi.name == "test.txt"
        assert fi.size_human_readable == "1.00 KB"
        assert fi.extension == ".txt"
    
    def test_size_formats(self):
        fi = FileInfo(path=Path("a"), size=500, modified_time=datetime.now())
        assert fi.size_human_readable == "500 B"
        
        fi.size = 1024 * 1024
        assert fi.size_human_readable == "1.00 MB"
        
        fi.size = 1024 * 1024 * 1024
        assert fi.size_human_readable == "1.00 GB"


class TestScanResult:
    """Test ScanResult dataclass"""
    
    def test_creation(self):
        files = [
            FileInfo(path=Path("a.txt"), size=100, modified_time=datetime.now()),
            FileInfo(path=Path("b.txt"), size=200, modified_time=datetime.now()),
        ]
        sr = ScanResult(
            target_path=Path("."),
            files=files,
            scan_time=datetime.now(),
            duration_seconds=1.0,
            total_files=2,
            total_directories=0,
            total_size=300
        )
        assert sr.total_size_human_readable == "300 B"
        assert sr.average_file_size == 150
    
    def test_get_largest_files(self):
        files = [
            FileInfo(path=Path("small.txt"), size=100, modified_time=datetime.now()),
            FileInfo(path=Path("large.txt"), size=1000, modified_time=datetime.now()),
            FileInfo(path=Path("medium.txt"), size=500, modified_time=datetime.now()),
        ]
        sr = ScanResult(
            target_path=Path("."),
            files=files,
            scan_time=datetime.now(),
            duration_seconds=1.0,
            total_files=3,
            total_directories=0,
            total_size=1600
        )
        largest = sr.get_largest_files(2)
        assert len(largest) == 2
        assert largest[0].name == "large.txt"
        assert largest[1].name == "medium.txt"


class TestAnalysisResult:
    """Test AnalysisResult dataclass"""
    
    def test_creation(self):
        fi = FileInfo(path=Path("test.txt"), size=1024, modified_time=datetime.now())
        rec = DeletionRecommendation(
            file=fi,
            reason="test",
            risk_level=RiskLevel.LOW,
            confidence=0.9,
            potential_savings=1024
        )
        ar = AnalysisResult(
            recommendations=[rec],
            total_potential_savings=1024,
            analysis_time=datetime.now(),
            duration_seconds=0.5
        )
        assert ar.total_potential_savings_human_readable == "1.00 KB"
        assert len(ar.recommendations) == 1


class TestScanOptions:
    """Test ScanOptions dataclass"""
    
    def test_defaults(self):
        so = ScanOptions()
        assert so.max_depth is None
        assert so.include_hidden is False
        assert so.follow_symlinks is False
    
    def test_to_dict(self):
        so = ScanOptions(max_depth=5, include_hidden=True)
        d = so.to_dict()
        assert d['max_depth'] == 5
        assert d['include_hidden'] is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])