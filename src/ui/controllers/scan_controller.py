"""ScanController — 扫描业务逻辑，UI 无关。"""
import logging
import os
import threading
from datetime import datetime as _dt
from pathlib import Path
from typing import Callable, List, Optional

from src.scanner import StreamingScanner, ScanOptions, ScanStatus
from src.models import FileInfo, ScanResult

logger = logging.getLogger(__name__)

# 文件显示上限 (防止大量文件撑爆内存)
MAX_SCAN_FILES = 5000
MAX_DISPLAY_FILES = 500


class ScanController:
    """管理扫描流程、文件池和批次导航。不导入任何 GUI 库。"""

    def __init__(
        self,
        scanner: Optional[StreamingScanner] = None,
        *,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        status_callback: Optional[Callable[[str, str], None]] = None,
        on_batch_ready: Optional[Callable[[int], None]] = None,
        on_scan_complete: Optional[Callable[[List[FileInfo]], None]] = None,
        on_scan_error: Optional[Callable[[str], None]] = None,
        on_start_animation: Optional[Callable[[], None]] = None,
        on_stop_animation: Optional[Callable[[], None]] = None,
        on_show_skeleton: Optional[Callable[[], None]] = None,
        on_hide_skeleton: Optional[Callable[[], None]] = None,
    ):
        self._scanner = scanner
        self._streaming_scanner = None

        # 回调
        self._progress_cb = progress_callback
        self._status_cb = status_callback
        self._on_batch_ready = on_batch_ready
        self._on_scan_complete = on_scan_complete
        self._on_scan_error = on_scan_error
        self._on_start_animation = on_start_animation
        self._on_stop_animation = on_stop_animation
        self._on_show_skeleton = on_show_skeleton
        self._on_hide_skeleton = on_hide_skeleton

        # 状态
        self.scan_result: Optional[ScanResult] = None
        self._file_pool: List[FileInfo] = []
        self._scan_target: Optional[str] = None
        self._scan_options: Optional[ScanOptions] = None
        self._total_pool_files: int = 0
        self._streaming_in_progress: bool = False
        self._current_batch: int = 0
        self._batch_size: int = 50

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def scan(self, target: str, options: ScanOptions, wiztree_path: str) -> None:
        """启动流式扫描（后台线程）。"""
        self._streaming_scanner = StreamingScanner(
            wiztree_path=wiztree_path,
            progress_callback=self._on_scan_progress,
        )
        self._scanner = self._streaming_scanner
        self._scan_target = target
        self._scan_options = options

        # 重置状态
        self._file_pool = []
        self._current_batch = 0
        self._total_pool_files = 0
        self._streaming_in_progress = True
        self.scan_result = None

        # UI 回调
        if self._on_start_animation:
            self._on_start_animation()
        if self._on_show_skeleton:
            self._on_show_skeleton()
        if self._status_cb:
            self._status_cb("Streaming scan in progress...", "yellow")

        thread = threading.Thread(
            target=self._streaming_scan_thread,
            args=(target, options),
            daemon=True,
        )
        thread.start()

    def cancel(self) -> None:
        """取消扫描（目前仅设置标志位）。"""
        self._streaming_in_progress = False
        if self._status_cb:
            self._status_cb("Scan cancelled", "gray")

    def get_status(self) -> ScanStatus:
        """返回当前扫描状态。"""
        if self._streaming_in_progress:
            return ScanStatus.SCANNING
        if self.scan_result:
            return ScanStatus.COMPLETED
        return ScanStatus.IDLE

    def get_file_pool(self) -> List[FileInfo]:
        return list(self._file_pool)

    def get_scan_result(self) -> Optional[ScanResult]:
        return self.scan_result

    def is_streaming(self) -> bool:
        return self._streaming_in_progress

    def has_scanner(self) -> bool:
        return self._streaming_scanner is not None

    def get_scan_target(self) -> Optional[str]:
        return self._scan_target

    def get_scan_options(self) -> Optional[ScanOptions]:
        return self._scan_options

    # ------------------------------------------------------------------
    # 批次导航
    # ------------------------------------------------------------------
    @property
    def current_batch(self) -> int:
        return self._current_batch

    @property
    def batch_size(self) -> int:
        return self._batch_size

    def get_current_batch_files(self) -> List[FileInfo]:
        start = self._current_batch * self._batch_size
        end = start + self._batch_size
        return self._file_pool[start:end]

    def prev_batch(self) -> None:
        if self._current_batch > 0:
            self._current_batch -= 1

    def next_batch(
        self,
        *,
        on_wait: Optional[Callable[[], None]] = None,
        on_delayed_scan: Optional[Callable[[int], None]] = None,
    ) -> None:
        max_batch = (len(self._file_pool) - 1) // self._batch_size if self._file_pool else 0
        if self._current_batch < max_batch:
            self._current_batch += 1
        elif self._streaming_in_progress:
            if on_wait:
                on_wait()
        elif self.has_scanner() and self._scan_target:
            if on_delayed_scan:
                on_delayed_scan(self._current_batch + 1)

    def navigate_to_batch(
        self,
        *,
        on_update: Optional[Callable[[], None]] = None,
        on_delayed_scan: Optional[Callable[[int], None]] = None,
    ) -> None:
        start_idx = self._current_batch * self._batch_size
        end_idx = start_idx + self._batch_size

        if start_idx < len(self._file_pool):
            if on_update:
                on_update()
            total_batches = (len(self._file_pool) - 1) // self._batch_size if self._file_pool else 0
            if self._status_cb:
                self._status_cb(
                    f"Batch {self._current_batch + 1}/{total_batches + 1} "
                    f"(files {start_idx + 1}-{min(end_idx, len(self._file_pool))} of {len(self._file_pool)})",
                    "gray",
                )
        elif self.has_scanner() and self._scan_target:
            if on_delayed_scan:
                on_delayed_scan(self._current_batch)

    def delayed_scan_batch(
        self,
        batch_index: int,
        *,
        on_done: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        if not self._streaming_scanner or not self._scan_target:
            return

        if self._status_cb:
            self._status_cb(f"Loading batch {batch_index + 1}...", "yellow")

        thread = threading.Thread(
            target=self._delayed_scan_thread,
            args=(self._scan_target, self._scan_options, batch_index, on_done, on_error),
            daemon=True,
        )
        thread.start()

    def get_batch_button_state(self) -> dict:
        """返回批次按钮应该处于的状态。"""
        max_batch = (len(self._file_pool) - 1) // self._batch_size if self._file_pool else 0
        has_next = self._current_batch < max_batch
        can_delayed = self._streaming_in_progress or (
            self._streaming_scanner is not None and self._scan_target is not None
        )
        return {
            "prev": "normal" if self._current_batch > 0 else "disabled",
            "next": "normal" if (has_next or can_delayed) else "disabled",
        }

    def remove_deleted_files(self, deleted_paths: set) -> None:
        """从文件池中移除已删除的文件。"""
        self._file_pool = [f for f in self._file_pool if str(f.path) not in deleted_paths]

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    @staticmethod
    def format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    def _on_scan_progress(self, progress_info) -> None:
        try:
            msg = progress_info.message or "Scanning..."
            files = getattr(progress_info, "files_scanned", 0)
            if self._progress_cb:
                self._progress_cb(msg, files)
        except Exception:
            logger.warning("Scan progress callback failed", exc_info=True)

    def _streaming_scan_thread(self, target: str, options: ScanOptions) -> None:
        try:
            if self._status_cb:
                self._status_cb(f"Streaming scan {target}...", "yellow")

            streamed_files: List[FileInfo] = []
            batch_refresh_interval = 50
            last_refresh = 0

            for file_info in self._streaming_scanner.scan_streaming(target, options):
                streamed_files.append(file_info)

                if len(streamed_files) - last_refresh >= batch_refresh_interval:
                    last_refresh = len(streamed_files)
                    sorted_batch = sorted(streamed_files, key=lambda x: x.size, reverse=True)
                    self._file_pool = sorted_batch
                    self._total_pool_files = len(sorted_batch)
                    count = len(sorted_batch)
                    if self._on_batch_ready:
                        self._on_batch_ready(count)

            # 最终排序
            self._file_pool = sorted(streamed_files, key=lambda x: x.size, reverse=True)
            self._total_pool_files = len(self._file_pool)
            self._streaming_in_progress = False

            # 截断
            if len(self._file_pool) > MAX_SCAN_FILES:
                original_count = len(self._file_pool)
                self._file_pool = self._file_pool[:MAX_SCAN_FILES]
                logger.warning("Scan truncated: %d -> %d files", original_count, MAX_SCAN_FILES)

            # 构建 ScanResult
            total_size = sum(f.size for f in self._file_pool)
            self.scan_result = ScanResult(
                target_path=Path(target),
                files=self._file_pool,
                scan_time=_dt.now(),
                duration_seconds=0.0,
                total_files=self._total_pool_files,
                total_directories=sum(1 for f in self._file_pool if f.is_directory),
                total_size=total_size,
                scan_options=options.to_dict() if options else None,
                errors=[],
            )

            # 通知扫描完成
            if self._on_scan_complete:
                self._on_scan_complete(self._file_pool)

        except Exception as e:
            self._streaming_in_progress = False
            if self._on_scan_error:
                self._on_scan_error(str(e))
        finally:
            self._streaming_in_progress = False
            if self._on_stop_animation:
                self._on_stop_animation()

    def _delayed_scan_thread(
        self,
        target: str,
        options: ScanOptions,
        batch_index: int,
        on_done: Optional[Callable[[], None]],
        on_error: Optional[Callable[[str], None]],
    ) -> None:
        try:
            result = self._streaming_scanner.scan_batch(
                target, options,
                batch_size=self._batch_size,
                batch_index=batch_index,
            )
            if result and result.files:
                existing_paths = {str(f.path) for f in self._file_pool}
                new_files = [f for f in result.files if str(f.path) not in existing_paths]
                self._file_pool.extend(new_files)
                self._file_pool.sort(key=lambda x: x.size, reverse=True)
                self._total_pool_files = len(self._file_pool)

            if on_done:
                on_done()

        except Exception as e:
            logger.warning("Delayed scan failed: %s", e, exc_info=True)
            if on_error:
                on_error(str(e))
