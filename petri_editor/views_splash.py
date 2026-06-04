"""Splash screen — shown briefly on launch, then advances to the main menu."""

from __future__ import annotations

import math
import time

import arcade

from . import __app_name__, __version__
from .theme import (
    ACCENT, ARC_COLOR, BG_COLOR, NODE_FILL, NODE_STROKE, STATE_ACTIVE_FILL,
    STATE_FILL, TEXT_COLOR, TEXT_DIM, TRANSITION_FILL,
)

SPLASH_DURATION = 2.0


class SplashView(arcade.View):
    def __init__(self) -> None:
        super().__init__()
        self.background_color = BG_COLOR
        self.start_time: float = 0.0
        self.elapsed: float = 0.0

    def on_show_view(self) -> None:
        self.start_time = time.monotonic()

    def on_update(self, dt: float) -> None:
        self.elapsed = time.monotonic() - self.start_time
        if self.elapsed >= SPLASH_DURATION:
            self._advance()

    def on_mouse_press(self, *args, **kwargs) -> None:
        self._advance()

    def on_key_press(self, *args, **kwargs) -> None:
        self._advance()

    def _advance(self) -> None:
        from .views_menu import MainMenuView
        self.window.show_view(MainMenuView())

    def on_draw(self) -> None:
        self.clear()
        cx = self.window.width / 2
        cy = self.window.height / 2
        self._draw_glyph(cx, cy + 60)
        arcade.draw_text(__app_name__, cx, cy - 40,
                         TEXT_COLOR, 36, anchor_x="center", bold=True)
        arcade.draw_text("Visual editor for Petri nets and state machines",
                         cx, cy - 80, TEXT_DIM, 14, anchor_x="center")
        arcade.draw_text(f"v{__version__}", cx, 40,
                         TEXT_DIM, 10, anchor_x="center")
        arcade.draw_text("click or press any key to continue", cx, 20,
                         TEXT_DIM, 10, anchor_x="center")

    def _draw_glyph(self, cx: float, cy: float) -> None:
        # Layout: P1 → T → P2, with a State below T.
        spacing = 90
        p1 = (cx - spacing, cy)
        t = (cx, cy)
        p2 = (cx + spacing, cy)
        state = (cx, cy - 70)
        r = 22

        arcade.draw_line(p1[0] + r, p1[1], t[0] - 9, t[1], ARC_COLOR, 2)
        arcade.draw_line(t[0] + 9, t[1], p2[0] - r, p2[1], ARC_COLOR, 2)
        arcade.draw_line(state[0], state[1] + 18, t[0], t[1] - 28, ARC_COLOR, 2)

        phase = (self.elapsed % 1.6) / 1.6
        eased = 0.5 - 0.5 * math.cos(phase * 2 * math.pi)
        tok_x = p1[0] + (p2[0] - p1[0]) * eased
        arcade.draw_circle_filled(tok_x, cy, 5, ACCENT)

        for px, py in (p1, p2):
            arcade.draw_circle_filled(px, py, r, NODE_FILL)
            arcade.draw_circle_outline(px, py, r, NODE_STROKE, 2)

        rect = arcade.LBWH(t[0] - 9, t[1] - 28, 18, 56)
        arcade.draw_rect_filled(rect, TRANSITION_FILL)
        arcade.draw_rect_outline(rect, NODE_STROKE, 2)

        # State (rounded rect; arcade has no rounded primitive — fake with two rects).
        sx, sy = state
        active = (eased > 0.5)
        fill = STATE_ACTIVE_FILL if active else STATE_FILL
        srect = arcade.LBWH(sx - 35, sy - 18, 70, 36)
        arcade.draw_rect_filled(srect, fill)
        arcade.draw_rect_outline(srect, NODE_STROKE, 2)
        arcade.draw_text("S", sx, sy - 7, NODE_STROKE, 12,
                         anchor_x="center", bold=True)
