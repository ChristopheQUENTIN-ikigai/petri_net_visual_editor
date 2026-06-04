"""Terminal debug logger.

Logs at INFO level by default. Format is compact and grep-friendly:
    [HH:MM:SS] LEVEL  area: message

Areas in use:
    model    — graph mutations (add / delete / fire / change)
    ui       — user actions (tool change, click, drag)
    io       — save / load
    sim      — simulation step / run / animation
    history  — undo / redo
"""

from __future__ import annotations

import logging
import sys


_LEVEL_TAG = {
    logging.DEBUG: "DBG ",
    logging.INFO: "INFO",
    logging.WARNING: "WARN",
    logging.ERROR: "ERR ",
    logging.CRITICAL: "CRIT",
}


class _CompactFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%H:%M:%S")
        tag = _LEVEL_TAG.get(record.levelno, str(record.levelno))
        return f"[{ts}] {tag}  {record.name:<7}: {record.getMessage()}"


def _configure_root() -> None:
    root = logging.getLogger("petri")
    if root.handlers:
        return  # already configured (avoid duplicate handlers on reload)
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_CompactFormatter())
    root.addHandler(handler)
    root.propagate = False


def get_logger(area: str) -> logging.Logger:
    """Return a child logger for a given area (model, ui, io, sim, history)."""
    _configure_root()
    return logging.getLogger(f"petri.{area}").getChild("") \
        if False else logging.getLogger(f"petri.{area}")


# Pre-built area loggers — import these directly for a tiny convenience.
_configure_root()
log_model = logging.getLogger("petri.model")
log_ui = logging.getLogger("petri.ui")
log_io = logging.getLogger("petri.io")
log_sim = logging.getLogger("petri.sim")
log_history = logging.getLogger("petri.history")


def set_verbose(verbose: bool) -> None:
    """Toggle DEBUG level (mouse coords, frame events) on or off."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger("petri").setLevel(level)
