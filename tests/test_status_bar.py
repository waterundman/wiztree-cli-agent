"""Tests for the bottom :class:`StatusBar`.

The status bar is exercised in two flavours:

* **Real Tk root** — hidden ``Tk`` instance so the bar's widgets
  are real.  Skipped when tkinter is unavailable.
* **Mock master** — a hand-rolled mock of ``ctk.CTkFrame`` so the
  widget's pure-Python logic can still be exercised in CI
  environments without a display.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# --- Defensive import: status_bar.py imports customtkinter, so we
# load it through a shim that bypasses ``src.ui.__init__`` when
# tkinter is not available.

_TEST_DIR = Path(__file__).parent
_SRC_DIR = _TEST_DIR.parent


def _safe_load(path: Path, dotted_parent: str):
    """Load a module from ``path`` without triggering its real
    parent package ``__init__``.  Returns ``None`` when the import
    fails (e.g. tkinter not available).
    """
    parent_pkg = dotted_parent
    saved = sys.modules.get(parent_pkg)
    shim = types.ModuleType(parent_pkg)
    shim.__path__ = [str(_SRC_DIR / "src" / "ui")]
    sys.modules[parent_pkg] = shim
    try:
        spec = importlib.util.spec_from_file_location(
            dotted_parent + "." + path.stem, str(path)
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[dotted_parent + "." + path.stem] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    except Exception as exc:
        return None
    finally:
        if saved is not None:
            sys.modules[parent_pkg] = saved
        else:
            sys.modules.pop(parent_pkg, None)


_status_bar_mod = _safe_load(
    _SRC_DIR / "src" / "ui" / "components" / "status_bar.py",
    "src.ui",
)


# Make sure customtkinter is importable (it pulls in tkinter).
# If the import fails we skip the tkinter-dependent tests.
TK_AVAILABLE = _status_bar_mod is not None and hasattr(_status_bar_mod, "StatusBar")

import pytest  # noqa: E402

skip_if_no_tkinter = pytest.mark.skipif(
    not TK_AVAILABLE,
    reason="tkinter not available",
)

StatusBar = _status_bar_mod.StatusBar if TK_AVAILABLE else None  # type: ignore


# ---------------------------------------------------------------- Tk path

@skip_if_no_tkinter
def test_status_bar_constructs_with_hidden_tk_root():
    """A hidden Tk root is enough for the bar to be created."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        bar = StatusBar(root)
        assert bar is not None
        # Default state is "ready"
        assert "Ready" in bar.current_state_label()
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_status_bar_set_state_scanning():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        bar = StatusBar(root)
        bar.set_state("scanning", progress=0.4, msg="C:\\Users")
        text = bar.current_state_label()
        assert "Scanning" in text
        assert "C:\\Users" in text
        assert bar.current_progress() == pytest.approx(0.4, abs=1e-6)
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_status_bar_set_state_analyzing():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        bar = StatusBar(root)
        bar.set_state("analyzing", progress=0.2, msg="(3/15) recommendations")
        text = bar.current_state_label()
        assert "Analyzing" in text
        assert "3/15" in text
        assert bar.current_progress() == pytest.approx(0.2, abs=1e-6)
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_status_bar_set_state_ready_resets_message():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        bar = StatusBar(root)
        bar.set_state("scanning", progress=0.7, msg="C:\\Users")
        bar.set_state("ready")
        text = bar.current_state_label()
        assert "Ready" in text
        assert bar.current_progress() == pytest.approx(0.0, abs=1e-6)
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_status_bar_set_state_error():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        bar = StatusBar(root)
        bar.set_state("error", msg="permission denied")
        text = bar.current_state_label()
        assert "Error" in text
        assert "permission denied" in text
    finally:
        root.destroy()


@skip_if_no_tkinter
def test_status_bar_progress_is_clamped():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        bar = StatusBar(root)
        bar.set_state("scanning", progress=2.0)  # over
        assert bar.current_progress() <= 1.0
        bar.set_state("scanning", progress=-0.5)  # under
        assert bar.current_progress() >= 0.0
    finally:
        root.destroy()


