"""Inspector panel buttons and editor keyboard shortcuts.

Inspector covers: rename input, token +/- buttons, Active toggle for states.
Keyboard covers: Ctrl+S/O/Z/Y/A/D, Delete, Home, Esc, F5, F6, F.
All shortcuts route through the same _do_action dispatcher as the toolbar.
"""

from __future__ import annotations

import pytest


# ===========================================================================
# Inspector — node selection wires up the right widgets
# ===========================================================================
class TestInspectorWiring:
    def test_no_selection_shows_empty_inspector(self, editor):
        # Brand-new editor: nothing selected, no widgets in the box.
        assert editor.inspector._target is None
        assert editor.inspector._box.children == []

    def test_place_selection_builds_label_and_tokens_fields(self, small_net):
        editor, p1, *_ = small_net
        editor._set_selection({p1})
        kids = editor.inspector._box.children
        # 3 children: label-wrap, tokens-wrap, position label.
        assert len(kids) == 3

    def test_transition_selection_builds_only_label(self, small_net):
        editor, _p1, t1, _p2, _s = small_net
        editor._set_selection({t1})
        kids = editor.inspector._box.children
        # Transition: label-wrap + position label = 2 children.
        assert len(kids) == 2

    def test_state_selection_builds_label_and_active(self, small_net):
        editor, _p1, _t, _p2, s1 = small_net
        editor._set_selection({s1})
        kids = editor.inspector._box.children
        assert len(kids) == 3  # label-wrap, active-wrap, position label

    def test_changing_selection_rebuilds(self, small_net):
        editor, p1, t1, *_ = small_net
        editor._set_selection({p1})
        place_kids = len(editor.inspector._box.children)
        editor._set_selection({t1})
        trans_kids = len(editor.inspector._box.children)
        assert place_kids != trans_kids


# ===========================================================================
# Inspector — token +/- buttons
# ===========================================================================
class TestInspectorTokenButtons:
    def _token_buttons(self, editor):
        """Walk to the [-, val, +] row inside the place inspector."""
        # box children: [label_wrap, tokens_wrap, pos_label]
        tokens_wrap = editor.inspector._box.children[1]
        # tokens_wrap children: [label, row]
        row = tokens_wrap.children[1]
        # row children: [minus, val_label, plus]
        return row.children[0], row.children[1], row.children[2]

    def test_plus_increments_tokens(self, small_net):
        editor, p1, *_ = small_net
        editor._set_selection({p1})
        minus, val, plus = self._token_buttons(editor)
        before = p1.tokens
        plus.click()
        assert p1.tokens == before + 1
        assert val.text == str(p1.tokens)

    def test_minus_decrements_tokens(self, small_net):
        editor, p1, *_ = small_net
        p1.tokens = 3
        editor._set_selection({p1})
        minus, val, _plus = self._token_buttons(editor)
        minus.click()
        assert p1.tokens == 2

    def test_minus_clamps_at_zero(self, small_net):
        editor, p1, *_ = small_net
        p1.tokens = 0
        editor._set_selection({p1})
        minus, val, _plus = self._token_buttons(editor)
        minus.click()
        assert p1.tokens == 0  # ChangeTokensCmd.do uses max(0, …)

    def test_token_change_is_undoable(self, small_net):
        editor, p1, *_ = small_net
        editor._set_selection({p1})
        _minus, _val, plus = self._token_buttons(editor)
        plus.click()
        plus.click()
        assert p1.tokens == 3
        editor._do_action("undo")
        assert p1.tokens == 2
        editor._do_action("undo")
        assert p1.tokens == 1


# ===========================================================================
# Inspector — Active toggle for states
# ===========================================================================
class TestInspectorActiveButton:
    def test_active_toggle_flips_state(self, small_net):
        editor, _p1, _t, _p2, s1 = small_net
        assert s1.active is False
        editor._set_selection({s1})
        # State inspector: [label_wrap, active_wrap, pos_label]
        active_wrap = editor.inspector._box.children[1]
        # active_wrap children: [label, btn]
        btn = active_wrap.children[1]
        btn.click()
        assert s1.active is True
        btn.click()
        assert s1.active is False

    def test_active_toggle_is_undoable(self, small_net):
        editor, _p1, _t, _p2, s1 = small_net
        editor._set_selection({s1})
        active_wrap = editor.inspector._box.children[1]
        btn = active_wrap.children[1]
        btn.click()
        assert s1.active is True
        editor._do_action("undo")
        assert s1.active is False


