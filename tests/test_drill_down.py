"""Tests for :class:`DrillDownController`.

The controller is exercised in two flavours:

* **Synchronous** — by passing ``master=None`` the controller
  fires its callbacks inline.  This lets us assert state changes
  deterministically without threads.
* **Async** — a mock master is used to verify that
  ``after(0, callback, path)`` is scheduled exactly once per
  navigation event.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest  # noqa: E402

# The controller does not depend on tkinter but lives in
# ``src.ui.components`` whose package import path traverses
# ``src.ui.__init__`` which unconditionally imports
# ``customtkinter``.  We bypass that by pre-seeding
# ``sys.modules['src.ui']`` with a shim whose only job is to
# forward to ``src.ui.components``.  After the controller is
# loaded we restore whatever was previously registered.

_DRILL_DOWN_PATH = (
    Path(__file__).parent.parent / "src" / "ui" / "components" / "drill_down.py"
)


def _load_drill_down():
    if "src.ui" in sys.modules:
        saved = sys.modules["src.ui"]
    else:
        saved = None
    shim = types.ModuleType("src.ui")
    shim.__path__ = [str(Path(__file__).parent.parent / "src" / "ui")]
    sys.modules["src.ui"] = shim
    try:
        from src.ui.components.drill_down import DrillDownController
        return DrillDownController
    finally:
        if saved is not None:
            sys.modules["src.ui"] = saved
        else:
            sys.modules.pop("src.ui", None)


DrillDownController = _load_drill_down()
from src.models.file_info import FileInfo  # noqa: E402


# ----------------------------------------------------------------- helpers

def _make_file_info(path: Path, size: int = 1024) -> FileInfo:
    from datetime import datetime
    return FileInfo(
        path=path,
        size=size,
        modified_time=datetime.now(),
        is_directory=path.is_dir(),
    )


# --------------------------------------------------------------- sync tests

def test_initial_current_path_is_root():
    c = DrillDownController(master=None, root_path="/data")
    assert c.current_path() == "/data"


def test_enter_updates_current_path():
    c = DrillDownController(master=None, root_path="/data")
    c.enter("/data/sub")
    assert c.current_path() == "/data/sub"


def test_up_returns_parent_path():
    c = DrillDownController(master=None, root_path="/data")
    c.enter("/data/sub/deep")
    parent = c.up()
    assert parent == str(Path("/data/sub/deep").parent)
    assert c.current_path() == parent


def test_up_returns_none_at_root():
    c = DrillDownController(master=None, root_path="/data")
    # Already at root — going up should be a no-op.
    assert c.up() is None
    assert c.current_path() == "/data"


def test_home_resets_to_root():
    c = DrillDownController(master=None, root_path="/data")
    c.enter("/data/sub")
    c.home()
    assert c.current_path() == "/data"


def test_on_path_change_callback_fires_synchronously_when_no_master():
    events = []
    c = DrillDownController(
        master=None,
        root_path="/data",
        on_path_change=lambda p: events.append(p),
    )
    c.enter("/data/a")
    c.enter("/data/b")
    c.up()
    assert events == ["/data/a", "/data/b", str(Path("/data/b").parent)]


def test_set_data_loader_is_used_by_get_children():
    c = DrillDownController(master=None, root_path="/x")
    sentinel = [_make_file_info(Path("C:/dummy/a.txt"), 1)]
    c.set_data_loader(lambda p: sentinel)
    # ``get_children`` defensively copies the loader result, so we
    # compare by value rather than identity.
    result = c.get_children("/x")
    assert result == sentinel


def test_set_data_loader_none_resets_to_default():
    c = DrillDownController(master=None, root_path="/x")
    c.set_data_loader(lambda p: [])
    c.set_data_loader(None)  # type: ignore[arg-type]
    # Default loader is a no-op for a non-existent path.
    assert c.get_children("/__definitely_missing__/__") == []


def test_set_data_loader_rejects_non_callable():
    c = DrillDownController(master=None, root_path="/x")
    with pytest.raises(TypeError):
        c.set_data_loader(42)  # type: ignore[arg-type]


def test_get_children_uses_default_loader_for_real_directory(tmp_path):
    """The default loader walks ``Path.iterdir`` and returns
    :class:`FileInfo` instances sorted by size.
    """
    # Create files of distinct sizes
    (tmp_path / "small.txt").write_bytes(b"a")
    (tmp_path / "medium.txt").write_bytes(b"ab")
    (tmp_path / "large.txt").write_bytes(b"abc")
    c = DrillDownController(master=None, root_path=str(tmp_path))
    children = c.get_children(str(tmp_path))
    assert len(children) == 3
    assert all(isinstance(item, FileInfo) for item in children)
    # Sorted by size descending
    assert children[0].name == "large.txt"
    assert children[-1].name == "small.txt"


def test_get_children_handles_missing_path():
    c = DrillDownController(master=None, root_path="/x")
    assert c.get_children("Z:/__missing__/__never__") == []


def test_set_on_path_change_can_be_swapped_at_runtime():
    events = []
    c = DrillDownController(master=None, root_path="/x")
    c.set_on_path_change(lambda p: events.append("first:" + p))
    c.enter("/x/a")
    c.set_on_path_change(lambda p: events.append("second:" + p))
    c.enter("/x/b")
    assert events == ["first:/x/a", "second:/x/b"]


# --------------------------------------------------------------- async tests

class _MockMaster:
    """Minimal stand-in for a tk master widget.

    The :class:`DrillDownController` only needs ``after(0, callback, *args)``
    from its master; we record every scheduling call so tests can
    assert the contract.
    """

    def __init__(self):
        self.scheduled = []  # list of (delay, callback, args)
        self._lock = threading.Lock()

    def after(self, delay, callback, *args):
        with self._lock:
            self.scheduled.append((delay, callback, args))
        # Run the callback immediately for the test so we can
        # assert the effect on the main thread.
        try:
            callback(*args)
        except Exception:
            pass
        return "after-id-{}".format(len(self.scheduled))


def test_async_mode_schedules_after_call():
    master = _MockMaster()
    events = []
    c = DrillDownController(
        master=master,
        root_path="/x",
        on_path_change=lambda p: events.append(p),
    )
    c.enter("/x/sub")
    # The background thread may not have run yet; wait briefly.
    time.sleep(0.1)
    # ``after`` was called with delay=0 and the path as arg.
    assert any(call[0] == 0 and call[2] == ("/x/sub",) for call in master.scheduled)


def test_async_mode_eventually_fires_callback():
    master = _MockMaster()
    events = []
    c = DrillDownController(
        master=master,
        root_path="/x",
        on_path_change=lambda p: events.append(p),
    )
    c.enter("/x/sub")
    time.sleep(0.1)
    assert "/x/sub" in events


def test_async_mode_keeps_current_path_synchronous():
    """The state must be updated synchronously even when the
    callback runs later on the master thread.
    """
    master = _MockMaster()
    c = DrillDownController(
        master=master,
        root_path="/x",
        on_path_change=lambda p: None,
    )
    c.enter("/x/alpha")
    # State should already reflect the new path...
    assert c.current_path() == "/x/alpha"
    # ...even before the background thread runs.
    time.sleep(0.05)
    assert c.current_path() == "/x/alpha"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
