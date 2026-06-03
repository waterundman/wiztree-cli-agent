"""Stage 4: Performance benchmark tests.

Measures:
1. VirtualTreeview 10000-row data load < 1s
2. FileInfo memory reduction >= 30% vs dict baseline
3. Scan cache hit rate (2nd call returns cached)
4. Large CSV streaming memory stability
5. FileInfo bulk creation throughput
6. Cache key generation throughput
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import time
import tracemalloc
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.file_info import FileInfo
from src.scanner.wiztree_scanner import WizTreeScanner
from src.scanner.options import ScanOptions
from src.models import ScanResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fileinfo(i: int) -> FileInfo:
    """Create a FileInfo with realistic paths."""
    return FileInfo(
        path=Path(f"C:\\Users\\test\\Documents\\file_{i:05d}.txt"),
        size=1024 * (i + 1),
        modified_time=datetime(2025, 1, 1, 12, 0, i % 60),
        created_time=datetime(2025, 1, 1, 0, 0, 0),
        is_directory=False,
        extension=".txt",
        depth=i % 10,
        parent_path=Path(f"C:\\Users\\test\\Documents"),
    )


def _make_scan_result(target: str = "C:\\", n_files: int = 3) -> ScanResult:
    files = [_make_fileinfo(i) for i in range(n_files)]
    now = datetime.now()
    return ScanResult(
        target_path=Path(target),
        files=files,
        scan_time=now,
        duration_seconds=1.5,
        total_files=n_files,
        total_directories=0,
        total_size=sum(f.size for f in files),
        scan_options=ScanOptions().to_dict(),
        errors=[],
    )


# ---------------------------------------------------------------------------
# 1. VirtualTreeview 10000-row data load < 1s
# ---------------------------------------------------------------------------

class TestVirtualTreeviewPerformance:
    """VirtualTreeview 10k data load benchmark."""

    def test_set_data_10000_rows_under_1s(self):
        """set_data(10000 rows) must complete in < 1 second."""
        import importlib.util
        import types

        src_dir = Path(__file__).parent.parent / "src" / "ui"
        parent_pkg = "src.ui"
        saved = sys.modules.get(parent_pkg)
        shim = types.ModuleType(parent_pkg)
        shim.__path__ = [str(src_dir)]
        sys.modules[parent_pkg] = shim
        VirtualTreeview = None
        try:
            spec = importlib.util.spec_from_file_location(
                "src.ui.virtual_treeview_perf",
                src_dir / "components" / "virtual_treeview.py",
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            VirtualTreeview = getattr(mod, "VirtualTreeview", None)
        except Exception:
            pass
        finally:
            if saved is not None:
                sys.modules[parent_pkg] = saved
            else:
                sys.modules.pop(parent_pkg, None)

        if VirtualTreeview is None:
            pytest.skip("VirtualTreeview not loadable")

        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
        except Exception:
            pytest.skip("tkinter not available")

        try:
            columns = ("col1", "col2", "col3")
            tree = VirtualTreeview(root, columns=columns, show="headings", buffer_size=10)
            data = [(i, f"file_{i:05d}.txt", f"{i * 1024}") for i in range(10000)]

            start = time.perf_counter()
            tree.set_data(data)
            elapsed = time.perf_counter() - start

            assert tree._total_rows == 10000
            assert elapsed < 1.0, f"set_data took {elapsed:.3f}s, expected < 1.0s"
        finally:
            root.destroy()


# ---------------------------------------------------------------------------
# 2. FileInfo memory reduction >= 30% vs dict-based baseline
# ---------------------------------------------------------------------------

class TestFileInfoMemoryReduction:
    """FileInfo __slots__ memory savings benchmark."""

    def test_slots_memory_reduction_30_percent(self):
        """slots=True FileInfo must use >= 30% less memory than a dict-based equivalent."""

        # Create a dict-based baseline object
        class FileInfoDict:
            def __init__(self, path, size, modified_time, created_time=None,
                         is_directory=False, extension=None, depth=0, parent_path=None):
                self.path = path
                self.size = size
                self.modified_time = modified_time
                self.created_time = created_time
                self.is_directory = is_directory
                self.extension = extension
                self.depth = depth
                self.parent_path = parent_path

        n = 1000
        slots_objs = []
        dict_objs = []

        for i in range(n):
            kw = dict(
                path=Path(f"C:\\file_{i}.txt"),
                size=i * 100,
                modified_time=datetime.now(),
                created_time=datetime.now(),
                is_directory=False,
                extension=".txt",
                depth=1,
                parent_path=Path("C:\\"),
            )
            slots_objs.append(FileInfo(**kw))
            dict_objs.append(FileInfoDict(**kw))

        slots_size = sum(sys.getsizeof(o) for o in slots_objs)
        dict_size = sum(sys.getsizeof(o) for o in dict_objs)

        # Also account for __dict__ overhead
        dict_total = dict_size + sum(sys.getsizeof(o.__dict__) for o in dict_objs)

        reduction_pct = (1 - slots_size / dict_total) * 100
        assert reduction_pct >= 30.0, (
            f"Memory reduction {reduction_pct:.1f}%, expected >= 30%"
        )


# ---------------------------------------------------------------------------
# 3. Scan cache hit rate
# ---------------------------------------------------------------------------

class TestScanCacheHitRate:
    """Second scan call must return cached result without re-scanning."""

    def test_cache_hit_returns_result_without_scan(self, tmp_path):
        scanner = WizTreeScanner()
        scanner._CACHE_FILE = str(tmp_path / "cache.json")
        mock_result = _make_scan_result()

        with patch.object(scanner, "scan", return_value=mock_result) as mock_scan:
            first = scanner.scan_with_cache("C:\\", ScanOptions())
            second = scanner.scan_with_cache("C:\\", ScanOptions())

            assert mock_scan.call_count == 1, "scan() should only be called once"
            assert second.total_files == first.total_files
            assert second.total_size == first.total_size


# ---------------------------------------------------------------------------
# 4. Large CSV streaming memory stability
# ---------------------------------------------------------------------------

class TestCSVStreamingMemoryStability:
    """Streaming 5000 rows should not spike memory."""

    def test_streaming_5000_rows_memory_stable(self):
        scanner = WizTreeScanner()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False,
                                         encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Size', 'Allocated', 'Modified', 'Created', 'Entries'])
            for i in range(5000):
                writer.writerow([
                    f'C:\\Users\\test\\file_{i:05d}.txt',
                    str(i + 1), str(i + 1),
                    '2024-01-01 12:00:00', '', ''
                ])
            csv_path = f.name

        try:
            tracemalloc.start()
            snapshot_before = tracemalloc.take_snapshot()

            count = 0
            for fi in scanner._parse_csv_streaming(csv_path):
                count += 1
                del fi  # allow GC

            snapshot_after = tracemalloc.take_snapshot()
            tracemalloc.stop()

            stats = snapshot_after.compare_to(snapshot_before, 'lineno')
            total_increase = sum(s.size_diff for s in stats)

            assert count == 5000
            # Memory increase should be < 50 MB for streaming 5000 rows
            assert total_increase < 50 * 1024 * 1024, (
                f"Memory increase {total_increase / 1024 / 1024:.1f} MB, "
                f"expected < 50 MB"
            )
        finally:
            os.unlink(csv_path)


# ---------------------------------------------------------------------------
# 5. FileInfo bulk creation throughput
# ---------------------------------------------------------------------------

class TestFileInfoThroughput:
    """Bulk FileInfo creation must be fast."""

    def test_create_10000_fileinfo_under_2s(self):
        start = time.perf_counter()
        objects = []
        for i in range(10000):
            objects.append(FileInfo(
                path=Path(f"C:\\path\\file_{i:05d}.txt"),
                size=i * 100,
                modified_time=datetime(2025, 6, 1, 12, 0, 0),
                created_time=datetime(2025, 6, 1, 0, 0, 0),
                is_directory=False,
                extension=".txt",
                depth=1,
                parent_path=Path("C:\\path"),
            ))
        elapsed = time.perf_counter() - start

        assert len(objects) == 10000
        assert elapsed < 2.0, f"Creating 10000 FileInfo took {elapsed:.3f}s, expected < 2.0s"


# ---------------------------------------------------------------------------
# 6. Cache key generation throughput
# ---------------------------------------------------------------------------

class TestCacheKeyThroughput:
    """Cache key generation must be fast."""

    def test_10000_keys_under_1s(self):
        scanner = WizTreeScanner()
        opts = ScanOptions()

        start = time.perf_counter()
        keys = set()
        for i in range(10000):
            k = scanner._get_cache_key(f"C:\\path\\{i}", opts)
            keys.add(k)
        elapsed = time.perf_counter() - start

        assert len(keys) == 10000, "All keys must be unique"
        assert elapsed < 1.0, f"Generating 10000 keys took {elapsed:.3f}s, expected < 1.0s"
