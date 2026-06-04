"""Simulation engine: step, continuous run, and fire animations.

The engine is decoupled from the editor view; the view calls `update(dt)`
each frame and reads `flying_tokens` to render moving tokens.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from .commands import FireCmd, History
from .logger import log_sim
from .model import Graph, Place, State, Transition
from .theme import FIRE_ANIM_DURATION


@dataclass
class FlyingToken:
    """A token mid-flight along an arc, used purely for rendering."""
    x0: float
    y0: float
    x1: float
    y1: float
    t: float = 0.0  # 0..1 progress

    @property
    def pos(self) -> tuple[float, float]:
        u = self.t
        return (self.x0 + (self.x1 - self.x0) * u,
                self.y0 + (self.y1 - self.y0) * u)


class Simulator:
    def __init__(self, graph: Graph, history: History) -> None:
        self.graph = graph
        self.history = history
        self.running: bool = False
        self.run_interval: float = 0.6  # seconds between auto-fires
        self._timer: float = 0.0
        self.flying: list[FlyingToken] = []
        self._anim_timer: float = 0.0
        self._initial_marking: dict | None = None

    # ---- API ----
    def capture_initial(self) -> None:
        """Snapshot the current marking as the 'initial' for reset_to_initial."""
        self._initial_marking = self.graph.snapshot_marking()
        log_sim.info("captured initial marking")

    def reset_to_initial(self) -> None:
        if self._initial_marking is None:
            self._initial_marking = self.graph.snapshot_marking()
        # Route through history so reset is undoable and doesn't leave
        # FireCmd entries inconsistent with the graph state.
        from .commands import ResetMarkingCmd
        self.history.push(ResetMarkingCmd(snapshot=dict(self._initial_marking)))
        self.flying.clear()
        log_sim.info("reset to initial marking")

    def step(self) -> bool:
        """Fire one enabled transition, chosen at random. Returns True if fired."""
        enabled = [t for t in self.graph.transitions
                   if self.graph.is_enabled(t)]
        if not enabled:
            log_sim.warning("step: no enabled transition")
            return False
        t = random.choice(enabled)
        self._begin_animation(t)
        self.history.push(FireCmd(transition_id=t.id))
        return True

    def fire_specific(self, t: Transition) -> bool:
        if not self.graph.is_enabled(t):
            log_sim.warning(f"fire {t.label}: not enabled")
            return False
        self._begin_animation(t)
        self.history.push(FireCmd(transition_id=t.id))
        return True

    def toggle_run(self) -> None:
        self.running = not self.running
        self._timer = 0.0
        log_sim.info(f"run {'ON' if self.running else 'OFF'}")

    # ---- per-frame ----
    def update(self, dt: float) -> None:
        # Animation progress.
        if self.flying:
            self._anim_timer += dt
            progress = min(1.0, self._anim_timer / FIRE_ANIM_DURATION)
            for ft in self.flying:
                ft.t = progress
            if progress >= 1.0:
                self.flying.clear()
                self._anim_timer = 0.0

        # Auto-run.
        if self.running:
            self._timer += dt
            if self._timer >= self.run_interval and not self.flying:
                self._timer = 0.0
                if not self.step():
                    self.running = False  # nothing left to do

    # ---- internals ----
    def _begin_animation(self, t: Transition) -> None:
        self.flying.clear()
        self._anim_timer = 0.0
        # Incoming arcs: token flies from src toward transition.
        for a in self.graph.arcs:
            if a.dst is t and isinstance(a.src, Place) and a.src.tokens > 0:
                x0, y0 = a.src.boundary_point(t.x, t.y)
                x1, y1 = t.boundary_point(a.src.x, a.src.y)
                self.flying.append(FlyingToken(x0, y0, x1, y1))
        # Outgoing arcs: token flies from transition toward dst.
        for a in self.graph.arcs:
            if a.src is t and isinstance(a.dst, Place):
                x0, y0 = t.boundary_point(a.dst.x, a.dst.y)
                x1, y1 = a.dst.boundary_point(t.x, t.y)
                self.flying.append(FlyingToken(x0, y0, x1, y1))
