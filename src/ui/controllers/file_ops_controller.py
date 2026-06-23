"""FileOperationController — 文件删除/恢复逻辑，UI 无关。"""
import logging
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from src.models import FileInfo, DeletionRecommendation

logger = logging.getLogger(__name__)


@dataclass
class DeleteResult:
    deleted: int = 0
    errors: int = 0
    deleted_paths: set = field(default_factory=set)


class FileOperationController:
    """管理文件删除和恢复操作。不导入任何 GUI 库。"""

    def __init__(
        self,
        *,
        on_status: Optional[Callable[[str, str], None]] = None,
        on_confirm: Optional[Callable[[str], bool]] = None,
        on_result: Optional[Callable[[str], None]] = None,
    ):
        self._on_status = on_status
        self._on_confirm = on_confirm  # (message) -> bool
        self._on_result = on_result    # (message) -> None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def delete_files(
        self,
        selected_files: List[tuple],
    ) -> DeleteResult:
        """
        删除文件列表。

        selected_files: List of (FileInfo, DeletionRecommendation) tuples.
        Returns DeleteResult with counts and paths.
        """
        if not selected_files:
            return DeleteResult()

        # 确认
        if self._on_confirm:
            confirmed = self._on_confirm(
                f"Are you sure you want to delete {len(selected_files)} files?\n\n"
                "Files will be moved to Recycle Bin if send2trash is available."
            )
            if not confirmed:
                return DeleteResult()

        # 执行删除
        try:
            from send2trash import send2trash
            use_send2trash = True
        except ImportError:
            logger.debug("send2trash not available, falling back to os.remove")
            use_send2trash = False

        result = DeleteResult()
        for file_info, rec in selected_files:
            try:
                path = str(file_info.path)
                if os.path.exists(path):
                    if use_send2trash:
                        send2trash(path)
                    else:
                        os.remove(path)
                    result.deleted += 1
                    result.deleted_paths.add(path)
            except Exception:
                logger.warning("Delete failed: %s", file_info.path, exc_info=True)
                result.errors += 1

        if self._on_result:
            self._on_result(f"Deleted: {result.deleted}\nErrors: {result.errors}")

        return result

    def restore_file(self, record_id: int) -> bool:
        """从审计日志恢复文件（占位 — 后续实现）。"""
        logger.info("Restore file requested for record_id=%d (not yet implemented)", record_id)
        return False

    def get_history(self) -> List[dict]:
        """返回操作历史（占位 — 后续实现）。"""
        return []
