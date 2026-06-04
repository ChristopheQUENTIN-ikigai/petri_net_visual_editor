"""Test fixtures and arcade stubbing.

Why we stub arcade:
    The editor view, inspector, and overlays import `arcade` and `arcade.gui`
    at module import time, and arcade itself opens an OpenGL context as soon
    as a Window is constructed. Tests run headless on CI and on dev boxes
    without a display server, so we install lightweight stand-ins before any
    petri_editor module is imported.

What we stub:
    Just enough of the arcade surface area to let import succeed and let our
    button-dispatch code paths run. Drawing functions are no-ops, Camera2D
    holds plain attributes, key constants are unique sentinels. arcade.gui
    widgets are dataclass-style stubs that record callbacks and clicks.

We do NOT stub:
    Any petri_editor module. The model, commands, simulator, IO, history —
    those are tested as-is. The whole point of this suite is that toolbar
    button handlers exercise the real History, real Graph, real Simulator.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


# Make `import petri_editor.*` work when pytest is invoked from any cwd.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ---------------------------------------------------------------------------
# Arcade stub installation — must run before any petri_editor import.
# ---------------------------------------------------------------------------
def _install_arcade_stub() -> None:
    if "arcade" in sys.modules:
        return  # real arcade already loaded; nothing to do.

    arcade = types.ModuleType("arcade")

    # ---- key constants: unique, stable sentinels ----
    class _KeyNamespace:
        """All arcade.key.* attrs become unique ints on access."""
        _next = 1
        _cache: dict[str, int] = {}
        # Modifier bits — use distinct power-of-two so masking works.
        MOD_SHIFT = 1
        MOD_CTRL = 2
        MOD_ALT = 4

        def __getattr__(self, name: str) -> int:
            if name in self._cache:
                return self._cache[name]
            self._cache[name] = self._next
            type(self)._next += 1
            return self._cache[name]

    arcade.key = _KeyNamespace()

    # ---- mouse buttons ----
    arcade.MOUSE_BUTTON_LEFT = 1
    arcade.MOUSE_BUTTON_RIGHT = 2
    arcade.MOUSE_BUTTON_MIDDLE = 4

    # ---- drawing primitives: no-ops ----
    def _noop(*args, **kwargs):
        return None

    arcade.draw_text = _noop
    arcade.draw_circle_filled = _noop
    arcade.draw_circle_outline = _noop
    arcade.draw_line = _noop
    arcade.draw_rect_filled = _noop
    arcade.draw_rect_outline = _noop

    class _LBWH:
        __slots__ = ("x", "y", "width", "height")
        def __init__(self, x, y, w, h):
            self.x, self.y, self.width, self.height = x, y, w, h
    arcade.LBWH = _LBWH

    # ---- Text: cached object the editor uses for the toolbar ----
    class _Text:
        def __init__(self, text, x, y, color=None, font_size=12, **kw):
            self.text = text
            self.x = x
            self.y = y
            self.color = color
            self.font_size = font_size
        def draw(self):
            pass
    arcade.Text = _Text

    # ---- Camera2D ----
    class _Camera2D:
        def __init__(self):
            self.position = (0.0, 0.0)
            self.zoom = 1.0
        def use(self):
            pass
    arcade.Camera2D = _Camera2D

    # ---- Window ----
    class _Window:
        def __init__(self, w=1280, h=820, title=""):
            self.width = w
            self.height = h
            self.title = title
            self._views: list = []
        def show_view(self, view):
            self._views.append(view)
            # Mirror arcade's dispatch: hide previous, show new.
            if len(self._views) > 1:
                prev = self._views[-2]
                if hasattr(prev, "on_hide_view"):
                    prev.on_hide_view()
            view.window = self
            if hasattr(view, "on_show_view"):
                view.on_show_view()
    arcade.Window = _Window

    # ---- View ----
    class _View:
        def __init__(self):
            self.window = None
            self.background_color = (0, 0, 0)
        def clear(self):
            pass
    arcade.View = _View

    arcade.run = lambda: None
    arcade.exit = lambda: None

    # ---- arcade.gui ----
    gui = types.ModuleType("arcade.gui")

    class _UIWidget:
        def __init__(self, **kw):
            self.text = kw.get("text", "")
            self.width = kw.get("width", 0)
            self.height = kw.get("height", 0)
            self.font_size = kw.get("font_size", 12)
            self.text_color = kw.get("text_color", None)
            self._on_click = None
            self._on_change = None
        @property
        def on_click(self):
            return self._on_click
        @on_click.setter
        def on_click(self, cb):
            self._on_click = cb
        @property
        def on_change(self):
            return self._on_change
        @on_change.setter
        def on_change(self, cb):
            self._on_change = cb
        def click(self):
            """Test helper: synthesise a click event."""
            if self._on_click:
                self._on_click(None)

    gui.UIFlatButton = _UIWidget
    gui.UILabel = _UIWidget
    gui.UIInputText = _UIWidget
    gui.UISpace = _UIWidget

    class _UILayout(_UIWidget):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.children: list = []
            self.vertical = kw.get("vertical", True)
            self.space_between = kw.get("space_between", 0)
            self.align = kw.get("align", "")
        def add(self, child=None, **kw):
            if child is not None:
                self.children.append(child)
                return child
            return None
        def clear(self):
            self.children.clear()

    class _UIBoxLayout(_UILayout):
        pass

    class _UIAnchorLayout(_UILayout):
        def add(self, child=None, **kw):
            if child is not None:
                self.children.append(child)
                return child
            return None

    gui.UIBoxLayout = _UIBoxLayout
    gui.UIAnchorLayout = _UIAnchorLayout

    class _UIManager:
        def __init__(self):
            self._enabled = False
            self._root: _UIAnchorLayout | None = None
        def add(self, layout):
            self._root = layout
            return layout
        def enable(self):
            self._enabled = True
        def disable(self):
            self._enabled = False
        def draw(self):
            pass
    gui.UIManager = _UIManager

    arcade.gui = gui

    # exceptions module — the perf warning lives here in real arcade.
    exceptions = types.ModuleType("arcade.exceptions")
    class PerformanceWarning(UserWarning):
        pass
    exceptions.PerformanceWarning = PerformanceWarning
    arcade.exceptions = exceptions

    sys.modules["arcade"] = arcade
    sys.modules["arcade.gui"] = gui
    sys.modules["arcade.exceptions"] = exceptions


_install_arcade_stub()


# ---------------------------------------------------------------------------
# Auto-reset module-level singletons between tests.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_settings():
    """SETTINGS is a module-level singleton; reset between tests."""
    from petri_editor.views_options import SETTINGS, Settings
    saved = {f: getattr(SETTINGS, f) for f in Settings.__dataclass_fields__}
    yield
    for f, v in saved.items():
        setattr(SETTINGS, f, v)


# ---------------------------------------------------------------------------
# Common fixtures.
# ---------------------------------------------------------------------------
@pytest.fixture
def editor():
    """A fully constructed editor view backed by a stub window.

    on_show_view runs, so all overlays, the inspector, the camera, and the
    HUD button list are populated — exactly as in a real session right after
    'menu: new net' fires.
    """
    import arcade
    from petri_editor.views_editor import EditorView

    win = arcade.Window(1280, 820, "test")
    view = EditorView()
    win.show_view(view)
    return view


@pytest.fixture
def small_net(editor):
    """An editor with a tiny live net: P1 (1 token) -> T1 -> P2, plus S1.

    Returns (editor, place1, transition, place2, state).
    """
    g = editor.graph
    p1 = g.add_place(100, 100, "P1", tokens=1)
    t1 = g.add_transition(200, 100, "T1")
    p2 = g.add_place(300, 100, "P2", tokens=0)
    s1 = g.add_state(200, 200, "S1", active=False)
    g.add_arc(p1, t1)
    g.add_arc(t1, p2)
    # Capture this as the initial marking so reset() restores it.
    editor.simulator.capture_initial()
    return editor, p1, t1, p2, s1