# ===========================================================================
# Inspector — label rename
# ===========================================================================
class TestInspectorRename:
    def test_label_change_pushes_command(self, small_net):
        editor, p1, *_ = small_net
        editor._set_selection({p1})
        # box.children[0] is the label wrap, child[1] is the UIInputText.
        label_wrap = editor.inspector._box.children[0]
        ti = label_wrap.children[1]
        # Simulate user editing — set the text then trigger on_change.
        ti.text = "NewName"
        if ti._on_change:
            ti._on_change(None)
        assert p1.label == "NewName"
        assert editor.history.can_undo()

    def test_empty_label_is_rejected(self, small_net):
        editor, p1, *_ = small_net
        original = p1.label
        editor._set_selection({p1})
        label_wrap = editor.inspector._box.children[0]
        ti = label_wrap.children[1]
        ti.text = "   "  # whitespace only
        if ti._on_change:
            ti._on_change(None)
        assert p1.label == original  # unchanged

    def test_unchanged_label_does_not_push(self, small_net):
        editor, p1, *_ = small_net
        editor._set_selection({p1})
        label_wrap = editor.inspector._box.children[0]
        ti = label_wrap.children[1]
        # Same text as current label.
        ti.text = p1.label
        if ti._on_change:
            ti._on_change(None)
        assert not editor.history.can_undo()


