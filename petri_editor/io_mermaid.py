"""Mermaid flowchart export.

Mermaid has no native Petri-net diagram type, so we map onto the closest
available shapes:
    Place         -> ((label•••))   double-circle, tokens shown as bullets
    Transition    -> [label]        rectangle
    State         -> ([label])      stadium (rounded ends), active gets a class
    Arc           -> -->|w|         labelled with weight when w > 1

This is a one-way export intended for embedding in README/wiki. Mermaid auto-
lays out, so positions are dropped. PN coordinates and arc semantics like
inhibitor arcs cannot be expressed and are lost.
"""

from __future__ import annotations

import re
from pathlib import Path

from .logger import log_io
from .model import Graph, Place, State, Transition


_TOKEN_DOT = "•"
_MAX_TOKEN_DOTS = 5  # cap visual; show "+N" beyond


def _safe_id(prefix: str, n: int) -> str:
    return f"{prefix}{n}"


def _safe_label(label: str) -> str:
    # Mermaid label content can mostly be plain text; escape the ones it eats.
    return re.sub(r'[\["()|`#]', "_", label).strip() or "node"


def _tokens_glyph(n: int) -> str:
    if n <= 0:
        return ""
    if n <= _MAX_TOKEN_DOTS:
        return " " + _TOKEN_DOT * n
    return f" {_TOKEN_DOT * _MAX_TOKEN_DOTS}+{n - _MAX_TOKEN_DOTS}"


def graph_to_mermaid(g: Graph) -> str:
    lines = ["flowchart LR"]

    # Node declarations.
    for p in g.places:
        nid = _safe_id("P", p.id)
        label = _safe_label(p.label) + _tokens_glyph(p.tokens)
        lines.append(f"    {nid}(({label}))")
    for t in g.transitions:
        nid = _safe_id("T", t.id)
        lines.append(f"    {nid}[{_safe_label(t.label)}]")
    for s in g.states:
        nid = _safe_id("S", s.id)
        lines.append(f"    {nid}([{_safe_label(s.label)}])")

    # Active state styling.
    active_states = [s for s in g.states if s.active]
    if active_states:
        lines.append("    classDef active fill:#ffd87a,stroke:#222,stroke-width:2px;")
        ids = ",".join(_safe_id("S", s.id) for s in active_states)
        lines.append(f"    class {ids} active;")

    # Arcs.
    kind_prefix = {"place": "P", "transition": "T", "state": "S"}
    for a in g.arcs:
        src_id = f"{kind_prefix[a.src.kind]}{a.src.id}"
        dst_id = f"{kind_prefix[a.dst.kind]}{a.dst.id}"
        if a.weight > 1:
            lines.append(f"    {src_id} -->|{a.weight}| {dst_id}")
        else:
            lines.append(f"    {src_id} --> {dst_id}")

    return "\n".join(lines) + "\n"


def save_mermaid(g: Graph, path: str | Path) -> None:
    path = Path(path)
    path.write_text(graph_to_mermaid(g), encoding="utf-8")
    log_io.info(f"export mermaid → {path}")
