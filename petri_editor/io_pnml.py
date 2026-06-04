"""PNML (Petri Net Markup Language) import / export.

Supports the P/T-net flavour from ISO/IEC 15909-2:
    http://www.pnml.org/version-2009/grammar/ptnet

Implementation note: output is hand-written XML because Python's
`xml.etree.ElementTree` mis-serializes the literal tag `<name>` to
`<n>` in some namespace contexts, which breaks strict PNML parsers
(CPN Tools, WoPeD). Reading uses ElementTree, which is unaffected.

Quirks worth knowing:
- PNML's Y axis points down; Arcade's points up. We flip on import/export
  using a configurable height (default 800).
- States have no PNML representation. They are exported as places with a
  `<toolspecific>` annotation so we can reimport them lossless. Tools that
  ignore unknown <toolspecific> blocks see them as plain places.
- Hierarchical pages, coloured tokens, and other high-level constructs
  are not supported.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from typing import Optional

from .logger import log_io
from .model import Arc, Graph, Place, State, Transition


PNML_NS = "http://www.pnml.org/version-2009/grammar/pnml"
PT_TYPE = "http://www.pnml.org/version-2009/grammar/ptnet"
TOOL_NAME = "petri-editor"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def graph_to_pnml(graph: Graph, y_max: float = 800.0) -> str:
    out: list[str] = []
    add = out.append

    add('<?xml version="1.0" encoding="UTF-8"?>')
    add(f'<pnml xmlns="{PNML_NS}">')
    add(f'  <net id="n1" type="{PT_TYPE}">')
    add('    <name><text>Petri net</text></name>')
    add('    <page id="page0">')

    def emit_graphics(x: float, y: float, indent: str) -> None:
        # Flip Y so PNML's down-positive matches our up-positive.
        add(f'{indent}<graphics><position x="{x:.0f}" y="{y_max - y:.0f}"/></graphics>')

    for p in graph.places:
        add(f'      <place id="p{p.id}">')
        add(f'        <name><text>{escape(p.label)}</text></name>')
        if p.tokens:
            add(f'        <initialMarking><text>{p.tokens}</text></initialMarking>')
        emit_graphics(p.x, p.y, '        ')
        add('      </place>')

    for t in graph.transitions:
        add(f'      <transition id="t{t.id}">')
        add(f'        <name><text>{escape(t.label)}</text></name>')
        emit_graphics(t.x, t.y, '        ')
        add('      </transition>')

    for s in graph.states:
        add(f'      <place id="s{s.id}">')
        add(f'        <name><text>{escape(s.label)}</text></name>')
        if s.active:
            add('        <initialMarking><text>1</text></initialMarking>')
        emit_graphics(s.x, s.y, '        ')
        add(f'        <toolspecific tool="{TOOL_NAME}" version="0.3">')
        add('          <kind>state</kind>')
        add('        </toolspecific>')
        add('      </place>')

    kind_prefix = {"place": "p", "transition": "t", "state": "s"}
    for i, a in enumerate(graph.arcs, start=1):
        src_id = f"{kind_prefix[a.src.kind]}{a.src.id}"
        dst_id = f"{kind_prefix[a.dst.kind]}{a.dst.id}"
        add(f'      <arc id="a{i}" source="{src_id}" target="{dst_id}">')
        if a.weight > 1:
            add(f'        <inscription><text>{a.weight}</text></inscription>')
        add('      </arc>')

    add('    </page>')
    add('  </net>')
    add('</pnml>')
    return "\n".join(out) + "\n"


def save_pnml(graph: Graph, path: str | Path,
              y_max: float = 800.0) -> None:
    path = Path(path)
    path.write_text(graph_to_pnml(graph, y_max), encoding="utf-8")
    log_io.info(f"export pnml → {path}")


# ---------------------------------------------------------------------------
# Import (ElementTree — read side is unaffected by the serialization bug)
# ---------------------------------------------------------------------------
def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_text(parent: ET.Element, tag: str) -> Optional[str]:
    for child in parent:
        if _strip_ns(child.tag) == tag:
            for sub in child:
                if _strip_ns(sub.tag) == "text":
                    return (sub.text or "").strip()
    return None


def _find_graphics(parent: ET.Element) -> tuple[float, float]:
    for child in parent:
        if _strip_ns(child.tag) == "graphics":
            for sub in child:
                if _strip_ns(sub.tag) == "position":
                    try:
                        return (float(sub.get("x", "0")),
                                float(sub.get("y", "0")))
                    except ValueError:
                        return 0.0, 0.0
    return 0.0, 0.0


def _is_state_marker(node: ET.Element) -> bool:
    for child in node:
        if (_strip_ns(child.tag) == "toolspecific"
                and child.get("tool") == TOOL_NAME):
            for sub in child:
                if (_strip_ns(sub.tag) == "kind"
                        and (sub.text or "").strip() == "state"):
                    return True
    return False


def graph_from_pnml(xml_text: str, y_max: float = 800.0) -> Graph:
    root = ET.fromstring(xml_text)
    g = Graph()
    id_map: dict[str, tuple[str, int]] = {}
    next_pid = next_tid = next_sid = 1

    for node in root.iter():
        tag = _strip_ns(node.tag)
        if tag == "place":
            label = _find_text(node, "name") or ""
            marking = _find_text(node, "initialMarking") or "0"
            try:
                tokens = int(marking)
            except ValueError:
                tokens = 0
            x, y = _find_graphics(node)
            ext_id = node.get("id", "")
            if _is_state_marker(node):
                s = State(x=x, y=y_max - y, label=label,
                          active=tokens > 0, id=next_sid)
                g.states.append(s)
                id_map[ext_id] = ("state", s.id)
                next_sid += 1
            else:
                p = Place(x=x, y=y_max - y, label=label,
                          tokens=tokens, id=next_pid)
                g.places.append(p)
                id_map[ext_id] = ("place", p.id)
                next_pid += 1
        elif tag == "transition":
            label = _find_text(node, "name") or ""
            x, y = _find_graphics(node)
            t = Transition(x=x, y=y_max - y, label=label, id=next_tid)
            g.transitions.append(t)
            id_map[node.get("id", "")] = ("transition", t.id)
            next_tid += 1

    g._next_pid = next_pid
    g._next_tid = next_tid
    g._next_sid = next_sid

    for node in root.iter():
        if _strip_ns(node.tag) != "arc":
            continue
        src_ext = node.get("source")
        dst_ext = node.get("target")
        if src_ext not in id_map or dst_ext not in id_map:
            log_io.warning(f"pnml: skip arc {src_ext}->{dst_ext}")
            continue
        src_kind, src_id = id_map[src_ext]
        dst_kind, dst_id = id_map[dst_ext]
        src = g.find_node_by_id(src_kind, src_id)
        dst = g.find_node_by_id(dst_kind, dst_id)
        weight_text = _find_text(node, "inscription") or "1"
        try:
            weight = int(weight_text)
        except ValueError:
            weight = 1
        if src and dst:
            g.arcs.append(Arc(src=src, dst=dst, weight=weight))

    return g


def load_pnml(path: str | Path, y_max: float = 800.0) -> Graph:
    path = Path(path)
    g = graph_from_pnml(path.read_text(encoding="utf-8"), y_max)
    log_io.info(f"import pnml ← {path}: {len(g.places)}P "
                f"{len(g.transitions)}T {len(g.states)}S {len(g.arcs)}A")
    return g