# --------------------------------------------------------- Mock-master path

class _MockCTk:
    """Tiny stand-in for ``ctk.CTkLabel`` / ``ctk.CTkProgressBar``.

    Records ``configure`` / ``set`` calls so tests can assert the
    StatusBar logic in pure Python without a real Tk root.
    """

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self.configs = []  # list of kwargs
        self.value = 0.0

    def configure(self, **kwargs):
        self.configs.append(kwargs)
        self._kwargs.update(kwargs)

    def cget(self, name):
        return self._kwargs.get(name)

    def set(self, v):
        self.value = float(v)

    def get(self):
        return self.value

    def grid(self, **kwargs):
        pass

    def pack(self, **kwargs):
        pass


@skip_if_no_tkinter
def test_set_state_scanning_via_mock():
    bar = _make_mock_bar()
    bar.set_state("scanning", progress=0.4, msg="C:\\Users")
    last_cfg = bar._label.configs[-1]
    assert "Scanning" in last_cfg["text"]
    assert "C:\\Users" in last_cfg["text"]
    assert bar._progress.value == pytest.approx(0.4, abs=1e-6)


@skip_if_no_tkinter
def test_set_state_analyzing_via_mock():
    bar = _make_mock_bar()
    bar.set_state("analyzing", progress=0.2, msg="(3/15) recommendations")
    last_cfg = bar._label.configs[-1]
    assert "Analyzing" in last_cfg["text"]
    assert "3/15" in last_cfg["text"]
    assert bar._progress.value == pytest.approx(0.2, abs=1e-6)


@skip_if_no_tkinter
def test_set_state_ready_via_mock():
    bar = _make_mock_bar()
    bar.set_state("scanning", progress=0.7)
    bar.set_state("ready")
    last_cfg = bar._label.configs[-1]
    assert "Ready" in last_cfg["text"]
    assert bar._progress.value == pytest.approx(0.0, abs=1e-6)


@skip_if_no_tkinter
def test_set_state_error_via_mock():
    bar = _make_mock_bar()
    bar.set_state("error", msg="permission denied")
    last_cfg = bar._label.configs[-1]
    assert "Error" in last_cfg["text"]
    assert "permission denied" in last_cfg["text"]


@skip_if_no_tkinter
def test_set_state_progress_clamped_via_mock():
    bar = _make_mock_bar()
    bar.set_state("scanning", progress=2.0)
    assert bar._progress.value == pytest.approx(1.0, abs=1e-6)
    bar.set_state("scanning", progress=-0.5)
    assert bar._progress.value == pytest.approx(0.0, abs=1e-6)


@skip_if_no_tkinter
def test_set_state_colour_changes_with_state():
    bar = _make_mock_bar()
    bar.set_state("scanning")
    scanning_color = bar._current_color
    bar.set_state("error")
    assert bar._current_color != scanning_color
    bar.set_state("ready")
    assert bar._current_color != scanning_color


def _make_mock_bar():
    """Build a :class:`StatusBar` instance whose widget constructors
    are replaced with :class:`_MockCTk` so we can run the logic in
    plain Python.
    """
    import customtkinter as ctk
    # Replace CTkFrame/CTkLabel/CTkProgressBar constructors with
    # the mock while the bar is built.
    original_frame = ctk.CTkFrame.__init__
    original_label = ctk.CTkLabel
    original_progress = ctk.CTkProgressBar
    ctk.CTkFrame.__init__ = lambda self, *a, **kw: None
    ctk.CTkLabel = _MockCTk
    ctk.CTkProgressBar = _MockCTk
    try:
        bar = StatusBar(master=None)
        # Hook the mock label/progress onto the bar manually since
        # the patched __init__ skipped the real construction.
        bar._label = _MockCTk(text="Ready")
        bar._progress = _MockCTk(width=180)
        bar._current_color = "#5eff8e"
    finally:
        ctk.CTkFrame.__init__ = original_frame
        ctk.CTkLabel = original_label
        ctk.CTkProgressBar = original_progress
    return bar


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
