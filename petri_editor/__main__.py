"""Package entry: opens splash → menu → editor flow."""

from __future__ import annotations

import arcade

from . import __app_name__
from .logger import log_ui
from .theme import WINDOW_H, WINDOW_W
from .views_splash import SplashView


def main() -> None:
    log_ui.info(f"start {__app_name__}")
    window = arcade.Window(WINDOW_W, WINDOW_H, __app_name__)
    window.show_view(SplashView())
    arcade.run()
    log_ui.info("exit")


if __name__ == "__main__":
    main()
