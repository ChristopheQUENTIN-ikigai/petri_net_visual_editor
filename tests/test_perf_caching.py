"""Locks in the cached-text perf fix.

The user's original log showed:
    PerformanceWarning: draw_text is an extremely slow function for displaying
    text. Consider using Text objects instead.

The toolbar already used cached `arcade.Text`. These tests pin the rest of
the editor's hot draw paths (status bar, node labels, arc weights, tooltip,
empty-canvas hint) to do the same.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helper: patch arcade.draw_text and run the draw passes.
# ---------------------------------------------------------------------------
def _draw_text_call_count_during(callback, editor) -> int:
    """Return how many times arcade.draw_text gets called during `callback`."""
    import arcade
    counter = {"n": 0}
    real = arcade.draw_text
    def counting(*args, **kwargs):
        counter["n"] += 1
        return real(*args, **kwargs)
    with patch.object(arcade, "draw_text", side_effect=counting):
        callback()
    return counter["n"]


# ===========================================================================
# Hot path: drawing nodes, arcs, status, hints — must not call draw_text.
# ===========================================================================
class TestHotDrawPathsUseCache:
    def test_draw_nodes_does_not_call_draw_text(self, small_net):
        editor, *_ = small_net
        n = _draw_text_call_count_during(editor._draw_nodes, editor)
        assert n == 0

    def test_draw_arcs_does_not_call_draw_text(self, small_net):
        editor, p1, t1, *_ = small_net
        # Force at least one weight > 1 so the weight label path runs.
        editor.graph.add_arc(p1, t1)  # bumps weight to 2
        n = _draw_text_call_count_during(editor._draw_arcs, editor)
        assert n == 0

    def test_draw_tokens_overflow_does_not_call_draw_text(self, small_net):
        editor, p1, *_ = small_net
        p1.tokens = 9  # > 4 → overflow path uses count text
        n = _draw_text_call_count_during(
            lambda: editor._draw_tokens(p1), editor
        )
        assert n == 0

    def test_draw_status_bar_does_not_call_draw_text(self, small_net):
        editor, *_ = small_net
        n = _draw_text_call_count_during(editor._draw_status_bar, editor)
        assert n == 0

    def test_draw_status_bar_with_flash_does_not_call_draw_text(self, editor):
        editor.flash("saved", duration=10.0)  # set flash msg
        n = _draw_text_call_count_during(editor._draw_status_bar, editor)
        assert n == 0

    def test_draw_empty_canvas_hint_does_not_call_draw_text(self, editor):
        n = _draw_text_call_count_during(
            editor._draw_empty_canvas_hint, editor
        )
        assert n == 0

    def test_draw_tooltip_does_not_call_draw_text(self, editor):
        # Force a hovered button past the delay.
        editor._hovered_btn_idx = 0
        editor._hover_start_time = 0.0
        editor._time = 5.0  # > _tooltip_delay
        n = _draw_text_call_count_during(editor._draw_tooltip, editor)
        assert n == 0

    def test_draw_toolbar_does_not_call_draw_text(self, editor):
        n = _draw_text_call_count_during(editor._draw_toolbar, editor)
        assert n == 0


# ===========================================================================
# Cache eviction: load clears node-keyed labels.
# ===========================================================================
class TestCacheEviction:
    def test_load_evicts_per_node_caches(self, small_net, tmp_path,
                                         monkeypatch):
        from petri_editor import dialogs, io_json
        editor, p1, *_ = small_net
        # Trigger draw to seed both per-node and non-node caches.
        editor._draw_nodes()
        editor._draw_arcs()
        editor._draw_status_bar()
        editor._draw_toolbar()
        keys_before = set(editor._cached_text.keys())
        node_keys = {k for k in keys_before
                     if k.startswith(("plabel:", "tlabel:", "slabel:"))}
        non_node_keys = keys_before - node_keys
        assert node_keys, "expected per-node entries"
        assert non_node_keys, "expected non-node entries (status, btn:*)"
        # Save & load to trigger eviction.
        target = tmp_path / "g.json"
        io_json.save(editor.graph, target)
        monkeypatch.setattr(dialogs, "tkinter_available", lambda: False)
        editor._do_action("load")
        # Drive the fallback overlay.
        editor.path_entry.is_open = False
        editor.path_entry._on_confirm(str(target))
        # Per-node cached entries must be gone.
        keys_after = set(editor._cached_text.keys())
        node_keys_after = {k for k in keys_after
                           if k.startswith(("plabel:", "tlabel:", "slabel:"))}
        assert node_keys_after == set()
        # But non-node entries (status, toolbar buttons, etc.) survive.
        assert non_node_keys & keys_after, \
            "non-node cache entries should be preserved across load"


# ===========================================================================
# Label updates: cached labels reflect renames without re-creating Text.
# ===========================================================================
class TestCachedLabelUpdates:
    def test_rename_updates_cached_label_in_place(self, small_net):
        editor, p1, *_ = small_net
        editor._draw_nodes()
        cached = editor._cached_text[f"plabel:{p1.id}"]
        first_id = id(cached)
        # Rename; redraw.
        p1.label = "Renamed"
        editor._draw_nodes()
        cached2 = editor._cached_text[f"plabel:{p1.id}"]
        assert id(cached2) == first_id  # same Text object
        assert cached2.text == "Renamed"  # text updated

    def test_status_bar_message_updates_in_place(self, editor):
        editor._draw_status_bar()
        first = id(editor._cached_text["status"])
        editor._do_action("tool_place")  # changes 'Tool: PLACE' in msg
        editor._draw_status_bar()
        assert id(editor._cached_text["status"]) == first
        assert "PLACE" in editor._cached_text["status"].text
