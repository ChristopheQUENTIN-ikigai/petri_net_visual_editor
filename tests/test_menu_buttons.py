"""Main-menu and Options-view buttons.

The menu has 6 buttons (New / Open / Examples / Options / About / Quit).
We exercise each via its `_on_*` handler since arcade.gui.UIFlatButton
in our stub forwards `click()` to `on_click`.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# MainMenu fixtures.
# ---------------------------------------------------------------------------
@pytest.fixture
def menu():
    import arcade
    from petri_editor.views_menu import MainMenuView
    win = arcade.Window(1280, 820, "menu-test")
    v = MainMenuView()
    win.show_view(v)
    return v


def _menu_buttons(menu_view) -> dict[str, object]:
    """Pull the menu's UIFlatButton widgets out by their text labels."""
    # The constructor adds them in this order under an anchor → box layout.
    root = menu_view.ui._root
    box = root.children[0]
    return {b.text: b for b in box.children}


# ===========================================================================
# Main menu buttons
# ===========================================================================
class TestMenuNewButton:
    def test_new_net_opens_editor(self, menu):
        btns = _menu_buttons(menu)
        btns["New net"].click()
        # Latest view on the window should be an EditorView.
        from petri_editor.views_editor import EditorView
        assert isinstance(menu.window._views[-1], EditorView)

    def test_new_net_starts_empty(self, menu):
        _menu_buttons(menu)["New net"].click()
        editor = menu.window._views[-1]
        assert len(editor.graph.places) == 0
        assert len(editor.graph.transitions) == 0
        assert len(editor.graph.states) == 0


class TestMenuOpenButton:
    def test_open_with_no_tk_returns_silently(self, menu, monkeypatch):
        # Without Tkinter, dialogs.ask_open returns None and the handler
        # short-circuits — no view change.
        from petri_editor import dialogs
        monkeypatch.setattr(dialogs, "tkinter_available", lambda: False)
        before_views = len(menu.window._views)
        _menu_buttons(menu)["Open…"].click()
        # No new view should have been pushed.
        assert len(menu.window._views) == before_views

    def test_open_with_valid_path_opens_editor(self, menu, tmp_path, monkeypatch):
        # Build a real JSON file then patch ask_open to return it.
        from petri_editor import dialogs, io_json
        from petri_editor.model import Graph
        g = Graph()
        g.add_place(50, 50, "P1", tokens=2)
        target = tmp_path / "g.json"
        io_json.save(g, target)
        monkeypatch.setattr(dialogs, "ask_open", lambda **kw: str(target))
        _menu_buttons(menu)["Open…"].click()
        from petri_editor.views_editor import EditorView
        latest = menu.window._views[-1]
        assert isinstance(latest, EditorView)
        assert len(latest.graph.places) == 1
        assert latest.current_path == str(target)

    def test_open_with_bad_path_does_not_crash(self, menu, tmp_path, monkeypatch):
        from petri_editor import dialogs
        monkeypatch.setattr(
            dialogs, "ask_open",
            lambda **kw: str(tmp_path / "missing.json"),
        )
        before_views = len(menu.window._views)
        _menu_buttons(menu)["Open…"].click()
        # Failure path: no editor view pushed, but no crash either.
        assert len(menu.window._views) == before_views


class TestMenuExamplesButton:
    def test_examples_opens_examples_view(self, menu):
        _menu_buttons(menu)["Examples"].click()
        from petri_editor.views_examples import ExamplesView
        assert isinstance(menu.window._views[-1], ExamplesView)


class TestMenuOptionsButton:
    def test_options_opens_options_view(self, menu):
        _menu_buttons(menu)["Options"].click()
        from petri_editor.views_options import OptionsView
        assert isinstance(menu.window._views[-1], OptionsView)


class TestMenuAboutButton:
    def test_about_opens_about_view(self, menu):
        _menu_buttons(menu)["About / Credits"].click()
        from petri_editor.views_about import AboutView
        assert isinstance(menu.window._views[-1], AboutView)


