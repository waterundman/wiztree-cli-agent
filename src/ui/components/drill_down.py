"""Folder drill-down controller.

Stage 3 — manages the current Treemap path and triggers UI re-render
when the user navigates.  Designed to be decoupled from any concrete
widget: the controller holds a reference to a Tk-style master (only
used for ``after(0, ...)`` scheduling) and a callback for path
changes.  Data loading is injected via :meth:`set_data_loader` so
Stage 5 (real scanner integration) can plug in a different source
without changing this class.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, List, Optional

from ...models.file_info import FileInfo

PathLoader = Callable[[str], List[FileInfo]]
PathChangeCallback = Callable[[str], None]


_DEFAULT_MAX_ITEMS = 1000


def _default_loader(path: str, max_items: int = _DEFAULT_MAX_ITEMS) -> List[FileInfo]:
    """Default data loader used when no custom loader has been set.

    Reads a single level of children for ``path`` using
    :meth:`pathlib.Path.iterdir`.  When ``path`` itself is a regular
    file the result is a one-element list.  Children are returned in
    descending order of size and truncated to ``max_items`` entries.
    The implementation never raises — it swallows
    :class:`PermissionError` and :class:`OSError` and returns an
    empty list, matching the "best-effort" semantics required for a
    background data loader.
    """
    if path is None:
        return []
    try:
        p = Path(path)
    except (TypeError, ValueError):
        return []
    if not p.exists():
        return []
    if p.is_file():
        try:
            return [FileInfo.from_path(p, depth=0)]
        except Exception:
            return []
    try:
        children = list(p.iterdir())
    except (PermissionError, OSError, NotADirectoryError):
        return []
    items: List[FileInfo] = []
    for child in children:
        try:
            items.append(FileInfo.from_path(child, depth=0))
        except Exception:
            continue
    items.sort(key=lambda f: -f.size)
    return items[:max_items]


class DrillDownController:
    """Manage the current Treemap path and notify the view on change.

    Parameters
    ----------
    master:
        Optional Tk-style master used for ``master.after(0, ...)``
        scheduling.  When ``None`` the controller falls back to
        synchronous notification, which keeps it unit-testable
        without a real Tk root.
    on_path_change:
        Optional callback fired on the master thread whenever the
        current path changes.  Receives the new path as its single
        argument.  The signature matches the Stage 3 contract
        ``Callable[[str], None]``.
    root_path:
        Initial path.  :meth:`home` always returns to this value.
    """

    def __init__(
        self,
        master=None,
        on_path_change: Optional[PathChangeCallback] = None,
        root_path: str = "",
    ) -> None:
        self._master = master
        self._on_path_change = on_path_change
        self._root_path: str = root_path or ""
        self._current_path: str = self._root_path
        self._data_loader: Optional[PathLoader] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ API

    def set_data_loader(self, loader: PathLoader) -> None:
        """Inject a custom data loader.

        The loader is a callable that, given a path, returns the list
        of :class:`FileInfo` for that path.  When no loader has been
        set the controller falls back to :func:`_default_loader`,
        which walks ``Path.iterdir`` and applies a size-descending
        sort with a 1000-item cap.
        """
        if loader is None:
            self._data_loader = None
            return
        if not callable(loader):
            raise TypeError("data loader must be a callable")
        self._data_loader = loader

    def set_on_path_change(self, callback: Optional[PathChangeCallback]) -> None:
        """Install or remove the path-change callback.

        The controller always invokes the most recently set callback.
        Passing ``None`` disables notifications.
        """
        self._on_path_change = callback

    def set_root(self, path: str) -> None:
        """Set the root path used by :meth:`home` and as the upper
        bound of :meth:`up` navigation.
        """
        self._root_path = path or ""

    def root_path(self) -> str:
        """Return the configured root path."""
        return self._root_path

    def current_path(self) -> str:
        """Return the currently displayed path."""
        return self._current_path

    def enter(self, path: str) -> None:
        """Navigate into ``path`` and notify listeners.

        ``path`` may be absolute or relative.  No filesystem check is
        performed here — the actual children are loaded by the
        configured loader on the background thread.
        """
        if path is None:
            return
        with self._lock:
            self._current_path = path
        self._notify_async(path)

    def up(self) -> Optional[str]:
        """Navigate to the parent directory.

        Returns the new path or ``None`` when already at the root
        (or at a filesystem root that has no parent).
        """
        with self._lock:
            cur = self._current_path
            root = self._root_path
        if not cur:
            return None
        if root and cur == root:
            return None
        try:
            parent_path = Path(cur).parent
        except (OSError, ValueError):
            return None
        parent = str(parent_path)
        if not parent or parent == cur:
            return None
        if root and not self._is_within_root(parent, root):
            return None
        with self._lock:
            self._current_path = parent
        self._notify_async(parent)
        return parent

    def home(self) -> None:
        """Return to the configured root path."""
        with self._lock:
            self._current_path = self._root_path
        self._notify_async(self._root_path)

    def get_children(self, path: str) -> List[FileInfo]:
        """Synchronously load the children of ``path``.

        When a custom loader has been installed it is used;
        otherwise the controller falls back to
        :func:`_default_loader`.
        """
        if self._data_loader is not None:
            try:
                return list(self._data_loader(path))
            except Exception:
                return []
        return _default_loader(path)

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _is_within_root(child: str, root: str) -> bool:
        """Return True when ``child`` equals ``root`` or is nested
        below it.  Works on both POSIX and Windows-style paths.
        """
        if not child or not root:
            return True
        if child == root:
            return True
        # Normalise to Path for robust prefix comparison.
        try:
            c = Path(child)
            r = Path(root)
        except (OSError, ValueError):
            return False
        try:
            c.relative_to(r)
            return True
        except ValueError:
            return False

    def _notify_async(self, path: str) -> None:
        """Schedule the path-change callback on the master thread.

        When no master is configured the callback is invoked
        synchronously, which keeps the controller usable in unit
        tests and in non-GUI contexts.
        """
        cb = self._on_path_change
        if cb is None:
            return
        master = self._master
        if master is None:
            try:
                cb(path)
            except Exception:
                pass
            return

        def _work() -> None:
            # Run the (potentially slow) loader eagerly so the heavy
            # work happens off the GUI thread, then schedule the
            # callback on the main thread.
            loader = self._data_loader
            try:
                if loader is not None:
                    loader(path)
                else:
                    _default_loader(path)
            except Exception:
                pass
            try:
                master.after(0, cb, path)
            except Exception:
                # Master may have been destroyed (window closed); fall
                # back to a best-effort synchronous call.
                try:
                    cb(path)
                except Exception:
                    pass

        threading.Thread(target=_work, daemon=True).start()


__all__ = ['DrillDownController']
