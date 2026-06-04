"""File dialogs.

Primary path: Tkinter (stdlib on most Python builds, modal, native-looking).
Fallback path: an in-canvas path-entry overlay rendered by the editor view —
this kicks in when Tkinter is missing. The functions here return None when
Tkinter is unavailable so the caller can route to the overlay.
"""

from __future__ import annotations

import os
from typing import Optional

from .logger import log_io


_TK_AVAILABLE: Optional[bool] = None


def tkinter_available() -> bool:
    """Cached probe for Tkinter (some Python builds lack `_tkinter`)."""
    global _TK_AVAILABLE
    if _TK_AVAILABLE is None:
        try:
            import tkinter  # noqa: F401
            from tkinter import filedialog  # noqa: F401
            _TK_AVAILABLE = True
        except Exception as e:
            log_io.warning(f"tkinter unavailable: {e} — using path-entry fallback")
            _TK_AVAILABLE = False
    return _TK_AVAILABLE


def ask_open(initial_dir: str | None = None) -> Optional[str]:
    if not tkinter_available():
        return None
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw()
    try:
        path = filedialog.askopenfilename(
            title="Open Petri net",
            initialdir=initial_dir or os.getcwd(),
            filetypes=[("Petri net JSON", "*.json"), ("All files", "*.*")],
        )
    finally:
        root.destroy()
    return path or None


def ask_save(initial_dir: str | None = None,
             default_name: str = "net.json",
             extensions: list[tuple[str, str]] | None = None) -> Optional[str]:
    if not tkinter_available():
        return None
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw()
    try:
        path = filedialog.asksaveasfilename(
            title="Save",
            initialdir=initial_dir or os.getcwd(),
            initialfile=default_name,
            defaultextension=os.path.splitext(default_name)[1] or ".json",
            filetypes=extensions or [("Petri net JSON", "*.json"),
                                     ("All files", "*.*")],
        )
    finally:
        root.destroy()
    return path or None
