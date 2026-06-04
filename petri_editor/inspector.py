"""Inspector panel — right sidebar for editing selected node/arc properties.

Uses arcade.gui input fields, committing on Enter. Each commit pushes a
single command onto the history so undo gets one entry per edit.
"""

from __future__ import annotations

from typing import Optional

import arcade
import arcade.gui

from .commands import (
    ChangeTokensCmd, History, RenameNodeCmd, SetTokensCmd,
    ToggleStateActiveCmd,
)
from .logger import log_ui
from .model import Arc, Graph, Node, Place, State, Transition
from .theme import (
    ACCENT, INSPECTOR_W, PANEL_BG, PANEL_BORDER, TEXT_COLOR, TEXT_DIM,
)


class Inspector:
    """Holds a UIManager confined to the right sidebar region."""

    def __init__(self, window: arcade.Window, history: History) -> None:
        self.window = window
        self.history = history
        self.ui = arcade.gui.UIManager()
        self._target: Optional[Node | Arc] = None
        self._anchor = self.ui.add(arcade.gui.UIAnchorLayout())
        self._box = arcade.gui.UIBoxLayout(space_between=8, align="left")
        self._anchor.add(child=self._box,
                         anchor_x="right", anchor_y="top",
                         align_x=-12, align_y=-72)
        self._rebuild()

    # ---- public API ----
    def enable(self) -> None:
        self.ui.enable()

    def disable(self) -> None:
        self.ui.disable()

    def set_target(self, target: Optional[Node | Arc]) -> None:
        if target is self._target:
            return
        self._target = target
        self._rebuild()

    def draw_background(self) -> None:
        """Draw the sidebar panel — call this in the editor's draw before ui.draw()."""
        x = self.window.width - INSPECTOR_W
        rect = arcade.LBWH(x, 0, INSPECTOR_W, self.window.height)
        arcade.draw_rect_filled(rect, PANEL_BG)
        arcade.draw_line(x, 0, x, self.window.height, PANEL_BORDER, 1)
        # Header.
        arcade.draw_text("Inspector",
                         x + 14, self.window.height - 38,
                         TEXT_COLOR, 16, bold=True)
        if self._target is None:
            arcade.draw_text("(nothing selected)",
                             x + 14, self.window.height - 64,
                             TEXT_DIM, 11)
        else:
            kind_label = self._kind_label()
            arcade.draw_text(kind_label,
                             x + 14, self.window.height - 64,
                             ACCENT, 12, bold=True)

    def draw_widgets(self) -> None:
        self.ui.draw()

    def in_panel(self, sx: float, sy: float) -> bool:
        return sx >= self.window.width - INSPECTOR_W

    # ---- internal ----
    def _kind_label(self) -> str:
        t = self._target
        if isinstance(t, Place):
            return f"Place #{t.id}"
        if isinstance(t, Transition):
            return f"Transition #{t.id}"
        if isinstance(t, State):
            return f"State #{t.id}"
        if isinstance(t, Arc):
            return f"Arc {t.src.label} → {t.dst.label}"
        return ""

    def _rebuild(self) -> None:
        self._box.clear()
        t = self._target
        if t is None:
            return
        if isinstance(t, (Place, Transition, State)):
            self._build_node_fields(t)
        elif isinstance(t, Arc):
            self._build_arc_fields(t)

    def _label_field(self, node: Node) -> arcade.gui.UIBoxLayout:
        wrap = arcade.gui.UIBoxLayout(space_between=2, align="left")
        wrap.add(arcade.gui.UILabel(text="Label", font_size=10,
                                    text_color=TEXT_DIM))
        ti = arcade.gui.UIInputText(
            text=node.label,
            width=INSPECTOR_W - 30, height=28,
            font_size=12,
        )

        def commit(_event=None, n=node, w=ti) -> None:
            new = w.text.strip()
            if new and new != n.label:
                self.history.push(RenameNodeCmd(
                    kind=n.kind, node_id=n.id, new_label=new,
                ))
                log_ui.info(f"rename {n.kind} #{n.id} -> {new!r}")

        ti.on_change = commit  # commit on every change is fine — coalesced visually
        wrap.add(ti)
        return wrap

    def _tokens_field(self, place: Place) -> arcade.gui.UIBoxLayout:
        wrap = arcade.gui.UIBoxLayout(space_between=4, align="left")
        wrap.add(arcade.gui.UILabel(text="Tokens", font_size=10,
                                    text_color=TEXT_DIM))
        row = arcade.gui.UIBoxLayout(vertical=False, space_between=6)
        minus = arcade.gui.UIFlatButton(text="−", width=32, height=28)
        val = arcade.gui.UILabel(text=str(place.tokens), width=44,
                                 font_size=13, text_color=TEXT_COLOR)
        plus = arcade.gui.UIFlatButton(text="+", width=32, height=28)

        def bump(delta: int) -> None:
            self.history.push(ChangeTokensCmd(
                place_id=place.id, delta=delta,
            ))
            val.text = str(place.tokens)

        minus.on_click = lambda _e: bump(-1)
        plus.on_click = lambda _e: bump(+1)
        row.add(minus); row.add(val); row.add(plus)
        wrap.add(row)
        return wrap

    def _active_field(self, state: State) -> arcade.gui.UIBoxLayout:
        wrap = arcade.gui.UIBoxLayout(space_between=4, align="left")
        wrap.add(arcade.gui.UILabel(text="Active", font_size=10,
                                    text_color=TEXT_DIM))
        btn = arcade.gui.UIFlatButton(
            text="ACTIVE" if state.active else "INACTIVE",
            width=120, height=28,
        )

        def toggle(_e) -> None:
            self.history.push(ToggleStateActiveCmd(state_id=state.id))
            btn.text = "ACTIVE" if state.active else "INACTIVE"

        btn.on_click = toggle
        wrap.add(btn)
        return wrap

    def _build_node_fields(self, node: Node) -> None:
        # All nodes have a label.
        self._box.add(self._label_field(node))
        if isinstance(node, Place):
            self._box.add(self._tokens_field(node))
        elif isinstance(node, State):
            self._box.add(self._active_field(node))
        # Position read-out.
        pos = arcade.gui.UILabel(
            text=f"x={node.x:.0f}  y={node.y:.0f}",
            font_size=10, text_color=TEXT_DIM,
        )
        self._box.add(pos)

    def _build_arc_fields(self, arc: Arc) -> None:
        info = arcade.gui.UILabel(
            text=f"weight: {arc.weight}",
            font_size=12, text_color=TEXT_COLOR,
        )
        hint = arcade.gui.UILabel(
            text="(arc weight editing arrives in M3)",
            font_size=10, text_color=TEXT_DIM,
        )
        self._box.add(info)
        self._box.add(hint)
