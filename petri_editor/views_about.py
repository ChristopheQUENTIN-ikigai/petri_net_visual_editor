"""About / credits view."""

from __future__ import annotations

import arcade

from . import __app_name__, __version__
from .theme import ACCENT, BG_COLOR, TEXT_COLOR, TEXT_DIM


CREDITS = [
    ("title", __app_name__),
    ("subtitle", f"version {__version__}"),
    ("space", ""),
    ("h", "Authors"),
    ("p", "Built with the help of Claude (Anthropic)."),
    ("space", ""),
    ("h", "License"),
    ("p", "MIT — fork, adapt, ship."),
    ("space", ""),
    ("h", "Built with"),
    ("p", "• Python 3.11"),
    ("p", "• Arcade 3.x — windowing, rendering, GUI"),
    ("p", "• Tkinter (stdlib) — file dialogs"),
    ("p", "• (planned) NetworkX — reachability and graph analysis"),
    ("space", ""),
    ("h", "Acknowledgements"),
    ("p", "Carl Adam Petri — 1962 dissertation introducing Petri nets."),
    ("p", "ISO/IEC 15909-2 — the PNML interchange standard."),
    ("p", "The arcade-academy team for an excellent 2D framework."),
    ("space", ""),
    ("hint", "Press Esc or click anywhere to return to the menu"),
]


class AboutView(arcade.View):
    def __init__(self) -> None:
        super().__init__()
        self.background_color = BG_COLOR

    def on_draw(self) -> None:
        self.clear()
        cx = self.window.width / 2
        y = self.window.height - 80
        for kind, text in CREDITS:
            if kind == "title":
                arcade.draw_text(text, cx, y, TEXT_COLOR, 28,
                                 anchor_x="center", bold=True)
                y -= 36
            elif kind == "subtitle":
                arcade.draw_text(text, cx, y, TEXT_DIM, 13,
                                 anchor_x="center")
                y -= 26
            elif kind == "h":
                arcade.draw_text(text, cx, y, ACCENT, 16,
                                 anchor_x="center", bold=True)
                y -= 22
            elif kind == "p":
                arcade.draw_text(text, cx, y, TEXT_COLOR, 12,
                                 anchor_x="center")
                y -= 18
            elif kind == "hint":
                arcade.draw_text(text, cx, 30, TEXT_DIM, 11,
                                 anchor_x="center")
            elif kind == "space":
                y -= 10

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol in (arcade.key.ESCAPE, arcade.key.ENTER, arcade.key.SPACE):
            self._back()

    def on_mouse_press(self, *args, **kwargs) -> None:
        self._back()

    def _back(self) -> None:
        from .views_menu import MainMenuView
        self.window.show_view(MainMenuView())
