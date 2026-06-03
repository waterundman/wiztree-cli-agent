"""扫描器模块测试"""
import pytest
from pathlib import Path
from src.scanner import WizTreeScanner, PathValidator, ScanProgress
from src.scanner.options import ScanOptions
from src.models import FileInfo, ScanResult


class TestPathValidator:
    def test_validate_existing_path(self, tmp_path):
        validator = PathValidator()
        is_valid, error = validator.validate(str(tmp_path))
        assert is_valid
        assert error is None

    def test_validate_nonexistent_path(self):
        validator = PathValidator()
        is_valid, error = validator.validate("Z:\\nonexistent\\path")
        assert not is_valid
        assert error is not None

    def test_validate_empty_path(self):
        validator = PathValidator()
        is_valid, error = validator.validate("")
        assert not is_valid

    def test_validate_deep_search_existing_dir(self, tmp_path):
        validator = PathValidator()
        is_valid, error, code = validator.validate_deep_search(str(tmp_path))
        assert is_valid
        assert code is None

    def test_validate_deep_search_nonexistent(self):
        validator = PathValidator()
        is_valid, error, code = validator.validate_deep_search("Z:\\nonexistent\\path")
        assert not is_valid
        assert code is not None

    def test_get_available_drives(self):
        validator = PathValidator()
        drives = validator.get_available_drives()
        assert isinstance(drives, list)
        assert len(drives) > 0

    def test_get_path_info(self, tmp_path):
        validator = PathValidator()
        info = validator.get_path_info(str(tmp_path))
        assert info['exists']
        assert info['is_directory']
        assert info['is_readable']


class TestWizTreeScanner:
    def test_scanner_interface(self):
        scanner = WizTreeScanner("dummy.exe")
        assert hasattr(scanner, 'scan')
        assert hasattr(scanner, 'cancel')
        assert hasattr(scanner, 'is_scanning')

    def test_scanner_defaults(self):
        scanner = WizTreeScanner()
        assert scanner._wiztree_path is None
        assert not scanner.is_scanning
        assert scanner.progress_info is None

    def test_scanner_set_wiztree_path(self):
        scanner = WizTreeScanner()
        scanner.set_wiztree_path("/some/path.exe")
        assert scanner._wiztree_path == "/some/path.exe"

    def test_scanner_set_timeout(self):
        scanner = WizTreeScanner()
        scanner.set_timeout(600)
        assert scanner._timeout == 600

    def test_scanner_get_supported_options(self):
        scanner = WizTreeScanner()
        options = scanner.get_supported_options()
        assert isinstance(options, list)
        assert 'min_size' in options


class TestScanOptions:
    def test_default_options(self):
        options = ScanOptions()
        assert options is not None

    def test_options_to_dict(self):
        options = ScanOptions()
        d = options.to_dict()
        assert isinstance(d, dict)
