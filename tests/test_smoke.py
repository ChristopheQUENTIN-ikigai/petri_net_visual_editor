"""Smoke: editor view constructs, hud buttons populated."""

def test_editor_constructs(editor):
    assert editor is not None
    assert editor.graph is not None
    assert editor.history is not None
    assert editor.simulator is not None

def test_hud_has_all_expected_buttons(editor):
    actions = [b[6] for b in editor._hud_buttons]
    expected = {
        "tool_select", "tool_place", "tool_transition", "tool_state",
        "tool_arc", "save", "load", "export_pnml", "export_mermaid",
        "undo", "redo", "step", "run", "reset", "help",
    }
    assert set(actions) == expected