class TestMenuQuitButton:
    def test_quit_calls_arcade_exit(self, menu, monkeypatch):
        import arcade
        called: list[bool] = []
        monkeypatch.setattr(arcade, "exit", lambda: called.append(True))
        _menu_buttons(menu)["Quit"].click()
        assert called == [True]

    def test_escape_in_menu_quits(self, menu, monkeypatch):
        import arcade
        called: list[bool] = []
        monkeypatch.setattr(arcade, "exit", lambda: called.append(True))
        menu.on_key_press(arcade.key.ESCAPE, 0)
        assert called == [True]


# ===========================================================================
# Options view buttons
# ===========================================================================
@pytest.fixture
def options():
    import arcade
    from petri_editor.views_options import OptionsView
    win = arcade.Window(1280, 820, "opts-test")
    v = OptionsView()
    win.show_view(v)
    return v


def _options_widgets(opt_view):
    """Walk the option view's layout to find every button by its text."""
    found: list = []
    def walk(node):
        if hasattr(node, "children"):
            for c in node.children:
                walk(c)
        else:
            found.append(node)
        # layouts also have text in our stub if set
        if hasattr(node, "text") and node.text:
            found.append(node)
    walk(opt_view.ui._root)
    return found


class TestOptionsToggles:
    def test_toggle_show_grid(self, options):
        from petri_editor.views_options import SETTINGS
        before = SETTINGS.show_grid
        # Find the "ON"/"OFF" button next to "Show grid" — it has text "ON" or "OFF".
        # The first toggle row added is "Show grid".
        root = options.ui._root
        stack = root.children[0]
        # stack.children[0] is the row for show_grid.
        row = stack.children[0]
        # row children: [label, ON/OFF button]
        toggle_btn = row.children[1]
        toggle_btn.click()
        assert SETTINGS.show_grid is (not before)
        # And the button label flipped.
        assert toggle_btn.text in ("ON", "OFF")

    def test_toggle_snap(self, options):
        from petri_editor.views_options import SETTINGS
        before = SETTINGS.snap_to_grid
        root = options.ui._root
        stack = root.children[0]
        # Row 1 is snap_to_grid.
        row = stack.children[1]
        toggle_btn = row.children[1]
        toggle_btn.click()
        assert SETTINGS.snap_to_grid is (not before)

    def test_grid_size_plus_minus(self, options):
        from petri_editor.views_options import SETTINGS
        original = SETTINGS.grid_size
        root = options.ui._root
        stack = root.children[0]
        # Row 2 is grid_size: [label, minus, val, plus]
        row = stack.children[2]
        minus, _val, plus = row.children[1], row.children[2], row.children[3]
        plus.click()
        assert SETTINGS.grid_size == original + 4
        minus.click()
        assert SETTINGS.grid_size == original

    def test_grid_size_clamps_at_bounds(self, options):
        from petri_editor.views_options import SETTINGS
        SETTINGS.grid_size = 4  # min
        root = options.ui._root
        stack = root.children[0]
        row = stack.children[2]
        minus = row.children[1]
        minus.click()  # would go below 4
        assert SETTINGS.grid_size == 4

    def test_verbose_log_toggle_changes_logger_level(self, options):
        import logging
        from petri_editor.views_options import SETTINGS
        SETTINGS.verbose_log = False
        root = options.ui._root
        stack = root.children[0]
        # Row 4 is verbose_log.
        row = stack.children[4]
        toggle_btn = row.children[1]
        toggle_btn.click()
        assert SETTINGS.verbose_log is True
        assert logging.getLogger("petri").level == logging.DEBUG
        # Toggle back.
        toggle_btn.click()
        assert SETTINGS.verbose_log is False
        assert logging.getLogger("petri").level == logging.INFO


class TestOptionsBackButton:
    def test_back_returns_to_menu(self, options):
        # The Back button is at the bottom of the stack.
        root = options.ui._root
        stack = root.children[0]
        back = stack.children[-1]
        assert back.text == "Back to menu"
        back.click()
        from petri_editor.views_menu import MainMenuView
        assert isinstance(options.window._views[-1], MainMenuView)

    def test_escape_returns_to_menu(self, options):
        import arcade
        options.on_key_press(arcade.key.ESCAPE, 0)
        from petri_editor.views_menu import MainMenuView
        assert isinstance(options.window._views[-1], MainMenuView)
