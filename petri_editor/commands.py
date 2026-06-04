"""Undo/redo via command pattern.

Each user-facing mutation is wrapped in a Command that knows how to do() and
undo() itself. The History class maintains do/undo stacks and clears the redo
stack on any new action (standard editor behaviour).

Move actions deliberately do NOT push per-pixel commands; the editor pushes
one MoveNodes command on mouse-release with the final delta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .logger import log_history
from .model import Arc, Graph, Node, Place, State, Transition


# ---------------------------------------------------------------------------
# Command base
# ---------------------------------------------------------------------------
class Command:
    name: str = "command"

    def do(self, g: Graph) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def undo(self, g: Graph) -> None:  # pragma: no cover - abstract
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Concrete commands
# ---------------------------------------------------------------------------
@dataclass
class AddNodeCmd(Command):
    kind: str            # "place" | "transition" | "state"
    x: float
    y: float
    label: Optional[str] = None
    # Resolved on `do` so undo can find the same instance again.
    _id: int = 0
    name: str = "add node"

    def do(self, g: Graph) -> None:
        if self.kind == "place":
            n = g.add_place(self.x, self.y, self.label)
        elif self.kind == "transition":
            n = g.add_transition(self.x, self.y, self.label)
        else:
            n = g.add_state(self.x, self.y, self.label)
        self._id = n.id
        if self.label is None:
            self.label = n.label  # capture auto-generated for redo idempotence

    def undo(self, g: Graph) -> None:
        n = g.find_node_by_id(self.kind, self._id)
        if n is not None:
            g.remove_node(n)


@dataclass
class AddArcCmd(Command):
    src_kind: str
    src_id: int
    dst_kind: str
    dst_id: int
    name: str = "add arc"

    def do(self, g: Graph) -> None:
        src = g.find_node_by_id(self.src_kind, self.src_id)
        dst = g.find_node_by_id(self.dst_kind, self.dst_id)
        if src and dst:
            g.add_arc(src, dst)

    def undo(self, g: Graph) -> None:
        for a in list(g.arcs):
            if (a.src.kind == self.src_kind and a.src.id == self.src_id
                    and a.dst.kind == self.dst_kind and a.dst.id == self.dst_id):
                # Decrement weight if >1, else remove.
                if a.weight > 1:
                    a.weight -= 1
                else:
                    g.remove_arc(a)
                return


@dataclass
class DeleteNodesCmd(Command):
    """Delete a set of nodes plus all arcs incident on any of them."""
    targets: list[tuple[str, int]]
    # Snapshot for undo: nodes and arcs we removed.
    _node_data: list[dict] = field(default_factory=list)
    _arc_data: list[tuple[str, int, str, int, int]] = field(default_factory=list)
    name: str = "delete"

    def do(self, g: Graph) -> None:
        self._node_data.clear()
        self._arc_data.clear()
        nodes = [g.find_node_by_id(k, i) for k, i in self.targets]
        nodes = [n for n in nodes if n is not None]
        # Capture arcs first.
        for a in list(g.arcs):
            if a.src in nodes or a.dst in nodes:
                self._arc_data.append(
                    (a.src.kind, a.src.id, a.dst.kind, a.dst.id, a.weight)
                )
        # Capture node data.
        for n in nodes:
            d = {"kind": n.kind, "id": n.id, "x": n.x, "y": n.y,
                 "label": n.label}
            if isinstance(n, Place):
                d["tokens"] = n.tokens
            elif isinstance(n, State):
                d["active"] = n.active
            self._node_data.append(d)
        # Now remove.
        for n in nodes:
            g.remove_node(n)

    def undo(self, g: Graph) -> None:
        # Restore nodes with their original ids.
        for d in self._node_data:
            if d["kind"] == "place":
                p = Place(x=d["x"], y=d["y"], label=d["label"],
                          tokens=d.get("tokens", 0), id=d["id"])
                g.places.append(p)
                g._next_pid = max(g._next_pid, p.id + 1)
            elif d["kind"] == "transition":
                t = Transition(x=d["x"], y=d["y"], label=d["label"],
                               id=d["id"])
                g.transitions.append(t)
                g._next_tid = max(g._next_tid, t.id + 1)
            else:
                s = State(x=d["x"], y=d["y"], label=d["label"],
                          active=d.get("active", False), id=d["id"])
                g.states.append(s)
                g._next_sid = max(g._next_sid, s.id + 1)
        # Restore arcs.
        for sk, si, dk, di, w in self._arc_data:
            src = g.find_node_by_id(sk, si)
            dst = g.find_node_by_id(dk, di)
            if src and dst:
                g.arcs.append(Arc(src=src, dst=dst, weight=w))


@dataclass
class MoveNodesCmd(Command):
    """Move a set of nodes by (dx, dy). Coalesces a whole drag into one cmd."""
    targets: list[tuple[str, int]]
    dx: float
    dy: float
    name: str = "move"

    def do(self, g: Graph) -> None:
        for k, i in self.targets:
            n = g.find_node_by_id(k, i)
            if n is not None:
                n.x += self.dx
                n.y += self.dy

    def undo(self, g: Graph) -> None:
        for k, i in self.targets:
            n = g.find_node_by_id(k, i)
            if n is not None:
                n.x -= self.dx
                n.y -= self.dy


@dataclass
class ChangeTokensCmd(Command):
    place_id: int
    delta: int
    name: str = "tokens"

    def do(self, g: Graph) -> None:
        p = g.find_node_by_id("place", self.place_id)
        if isinstance(p, Place):
            p.tokens = max(0, p.tokens + self.delta)

    def undo(self, g: Graph) -> None:
        p = g.find_node_by_id("place", self.place_id)
        if isinstance(p, Place):
            p.tokens = max(0, p.tokens - self.delta)


@dataclass
class SetTokensCmd(Command):
    place_id: int
    new_value: int
    _old_value: int = 0
    name: str = "set tokens"

    def do(self, g: Graph) -> None:
        p = g.find_node_by_id("place", self.place_id)
        if isinstance(p, Place):
            self._old_value = p.tokens
            p.tokens = max(0, self.new_value)

    def undo(self, g: Graph) -> None:
        p = g.find_node_by_id("place", self.place_id)
        if isinstance(p, Place):
            p.tokens = self._old_value


@dataclass
class ToggleStateActiveCmd(Command):
    state_id: int
    name: str = "toggle state"

    def do(self, g: Graph) -> None:
        s = g.find_node_by_id("state", self.state_id)
        if isinstance(s, State):
            s.active = not s.active

    def undo(self, g: Graph) -> None:
        self.do(g)  # toggle is its own inverse


@dataclass
class RenameNodeCmd(Command):
    kind: str
    node_id: int
    new_label: str
    _old_label: str = ""
    name: str = "rename"

    def do(self, g: Graph) -> None:
        n = g.find_node_by_id(self.kind, self.node_id)
        if n is not None:
            self._old_label = n.label
            n.label = self.new_label

    def undo(self, g: Graph) -> None:
        n = g.find_node_by_id(self.kind, self.node_id)
        if n is not None:
            n.label = self._old_label


@dataclass
class FireCmd(Command):
    """Fire transition once.

    Records the consume/produce delta rather than a full marking snapshot,
    so undo composes correctly with other state-changing commands
    (notably ResetMarkingCmd) regardless of intervening operations.
    """
    transition_id: int
    _consumed_places: list = field(default_factory=list)  # (id, amount)
    _consumed_states: list = field(default_factory=list)  # id
    _produced_places: list = field(default_factory=list)
    _produced_states: list = field(default_factory=list)
    name: str = "fire"

    def do(self, g: Graph) -> None:
        t = g.find_node_by_id("transition", self.transition_id)
        if not isinstance(t, Transition) or not g.is_enabled(t):
            return
        self._consumed_places.clear()
        self._consumed_states.clear()
        self._produced_places.clear()
        self._produced_states.clear()
        for a in g.arcs:
            if a.dst is t:
                if isinstance(a.src, Place):
                    self._consumed_places.append((a.src.id, a.weight))
                elif isinstance(a.src, State):
                    self._consumed_states.append(a.src.id)
        for a in g.arcs:
            if a.src is t:
                if isinstance(a.dst, Place):
                    self._produced_places.append((a.dst.id, a.weight))
                elif isinstance(a.dst, State):
                    self._produced_states.append(a.dst.id)
        for pid, w in self._consumed_places:
            p = g.find_node_by_id("place", pid)
            if isinstance(p, Place):
                p.tokens -= w
        for sid in self._consumed_states:
            s = g.find_node_by_id("state", sid)
            if isinstance(s, State):
                s.active = False
        for pid, w in self._produced_places:
            p = g.find_node_by_id("place", pid)
            if isinstance(p, Place):
                p.tokens += w
        for sid in self._produced_states:
            s = g.find_node_by_id("state", sid)
            if isinstance(s, State):
                s.active = True

    def undo(self, g: Graph) -> None:
        for pid, w in self._produced_places:
            p = g.find_node_by_id("place", pid)
            if isinstance(p, Place):
                p.tokens -= w
        for sid in self._produced_states:
            s = g.find_node_by_id("state", sid)
            if isinstance(s, State):
                s.active = False
        for pid, w in self._consumed_places:
            p = g.find_node_by_id("place", pid)
            if isinstance(p, Place):
                p.tokens += w
        for sid in self._consumed_states:
            s = g.find_node_by_id("state", sid)
            if isinstance(s, State):
                s.active = True


@dataclass
class ResetMarkingCmd(Command):
    """Reset marking to a captured snapshot (or all-zero). Undoable."""
    snapshot: dict = field(default_factory=dict)
    _previous: dict = field(default_factory=dict)
    name: str = "reset marking"

    def do(self, g: Graph) -> None:
        self._previous = g.snapshot_marking()
        g.reset_marking(self.snapshot)

    def undo(self, g: Graph) -> None:
        g.reset_marking(self._previous)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
class History:
    def __init__(self, graph: Graph, capacity: int = 200) -> None:
        self.graph = graph
        self.undo_stack: list[Command] = []
        self.redo_stack: list[Command] = []
        self.capacity = capacity

    def push(self, cmd: Command) -> None:
        cmd.do(self.graph)
        self.undo_stack.append(cmd)
        if len(self.undo_stack) > self.capacity:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        log_history.info(f"do {cmd.name} (undo depth={len(self.undo_stack)})")

    def undo(self) -> bool:
        if not self.undo_stack:
            log_history.info("undo: stack empty")
            return False
        cmd = self.undo_stack.pop()
        cmd.undo(self.graph)
        self.redo_stack.append(cmd)
        log_history.info(f"undo {cmd.name}")
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            log_history.info("redo: stack empty")
            return False
        cmd = self.redo_stack.pop()
        cmd.do(self.graph)
        self.undo_stack.append(cmd)
        log_history.info(f"redo {cmd.name}")
        return True

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)
