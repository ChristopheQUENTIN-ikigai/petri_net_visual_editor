"""Simulation toolbar buttons: Step / Run/Pause / Reset, plus the ? help button.

Step fires one randomly-chosen enabled transition. Run toggles auto-fire.
Reset restores the captured initial marking. ? toggles the help overlay.
"""

from __future__ import annotations

import pytest


# ===========================================================================
# Step
# ===========================================================================
class TestStepButton:
    def test_step_fires_enabled_transition(self, small_net):
        editor, p1, t1, p2, _s = small_net
        # Initial: P1 has 1 token, T1 enabled, P2 has 0.
        assert editor.graph.is_enabled(t1)
        editor._do_action("step")
        # After step: P1 should be 0, P2 should be 1.
        assert p1.tokens == 0
        assert p2.tokens == 1
        # And T1 is no longer enabled.
        assert not editor.graph.is_enabled(t1)

    def test_step_no_op_when_nothing_enabled(self, editor):
        # Empty net: step is a no-op (and must not crash).
        editor._do_action("step")
        # No history pushed by a no-op step.
        assert not editor.history.can_undo()

    def test_step_pushes_undoable_command(self, small_net):
        editor, p1, t1, p2, _s = small_net
        editor._do_action("step")
        assert editor.history.can_undo()
        # Undo restores tokens.
        editor._do_action("undo")
        assert p1.tokens == 1
        assert p2.tokens == 0

    def test_step_starts_animation(self, small_net):
        editor, *_ = small_net
        assert editor.simulator.flying == []
        editor._do_action("step")
        # Flying tokens scheduled for the firing animation.
        assert len(editor.simulator.flying) > 0


# ===========================================================================
# Run/Pause
# ===========================================================================
class TestRunButton:
    def test_run_toggles_running_flag(self, small_net):
        editor, *_ = small_net
        assert editor.simulator.running is False
        editor._do_action("run")
        assert editor.simulator.running is True
        editor._do_action("run")
        assert editor.simulator.running is False

    def test_run_active_highlight(self, editor):
        assert editor._is_active_button("run") is False
        editor._do_action("run")
        assert editor._is_active_button("run") is True

    def test_run_auto_fires_over_time(self, small_net):
        editor, p1, _t, p2, _s = small_net
        editor._do_action("run")
        # Simulate enough frames for one fire interval (0.6s) plus animation.
        # update(dt) is called per frame. Burn through a few seconds in chunks.
        for _ in range(20):
            editor.simulator.update(0.1)
        # After ~2s the single available fire should have happened, and run
        # should have stopped (no more enabled transitions).
        assert p1.tokens == 0
        assert p2.tokens == 1
        # Sim auto-disables when nothing is left to fire.
        assert editor.simulator.running is False

    def test_run_stops_when_deadlocked(self, editor):
        # A net with no enabled transitions should auto-stop on first tick.
        editor.graph.add_place(100, 100, "P1", tokens=0)
        editor.graph.add_transition(200, 100, "T1")
        # T1 has no inputs → not enabled.
        editor.simulator.toggle_run()
        assert editor.simulator.running is True
        # Tick past the run interval.
        for _ in range(10):
            editor.simulator.update(0.1)
        assert editor.simulator.running is False


# ===========================================================================
# Reset
# ===========================================================================
class TestResetButton:
    def test_reset_restores_initial_marking(self, small_net):
        editor, p1, _t, p2, _s = small_net
        # Step once to perturb the marking.
        editor._do_action("step")
        assert p1.tokens == 0 and p2.tokens == 1
        editor._do_action("reset")
        assert p1.tokens == 1 and p2.tokens == 0

    def test_reset_is_undoable(self, small_net):
        editor, p1, _t, p2, _s = small_net
        editor._do_action("step")
        editor._do_action("reset")
        # Reset itself is undoable, taking us back to the post-step state.
        editor._do_action("undo")
        assert p1.tokens == 0 and p2.tokens == 1

    def test_reset_clears_flying_tokens(self, small_net):
        editor, *_ = small_net
        editor._do_action("step")
        # Mid-animation we have flying tokens.
        assert editor.simulator.flying
        editor._do_action("reset")
        assert editor.simulator.flying == []

    def test_reset_with_no_initial_captured_works(self, editor):
        # Simulator captures initial in on_show_view; force-clear and try.
        editor.simulator._initial_marking = None
        # Add some state to give reset something to do.
        editor.graph.add_place(100, 100, "P1", tokens=2)
        editor._do_action("reset")
        # Should not crash; it captures-on-demand.
        assert editor.simulator._initial_marking is not None


# ===========================================================================
# Help (?)
# ===========================================================================
class TestHelpButton:
    def test_help_opens_overlay(self, editor):
        assert editor.help_overlay.is_open is False
        editor._do_action("help")
        assert editor.help_overlay.is_open is True

    def test_help_toggles(self, editor):
        editor._do_action("help")
        editor._do_action("help")
        assert editor.help_overlay.is_open is False

    def test_h_key_opens_help(self, editor):
        import arcade
        editor.on_key_press(arcade.key.H, 0)
        assert editor.help_overlay.is_open is True
