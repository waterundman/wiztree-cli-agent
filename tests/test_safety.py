"""安全模块测试"""
import pytest
from pathlib import Path
from src.safety import Blocklist, FileValidator, AuditLogger
from src.safety.file_validator import ValidationResult


class TestBlocklist:
    def test_is_blocked_system_path(self):
        blocklist = Blocklist()
        assert blocklist.is_blocked("C:\\Windows\\System32")

    def test_is_blocked_windows_root(self):
        blocklist = Blocklist()
        assert blocklist.is_blocked("C:\\Windows")

    def test_is_not_blocked_user_path(self):
        blocklist = Blocklist()
        assert not blocklist.is_blocked("C:\\Users\\test\\Documents")

    def test_add_custom_path(self):
        blocklist = Blocklist()
        blocklist.add_path("C:\\MyBlockedFolder")
        assert blocklist.is_blocked("C:\\MyBlockedFolder")

    def test_remove_path(self):
        blocklist = Blocklist()
        blocklist.add_path("C:\\TempBlocked")
        assert blocklist.remove_path("C:\\TempBlocked")
        assert not blocklist.is_blocked("C:\\TempBlocked")

    def test_remove_nonexistent_path(self):
        blocklist = Blocklist()
        assert not blocklist.remove_path("C:\\NeverExisted")

    def test_contains_operator(self):
        blocklist = Blocklist()
        assert "C:\\Windows" in blocklist

    def test_len(self):
        blocklist = Blocklist()
        assert len(blocklist) > 0

    def test_custom_blocked_paths(self):
        custom = ["D:\\CustomBlocked"]
        blocklist = Blocklist(custom_blocked_paths=custom)
        assert blocklist.is_blocked("D:\\CustomBlocked")


class TestFileValidator:
    def test_validate_existing_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        validator = FileValidator()
        result, message = validator.validate(str(test_file))
        assert result == ValidationResult.VALID

    def test_validate_nonexistent_file(self):
        validator = FileValidator()
        result, message = validator.validate("Z:\\nonexistent\\file.txt")
        assert result == ValidationResult.NOT_FOUND

    def test_validate_directory(self, tmp_path):
        validator = FileValidator()
        result, message = validator.validate(str(tmp_path))
        assert result == ValidationResult.VALID

    def test_is_safe_to_delete(self, tmp_path):
        test_file = tmp_path / "safe.txt"
        test_file.write_text("safe to delete")
        validator = FileValidator()
        assert validator.is_safe_to_delete(str(test_file))

    def test_validate_batch(self, tmp_path):
        test_file = tmp_path / "batch.txt"
        test_file.write_text("batch test")
        validator = FileValidator()
        results = validator.validate_batch([str(test_file)])
        assert 'valid' in results
        assert len(results['valid']) == 1

    def test_get_detailed_report(self, tmp_path):
        test_file = tmp_path / "report.txt"
        test_file.write_text("report test")
        validator = FileValidator()
        report = validator.get_detailed_report(str(test_file))
        assert 'file_info' in report
        assert 'validation_result' in report
        assert report['is_safe']
