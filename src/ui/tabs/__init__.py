"""UI 标签页包（v1.2.1）"""
# HistoryTab, PromptsTab, ModelsTab removed — always empty, no data sources

try:
    from .diff_preview import DiffPreviewDialog
except ImportError:  # pragma: no cover
    DiffPreviewDialog = None  # type: ignore

__all__ = [
    "DiffPreviewDialog",
]
