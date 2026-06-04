"""Options view — UI only at this milestone. Disk persistence comes later."""

from __future__ import annotations

from dataclasses import dataclass

import arcade
import arcade.gui

from .logger import log_ui, set_verbose
from .theme import BG_COLOR, TEXT_COLOR, TEXT_DIM


@dataclass
class Settings:
    snap_to_grid: bool = False
    grid_size: int = 20
    show_grid: bool = True
    confirm_on_delete: bool = False
    verbose_log: bool = False


# Module-level singleton — survives view transitions.
SETTINGS = Settings()


class OptionsView(arcade.View):
    def __init__(self) -> None:
        super().__init__()
        self.background_color = BG_COLOR
        self.ui = arcade.gui.UIManager()
        anchor = self.ui.add(arcade.gui.UIAnchorLayout())
        stack = arcade.gui.UIBoxLayout(space_between=10)

        stack.add(self._row_toggle("Show grid", "show_grid"))
        stack.add(self._row_toggle("Snap to grid", "snap_to_grid"))
        stack.add(self._row_int("Grid size (px)", "grid_size",
                                step=4, lo=4, hi=80))
        stack.add(self._row_toggle("Confirm on delete", "confirm_on_delete"))
        stack.add(self._row_toggle("Verbose log (DEBUG)", "verbose_log",
                                   on_change=lambda v: set_verbose(v)))

        back = arcade.gui.UIFlatButton(text="Back to menu",
                                       width=200, height=36)
        back.on_click = self._on_back
        stack.add(arcade.gui.UISpace(height=12, width=1))
        stack.add(back)

        anchor.add(child=stack, anchor_x="center_x", anchor_y="center_y")

    def _row_toggle(self, label: str, attr: str,
                    on_change=None) -> arcade.gui.UIBoxLayout:
        row = arcade.gui.UIBoxLayout(vertical=False, space_between=12)
        row.add(arcade.gui.UILabel(text=label, width=260, font_size=12,
                                   text_color=TEXT_COLOR))
        current = getattr(SETTINGS, attr)
        btn = arcade.gui.UIFlatButton(
            text="ON" if current else "OFF", width=80, height=32,
        )

        def toggle(_e, a=attr, b=btn) -> None:
            new = not getattr(SETTINGS, a)
            setattr(SETTINGS, a, new)
            b.text = "ON" if new else "OFF"
            log_ui.info(f"option {a} = {new}")
            if on_change:
                on_change(new)

        btn.on_click = toggle
        row.add(btn)
        return row

    def _row_int(self, label: str, attr: str, step: int,
                 lo: int, hi: int) -> arcade.gui.UIBoxLayout:
        row = arcade.gui.UIBoxLayout(vertical=False, space_between=8)
        row.add(arcade.gui.UILabel(text=label, width=260, font_size=12,
                                   text_color=TEXT_COLOR))
        minus = arcade.gui.UIFlatButton(text="−", width=32, height=32)
        val = arcade.gui.UILabel(text=str(getattr(SETTINGS, attr)),
                                 width=44, font_size=13,
                                 text_color=TEXT_COLOR)
        plus = arcade.gui.UIFlatButton(text="+", width=32, height=32)

        def bump(delta: int, a=attr, v=val) -> None:
            new = max(lo, min(hi, getattr(SETTINGS, a) + delta))
            setattr(SETTINGS, a, new)
            v.text = str(new)
            log_ui.info(f"option {a} = {new}")

        minus.on_click = lambda _e: bump(-step)
        plus.on_click = lambda _e: bump(+step)
        row.add(minus); row.add(val); row.add(plus)
        return row

    def on_show_view(self) -> None:
        self.ui.enable()

    def on_hide_view(self) -> None:
        self.ui.disable()

    def on_draw(self) -> None:
        self.clear()
        cx = self.window.width / 2
        arcade.draw_text("Options", cx, self.window.height - 80,
                         TEXT_COLOR, 28, anchor_x="center", bold=True)
        arcade.draw_text("settings persist for this session only",
                         cx, self.window.height - 110,
                         TEXT_DIM, 11, anchor_x="center")
        self.ui.draw()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == arcade.key.ESCAPE:
            self._back()

    def _on_back(self, _e) -> None:
        self._back()

    def _back(self) -> None:
        from .views_menu import MainMenuView
        self.window.show_view(MainMenuView())
