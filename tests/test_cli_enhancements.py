"""CLI enhancements tests - batch scanning"""
import pytest
import os
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

from cli import WizTreeCLI, OutputFormatter
from src.models import FileInfo, ScanResult
from src.scanner.options import ScanOptions


def _make_cli_mock():
    cli = WizTreeCLI.__new__(WizTreeCLI)
    cli.output = MagicMock(spec=OutputFormatter)
    cli.validator = MagicMock()
    cli.scanner = MagicMock()
    cli.rule_engine = MagicMock()
    cli.safety = MagicMock()
    return cli


def _make_file_info(path_str: str, size: int) -> FileInfo:
    return FileInfo(
        path=Path(path_str),
        size=size,
        modified_time=datetime.now(),
        created_time=None,
        is_directory=False,
        extension=Path(path_str).suffix.lower(),
        depth=0,
        parent_path=Path(path_str).parent,
    )


def _make_scan_result(target: str, files, duration: float = 1.0) -> ScanResult:
    total_size = sum(f.size for f in files)
    return ScanResult(
        target_path=Path(target),
        files=files,
        scan_time=datetime.now(),
        duration_seconds=duration,
        total_files=len(files),
        total_directories=0,
        total_size=total_size,
        scan_options=None,
        errors=[],
    )


class TestBatchArgumentParsing:
    """Test --batch and --batch-file argument parsing"""

    def test_batch_arg_accepts_multiple_dirs(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--batch', nargs='+', metavar='DIR')
        parser.add_argument('--batch-file', type=str, metavar='FILE')
        args = parser.parse_args(['--batch', 'C:\\Users', 'D:\\Temp'])
        assert args.batch == ['C:\\Users', 'D:\\Temp']
        assert args.batch_file is None

    def test_batch_file_arg(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--batch', nargs='+', metavar='DIR')
        parser.add_argument('--batch-file', type=str, metavar='FILE')
        args = parser.parse_args(['--batch-file', 'dirs.txt'])
        assert args.batch is None
        assert args.batch_file == 'dirs.txt'

    def test_batch_combined(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--batch', nargs='+', metavar='DIR')
        parser.add_argument('--batch-file', type=str, metavar='FILE')
        args = parser.parse_args(['--batch', 'A', '--batch-file', 'dirs.txt'])
        assert args.batch == ['A']
        assert args.batch_file == 'dirs.txt'


class TestBatchScanMethod:
    """Test WizTreeCLI.scan_batch()"""

    def test_scan_batch_empty_paths(self):
        cli = _make_cli_mock()
        result = cli.scan_batch([])
        assert result is None

    def test_scan_batch_merges_files(self):
        cli = _make_cli_mock()
        cli.validator.validate = MagicMock(return_value=(True, None))

        files_a = [_make_file_info("a.txt", 100), _make_file_info("b.txt", 200)]
        files_b = [_make_file_info("c.txt", 300)]
        cli.scanner.scan = MagicMock(side_effect=[
            _make_scan_result("dir_a", files_a, 0.5),
            _make_scan_result("dir_b", files_b, 0.3),
        ])

        result = cli.scan_batch(["dir_a", "dir_b"])
        assert result is not None
        assert result.total_files == 3
        assert result.total_size == 600
        assert len(result.files) == 3

    def test_scan_batch_sorted_by_size_desc(self):
        cli = _make_cli_mock()
        cli.validator.validate = MagicMock(return_value=(True, None))

        files = [_make_file_info("a.txt", 10), _make_file_info("b.txt", 500), _make_file_info("c.txt", 50)]
        cli.scanner.scan = MagicMock(return_value=_make_scan_result("dir", files, 0.1))

        result = cli.scan_batch(["dir"])
        sizes = [f.size for f in result.files]
        assert sizes == sorted(sizes, reverse=True)

    def test_scan_batch_invalid_path_skipped(self):
        cli = _make_cli_mock()
        cli.validator.validate = MagicMock(side_effect=[(True, None), (False, "not found")])

        files = [_make_file_info("a.txt", 100)]
        cli.scanner.scan = MagicMock(return_value=_make_scan_result("dir_a", files, 0.1))

        result = cli.scan_batch(["dir_a", "dir_invalid"])
        assert result is not None
        assert result.total_files == 1
        assert len(result.errors) == 1
        assert "not found" in result.errors[0]

    def test_scan_batch_all_invalid_returns_none(self):
        cli = _make_cli_mock()
        cli.validator.validate = MagicMock(return_value=(False, "bad"))

        result = cli.scan_batch(["bad1", "bad2"])
        assert result is None

    def test_scan_batch_scan_exception_captured(self):
        cli = _make_cli_mock()
        cli.validator.validate = MagicMock(return_value=(True, None))
        cli.scanner.scan = MagicMock(side_effect=RuntimeError("boom"))

        result = cli.scan_batch(["dir_a"])
        assert result is None

    def test_scan_batch_partial_failure(self):
        cli = _make_cli_mock()
        cli.validator.validate = MagicMock(return_value=(True, None))

        cli.scanner.scan = MagicMock(side_effect=[
            _make_scan_result("dir_a", [_make_file_info("a.txt", 100)], 0.1),
            RuntimeError("boom"),
        ])

        result = cli.scan_batch(["dir_a", "dir_b"])
        assert result is not None
        assert result.total_files == 1
        assert len(result.errors) == 1

    def test_scan_batch_single_path(self):
        cli = _make_cli_mock()
        cli.validator.validate = MagicMock(return_value=(True, None))

        files = [_make_file_info("x.txt", 42)]
        cli.scanner.scan = MagicMock(return_value=_make_scan_result("single", files, 0.2))

        result = cli.scan_batch(["single"])
        assert result is not None
        assert result.target_path == Path("single")
        assert result.total_files == 1


class TestBatchFileReading:
    """Test reading directory list from --batch-file"""

    def test_batch_file_reads_paths(self, tmp_path):
        batch_file = tmp_path / "dirs.txt"
        batch_file.write_text("C:\\Users\nD:\\Temp\n# comment\n\nE:\\Data\n", encoding="utf-8")

        paths = []
        with open(str(batch_file), 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    paths.append(line)

        assert paths == ["C:\\Users", "D:\\Temp", "E:\\Data"]

    def test_batch_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            with open("nonexistent_batch_file.txt", 'r') as f:
                f.read()

    def test_batch_file_empty(self, tmp_path):
        batch_file = tmp_path / "empty.txt"
        batch_file.write_text("", encoding="utf-8")

        paths = []
        with open(str(batch_file), 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    paths.append(line)

        assert paths == []
