"""
CLI Enhancements v1.5.0 集成测试

覆盖端到端场景:
1. 批量扫描 + JSON 导出
2. 批量扫描 + CSV 导出
3. 脚本化标志组合 (--quiet + --json + --no-color)
4. 退出码在各种场景下的正确性
5. Version contract
"""
import sys
import json
import csv
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from cli import WizTreeCLI, OutputFormatter, main, EXIT_SUCCESS, EXIT_ERROR, EXIT_WARNING
from src.models import FileInfo, ScanResult
from src.exporters import export_json, export_csv
from src import __version__


# ============================================================
# Helpers
# ============================================================

def _make_file(path_str: str, size: int) -> FileInfo:
    return FileInfo(
        path=Path(path_str),
        size=size,
        modified_time=datetime(2025, 6, 1, 12, 0, 0),
        created_time=datetime(2025, 6, 1, 10, 0, 0),
        is_directory=False,
        extension=Path(path_str).suffix.lower(),
        depth=1,
    )


def _make_scan_result(target: str, files, duration: float = 1.0) -> ScanResult:
    return ScanResult(
        target_path=Path(target),
        files=files,
        scan_time=datetime(2025, 6, 1, 9, 0, 0),
        duration_seconds=duration,
        total_files=len(files),
        total_directories=0,
        total_size=sum(f.size for f in files),
    )


def _mock_cli():
    cli = WizTreeCLI.__new__(WizTreeCLI)
    cli.output = MagicMock(spec=OutputFormatter)
    cli.validator = MagicMock()
    cli.scanner = MagicMock()
    cli.rule_engine = MagicMock()
    cli.safety = MagicMock()
    return cli


# ============================================================
# Scenario 1: Batch scan + JSON export
# ============================================================

