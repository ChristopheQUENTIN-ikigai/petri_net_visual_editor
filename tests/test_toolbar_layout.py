"""Toolbar layout regressions.

The screenshot showed the right-most ? button clipped past the window's
right edge at 1280-wide. _build_hud now scales button widths down when the
natural layout would overflow; these tests pin that behaviour.
"""

from __future__ import annotations

import pytest


def _make_editor(width: int, height: int = 820):
    import arcade
    from petri_editor.views_editor import EditorView
    win = arcade.Window(width, height, "layout-test")
    v = EditorView()
    win.show_view(v)
    return v


@pytest.mark.parametrize("width", [1280, 1440, 1024, 900, 800])
def test_all_buttons_fit_inside_window(width):
    editor = _make_editor(width)
    assert editor._hud_buttons, "HUD should have buttons"
    rightmost = max(b[2] for b in editor._hud_buttons)  # x1
    assert rightmost <= width, (
        f"toolbar overflows: rightmost x1={rightmost} > width={width}"
    )


def test_all_buttons_have_minimum_width():
    """Even at narrow widths, buttons stay clickable (≥ 28 px)."""
    editor = _make_editor(800)
    for x0, _y0, x1, _y1, *_ in editor._hud_buttons:
        assert x1 - x0 >= 28


def test_help_button_is_last():
    editor = _make_editor(1280)
    last = editor._hud_buttons[-1]
    assert last[6] == "help"


def test_buttons_dont_overlap():
    editor = _make_editor(1280)
    rects = sorted(editor._hud_buttons, key=lambda r: r[0])
    for a, b in zip(rects, rects[1:]):
        assert a[2] <= b[0], f"button {a[5]!r} overlaps {b[5]!r}"


def test_hit_testing_works_on_last_button():
    """Regression for the ?-button-clipped bug: the rightmost button must
    still be hittable inside the window."""
    editor = _make_editor(1280)
    last_x0, last_y0, last_x1, last_y1, _kind, _label, action, _tip = \
        editor._hud_buttons[-1]
    cx = (last_x0 + last_x1) / 2
    cy = (last_y0 + last_y1) / 2
    assert cx < editor.window.width
    assert editor._hud_hit(cx, cy) == action
