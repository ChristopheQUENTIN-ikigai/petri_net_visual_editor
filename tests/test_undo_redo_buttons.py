"""Undo / Redo buttons.

Covers: dispatch, history stack interaction, disabled-button reporting,
selection clearing on undo, and undo of a destructive sequence.
"""

from __future__ import annotations

import pytest


# ===========================================================================
# Disabled state
# ===========================================================================
class TestUndoRedoDisabledState:
    def test_undo_disabled_when_history_empty(self, editor):
        assert editor._is_disabled_button("undo") is True
        assert editor._is_disabled_button("redo") is True

    def test_undo_enabled_after_action(self, editor):
        editor._do_action("tool_place")
        editor.on_mouse_press(400, 400, 1, 0)
        editor.on_mouse_release(400, 400, 1, 0)
        assert editor._is_disabled_button("undo") is False
        assert editor._is_disabled_button("redo") is True  # nothing to redo yet

    def test_redo_enabled_after_undo(self, editor):
        editor._do_action("tool_place")
        editor.on_mouse_press(400, 400, 1, 0)
        editor.on_mouse_release(400, 400, 1, 0)
        editor._do_action("undo")
        assert editor._is_disabled_button("undo") is True
        assert editor._is_disabled_button("redo") is False


# ===========================================================================
# Undo
# ===========================================================================
class TestUndoButton:
    def test_undo_no_op_on_empty(self, editor):
        # Pressing undo with nothing on the stack should not crash.
        editor._do_action("undo")
        assert not editor.history.can_undo()

    def test_undo_reverses_add_node(self, editor):
        editor._do_action("tool_place")
        editor.on_mouse_press(300, 300, 1, 0)
        editor.on_mouse_release(300, 300, 1, 0)
        assert len(editor.graph.places) == 1
        editor._do_action("undo")
        assert len(editor.graph.places) == 0

    def test_undo_reverses_add_arc(self, small_net):
        editor, p1, t1, _p2, _s = small_net
        # small_net set up: 2 arcs.
        before = len(editor.graph.arcs)
        editor._do_action("tool_arc")
        # Add a redundant P1 -> T1 (will bump weight from 1 to 2).
        editor.on_mouse_press(p1.x, p1.y, 1, 0)
        editor.on_mouse_release(p1.x, p1.y, 1, 0)
        editor.on_mouse_press(t1.x, t1.y, 1, 0)
        editor.on_mouse_release(t1.x, t1.y, 1, 0)
        a = next(a for a in editor.graph.arcs
                 if a.src is p1 and a.dst is t1)
        assert a.weight == 2
        editor._do_action("undo")
        assert a.weight == 1
        assert len(editor.graph.arcs) == before

    def test_undo_clears_selection(self, editor):
        # Add a node (which auto-selects it), then undo.
        editor._do_action("tool_place")
        editor.on_mouse_press(300, 300, 1, 0)
        editor.on_mouse_release(300, 300, 1, 0)
        assert editor.selection
        editor._do_action("undo")
        # Per views_editor lines 830-832: undo clears selection.
        assert editor.selection == set()


# ===========================================================================
# Redo
# ===========================================================================
class TestRedoButton:
    def test_redo_no_op_on_empty(self, editor):
        editor._do_action("redo")  # should not crash

    def test_redo_replays_undone_action(self, editor):
        editor._do_action("tool_place")
        editor.on_mouse_press(300, 300, 1, 0)
        editor.on_mouse_release(300, 300, 1, 0)
        editor._do_action("undo")
        assert len(editor.graph.places) == 0
        editor._do_action("redo")
        assert len(editor.graph.places) == 1

    def test_redo_stack_clears_on_new_action(self, editor):
        # add → undo → new action: redo stack should be discarded
        editor._do_action("tool_place")
        editor.on_mouse_press(300, 300, 1, 0)
        editor.on_mouse_release(300, 300, 1, 0)
        editor._do_action("undo")
        assert editor.history.can_redo()
        # New unrelated action.
        editor.on_mouse_press(500, 500, 1, 0)
        editor.on_mouse_release(500, 500, 1, 0)
        # Redo stack must now be empty.
        assert not editor.history.can_redo()


# ===========================================================================
# Round-trips
# ===========================================================================
class TestUndoRedoRoundTrip:
    def test_long_sequence_round_trip(self, editor):
        editor._do_action("tool_place")
        for x in (100, 200, 300, 400):
            editor.on_mouse_press(x, 300, 1, 0)
            editor.on_mouse_release(x, 300, 1, 0)
        assert len(editor.graph.places) == 4
        for _ in range(4):
            editor._do_action("undo")
        assert len(editor.graph.places) == 0
        for _ in range(4):
            editor._do_action("redo")
        assert len(editor.graph.places) == 4

    def test_undo_after_token_change(self, editor):
        # Add a place via the tool, then dial tokens via mouse-scroll on it.
        editor._do_action("tool_place")
        editor.on_mouse_press(400, 400, 1, 0)
        editor.on_mouse_release(400, 400, 1, 0)
        p = editor.graph.places[0]
        # Switch back to select so on_mouse_scroll routes to token-adjust.
        editor._do_action("tool_select")
        editor.on_mouse_scroll(p.x, p.y, 0, 3)
        assert p.tokens == 3
        editor._do_action("undo")
        assert p.tokens == 0  # tokens delta undone