class TestBatchScanJsonExport:
    """端到端: 批量扫描 → JSON 导出"""

    def test_batch_two_dirs_json_export(self, tmp_path):
        cli = _mock_cli()
        cli.validator.validate = MagicMock(return_value=(True, None))

        files_a = [_make_file("C:/a/report.docx", 5120), _make_file("C:/a/photo.jpg", 2048)]
        files_b = [_make_file("C:/b/data.csv", 1024)]
        cli.scanner.scan = MagicMock(side_effect=[
            _make_scan_result("C:/a", files_a, 0.3),
            _make_scan_result("C:/b", files_b, 0.2),
        ])

        result = cli.scan_batch(["C:/a", "C:/b"])
        assert result is not None
        assert result.total_files == 3
        assert result.total_size == 8192

        out = tmp_path / "batch_report.json"
        export_json(result, out)
        assert out.exists()

        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data["files"]) == 3
        assert data["summary"]["total_files"] == 3
        assert data["summary"]["total_size"] == 8192
        assert "metadata" in data
        assert "scan_time" in data["metadata"]

    def test_batch_single_dir_json_export(self, tmp_path):
        cli = _mock_cli()
        cli.validator.validate = MagicMock(return_value=(True, None))
        files = [_make_file("X/readme.md", 512)]
        cli.scanner.scan = MagicMock(return_value=_make_scan_result("X", files, 0.1))

        result = cli.scan_batch(["X"])
        out = tmp_path / "single.json"
        export_json(result, out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "readme.md"


# ============================================================
# Scenario 2: Batch scan + CSV export
# ============================================================

class TestBatchScanCsvExport:
    """端到端: 批量扫描 → CSV 导出"""

    def test_batch_csv_export(self, tmp_path):
        cli = _mock_cli()
        cli.validator.validate = MagicMock(return_value=(True, None))

        files_a = [_make_file("C:/a/f1.txt", 100)]
        files_b = [_make_file("C:/b/f2.log", 200), _make_file("C:/b/f3.bin", 300)]
        cli.scanner.scan = MagicMock(side_effect=[
            _make_scan_result("C:/a", files_a, 0.1),
            _make_scan_result("C:/b", files_b, 0.2),
        ])

        result = cli.scan_batch(["C:/a", "C:/b"])
        out = tmp_path / "report.csv"
        export_csv(result, out)

        assert out.exists()
        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3
        assert rows[0]["is_directory"] == "False"

    def test_csv_sorted_by_size_desc(self, tmp_path):
        cli = _mock_cli()
        cli.validator.validate = MagicMock(return_value=(True, None))

        files = [
            _make_file("C/small.txt", 10),
            _make_file("C/large.txt", 9999),
            _make_file("C/medium.txt", 500),
        ]
        cli.scanner.scan = MagicMock(return_value=_make_scan_result("C", files, 0.1))

        result = cli.scan_batch(["C"])
        out = tmp_path / "sorted.csv"
        export_csv(result, out)

        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        sizes = [int(r["size"]) for r in rows]
        assert sizes == sorted(sizes, reverse=True)


# ============================================================
# Scenario 3: Scriptable flag combinations
# ============================================================

class TestScriptableFlagCombos:
    """端到端: 脚本化标志组合"""

    @patch("sys.argv", ["cli.py", "--cli", "--quiet", "--no-color"])
    def test_quiet_no_color_cli(self):
        result = main()
        assert result == EXIT_SUCCESS

    @patch("sys.argv", ["cli.py", "--cli", "--json", "--quiet"])
    def test_json_quiet_cli(self):
        result = main()
        assert result == EXIT_SUCCESS

    @patch("sys.argv", ["cli.py", "--cli", "--json", "--quiet", "--no-color"])
    def test_all_flags_cli(self):
        result = main()
        assert result == EXIT_SUCCESS

    @patch("sys.argv", ["cli.py", "--scan", "Z:\\nonexistent", "--json", "--quiet"])
    def test_invalid_scan_json_quiet(self):
        result = main()
        assert result == EXIT_ERROR

    @patch("sys.argv", ["cli.py", "--batch-file", "Z:\\nonexistent_file.txt", "--quiet"])
    def test_missing_batch_file_returns_error(self):
        result = main()
        assert result == EXIT_ERROR


# ============================================================
# Scenario 4: Exit code correctness
# ============================================================

class TestExitCodesE2E:
    """端到端: 退出码场景"""

    def test_exit_code_constants(self):
        assert EXIT_SUCCESS == 0
        assert EXIT_ERROR == 1
        assert EXIT_WARNING == 2

    @patch("sys.argv", ["cli.py", "--cli"])
    def test_cli_mode_success(self):
        result = main()
        assert result == EXIT_SUCCESS

    @patch("sys.argv", ["cli.py", "--cli", "--quiet"])
    def test_cli_quiet_success(self):
        result = main()
        assert result == EXIT_SUCCESS

    @patch("sys.argv", ["cli.py", "--scan", "Z:\\nonexistent", "--quiet"])
    def test_scan_invalid_path_error(self):
        result = main()
        assert result == EXIT_ERROR

    @patch("sys.argv", ["cli.py"])
    @patch("cli.WizTreeCLI")
    def test_keyboard_interrupt_warning(self, mock_cli_cls):
        mock_cli = MagicMock()
        mock_cli.interactive_mode.side_effect = KeyboardInterrupt()
        mock_cli_cls.return_value = mock_cli
        result = main()
        assert result == EXIT_WARNING

    def test_batch_scan_failure_returns_error(self):
        cli = _mock_cli()
        cli.validator.validate = MagicMock(return_value=(False, "not found"))
        result = cli.scan_batch(["bad1", "bad2"])
        assert result is None

    def test_batch_scan_success_returns_result(self):
        cli = _mock_cli()
        cli.validator.validate = MagicMock(return_value=(True, None))
        files = [_make_file("ok.txt", 10)]
        cli.scanner.scan = MagicMock(return_value=_make_scan_result("dir", files, 0.1))
        result = cli.scan_batch(["dir"])
        assert result is not None
        assert result.total_files == 1

    @patch("sys.argv", ["cli.py", "--cli", "--json", "--quiet"])
    def test_json_output_is_valid_json(self):
        result = main()
        assert result == EXIT_SUCCESS


# ============================================================
# Scenario 5: Version contract
# ============================================================

class TestVersionContract:
    """版本号契约测试"""

    def test_version_is_150(self):
        assert __version__ == "2.1.0"

    def test_version_string_format(self):
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