# ===========================================================================
# Editor keyboard shortcuts
# ===========================================================================
class TestEditorKeyboardShortcuts:
    def test_keys_1_through_5_select_tools(self, editor):
        import arcade
        from petri_editor.views_editor import Tool
        cases = [
            (arcade.key.KEY_1, Tool.SELECT),
            (arcade.key.KEY_2, Tool.PLACE),
            (arcade.key.KEY_3, Tool.TRANSITION),
            (arcade.key.KEY_4, Tool.STATE),
            (arcade.key.KEY_5, Tool.ARC),
        ]
        for key, expected in cases:
            editor.on_key_press(key, 0)
            assert editor.tool is expected, f"{key} -> {expected}"

    def test_ctrl_a_selects_all(self, small_net):
        import arcade
        editor, *_ = small_net
        editor.on_key_press(arcade.key.A, arcade.key.MOD_CTRL)
        assert len(editor.selection) == 4  # 2 places + 1 transition + 1 state

    def test_ctrl_d_clears_selection(self, small_net):
        import arcade
        editor, p1, *_ = small_net
        editor._set_selection({p1})
        editor.on_key_press(arcade.key.D, arcade.key.MOD_CTRL)
        assert editor.selection == set()

    def test_delete_removes_selection(self, small_net):
        import arcade
        editor, p1, *_ = small_net
        editor._set_selection({p1})
        editor.on_key_press(arcade.key.DELETE, 0)
        assert p1 not in editor.graph.places
        assert editor.selection == set()
        # Incident arc P1->T1 also gone.
        assert all(a.src is not p1 and a.dst is not p1
                   for a in editor.graph.arcs)

    def test_backspace_removes_selection(self, small_net):
        import arcade
        editor, p1, *_ = small_net
        editor._set_selection({p1})
        editor.on_key_press(arcade.key.BACKSPACE, 0)
        assert p1 not in editor.graph.places

    def test_delete_with_no_selection_no_op(self, editor):
        import arcade
        editor.on_key_press(arcade.key.DELETE, 0)
        assert not editor.history.can_undo()

    def test_delete_is_undoable(self, small_net):
        import arcade
        editor, p1, *_ = small_net
        editor._set_selection({p1})
        editor.on_key_press(arcade.key.DELETE, 0)
        assert p1 not in editor.graph.places
        editor._do_action("undo")
        # Node restored with same id and incident arcs.
        restored = next((p for p in editor.graph.places if p.id == p1.id), None)
        assert restored is not None
        assert any(a.src.id == p1.id for a in editor.graph.arcs)

    def test_home_resets_camera(self, editor):
        import arcade
        editor.camera_world.zoom = 2.5
        editor.camera_world.cx = 999.0
        editor.on_key_press(arcade.key.HOME, 0)
        assert editor.camera_world.zoom == 1.0
        assert editor.camera_world.cx == editor.window.width / 2

    def test_f5_steps_simulation(self, small_net):
        import arcade
        editor, p1, _t, p2, _s = small_net
        editor.on_key_press(arcade.key.F5, 0)
        assert p1.tokens == 0 and p2.tokens == 1

    def test_f6_resets_marking(self, small_net):
        import arcade
        editor, p1, _t, p2, _s = small_net
        editor._do_action("step")
        editor.on_key_press(arcade.key.F6, 0)
        assert p1.tokens == 1 and p2.tokens == 0

    def test_f_fires_selected_transition(self, small_net):
        import arcade
        editor, p1, t1, p2, _s = small_net
        editor._set_selection({t1})
        editor.on_key_press(arcade.key.F, 0)
        assert p1.tokens == 0 and p2.tokens == 1

    def test_f_no_op_when_transition_disabled(self, editor):
        import arcade
        # Transition with no input is not enabled.
        t = editor.graph.add_transition(100, 100, "T1")
        editor._set_selection({t})
        editor.on_key_press(arcade.key.F, 0)
        # No change pushed.
        assert not editor.history.can_undo()

    def test_ctrl_z_undoes(self, editor):
        import arcade
        editor._do_action("tool_place")
        editor.on_mouse_press(300, 300, 1, 0)
        editor.on_mouse_release(300, 300, 1, 0)
        editor.on_key_press(arcade.key.Z, arcade.key.MOD_CTRL)
        assert len(editor.graph.places) == 0

    def test_ctrl_y_redoes(self, editor):
        import arcade
        editor._do_action("tool_place")
        editor.on_mouse_press(300, 300, 1, 0)
        editor.on_mouse_release(300, 300, 1, 0)
        editor._do_action("undo")
        editor.on_key_press(arcade.key.Y, arcade.key.MOD_CTRL)
        assert len(editor.graph.places) == 1

    def test_ctrl_shift_z_redoes(self, editor):
        import arcade
        editor._do_action("tool_place")
        editor.on_mouse_press(300, 300, 1, 0)
        editor.on_mouse_release(300, 300, 1, 0)
        editor._do_action("undo")
        editor.on_key_press(arcade.key.Z,
                            arcade.key.MOD_CTRL | arcade.key.MOD_SHIFT)
        assert len(editor.graph.places) == 1

    def test_escape_three_step_dance(self, small_net):
        """Esc cancels arc → clears selection → exits to menu."""
        import arcade
        from petri_editor.views_menu import MainMenuView
        editor, p1, *_ = small_net
        # Step 1: in arc mode with src set → Esc cancels arc.
        editor._do_action("tool_arc")
        editor.arc_src = p1
        editor.on_key_press(arcade.key.ESCAPE, 0)
        assert editor.arc_src is None
        # Step 2: with selection → Esc clears it.
        editor._set_selection({p1})
        editor.on_key_press(arcade.key.ESCAPE, 0)
        assert editor.selection == set()
        # Step 3: nothing selected → Esc returns to menu.
        editor.on_key_press(arcade.key.ESCAPE, 0)
        assert isinstance(editor.window._views[-1], MainMenuView)


# ===========================================================================
# Help overlay closes on key/click
# ===========================================================================
class TestHelpOverlayDismiss:
    def test_overlay_closes_on_h(self, editor):
        import arcade
        editor.help_overlay.is_open = True
        editor.on_key_press(arcade.key.H, 0)
        assert editor.help_overlay.is_open is False

    def test_overlay_closes_on_escape(self, editor):
        import arcade
        editor.help_overlay.is_open = True
        editor.on_key_press(arcade.key.ESCAPE, 0)
        assert editor.help_overlay.is_open is False

    def test_overlay_closes_on_click(self, editor):
        editor.help_overlay.is_open = True
        editor.on_mouse_press(400, 400, 1, 0)
        assert editor.help_overlay.is_open is False

    def test_overlay_consumes_other_keys(self, editor):
        import arcade
        from petri_editor.views_editor import Tool
        editor.help_overlay.is_open = True
        # Pressing 2 (which would normally select Place) should be eaten.
        editor.on_key_press(arcade.key.KEY_2, 0)
        assert editor.tool is Tool.SELECT
