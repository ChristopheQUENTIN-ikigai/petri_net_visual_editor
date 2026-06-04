"""Unified graph model: Petri-net Places + Transitions + state-machine States.

Why a single model class?
    State machines are formally a constrained Petri net (each transition has
    exactly one input and one output place, marking is single-token). Mixing
    both formalisms in the same canvas means we represent them with the same
    structure and let arc rules govern legality.

Arc legality rules (enforced by `add_arc`):
    Place         -> Transition      OK   (PN consumes input)
    Transition    -> Place           OK   (PN produces output)
    State         -> State           OK   (SM edge; see note — NOT executable)
    State         -> Transition      OK   (hybrid: SM enters PN sub-process)
    Transition    -> State           OK   (hybrid: PN signals SM state change)
    Place         -> Place           REJECTED
    Transition    -> Transition      REJECTED
    State         -> Place           REJECTED  (semantic mismatch)
    Place         -> State           REJECTED  (semantic mismatch)

State semantics:
    A `State` is "active" when its `active` flag is True. State machines
    typically have exactly one active state per machine; we don't enforce
    this — single-active is a per-graph convention, not a model invariant.

Firing semantics:
    Transitions fire as in plain P/T nets (consume tokens from input Places,
    produce tokens on output Places). When a Transition has incoming State
    arcs, the source state must be active for the transition to fire; on
    firing, the source state deactivates and any outgoing State target
    activates.

    IMPORTANT — only Transition nodes fire. The simulator iterates over
    `graph.transitions`; a direct State -> State arc is structurally legal and
    renders/exports, but the simulator never traverses it on its own, so a
    state machine built purely from State -> State edges is inert (it will
    never advance). To build an *executable* state machine, interpose a
    Transition between states (State -> Transition -> State). The bundled
    traffic_light, mtg_card_game and dominion examples use this pattern.

    Note also that a State used as a plain input to a Transition is consumed
    (deactivated) on firing. To keep a state/marker persistent across a firing
    (a catalytic gate, e.g. a cyclin that should remain active), give the
    transition an outgoing arc back to that same state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Union

from .logger import log_model
from .theme import (
    PLACE_RADIUS, STATE_H, STATE_W, TRANSITION_H, TRANSITION_W,
)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class Place:
    x: float
    y: float
    label: str = ""
    tokens: int = 0
    id: int = 0

    kind: str = field(default="place", init=False)

    def hit(self, mx: float, my: float) -> bool:
        return (mx - self.x) ** 2 + (my - self.y) ** 2 <= PLACE_RADIUS ** 2

    def boundary_point(self, tx: float, ty: float) -> tuple[float, float]:
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy) or 1.0
        return self.x + dx / d * PLACE_RADIUS, self.y + dy / d * PLACE_RADIUS

    def bbox(self) -> tuple[float, float, float, float]:
        r = PLACE_RADIUS
        return self.x - r, self.y - r, self.x + r, self.y + r


@dataclass(eq=False)
class Transition:
    x: float
    y: float
    label: str = ""
    id: int = 0

    kind: str = field(default="transition", init=False)

    def hit(self, mx: float, my: float) -> bool:
        return (abs(mx - self.x) <= TRANSITION_W / 2
                and abs(my - self.y) <= TRANSITION_H / 2)

    def boundary_point(self, tx: float, ty: float) -> tuple[float, float]:
        dx, dy = tx - self.x, ty - self.y
        if dx == 0 and dy == 0:
            return self.x, self.y
        sx = (TRANSITION_W / 2) / abs(dx) if dx else float("inf")
        sy = (TRANSITION_H / 2) / abs(dy) if dy else float("inf")
        s = min(sx, sy)
        return self.x + dx * s, self.y + dy * s

    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x - TRANSITION_W / 2, self.y - TRANSITION_H / 2,
                self.x + TRANSITION_W / 2, self.y + TRANSITION_H / 2)


@dataclass(eq=False)
class State:
    x: float
    y: float
    label: str = ""
    active: bool = False
    id: int = 0

    kind: str = field(default="state", init=False)

    def hit(self, mx: float, my: float) -> bool:
        return (abs(mx - self.x) <= STATE_W / 2
                and abs(my - self.y) <= STATE_H / 2)

    def boundary_point(self, tx: float, ty: float) -> tuple[float, float]:
        # Approximate edge point on the rounded-rect by treating it as a rect.
        dx, dy = tx - self.x, ty - self.y
        if dx == 0 and dy == 0:
            return self.x, self.y
        sx = (STATE_W / 2) / abs(dx) if dx else float("inf")
        sy = (STATE_H / 2) / abs(dy) if dy else float("inf")
        s = min(sx, sy)
        return self.x + dx * s, self.y + dy * s

    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x - STATE_W / 2, self.y - STATE_H / 2,
                self.x + STATE_W / 2, self.y + STATE_H / 2)


Node = Union[Place, Transition, State]


# ---------------------------------------------------------------------------
# Arc
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class Arc:
    src: Node
    dst: Node
    weight: int = 1


# ---------------------------------------------------------------------------
# Graph (unified PN + SM model)
# ---------------------------------------------------------------------------
# Allowed arc directions, by (src.kind, dst.kind).
_VALID_ARCS: set[tuple[str, str]] = {
    ("place", "transition"),
    ("transition", "place"),
    ("state", "state"),
    ("state", "transition"),
    ("transition", "state"),
}


@dataclass
class Graph:
    places: list[Place] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    states: list[State] = field(default_factory=list)
    arcs: list[Arc] = field(default_factory=list)
    _next_pid: int = 1
    _next_tid: int = 1
    _next_sid: int = 1

    # ---- iteration helpers ----
    def all_nodes(self):
        yield from self.places
        yield from self.transitions
        yield from self.states

    # ---- construction ----
    def add_place(self, x: float, y: float, label: str | None = None,
                  tokens: int = 0) -> Place:
        p = Place(x=x, y=y,
                  label=label or f"P{self._next_pid}",
                  tokens=tokens, id=self._next_pid)
        self._next_pid += 1
        self.places.append(p)
        log_model.info(f"add place {p.label} at ({x:.0f}, {y:.0f})")
        return p

    def add_transition(self, x: float, y: float,
                       label: str | None = None) -> Transition:
        t = Transition(x=x, y=y,
                       label=label or f"T{self._next_tid}",
                       id=self._next_tid)
        self._next_tid += 1
        self.transitions.append(t)
        log_model.info(f"add transition {t.label} at ({x:.0f}, {y:.0f})")
        return t

    def add_state(self, x: float, y: float,
                  label: str | None = None, active: bool = False) -> State:
        s = State(x=x, y=y,
                  label=label or f"S{self._next_sid}",
                  active=active, id=self._next_sid)
        self._next_sid += 1
        self.states.append(s)
        log_model.info(f"add state {s.label} at ({x:.0f}, {y:.0f})"
                       f"{' (active)' if active else ''}")
        return s

    def add_arc(self, src: Node, dst: Node) -> Optional[Arc]:
        key = (src.kind, dst.kind)
        if key not in _VALID_ARCS:
            log_model.warning(
                f"reject arc {src.label} -> {dst.label}: "
                f"{src.kind}->{dst.kind} not allowed"
            )
            return None
        if src is dst:
            log_model.warning(f"reject self-loop on {src.label}")
            return None
        # Same-direction duplicate → bump weight (PN convention).
        for a in self.arcs:
            if a.src is src and a.dst is dst:
                a.weight += 1
                log_model.info(
                    f"increment arc {src.label} -> {dst.label} "
                    f"weight={a.weight}"
                )
                return a
        arc = Arc(src=src, dst=dst)
        self.arcs.append(arc)
        log_model.info(f"add arc {src.label} -> {dst.label}")
        return arc

    def remove_node(self, node: Node) -> None:
        removed_arcs = [a for a in self.arcs
                        if a.src is node or a.dst is node]
        self.arcs = [a for a in self.arcs if a not in removed_arcs]
        if isinstance(node, Place):
            self.places.remove(node)
        elif isinstance(node, Transition):
            self.transitions.remove(node)
        else:
            self.states.remove(node)
        log_model.info(
            f"remove {node.kind} {node.label} "
            f"(+{len(removed_arcs)} incident arcs)"
        )

    def remove_arc(self, arc: Arc) -> None:
        self.arcs.remove(arc)
        log_model.info(f"remove arc {arc.src.label} -> {arc.dst.label}")

    # ---- semantics ----
    def is_enabled(self, t: Transition) -> bool:
        has_input = False
        for a in self.arcs:
            if a.dst is t:
                has_input = True
                if isinstance(a.src, Place) and a.src.tokens < a.weight:
                    return False
                if isinstance(a.src, State) and not a.src.active:
                    return False
        return has_input

    def fire(self, t: Transition) -> bool:
        if not self.is_enabled(t):
            log_model.warning(f"fire {t.label}: not enabled")
            return False
        # Consume.
        for a in self.arcs:
            if a.dst is t:
                if isinstance(a.src, Place):
                    a.src.tokens -= a.weight
                elif isinstance(a.src, State):
                    a.src.active = False
        # Produce.
        for a in self.arcs:
            if a.src is t:
                if isinstance(a.dst, Place):
                    a.dst.tokens += a.weight
                elif isinstance(a.dst, State):
                    a.dst.active = True
        log_model.info(f"fire {t.label}")
        return True

    def reset_marking(self, snapshot: dict[int, int] | None = None) -> None:
        """Reset to a snapshot or to all-zero."""
        if snapshot is None:
            for p in self.places:
                p.tokens = 0
            for s in self.states:
                s.active = False
        else:
            for p in self.places:
                p.tokens = snapshot.get(("p", p.id), 0)
            for s in self.states:
                s.active = bool(snapshot.get(("s", s.id), 0))
        log_model.info("reset marking")

    def snapshot_marking(self) -> dict:
        snap: dict = {}
        for p in self.places:
            snap[("p", p.id)] = p.tokens
        for s in self.states:
            snap[("s", s.id)] = 1 if s.active else 0
        return snap

    # ---- queries ----
    def hit_test(self, x: float, y: float) -> Optional[Node]:
        # Smallest hit areas first so they win when overlapped.
        for t in self.transitions:
            if t.hit(x, y):
                return t
        for s in self.states:
            if s.hit(x, y):
                return s
        for p in self.places:
            if p.hit(x, y):
                return p
        return None

    def nodes_in_rect(self, x0: float, y0: float,
                      x1: float, y1: float) -> list[Node]:
        lo_x, hi_x = sorted((x0, x1))
        lo_y, hi_y = sorted((y0, y1))
        result = []
        for n in self.all_nodes():
            nx0, ny0, nx1, ny1 = n.bbox()
            if nx0 >= lo_x and nx1 <= hi_x and ny0 >= lo_y and ny1 <= hi_y:
                result.append(n)
        return result

    def find_node_by_id(self, kind: str, id_: int) -> Optional[Node]:
        bucket = {"place": self.places,
                  "transition": self.transitions,
                  "state": self.states}.get(kind, [])
        for n in bucket:
            if n.id == id_:
                return n
        return None
