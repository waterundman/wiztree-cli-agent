"""CLI脚本化支持测试"""
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent))

from cli import WizTreeCLI, OutputFormatter, main, EXIT_SUCCESS, EXIT_ERROR, EXIT_WARNING


class TestExitCodes:
    """测试标准退出码常量"""

    def test_exit_success_is_zero(self):
        assert EXIT_SUCCESS == 0

    def test_exit_error_is_one(self):
        assert EXIT_ERROR == 1

    def test_exit_warning_is_two(self):
        assert EXIT_WARNING == 2


class TestOutputFormatter:
    """测试输出格式化器"""

    def test_quiet_suppresses_info(self):
        formatter = OutputFormatter(quiet=True)
        captured = StringIO()
        with patch("sys.stdout", captured):
            formatter.info("should not appear")
        assert captured.getvalue() == ""

    def test_quiet_suppresses_progress(self):
        formatter = OutputFormatter(quiet=True)
        captured = StringIO()
        with patch("sys.stdout", captured):
            formatter.progress("should not appear")
        assert captured.getvalue() == ""

    def test_quiet_suppresses_success(self):
        formatter = OutputFormatter(quiet=True)
        captured = StringIO()
        with patch("sys.stdout", captured):
            formatter.success("should not appear")
        assert captured.getvalue() == ""

    def test_quiet_does_not_suppress_error(self):
        formatter = OutputFormatter(quiet=True)
        captured = StringIO()
        with patch("sys.stderr", captured):
            formatter.error("must appear")
        assert "must appear" in captured.getvalue()

    def test_non_quiet_shows_info(self):
        formatter = OutputFormatter(quiet=False, no_color=True)
        captured = StringIO()
        with patch("sys.stdout", captured):
            formatter.info("visible")
        assert "visible" in captured.getvalue()

    def test_json_output(self):
        formatter = OutputFormatter(json_output=True)
        captured = StringIO()
        with patch("sys.stdout", captured):
            formatter.output_json({"key": "value"})
        output = captured.getvalue()
        data = json.loads(output)
        assert data["key"] == "value"

    def test_no_color_flag(self):
        formatter = OutputFormatter(no_color=True)
        result = formatter.red("test")
        assert result == "test"
        assert "\033[" not in result

    def test_colorize_disabled(self):
        formatter = OutputFormatter(no_color=True)
        assert formatter.green("ok") == "ok"
        assert formatter.yellow("warn") == "warn"
        assert formatter.cyan("info") == "info"

    def test_warning_quiet_suppressed(self):
        formatter = OutputFormatter(quiet=True)
        captured = StringIO()
        with patch("sys.stdout", captured):
            formatter.warning("suppressed")
        assert captured.getvalue() == ""

    def test_warning_non_quiet_shown(self):
        formatter = OutputFormatter(quiet=False, no_color=True)
        captured = StringIO()
        with patch("sys.stdout", captured):
            formatter.warning("visible")
        assert "visible" in captured.getvalue()


class TestWizTreeCLIScriptable:
    """测试CLI脚本化参数"""

    def test_cli_accepts_quiet_flag(self):
        cli = WizTreeCLI(quiet=True)
        assert cli.output.quiet is True

    def test_cli_accepts_json_flag(self):
        cli = WizTreeCLI(json_output=True)
        assert cli.output.json_output is True

    def test_cli_accepts_no_color_flag(self):
        cli = WizTreeCLI(no_color=True)
        assert cli.output.no_color is True

    def test_cli_defaults_verbose(self):
        cli = WizTreeCLI()
        assert cli.output.quiet is False
        assert cli.output.json_output is False


class TestMainFunction:
    """测试main函数返回退出码"""

    @patch("sys.argv", ["cli.py", "--cli", "--quiet"])
    def test_main_returns_int(self):
        result = main()
        assert isinstance(result, int)

    @patch("sys.argv", ["cli.py", "--cli", "--quiet"])
    def test_main_cli_quiet_returns_success(self):
        result = main()
        assert result == EXIT_SUCCESS

    @patch("sys.argv", ["cli.py", "--scan", "Z:\\nonexistent", "--quiet"])
    def test_main_scan_invalid_path_returns_error(self):
        result = main()
        assert result == EXIT_ERROR

    @patch("sys.argv", ["cli.py", "--cli"])
    def test_main_cli_mode_returns_success(self):
        result = main()
        assert result == EXIT_SUCCESS

    @patch("sys.argv", ["cli.py"])
    @patch("cli.WizTreeCLI")
    def test_main_keyboard_interrupt_returns_warning(self, mock_cli_cls):
        mock_cli = MagicMock()
        mock_cli.interactive_mode.side_effect = KeyboardInterrupt()
        mock_cli_cls.return_value = mock_cli
        result = main()
        assert result == EXIT_WARNING

    @patch("sys.argv", ["cli.py", "--cli", "--json", "--quiet"])
    def test_main_combined_flags(self):
        result = main()
        assert result == EXIT_SUCCESS


class TestJSONOutput:
    """测试JSON输出格式"""

    def test_output_results_json_format(self):
        cli = WizTreeCLI(json_output=True, quiet=False, no_color=True)
        mock_rec = MagicMock()
        mock_rec.file.path = Path("C:\\test\\file.tmp")
        mock_rec.file.size = 1024
        mock_rec.file.size_human_readable = "1.00 KB"
        mock_rec.risk_level.value = "LOW"
        mock_rec.reason = "Temporary file"

        captured = StringIO()
        with patch("sys.stdout", captured):
            cli.show_results([mock_rec], limit=10)

        data = json.loads(captured.getvalue())
        assert "recommendations" in data
        assert data["total"] == 1
        assert data["recommendations"][0]["path"] == "C:\\test\\file.tmp"
        assert data["recommendations"][0]["size"] == 1024
        assert data["recommendations"][0]["risk_level"] == "LOW"

    def test_output_results_json_empty(self):
        cli = WizTreeCLI(json_output=True, quiet=False, no_color=True)
        captured = StringIO()
        with patch("sys.stdout", captured):
            cli.show_results([], limit=10)

        data = json.loads(captured.getvalue())
        assert data["recommendations"] == []
        assert data["total"] == 0
