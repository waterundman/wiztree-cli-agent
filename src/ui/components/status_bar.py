"""Bottom status bar.

Stage 3 — a small :class:`ctk.CTkFrame` shown at the bottom of the
main window.  Surfaces the high-level state of long-running
operations (scan / analyse / ready / error) and a determinate
progress bar.

The public contract is intentionally tiny:

* :meth:`set_state` updates the textual label, colour theme, and
  progress value.  The state value is one of ``'scanning'``,
  ``'analyzing'``, ``'ready'``, ``'error'``.

The widget is decoupled from the rest of the application — Stage 4
just has to drop an instance into :class:`MainWindow` and call
:meth:`set_state` whenever the underlying scanner / analyser
progresses.
"""
from __future__ import annotations

from typing import Literal

import customtkinter as ctk

try:
    import tkinter as tk  # noqa: F401  (CTkProgressBar uses Tcl under the hood)
except Exception:  # pragma: no cover - tkinter missing
    tk = None  # type: ignore[assignment]

State = Literal['scanning', 'analyzing', 'ready', 'error']


_STATE_CONFIG = {
    'scanning': {
        'icon': '\U0001F50D',  # 🔍
        'verb': 'Scanning',
        'color': '#5e9bff',  # blue
    },
    'analyzing': {
        'icon': '\U0001F916',  # 🤖
        'verb': 'Analyzing',
        'color': '#b48eff',  # purple
    },
    'ready': {
        'icon': '\u2705',  # ✅
        'verb': 'Ready',
        'color': '#5eff8e',  # green
    },
    'error': {
        'icon': '\u274C',  # ❌
        'verb': 'Error',
        'color': '#ff5e5e',  # red
    },
}


class StatusBar(ctk.CTkFrame):
    """Bottom status bar with state icon, text, and progress bar.

    Parameters
    ----------
    master:
        Parent widget (typically :class:`MainWindow`).
    height:
        Fixed height in pixels.  Defaults to 28 — chosen to fit a
        single line of text plus a slim progress bar without
        competing with the main content area for vertical space.
    """

    def __init__(self, master, height: int = 28) -> None:
        super().__init__(master, height=height, corner_radius=0, fg_color="#1e1e2e")
        self._height = height
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        self._label = ctk.CTkLabel(
            self,
            text="\u2705 Ready",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=_STATE_CONFIG['ready']['color'],
        )
        self._label.grid(row=0, column=0, sticky="ew", padx=10, pady=4)

        self._progress = ctk.CTkProgressBar(
            self,
            width=180,
            height=10,
            progress_color=_STATE_CONFIG['ready']['color'],
        )
        self._progress.grid(row=0, column=1, sticky="e", padx=10, pady=8)
        self._progress.set(0.0)
        # Track the colour of the progress bar so we can re-tint it
        # to match the current state.
        self._current_color = _STATE_CONFIG['ready']['color']

    # ------------------------------------------------------------------ API

    def set_state(
        self,
        state: State,
        progress: float = 0.0,
        msg: str = "",
    ) -> None:
        """Update the status bar.

        Parameters
        ----------
        state:
            One of ``'scanning'``, ``'analyzing'``, ``'ready'``,
            ``'error'``.  Unknown values fall back to the ``'ready'``
            colour so the bar never becomes unreadable.
        progress:
            Determinate progress in ``[0.0, 1.0]``.  Values outside
            the range are clamped silently.
        msg:
            Optional free-form message appended to the state label
            (e.g. ``"C:\\Users"`` while scanning).
        """
        cfg = _STATE_CONFIG.get(state, _STATE_CONFIG['ready'])
        icon = cfg['icon']
        verb = cfg['verb']
        color = cfg['color']

        if state == 'ready':
            if msg:
                text = "{} {}".format(icon, msg)
            else:
                text = "{} {}".format(icon, verb)
        elif state == 'error':
            suffix = msg if msg else "see logs"
            text = "{} {}: {}".format(icon, verb, suffix)
        else:
            # scanning / analyzing — show the verb and the message
            # inline so the bar looks like a live status line.
            if msg:
                text = "{} {} {}...".format(icon, verb, msg)
            else:
                text = "{} {}...".format(icon, verb)

        try:
            self._label.configure(text=text, text_color=color)
        except Exception:
            # Defensive: ctk may not be fully initialised in some
            # mocked test environments.
            pass

        clamped = max(0.0, min(1.0, float(progress)))
        try:
            self._progress.set(clamped)
        except Exception:
            pass
        if color != self._current_color:
            try:
                self._progress.configure(progress_color=color)
            except Exception:
                pass
            self._current_color = color

    # ---------------------------------------------------------- convenience

    def set_progress(self, progress: float) -> None:
        """Convenience wrapper that only updates the progress bar."""
        clamped = max(0.0, min(1.0, float(progress)))
        try:
            self._progress.set(clamped)
        except Exception:
            pass

    def current_state_label(self) -> str:
        """Return the current label text — handy for tests."""
        try:
            return self._label.cget("text")
        except Exception:
            return ""

    def current_progress(self) -> float:
        """Return the current progress value — handy for tests."""
        try:
            return float(self._progress.get())
        except Exception:
            return 0.0


__all__ = ['StatusBar']
