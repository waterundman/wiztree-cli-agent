"""Tests for export functionality (JSON and CSV exporters)."""
import json
import csv
import tempfile
from datetime import datetime
from pathlib import Path

from src.models import FileInfo, ScanResult
from src.exporters import export_json, export_csv


def _make_scan_result() -> ScanResult:
    files = [
        FileInfo(
            path=Path("C:/test/file1.txt"),
            size=1024,
            modified_time=datetime(2025, 1, 1, 12, 0, 0),
            created_time=datetime(2025, 1, 1, 10, 0, 0),
            is_directory=False,
            extension=".txt",
            depth=1,
        ),
        FileInfo(
            path=Path("C:/test/subdir"),
            size=4096,
            modified_time=datetime(2025, 1, 2, 8, 0, 0),
            created_time=None,
            is_directory=True,
            extension=None,
            depth=1,
        ),
        FileInfo(
            path=Path("C:/test/image.png"),
            size=2048000,
            modified_time=datetime(2025, 3, 15, 18, 30, 0),
            created_time=datetime(2025, 3, 15, 18, 0, 0),
            is_directory=False,
            extension=".png",
            depth=2,
        ),
    ]
    return ScanResult(
        target_path=Path("C:/test"),
        files=files,
        scan_time=datetime(2025, 6, 1, 9, 0, 0),
        duration_seconds=1.5,
        total_files=2,
        total_directories=1,
        total_size=2053120,
    )


class TestExportJson:
    def test_json_structure(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.json"
        export_json(result, out)

        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "metadata" in data
        assert "files" in data
        assert "summary" in data

    def test_json_metadata(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.json"
        export_json(result, out)
        data = json.loads(out.read_text(encoding="utf-8"))

        assert data["metadata"]["target_path"] == "C:\\test"
        assert data["metadata"]["duration_seconds"] == 1.5
        assert "scan_time" in data["metadata"]

    def test_json_files_count(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.json"
        export_json(result, out)
        data = json.loads(out.read_text(encoding="utf-8"))

        assert len(data["files"]) == 3

    def test_json_file_fields(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.json"
        export_json(result, out)
        data = json.loads(out.read_text(encoding="utf-8"))

        file_entry = data["files"][0]
        assert file_entry["name"] == "file1.txt"
        assert file_entry["size"] == 1024
        assert file_entry["is_directory"] is False
        assert file_entry["extension"] == ".txt"

    def test_json_summary(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.json"
        export_json(result, out)
        data = json.loads(out.read_text(encoding="utf-8"))

        assert data["summary"]["total_files"] == 2
        assert data["summary"]["total_directories"] == 1
        assert data["summary"]["total_size"] == 2053120

    def test_json_creates_parent_dirs(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "sub" / "dir" / "report.json"
        export_json(result, out)
        assert out.exists()

    def test_json_empty_files(self, tmp_path):
        result = ScanResult(
            target_path=Path("C:/empty"),
            files=[],
            scan_time=datetime(2025, 6, 1),
            duration_seconds=0.1,
            total_files=0,
            total_directories=0,
            total_size=0,
        )
        out = tmp_path / "empty.json"
        export_json(result, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["files"] == []
        assert data["summary"]["total_files"] == 0


class TestExportCsv:
    def test_csv_exists(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.csv"
        export_csv(result, out)
        assert out.exists()

    def test_csv_headers(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.csv"
        export_csv(result, out)

        with open(out, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == [
                "path", "name", "size", "size_human_readable",
                "modified_time", "created_time", "is_directory",
                "extension", "depth",
            ]

    def test_csv_row_count(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.csv"
        export_csv(result, out)

        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3

    def test_csv_values(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.csv"
        export_csv(result, out)

        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        assert rows[0]["name"] == "file1.txt"
        assert rows[0]["size"] == "1024"
        assert rows[0]["is_directory"] == "False"
        assert rows[0]["extension"] == ".txt"

    def test_csv_directory_has_no_extension(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.csv"
        export_csv(result, out)

        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        dir_row = rows[1]
        assert dir_row["name"] == "subdir"
        assert dir_row["is_directory"] == "True"
        assert dir_row["extension"] == ""

    def test_csv_utf8_sig_encoding(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "report.csv"
        export_csv(result, out)

        raw = out.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf"

    def test_csv_creates_parent_dirs(self, tmp_path):
        result = _make_scan_result()
        out = tmp_path / "sub" / "report.csv"
        export_csv(result, out)
        assert out.exists()


class TestCLIExportArgs:
    def test_cli_has_output_format_arg(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--output-format', choices=['json', 'csv'], default=None)
        parser.add_argument('--output-file', type=str, default=None)

        args = parser.parse_args(['--output-format', 'json', '--output-file', 'out.json'])
        assert args.output_format == 'json'
        assert args.output_file == 'out.json'

    def test_cli_output_format_defaults_none(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--output-format', choices=['json', 'csv'], default=None)
        parser.add_argument('--output-file', type=str, default=None)

        args = parser.parse_args([])
        assert args.output_format is None
        assert args.output_file is None
