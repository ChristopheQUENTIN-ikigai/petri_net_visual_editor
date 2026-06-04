"""Save / Load / PNML / Mermaid toolbar buttons.

These actions all go through `_ask_path` which either uses Tkinter or falls
back to the in-canvas path-entry overlay. Tests force the fallback path by
patching `dialogs.tkinter_available` to return False, then drive the
overlay's `on_confirm` callback to inject a path.

This keeps tests deterministic and doesn't pop a real Tk dialog on dev
machines that happen to have Tkinter installed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helper: bypass the path-entry UI by capturing its on_confirm and calling
# it directly with a known path. The overlay opens, we confirm with a path,
# and the action fires.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _force_overlay_path(monkeypatch):
    """Make `tkinter_available()` always return False so all path prompts
    route through the in-canvas overlay (which we then drive)."""
    from petri_editor import dialogs
    monkeypatch.setattr(dialogs, "tkinter_available", lambda: False)
    # Reset the cache too.
    monkeypatch.setattr(dialogs, "_TK_AVAILABLE", False)


def _confirm_overlay_with(editor, path: str | None) -> None:
    """Close the path-entry overlay as if the user typed `path` and pressed OK.

    None simulates a Cancel.
    """
    pe = editor.path_entry
    assert pe is not None and pe.is_open, \
        "path-entry overlay should be open"
    if path is None:
        cancel = pe._on_cancel
        pe.is_open = False
        if cancel:
            cancel()
    else:
        confirm = pe._on_confirm
        pe.is_open = False
        if confirm:
            confirm(path)


# ===========================================================================
# Save
# ===========================================================================
class TestSaveButton:
    def test_save_writes_json(self, small_net, tmp_path: Path):
        editor, *_ = small_net
        editor._do_action("save")
        target = tmp_path / "out.json"
        _confirm_overlay_with(editor, str(target))
        assert target.exists()
        data = json.loads(target.read_text())
        assert data["format"] == "petri-editor"
        assert len(data["places"]) == 2
        assert len(data["transitions"]) == 1
        assert len(data["states"]) == 1
        assert len(data["arcs"]) == 2

    def test_save_updates_current_path(self, small_net, tmp_path: Path):
        editor, *_ = small_net
        editor._do_action("save")
        target = tmp_path / "out.json"
        _confirm_overlay_with(editor, str(target))
        assert editor.current_path == str(target)

    def test_save_cancel_does_not_write(self, small_net, tmp_path: Path):
        editor, *_ = small_net
        editor._do_action("save")
        _confirm_overlay_with(editor, None)  # cancel
        # No file should be created in tmp_path.
        assert list(tmp_path.iterdir()) == []
        assert editor.current_path is None

    def test_save_reports_failure(self, small_net, tmp_path: Path):
        editor, *_ = small_net
        editor._do_action("save")
        # Path inside a nonexistent directory → write fails.
        bad = tmp_path / "no" / "such" / "dir" / "f.json"
        _confirm_overlay_with(editor, str(bad))
        assert not bad.exists()
        assert "save failed" in editor._status_msg


# ===========================================================================
# Load
# ===========================================================================
class TestLoadButton:
    def test_load_replaces_graph(self, small_net, tmp_path: Path):
        # First save the small net to disk.
        small_editor, *_ = small_net
        target = tmp_path / "src.json"
        small_editor._do_action("save")
        _confirm_overlay_with(small_editor, str(target))
        # Now load into a fresh editor backed by a new window.
        import arcade
        from petri_editor.views_editor import EditorView
        win2 = arcade.Window(1280, 820, "test2")
        v2 = EditorView()
        win2.show_view(v2)
        assert len(v2.graph.places) == 0
        v2._do_action("load")
        _confirm_overlay_with(v2, str(target))
        assert len(v2.graph.places) == 2
        assert len(v2.graph.transitions) == 1
        assert len(v2.graph.states) == 1
        assert v2.current_path == str(target)

    def test_load_clears_selection_and_history(self, editor, tmp_path: Path):
        # Make a graph and save it.
        editor.graph.add_place(50, 50, "P1", tokens=2)
        # Build a save file directly to skip another overlay round-trip.
        from petri_editor.io_json import save
        target = tmp_path / "g.json"
        save(editor.graph, target)
        # Pollute selection and history.
        editor._do_action("tool_place")
        editor.on_mouse_press(500, 500, 1, 0)
        editor.on_mouse_release(500, 500, 1, 0)
        assert editor.history.can_undo()
        assert editor.selection
        # Load the saved file.
        editor._do_action("load")
        _confirm_overlay_with(editor, str(target))
        # After load: history reset, selection cleared.
        assert not editor.history.can_undo()
        assert editor.selection == set()

    def test_load_invalid_path_does_not_crash(self, editor, tmp_path: Path):
        editor._do_action("load")
        _confirm_overlay_with(editor, str(tmp_path / "missing.json"))
        # Editor stays usable; status message reports failure.
        assert "load failed" in editor._status_msg
        assert editor.graph is not None

    def test_load_pnml_dispatched_by_extension(self, editor, tmp_path: Path):
        # Save a small net as PNML, then load via the same Load button.
        from petri_editor.io_pnml import save_pnml
        editor.graph.add_place(50, 50, "P1", tokens=1)
        editor.graph.add_transition(150, 50, "T1")
        target = tmp_path / "n.pnml"
        save_pnml(editor.graph, target)
        # Fresh editor for clean load.
        from petri_editor.views_editor import EditorView
        win = editor.window
        v2 = EditorView()
        win.show_view(v2)
        v2._do_action("load")
        _confirm_overlay_with(v2, str(target))
        assert len(v2.graph.places) == 1
        assert len(v2.graph.transitions) == 1


# ===========================================================================
# PNML export
# ===========================================================================
class TestPNMLButton:
    def test_pnml_export_writes_valid_xml(self, small_net, tmp_path: Path):
        editor, *_ = small_net
        editor._do_action("export_pnml")
        target = tmp_path / "out.pnml"
        _confirm_overlay_with(editor, str(target))
        assert target.exists()
        text = target.read_text()
        assert text.startswith("<?xml")
        assert "<pnml" in text
        assert "<place" in text
        assert "<transition" in text
        # State exported as a place with a toolspecific marker.
        assert "<toolspecific" in text
        assert "<kind>state</kind>" in text

    def test_pnml_round_trip(self, small_net, tmp_path: Path):
        editor, p1, _t, _p2, _s = small_net
        editor._do_action("export_pnml")
        target = tmp_path / "rt.pnml"
        _confirm_overlay_with(editor, str(target))
        # Load it back.
        from petri_editor.io_pnml import load_pnml
        g2 = load_pnml(target)
        assert len(g2.places) == 2
        assert len(g2.transitions) == 1
        assert len(g2.states) == 1
        # Token count preserved.
        assert any(p.tokens == 1 for p in g2.places)

    def test_pnml_cancel_does_not_write(self, small_net, tmp_path: Path):
        editor, *_ = small_net
        editor._do_action("export_pnml")
        _confirm_overlay_with(editor, None)
        assert list(tmp_path.iterdir()) == []


# ===========================================================================
# Mermaid export
# ===========================================================================
class TestMermaidButton:
    def test_mermaid_export_writes_flowchart(self, small_net, tmp_path: Path):
        editor, *_ = small_net
        editor._do_action("export_mermaid")
        target = tmp_path / "out.mmd"
        _confirm_overlay_with(editor, str(target))
        assert target.exists()
        text = target.read_text()
        assert text.startswith("flowchart LR")
        # Place P1 with one token bullet.
        assert "P1((P1 •))" in text or "P1((P1 \u2022))" in text
        # Transition T1 as rectangle.
        assert "T1[T1]" in text
        # State S1 as stadium.
        assert "S1([S1])" in text
        # Arcs present.
        assert "P1 --> T1" in text or "P1 -->|" in text

    def test_mermaid_active_state_styling(self, editor, tmp_path: Path):
        s = editor.graph.add_state(100, 100, "S1", active=True)
        editor._do_action("export_mermaid")
        target = tmp_path / "active.mmd"
        _confirm_overlay_with(editor, str(target))
        text = target.read_text()
        assert "classDef active" in text
        assert "class S1 active" in text

    def test_mermaid_cancel_does_not_write(self, small_net, tmp_path: Path):
        editor, *_ = small_net
        editor._do_action("export_mermaid")
        _confirm_overlay_with(editor, None)
        assert list(tmp_path.iterdir()) == []
