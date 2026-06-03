#!/usr/bin/env python3
"""
WizTree CLI Agent - Command Line Interface
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List

# Add src to path (only for source runs; PyInstaller handles this)
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.scanner import WizTreeScanner, PathValidator, DeepSearcher, ScanOptions
from src.analyzer import RuleEngine
from src.safety import ComprehensiveSafetyManager
from src.models import FileInfo, ScanResult, AnalysisResult

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_WARNING = 2


class OutputFormatter:
    """输出格式化器，支持静默模式、JSON输出和颜色控制"""

    def __init__(self, quiet: bool = False, json_output: bool = False, no_color: bool = False):
        self.quiet = quiet
        self.json_output = json_output
        self.no_color = no_color or not self._supports_color()

    @staticmethod
    def _supports_color() -> bool:
        if os.environ.get("NO_COLOR"):
            return False
        if not hasattr(sys.stdout, "isatty"):
            return False
        return sys.stdout.isatty()

    def _colorize(self, text: str, color_code: str) -> str:
        if self.no_color:
            return text
        return f"\033[{color_code}m{text}\033[0m"

    def red(self, text: str) -> str:
        return self._colorize(text, "31")

    def green(self, text: str) -> str:
        return self._colorize(text, "32")

    def yellow(self, text: str) -> str:
        return self._colorize(text, "33")

    def cyan(self, text: str) -> str:
        return self._colorize(text, "36")

    def info(self, message: str):
        if not self.quiet:
            print(message)

    def error(self, message: str):
        print(self.red(f"Error: {message}"), file=sys.stderr)

    def warning(self, message: str):
        if not self.quiet:
            print(self.yellow(f"Warning: {message}"))

    def success(self, message: str):
        if not self.quiet:
            print(self.green(message))

    def progress(self, message: str):
        if not self.quiet:
            print(message)

    def output_json(self, data: dict):
        print(json.dumps(data, indent=2, ensure_ascii=False))

    def output_results(self, recommendations: list, limit: int = 20):
        if self.json_output:
            json_data = []
            for rec in recommendations[:limit]:
                file_info = rec.file
                json_data.append({
                    "path": str(file_info.path),
                    "size": file_info.size,
                    "size_human": file_info.size_human_readable,
                    "risk_level": rec.risk_level.value,
                    "reason": rec.reason,
                })
            self.output_json({"recommendations": json_data, "total": len(recommendations)})
        else:
            self._print_table(recommendations, limit)

    def _print_table(self, recommendations: list, limit: int):
        if not recommendations:
            self.info("No recommendations")
            return

        self.info(f"\nTop {min(limit, len(recommendations))} recommendations:")
        self.info("-" * 80)
        self.info(f"{'File Path':<50} {'Size':<10} {'Risk':<10} {'Reason'}")
        self.info("-" * 80)

        for rec in recommendations[:limit]:
            file_info = rec.file
            risk = rec.risk_level.value
            reason = rec.reason

            size_str = file_info.size_human_readable
            path_display = str(file_info.path)
            if len(path_display) > 48:
                path_display = "..." + path_display[-45:]

            risk_display = risk
            if not self.no_color:
                if risk == "CRITICAL":
                    risk_display = self.red(risk)
                elif risk == "HIGH":
                    risk_display = self.yellow(risk)
                elif risk == "LOW":
                    risk_display = self.green(risk)

            self.info(f"{path_display:<50} {size_str:<10} {risk_display:<10} {reason[:30]}")


class WizTreeCLI:
    """WizTree CLI Agent命令行接口"""

    def __init__(self, quiet: bool = False, json_output: bool = False, no_color: bool = False):
        self.output = OutputFormatter(quiet=quiet, json_output=json_output, no_color=no_color)
        # 使用默认WizTree路径
        wiztree_path = r"W:\WizTree\WizTree64.exe"
        self.scanner = WizTreeScanner(wiztree_path=wiztree_path)
        self.validator = PathValidator()
        self.rule_engine = RuleEngine()
        self.safety = ComprehensiveSafetyManager()

    def scan_directory(self, path: str, options: dict = None):
        """扫描目录"""
        self.output.progress(f"Scanning directory: {path}")

        # 验证路径
        is_valid, error = self.validator.validate(path)
        if not is_valid:
            self.output.error(error)
            return None

        # 创建扫描选项
        scan_options = ScanOptions()
        if options:
            for key, value in options.items():
                if hasattr(scan_options, key):
                    setattr(scan_options, key, value)

        # 执行扫描
        try:
            result = self.scanner.scan(path, scan_options)
            self.output.progress(f"Scan completed: {result.total_files} files, {result.total_directories} directories")
            self.output.progress(f"Total size: {result.total_size_human_readable}")
            return result
        except Exception as e:
            self.output.error(f"Scan failed: {e}")
            return None

    def scan_batch(self, paths: List[str], options: dict = None) -> ScanResult:
        """批量扫描多个目录，合并为统一 ScanResult"""
        if not paths:
            self.output.error("No paths provided for batch scan")
            return None

        all_files = []
        all_errors = []
        total_duration = 0.0
        scan_start = datetime.now()
        scanned = 0

        for i, path in enumerate(paths, 1):
            self.output.progress(f"\n[Batch {i}/{len(paths)}] Scanning: {path}")
            is_valid, error = self.validator.validate(path)
            if not is_valid:
                self.output.warning(f"Skipping invalid path: {error}")
                all_errors.append(f"{path}: {error}")
                continue

            scan_options = ScanOptions()
            if options:
                for key, value in options.items():
                    if hasattr(scan_options, key):
                        setattr(scan_options, key, value)

            try:
                result = self.scanner.scan(path, scan_options)
                all_files.extend(result.files)
                total_duration += result.duration_seconds
                scanned += 1
                self.output.progress(f"  Completed: {result.total_files} files, {result.total_size_human_readable}")
            except Exception as e:
                self.output.error(f"Scan failed: {e}")
                all_errors.append(f"{path}: {e}")

        if scanned == 0:
            self.output.error("All batch scans failed")
            return None

        all_files.sort(key=lambda x: x.size, reverse=True)
        total_size = sum(f.size for f in all_files)
        total_files = len(all_files)
        total_directories = sum(1 for f in all_files if f.is_directory)

        merged = ScanResult(
            target_path=Path(paths[0]) if len(paths) == 1 else Path("BATCH"),
            files=all_files,
            scan_time=scan_start,
            duration_seconds=total_duration,
            total_files=total_files,
            total_directories=total_directories,
            total_size=total_size,
            scan_options=options,
            errors=all_errors,
        )

        self.output.success(f"Batch scan completed: {scanned}/{len(paths)} paths, "
                            f"{total_files} files, {merged.total_size_human_readable}")
        return merged

    def analyze_files(self, scan_result: ScanResult):
        """分析文件"""
        if not scan_result:
            self.output.error("No scan result to analyze")
            return None

        self.output.progress(f"\nAnalyzing {len(scan_result.files)} files...")

        # 使用规则引擎分析
        recommendations, warnings = self.rule_engine.analyze_files(scan_result.files)

        self.output.progress(f"Found {len(recommendations)} potential cleanup candidates")
        if warnings:
            self.output.warning(f"{len(warnings)} warnings found")

        return recommendations

    def show_results(self, recommendations: list, limit: int = 20):
        """显示结果"""
        self.output.output_results(recommendations, limit)

    def interactive_mode(self):
        """交互模式"""
        self.output.info("WizTree CLI Agent - Interactive Mode")
        self.output.info("=" * 40)

        while True:
            self.output.info("\nCommands:")
            self.output.info("  scan <path>    - Scan a directory")
            self.output.info("  analyze        - Analyze last scan results")
            self.output.info("  show           - Show recommendations")
            self.output.info("  validate <path> - Validate a path")
            self.output.info("  exit           - Exit")

            try:
                command = input("\nEnter command: ").strip()
            except (EOFError, KeyboardInterrupt):
                self.output.info("\nExiting...")
                break

            if not command:
                continue

            parts = command.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else None

            if cmd == 'exit' or cmd == 'quit':
                self.output.info("Exiting...")
                break
            elif cmd == 'scan':
                if not arg:
                    self.output.info("Usage: scan <path>")
                    continue
                self.scan_result = self.scan_directory(arg)
            elif cmd == 'analyze':
                if not hasattr(self, 'scan_result') or not self.scan_result:
                    self.output.info("No scan result. Run 'scan' first.")
                    continue
                self.recommendations = self.analyze_files(self.scan_result)
            elif cmd == 'show':
                if not hasattr(self, 'recommendations'):
                    self.output.info("No analysis results. Run 'analyze' first.")
                    continue
                self.show_results(self.recommendations)
            elif cmd == 'validate':
                if not arg:
                    self.output.info("Usage: validate <path>")
                    continue
                is_valid, error = self.validator.validate(arg)
                if is_valid:
                    self.output.success(f"Path '{arg}' is valid")
                else:
                    self.output.error(f"Path '{arg}' is invalid: {error}")
            else:
                self.output.info(f"Unknown command: {cmd}")


def main() -> int:
    """主函数，返回退出码: 0=成功, 1=错误, 2=警告"""
    parser = argparse.ArgumentParser(description="WizTree CLI Agent")
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode')
    parser.add_argument('--scan', type=str, help='Scan a directory')
    parser.add_argument('--batch', nargs='+', metavar='DIR', help='Batch scan multiple directories')
    parser.add_argument('--batch-file', type=str, metavar='FILE', help='Read directory list from file (one per line)')
    parser.add_argument('--analyze', action='store_true', help='Analyze scan results')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress progress output, only show results')
    parser.add_argument('--json', action='store_true', dest='json_output', help='Output results in JSON format')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')

    args = parser.parse_args()

    try:
        cli = WizTreeCLI(quiet=args.quiet, json_output=args.json_output, no_color=args.no_color)
    except Exception as e:
        print(f"Initialization failed: {e}", file=sys.stderr)
        return EXIT_ERROR

    exit_code = EXIT_SUCCESS

    try:
        if args.interactive:
            cli.interactive_mode()
        elif args.batch or args.batch_file:
            paths = []
            if args.batch:
                paths.extend(args.batch)
            if args.batch_file:
                try:
                    with open(args.batch_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                paths.append(line)
                except FileNotFoundError:
                    cli.output.error(f"Batch file not found: {args.batch_file}")
                    return EXIT_ERROR
            result = cli.scan_batch(paths)
            if result and args.analyze:
                recommendations = cli.analyze_files(result)
                if recommendations:
                    cli.show_results(recommendations)
            elif result is None:
                exit_code = EXIT_ERROR
        elif args.scan:
            result = cli.scan_directory(args.scan)
            if result and args.analyze:
                recommendations = cli.analyze_files(result)
                if recommendations:
                    cli.show_results(recommendations)
                    has_high_risk = any(
                        rec.risk_level.value in ("HIGH", "CRITICAL")
                        for rec in recommendations
                    )
                    if has_high_risk:
                        exit_code = EXIT_WARNING
                else:
                    exit_code = EXIT_WARNING
            elif result is None:
                exit_code = EXIT_ERROR
        elif args.cli:
            if not args.quiet:
                cli.output.info("WizTree CLI Agent - CLI Mode")
                cli.output.info("=" * 40)
                cli.output.success("Scanner initialized successfully")
                cli.output.success("Safety manager initialized successfully")
                cli.output.info("\nUse --interactive for interactive mode")
                cli.output.info("Use --scan <path> to scan a directory")
        else:
            # 默认尝试GUI模式
            try:
                from src.ui import MainWindow
                app = WizTreeAgentApp()
                app.initialize()
                app.ui = MainWindow()
                app.ui.mainloop()
            except ImportError as e:
                if not args.quiet:
                    cli.output.warning(f"GUI mode not available: {e}")
                    cli.output.info("Running in CLI mode...")
                cli.interactive_mode()
    except KeyboardInterrupt:
        cli.output.info("\nOperation cancelled by user")
        exit_code = EXIT_WARNING
    except Exception as e:
        cli.output.error(str(e))
        exit_code = EXIT_ERROR

    return exit_code


if __name__ == "__main__":
    sys.exit(main())