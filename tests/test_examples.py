"""Validate every bundled example net.

This makes the one-off audit permanent: each JSON under ``examples/`` is
discovered and checked for the invariants a shipped example should hold.

For every example we assert:
    * it loads via ``io_json.load``;
    * every arc direction is legal (``_VALID_ARCS``) and no arc is a self-loop;
    * no two node bounding boxes overlap (a small pad guards against touching);
    * at most one state is active (the single-active-state SM convention);
    * at least one transition is enabled at the initial marking, i.e. the net
      actually *does* something when you press run;
    * the net round-trips through PNML and exports to Mermaid with matching
      node/arc counts.

These are deliberately structural — they don't pin exact coordinates or token
counts, so legitimate edits to an example won't break the suite, but a broken
or inert example will.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from petri_editor.io_json import load
from petri_editor.io_mermaid import graph_to_mermaid
from petri_editor.io_pnml import graph_from_pnml, graph_to_pnml
from petri_editor.model import _VALID_ARCS


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.json"))

# Padding (px) applied to every bbox before the overlap test. Nodes that merely
# touch within this margin are treated as overlapping.
OVERLAP_PAD = 6.0


def _ids(paths):
    return [p.stem for p in paths]


def test_examples_dir_is_populated():
    """Guard against an empty/missing examples directory silently passing."""
    assert EXAMPLE_FILES, f"no example nets found under {EXAMPLES_DIR}"


@pytest.fixture(params=EXAMPLE_FILES, ids=_ids(EXAMPLE_FILES))
def example_graph(request):
    """Load each example once and hand the Graph to the tests below."""
    return load(request.param)


def test_loads(example_graph):
    g = example_graph
    # A net with no nodes at all is almost certainly a broken file.
    assert (g.places or g.transitions or g.states), "example has no nodes"


def test_all_arcs_legal(example_graph):
    g = example_graph
    for a in g.arcs:
        key = (a.src.kind, a.dst.kind)
        assert key in _VALID_ARCS, f"illegal arc {key}"
        assert a.src is not a.dst, "self-loop arc"
        assert a.weight >= 1, f"non-positive arc weight {a.weight}"


def test_arc_endpoints_resolve(example_graph):
    """Every arc endpoint must be a node that still exists in the graph."""
    g = example_graph
    nodes = set(id(n) for n in g.all_nodes())
    for a in g.arcs:
        assert id(a.src) in nodes, "arc source not in graph"
        assert id(a.dst) in nodes, "arc target not in graph"


def test_no_node_overlap(example_graph):
    g = example_graph
    nodes = list(g.all_nodes())
    for i in range(len(nodes)):
        ax0, ay0, ax1, ay1 = nodes[i].bbox()
        ax0, ay0, ax1, ay1 = ax0 - OVERLAP_PAD, ay0 - OVERLAP_PAD, ax1 + OVERLAP_PAD, ay1 + OVERLAP_PAD
        for j in range(i + 1, len(nodes)):
            bx0, by0, bx1, by1 = nodes[j].bbox()
            overlap = not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)
            assert not overlap, (
                f"nodes overlap: {nodes[i].kind} '{nodes[i].label}' "
                f"and {nodes[j].kind} '{nodes[j].label}'"
            )


def test_at_most_one_active_state(example_graph):
    g = example_graph
    active = [s for s in g.states if s.active]
    assert len(active) <= 1, f"{len(active)} active states: {[s.label for s in active]}"


def test_has_enabled_transition_at_init(example_graph):
    g = example_graph
    if not g.transitions:
        pytest.skip("net has no transitions")
    assert any(g.is_enabled(t) for t in g.transitions), (
        "no transition is enabled at the initial marking — net is inert"
    )


def test_pnml_round_trip_counts(example_graph):
    g = example_graph
    reloaded = graph_from_pnml(graph_to_pnml(g))
    assert len(reloaded.places) == len(g.places)
    assert len(reloaded.transitions) == len(g.transitions)
    assert len(reloaded.states) == len(g.states)
    assert len(reloaded.arcs) == len(g.arcs)


def test_mermaid_export_runs(example_graph):
    g = example_graph
    text = graph_to_mermaid(g)
    assert text.strip().startswith("flowchart")
    # One declaration line per node (plus the flowchart header and any edges).
    node_count = len(g.places) + len(g.transitions) + len(g.states)
    assert text.count("\n") >= node_count
