"""In-canvas modal path-entry overlay.

Shown by the editor view when Tkinter isn't installed and we need a
file path from the user. Renders a centered panel with a single text
input plus OK/Cancel buttons. The editor view delegates input events
to this overlay while it's active.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

import arcade

from .theme import (
    ACCENT, BG_COLOR, NODE_STROKE, PANEL_BG, PANEL_BORDER, TEXT_COLOR,
    TEXT_DIM,
)


class PathEntryOverlay:
    """Modal text-entry overlay. Call `open(...)` to show, `is_open` to query."""

    def __init__(self, window: arcade.Window) -> None:
        self.window = window
        self.is_open: bool = False
        self.title: str = ""
        self.prompt: str = ""
        self.text: str = ""
        self._on_confirm: Optional[Callable[[str], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None
        self._cursor_blink: float = 0.0

    def open(self, title: str, prompt: str, default_text: str = "",
             on_confirm: Callable[[str], None] | None = None,
             on_cancel: Callable[[], None] | None = None) -> None:
        self.title = title
        self.prompt = prompt
        self.text = default_text
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    # ---- per-frame ----
    def update(self, dt: float) -> None:
        if self.is_open:
            self._cursor_blink = (self._cursor_blink + dt) % 1.0

    # ---- input ----
    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        """Return True if the overlay consumed the event."""
        if not self.is_open:
            return False
        if symbol == arcade.key.ESCAPE:
            self.is_open = False
            if self._on_cancel:
                self._on_cancel()
            return True
        if symbol in (arcade.key.RETURN, arcade.key.ENTER):
            self.is_open = False
            if self._on_confirm:
                self._on_confirm(self.text.strip())
            return True
        if symbol == arcade.key.BACKSPACE:
            self.text = self.text[:-1]
            return True
        # Paste support
        if (modifiers & arcade.key.MOD_CTRL) and symbol == arcade.key.V:
            try:
                import subprocess
                # xclip on Linux; falls back gracefully if unavailable.
                out = subprocess.check_output(
                    ["xclip", "-selection", "clipboard", "-o"],
                    timeout=0.5, stderr=subprocess.DEVNULL,
                ).decode("utf-8", errors="replace")
                self.text += out
            except Exception:
                pass
            return True
        return True  # consume everything while open

    def on_text(self, text: str) -> bool:
        if not self.is_open:
            return False
        # Filter to printable characters; arcade sends '\r' on Enter which
        # we already handle in on_key_press.
        if text and text.isprintable():
            self.text += text
        return True

    def on_mouse_press(self, x: float, y: float, button: int,
                       modifiers: int) -> bool:
        if not self.is_open:
            return False
        ok_rect = self._ok_rect()
        cancel_rect = self._cancel_rect()
        if self._inside(x, y, ok_rect):
            self.is_open = False
            if self._on_confirm:
                self._on_confirm(self.text.strip())
            return True
        if self._inside(x, y, cancel_rect):
            self.is_open = False
            if self._on_cancel:
                self._on_cancel()
            return True
        return True  # consume so editor doesn't react

    # ---- drawing ----
    def draw(self) -> None:
        if not self.is_open:
            return
        # Dim background.
        full = arcade.LBWH(0, 0, self.window.width, self.window.height)
        arcade.draw_rect_filled(full, (0, 0, 0, 140))

        # Panel.
        pw, ph = 560, 200
        cx = self.window.width / 2
        cy = self.window.height / 2
        panel = arcade.LBWH(cx - pw / 2, cy - ph / 2, pw, ph)
        arcade.draw_rect_filled(panel, PANEL_BG)
        arcade.draw_rect_outline(panel, PANEL_BORDER, 2)

        arcade.draw_text(self.title, cx, cy + ph / 2 - 30,
                         ACCENT, 14, anchor_x="center", bold=True)
        arcade.draw_text(self.prompt, cx, cy + ph / 2 - 56,
                         TEXT_DIM, 11, anchor_x="center")

        # Text field.
        fw, fh = pw - 40, 32
        field = arcade.LBWH(cx - fw / 2, cy - 8, fw, fh)
        arcade.draw_rect_filled(field, BG_COLOR)
        arcade.draw_rect_outline(field, ACCENT, 1)

        cursor = "|" if self._cursor_blink < 0.5 else " "
        arcade.draw_text(self.text + cursor,
                         cx - fw / 2 + 10, cy + 4,
                         TEXT_COLOR, 12)

        # Buttons.
        for label, rect, color in (
            ("OK (Enter)", self._ok_rect(), ACCENT),
            ("Cancel (Esc)", self._cancel_rect(), (60, 64, 72)),
        ):
            arcade.draw_rect_filled(rect, color)
            arcade.draw_rect_outline(rect, NODE_STROKE, 1)
            arcade.draw_text(label,
                             rect.x + rect.width / 2,
                             rect.y + rect.height / 2 - 7,
                             TEXT_COLOR, 11, anchor_x="center")

    def _ok_rect(self):
        cx = self.window.width / 2
        cy = self.window.height / 2
        return arcade.LBWH(cx + 30, cy - 80, 130, 32)

    def _cancel_rect(self):
        cx = self.window.width / 2
        cy = self.window.height / 2
        return arcade.LBWH(cx - 160, cy - 80, 130, 32)

    @staticmethod
    def _inside(x: float, y: float, rect) -> bool:
        return (rect.x <= x <= rect.x + rect.width
                and rect.y <= y <= rect.y + rect.height)
