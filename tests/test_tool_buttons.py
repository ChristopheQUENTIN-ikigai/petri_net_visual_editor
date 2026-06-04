"""Toolbar tool-selection buttons: Select / Place / Transition / State / Arc.

For each button we cover three angles:
1. Clicking the button switches `editor.tool` to the right enum value.
2. The active highlight (`_is_active_button`) tracks the current tool.
3. The tool actually does what it should when used on the canvas — adding
   the right node kind on click, or wiring an arc between two nodes.
"""

from __future__ import annotations

import pytest

from petri_editor.views_editor import Tool


# ---------------------------------------------------------------------------
# Helper: simulate a HUD click by looking up the button rect by action name.
# ---------------------------------------------------------------------------
def _click_button(editor, action: str) -> None:
    """Click the toolbar button whose action_id == `action`."""
    for x0, y0, x1, y1, _kind, _label, btn_action, _tip in editor._hud_buttons:
        if btn_action == action:
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2
            editor.on_mouse_press(cx, cy, 1, 0)  # left-click
            return
    raise AssertionError(f"no button with action {action!r}")


def _canvas_click(editor, x: float, y: float, modifiers: int = 0,
                  button: int = 1) -> None:
    """Click at (x, y) in canvas (screen) coordinates.

    The default camera maps screen→world identity at zoom 1, centered, so
    coordinates inside the canvas region work as world coordinates.
    """
    editor.on_mouse_press(x, y, button, modifiers)
    editor.on_mouse_release(x, y, button, modifiers)


# ===========================================================================
# Select
# ===========================================================================
class TestSelectButton:
    def test_select_is_default(self, editor):
        assert editor.tool is Tool.SELECT

    def test_clicking_select_sets_tool(self, editor):
        # First switch away, then click Select.
        editor._do_action("tool_place")
        assert editor.tool is Tool.PLACE
        _click_button(editor, "tool_select")
        assert editor.tool is Tool.SELECT

    def test_select_active_highlight(self, editor):
        assert editor._is_active_button("tool_select") is True
        editor._do_action("tool_place")
        assert editor._is_active_button("tool_select") is False

    def test_select_clicking_node_adds_to_selection(self, small_net):
        editor, p1, _t, _p2, _s = small_net
        editor._do_action("tool_select")
        # Click on P1's center directly (using its world coords).
        editor.on_mouse_press(p1.x, p1.y, 1, 0)
        editor.on_mouse_release(p1.x, p1.y, 1, 0)
        assert p1 in editor.selection
        assert len(editor.selection) == 1

    def test_select_clicking_empty_starts_box_select(self, small_net):
        editor, *_ = small_net
        editor._do_action("tool_select")
        # Click in canvas where no node lives.
        editor.on_mouse_press(500, 400, 1, 0)
        # Should be in box-select mode: no selection yet, but box started.
        assert editor._box_start is not None
        # And no nodes selected.
        assert editor.selection == set()

    def test_select_shift_click_toggles(self, small_net):
        import arcade
        editor, p1, t1, _p2, _s = small_net
        editor._do_action("tool_select")
        editor.on_mouse_press(p1.x, p1.y, 1, 0)
        editor.on_mouse_release(p1.x, p1.y, 1, 0)
        assert editor.selection == {p1}
        # Shift-click T1 → adds.
        shift = arcade.key.MOD_SHIFT
        editor.on_mouse_press(t1.x, t1.y, 1, shift)
        editor.on_mouse_release(t1.x, t1.y, 1, shift)
        assert editor.selection == {p1, t1}
        # Shift-click P1 again → removes.
        editor.on_mouse_press(p1.x, p1.y, 1, shift)
        editor.on_mouse_release(p1.x, p1.y, 1, shift)
        assert editor.selection == {t1}


# ===========================================================================
# Place
# ===========================================================================
class TestPlaceButton:
    def test_clicking_place_sets_tool(self, editor):
        _click_button(editor, "tool_place")
        assert editor.tool is Tool.PLACE

    def test_place_active_highlight(self, editor):
        editor._do_action("tool_place")
        assert editor._is_active_button("tool_place") is True

    def test_place_click_adds_a_place(self, editor):
        editor._do_action("tool_place")
        assert len(editor.graph.places) == 0
        _canvas_click(editor, 400, 400)
        assert len(editor.graph.places) == 1
        p = editor.graph.places[0]
        # Default label is auto-generated.
        assert p.label == "P1"
        # Newly placed node is selected (per views_editor lines 588-590).
        assert p in editor.selection

    def test_place_click_on_existing_node_does_not_add(self, small_net):
        editor, p1, *_ = small_net
        editor._do_action("tool_place")
        before = len(editor.graph.places)
        # Click ON p1: hit_test returns p1, so we should NOT add.
        _canvas_click(editor, p1.x, p1.y)
        assert len(editor.graph.places) == before

    def test_place_undo_after_add(self, editor):
        editor._do_action("tool_place")
        _canvas_click(editor, 300, 300)
        assert len(editor.graph.places) == 1
        assert editor.history.can_undo()
        editor._do_action("undo")
        assert len(editor.graph.places) == 0


