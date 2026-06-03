"""UI 标签页包（v1.2.0 / Stage 2-5）"""
from .models_tab import ModelsTab
from .prompts_tab import PromptsTab

# Stage 5 (v1.2.0): 审计历史 + Diff 预览
try:
    from .history_tab import HistoryTab
except ImportError:  # pragma: no cover
    HistoryTab = None  # type: ignore

try:
    from .diff_preview import DiffPreviewDialog
except ImportError:  # pragma: no cover
    DiffPreviewDialog = None  # type: ignore

__all__ = [
    "ModelsTab",
    "PromptsTab",
    "HistoryTab",
    "DiffPreviewDialog",
]
