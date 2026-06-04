"""Main menu — entry point after the splash."""

from __future__ import annotations

import arcade
import arcade.gui

from . import __app_name__
from .logger import log_ui
from .theme import BG_COLOR, TEXT_COLOR, TEXT_DIM


class MainMenuView(arcade.View):
    def __init__(self) -> None:
        super().__init__()
        self.background_color = BG_COLOR
        self.ui = arcade.gui.UIManager()

        anchor = self.ui.add(arcade.gui.UIAnchorLayout())
        box = arcade.gui.UIBoxLayout(space_between=12)

        entries = [
            ("New net", self._on_new),
            ("Open…", self._on_open),
            ("Examples", self._on_examples),
            ("Options", self._on_options),
            ("About / Credits", self._on_about),
            ("Quit", self._on_quit),
        ]
        for label, handler in entries:
            btn = arcade.gui.UIFlatButton(text=label, width=260, height=40)
            btn.on_click = handler
            box.add(btn)

        anchor.add(child=box, anchor_x="center_x", anchor_y="center_y")

    def on_show_view(self) -> None:
        self.ui.enable()

    def on_hide_view(self) -> None:
        self.ui.disable()

    def on_draw(self) -> None:
        self.clear()
        arcade.draw_text(
            __app_name__, self.window.width / 2,
            self.window.height - 140,
            TEXT_COLOR, 32, anchor_x="center", bold=True,
        )
        arcade.draw_text(
            "Petri nets + state machines",
            self.window.width / 2, self.window.height - 175,
            TEXT_DIM, 13, anchor_x="center",
        )
        self.ui.draw()
        arcade.draw_text("Esc — quit", 12, 12, TEXT_DIM, 10)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == arcade.key.ESCAPE:
            arcade.exit()

    def _on_new(self, _e) -> None:
        log_ui.info("menu: new net")
        from .views_editor import EditorView
        self.window.show_view(EditorView())

    def _on_open(self, _e) -> None:
        log_ui.info("menu: open")
        from . import dialogs, io_json
        path = dialogs.ask_open()
        if not path:
            return
        try:
            graph = io_json.load(path)
        except Exception as exc:
            log_ui.warning(f"open failed: {exc}")
            return
        from .views_editor import EditorView
        self.window.show_view(EditorView(graph=graph, current_path=path))

    def _on_examples(self, _e) -> None:
        log_ui.info("menu: examples")
        from .views_examples import ExamplesView
        self.window.show_view(ExamplesView())

    def _on_options(self, _e) -> None:
        from .views_options import OptionsView
        self.window.show_view(OptionsView())

    def _on_about(self, _e) -> None:
        from .views_about import AboutView
        self.window.show_view(AboutView())

    def _on_quit(self, _e) -> None:
        log_ui.info("menu: quit")
        arcade.exit()