# ===========================================================================
# Transition
# ===========================================================================
class TestTransitionButton:
    def test_clicking_transition_sets_tool(self, editor):
        _click_button(editor, "tool_transition")
        assert editor.tool is Tool.TRANSITION

    def test_transition_click_adds_a_transition(self, editor):
        editor._do_action("tool_transition")
        _canvas_click(editor, 400, 400)
        assert len(editor.graph.transitions) == 1
        assert editor.graph.transitions[0].label == "T1"

    def test_transition_undoable(self, editor):
        editor._do_action("tool_transition")
        _canvas_click(editor, 400, 400)
        editor._do_action("undo")
        assert len(editor.graph.transitions) == 0


# ===========================================================================
# State
# ===========================================================================
class TestStateButton:
    def test_clicking_state_sets_tool(self, editor):
        _click_button(editor, "tool_state")
        assert editor.tool is Tool.STATE

    def test_state_click_adds_a_state(self, editor):
        editor._do_action("tool_state")
        _canvas_click(editor, 400, 400)
        assert len(editor.graph.states) == 1
        assert editor.graph.states[0].label == "S1"
        assert editor.graph.states[0].active is False  # default

    def test_state_undoable(self, editor):
        editor._do_action("tool_state")
        _canvas_click(editor, 400, 400)
        editor._do_action("undo")
        assert len(editor.graph.states) == 0


# ===========================================================================
# Arc
# ===========================================================================
class TestArcButton:
    def test_clicking_arc_sets_tool(self, editor):
        _click_button(editor, "tool_arc")
        assert editor.tool is Tool.ARC

    def test_arc_two_clicks_creates_arc(self, small_net):
        editor, p1, t1, _p2, _s = small_net
        # Wipe existing arc to get a clean test.
        editor.graph.arcs.clear()
        editor._do_action("tool_arc")
        # First click: selects source.
        editor.on_mouse_press(p1.x, p1.y, 1, 0)
        editor.on_mouse_release(p1.x, p1.y, 1, 0)
        assert editor.arc_src is p1
        # Second click: creates arc.
        editor.on_mouse_press(t1.x, t1.y, 1, 0)
        editor.on_mouse_release(t1.x, t1.y, 1, 0)
        assert editor.arc_src is None
        assert len(editor.graph.arcs) == 1
        a = editor.graph.arcs[0]
        assert a.src is p1 and a.dst is t1

    def test_arc_rejects_illegal_pair(self, small_net):
        editor, p1, _t, p2, _s = small_net
        editor.graph.arcs.clear()
        editor._do_action("tool_arc")
        # place -> place is illegal.
        editor.on_mouse_press(p1.x, p1.y, 1, 0)
        editor.on_mouse_release(p1.x, p1.y, 1, 0)
        editor.on_mouse_press(p2.x, p2.y, 1, 0)
        editor.on_mouse_release(p2.x, p2.y, 1, 0)
        assert len(editor.graph.arcs) == 0
        # Source must be cleared regardless.
        assert editor.arc_src is None

    def test_arc_clicking_empty_resets_source(self, small_net):
        editor, p1, *_ = small_net
        editor._do_action("tool_arc")
        editor.on_mouse_press(p1.x, p1.y, 1, 0)
        editor.on_mouse_release(p1.x, p1.y, 1, 0)
        assert editor.arc_src is p1
        # Click empty space: source resets to None.
        editor.on_mouse_press(600, 600, 1, 0)
        editor.on_mouse_release(600, 600, 1, 0)
        assert editor.arc_src is None

    def test_arc_escape_cancels_in_progress(self, small_net):
        import arcade
        editor, p1, *_ = small_net
        editor._do_action("tool_arc")
        editor.on_mouse_press(p1.x, p1.y, 1, 0)
        editor.on_mouse_release(p1.x, p1.y, 1, 0)
        assert editor.arc_src is p1
        editor.on_key_press(arcade.key.ESCAPE, 0)
        assert editor.arc_src is None

    def test_arc_duplicate_increments_weight(self, small_net):
        editor, p1, t1, *_ = small_net
        # Start clean; small_net pre-built one P1->T1 arc, so use it.
        assert len(editor.graph.arcs) == 2  # P1->T1 and T1->P2
        editor._do_action("tool_arc")
        # Re-add P1 -> T1: should bump weight, not create a second arc.
        editor.on_mouse_press(p1.x, p1.y, 1, 0)
        editor.on_mouse_release(p1.x, p1.y, 1, 0)
        editor.on_mouse_press(t1.x, t1.y, 1, 0)
        editor.on_mouse_release(t1.x, t1.y, 1, 0)
        assert len(editor.graph.arcs) == 2
        a = next(a for a in editor.graph.arcs
                 if a.src is p1 and a.dst is t1)
        assert a.weight == 2
