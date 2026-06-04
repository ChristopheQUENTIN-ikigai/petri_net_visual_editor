"""JSON serialization for Graph.

Schema version 2 supports places, transitions, states, and arcs.
Schema version 1 (pre-state-machine) is read transparently — missing
states list defaults to empty.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .logger import log_io
from .model import Arc, Graph, Place, State, Transition


SCHEMA_VERSION = 2


def graph_to_dict(g: Graph) -> dict[str, Any]:
    return {
        "format": "petri-editor",
        "version": SCHEMA_VERSION,
        "places": [
            {"id": p.id, "label": p.label, "tokens": p.tokens,
             "x": p.x, "y": p.y}
            for p in g.places
        ],
        "transitions": [
            {"id": t.id, "label": t.label, "x": t.x, "y": t.y}
            for t in g.transitions
        ],
        "states": [
            {"id": s.id, "label": s.label, "active": s.active,
             "x": s.x, "y": s.y}
            for s in g.states
        ],
        "arcs": [
            {"src": {"kind": a.src.kind, "id": a.src.id},
             "dst": {"kind": a.dst.kind, "id": a.dst.id},
             "weight": a.weight}
            for a in g.arcs
        ],
    }


def graph_from_dict(d: dict[str, Any]) -> Graph:
    if d.get("format") != "petri-editor":
        raise ValueError(f"unrecognized file format: {d.get('format')!r}")
    version = d.get("version", 1)
    if version > SCHEMA_VERSION:
        raise ValueError(
            f"file is schema v{version}; this build supports up to "
            f"v{SCHEMA_VERSION}"
        )

    g = Graph()

    # Pre-allocate ids matching the source so arcs can resolve them.
    for pdata in d.get("places", []):
        p = Place(x=pdata["x"], y=pdata["y"],
                  label=pdata.get("label", ""),
                  tokens=int(pdata.get("tokens", 0)),
                  id=int(pdata["id"]))
        g.places.append(p)
        g._next_pid = max(g._next_pid, p.id + 1)
    for tdata in d.get("transitions", []):
        t = Transition(x=tdata["x"], y=tdata["y"],
                       label=tdata.get("label", ""),
                       id=int(tdata["id"]))
        g.transitions.append(t)
        g._next_tid = max(g._next_tid, t.id + 1)
    for sdata in d.get("states", []):
        s = State(x=sdata["x"], y=sdata["y"],
                  label=sdata.get("label", ""),
                  active=bool(sdata.get("active", False)),
                  id=int(sdata["id"]))
        g.states.append(s)
        g._next_sid = max(g._next_sid, s.id + 1)

    for adata in d.get("arcs", []):
        src = g.find_node_by_id(adata["src"]["kind"], int(adata["src"]["id"]))
        dst = g.find_node_by_id(adata["dst"]["kind"], int(adata["dst"]["id"]))
        if src is None or dst is None:
            log_io.warning(
                f"skip arc {adata['src']} -> {adata['dst']}: endpoint missing"
            )
            continue
        # Bypass add_arc so we don't double-log; trust the file.
        g.arcs.append(Arc(src=src, dst=dst,
                          weight=int(adata.get("weight", 1))))

    return g


def save(g: Graph, path: str | Path) -> None:
    path = Path(path)
    data = graph_to_dict(g)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log_io.info(
        f"save {path}: {len(g.places)}P {len(g.transitions)}T "
        f"{len(g.states)}S {len(g.arcs)}A"
    )


def load(path: str | Path) -> Graph:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    g = graph_from_dict(data)
    log_io.info(
        f"load {path}: {len(g.places)}P {len(g.transitions)}T "
        f"{len(g.states)}S {len(g.arcs)}A"
    )
    return g
