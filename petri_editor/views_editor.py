"""Editor view — interactive canvas with HUD, pan/zoom, undo, simulation."""

from __future__ import annotations

import math
from enum import Enum, auto
from typing import Optional

import arcade

from .camera import Camera
from .commands import (
    AddArcCmd, AddNodeCmd, ChangeTokensCmd, DeleteNodesCmd, History,
    MoveNodesCmd,
)
from .inspector import Inspector
from .logger import log_ui
from .model import Arc, Graph, Node, Place, State, Transition
from .simulator import Simulator
from .theme import (
    ACCENT, ARC_COLOR, ARC_HEAD_LEN, ARC_PREVIEW_COLOR, BG_COLOR,
    ENABLED_STROKE, GRID_DOT, GRID_DOT_RADIUS, INSPECTOR_W, NODE_FILL,
    NODE_STROKE, PANEL_BG, PANEL_BORDER, PLACE_RADIUS, RUBBER_BAND,
    RUBBER_BAND_BORDER, SELECTED_STROKE, STATE_ACTIVE_FILL, STATE_FILL,
    STATE_H, STATE_W, TEXT_COLOR, TEXT_DARK, TEXT_DIM, TOKEN_RADIUS,
    TOOLBAR_H, TRANSITION_FILL, TRANSITION_H, TRANSITION_W, WARNING,
)
from .views_options import SETTINGS

ARC_HEAD_ANGLE = math.radians(25)


class Tool(Enum):
    SELECT = auto()
    PLACE = auto()
    TRANSITION = auto()
    STATE = auto()
    ARC = auto()


# Toolbar layout: (group, label, key, action_id, tooltip)
# action_id is dispatched by _do_action.
_TOOL_BTNS = [
    ("tool", "Select", "1", "tool_select",
     "Select / move / multi-select  [1]"),
    ("tool", "Place", "2", "tool_place",
     "Click empty canvas to add a Place  [2]"),
    ("tool", "Transition", "3", "tool_transition",
     "Click empty canvas to add a Transition  [3]"),
    ("tool", "State", "4", "tool_state",
     "Click empty canvas to add a State  [4]"),
    ("tool", "Arc", "5", "tool_arc",
     "Click source then target to connect  [5]"),
    ("sep", "", "", "", ""),
    ("act", "Save", "Ctrl+S", "save",
     "Save graph as JSON  [Ctrl+S]"),
    ("act", "Load", "Ctrl+O", "load",
     "Open a JSON file  [Ctrl+O]"),
    ("act", "PNML", "", "export_pnml",
     "Export as PNML (ISO/IEC 15909-2)"),
    ("act", "Mermaid", "", "export_mermaid",
     "Export as Mermaid flowchart (lossy)"),
    ("sep", "", "", "", ""),
    ("act", "Undo", "Ctrl+Z", "undo",
     "Undo last action  [Ctrl+Z]"),
    ("act", "Redo", "Ctrl+Y", "redo",
     "Redo  [Ctrl+Y]"),
    ("sep", "", "", "", ""),
    ("act", "Step", "F5", "step",
     "Fire one enabled transition  [F5]"),
    ("act", "Run/Pause", "Space", "run",
     "Auto-fire continuously  [Space]"),
    ("act", "Reset", "F6", "reset",
     "Restore initial marking  [F6]"),
    ("sep", "", "", "", ""),
    ("act", "?", "H", "help",
     "Show keyboard reference  [H]"),
]


class EditorView(arcade.View):
    def __init__(self, graph: Optional[Graph] = None,
                 current_path: Optional[str] = None) -> None:
        super().__init__()
        self.background_color = BG_COLOR
        self.graph = graph or Graph()
        self.history = History(self.graph)
        self.simulator = Simulator(self.graph, self.history)
        self.current_path = current_path

        self.camera_world: Camera | None = None
        self.camera_hud = arcade.Camera2D()  # default screen-space camera

        self.tool: Tool = Tool.SELECT
        self.selection: set[Node] = set()
        self.selected_arc: Optional[Arc] = None
        self.arc_src: Optional[Node] = None

        # Drag state
        self._drag_node: Optional[Node] = None
        self._drag_start_world: tuple[float, float] = (0.0, 0.0)
        self._drag_total_dx: float = 0.0
        self._drag_total_dy: float = 0.0

        # Box-select state
        self._box_start: Optional[tuple[float, float]] = None  # world coords
        self._box_now: tuple[float, float] = (0.0, 0.0)

        # Pan state
        self._pan_active: bool = False
        self._space_held: bool = False

        self.mouse_screen: tuple[float, float] = (0.0, 0.0)
        self.mouse_world: tuple[float, float] = (0.0, 0.0)

        # HUD button rects (filled in on_show_view)
        self._hud_buttons: list[tuple[float, float, float, float, str, str, str, str]] = []
        self._hovered_btn_idx: Optional[int] = None
        self._hover_start_time: float = 0.0
        self._tooltip_delay: float = 0.4  # seconds before tooltip appears

        self.inspector: Optional[Inspector] = None
        self.help_overlay = None         # built in on_show_view
        self.path_entry = None           # built in on_show_view
        self._cached_text: dict[str, arcade.Text] = {}
        self._status_msg: str = ""
        self._status_until: float = 0.0
        self._time: float = 0.0

    # ---- lifecycle ----
    def on_show_view(self) -> None:
        from .help_overlay import HelpOverlay
        from .path_entry import PathEntryOverlay
        self.camera_world = Camera(self.window)
        self.inspector = Inspector(self.window, self.history)
        self.inspector.enable()
        self.help_overlay = HelpOverlay(self.window)
        self.path_entry = PathEntryOverlay(self.window)
        self._build_hud()
        self.simulator.capture_initial()
        log_ui.info("editor: view shown")

    def on_hide_view(self) -> None:
        if self.inspector:
            self.inspector.disable()

    def on_update(self, dt: float) -> None:
        self._time += dt
        self.simulator.update(dt)
        if self.path_entry:
            self.path_entry.update(dt)

    # ---- HUD ----
    def _build_hud(self) -> None:
        """Layout toolbar buttons from the left edge.

        We compute natural widths for every visible button, then if the total
        run would overflow the window, scale all widths down by a single
        factor so the rightmost button (currently `?`) still sits inside the
        canvas. This keeps the layout deterministic and avoids the clipping
        regression observed at narrow window widths.
        """
        self._hud_buttons.clear()
        left_margin = 8
        right_margin = 8
        gap = 4
        sep_gap = 8

        # First pass: collect natural widths in order, with separator info.
        items: list[tuple[str, str, str, str, str, int]] = []
        total = left_margin
        for kind, label, hotkey, action, tooltip in _TOOL_BTNS:
            if kind == "sep":
                total += sep_gap
                items.append((kind, label, hotkey, action, tooltip, 0))
                continue
            if action == "help":
                w = 36
            elif kind == "tool":
                w = 80
            else:
                w = 84
            items.append((kind, label, hotkey, action, tooltip, w))
            total += w + gap

        # If the natural width would clip past the right edge, scale buttons
        # down (separators stay fixed). Floor at a readable minimum.
        avail = self.window.width - right_margin
        scale = 1.0
        if total > avail:
            # Solve: left + Σ(w·scale + gap) + Σ(sep_gap) ≤ avail
            sum_w = sum(w for *_, w in items if w > 0)
            sum_overhead = (left_margin
                            + sum(gap for *_, w in items if w > 0)
                            + sum(sep_gap
                                  for kind, *_ in items if kind == "sep"))
            scale = max(0.4, (avail - sum_overhead) / sum_w)

        # Second pass: emit rects.
        x = left_margin
        y0 = self.window.height - TOOLBAR_H + 8
        y1 = self.window.height - 8
        for kind, label, hotkey, action, tooltip, w in items:
            if kind == "sep":
                x += sep_gap
                continue
            ws = max(28, int(round(w * scale)))
            self._hud_buttons.append(
                (x, y0, x + ws, y1, kind, label, action, tooltip)
            )
            x += ws + gap

    def _hud_hit(self, sx: float, sy: float) -> Optional[str]:
        for x0, y0, x1, y1, _kind, _label, action, _tooltip in self._hud_buttons:
            if x0 <= sx <= x1 and y0 <= sy <= y1:
                return action
        return None

    def _hud_hit_index(self, sx: float, sy: float) -> Optional[int]:
        for i, (x0, y0, x1, y1, *_) in enumerate(self._hud_buttons):
            if x0 <= sx <= x1 and y0 <= sy <= y1:
                return i
        return None

    def _is_active_button(self, action: str) -> bool:
        if action == "tool_select":
            return self.tool is Tool.SELECT
        if action == "tool_place":
            return self.tool is Tool.PLACE
        if action == "tool_transition":
            return self.tool is Tool.TRANSITION
        if action == "tool_state":
            return self.tool is Tool.STATE
        if action == "tool_arc":
            return self.tool is Tool.ARC
        if action == "run":
            return self.simulator.running
        return False

    def _is_disabled_button(self, action: str) -> bool:
        if action == "undo":
            return not self.history.can_undo()
        if action == "redo":
            return not self.history.can_redo()
        return False

    # ---- drawing ----
    def on_draw(self) -> None:
        self.clear()

        # World-space pass.
        if self.camera_world:
            self.camera_world.use()
        self._draw_grid()
        self._draw_arcs()
        self._draw_arc_preview()
        self._draw_nodes()
        self._draw_flying_tokens()
        self._draw_box_select()

        # HUD pass: switch back to screen space.
        self.camera_hud.use()
        self._draw_empty_canvas_hint()
        self._draw_inspector_panel()
        self._draw_toolbar()
        self._draw_status_bar()
        self._draw_tooltip()

        # Modal overlays render last.
        if self.help_overlay:
            self.help_overlay.draw()
        if self.path_entry:
            self.path_entry.draw()

    def _draw_grid(self) -> None:
        if not SETTINGS.show_grid:
            return
        cam = self.camera_world
        if cam is None:
            return
        # Compute world-space bounds visible on screen.
        x0, y0 = cam.screen_to_world(0, 0)
        x1, y1 = cam.screen_to_world(self.window.width, self.window.height)
        gs = SETTINGS.grid_size
        # Bail on extreme zoom to avoid drawing millions of dots.
        if (x1 - x0) / gs > 400 or (y1 - y0) / gs > 250:
            return
        gx0 = math.floor(x0 / gs) * gs
        gy0 = math.floor(y0 / gs) * gs
        x = gx0
        while x <= x1:
            y = gy0
            while y <= y1:
                arcade.draw_circle_filled(x, y, GRID_DOT_RADIUS, GRID_DOT)
                y += gs
            x += gs

    def _draw_arcs(self) -> None:
        for i, a in enumerate(self.graph.arcs):
            sx, sy = a.src.boundary_point(a.dst.x, a.dst.y)
            ex, ey = a.dst.boundary_point(a.src.x, a.src.y)
            color = SELECTED_STROKE if a is self.selected_arc else ARC_COLOR
            arcade.draw_line(sx, sy, ex, ey, color, 2)
            self._draw_arrowhead(sx, sy, ex, ey, color)
            if a.weight > 1:
                mx, my = (sx + ex) / 2, (sy + ey) / 2
                # Cache per-arc-index so two arcs with weight 2 don't share
                # a slot and clobber each other's positions.
                t = self._cached_label(f"arcw:{i}", str(a.weight), 12,
                                       anchor_x="left")
                t.x, t.y = mx + 6, my + 6
                t.draw()

    def _draw_arc_preview(self) -> None:
        if self.tool is Tool.ARC and self.arc_src is not None:
            mx, my = self.mouse_world
            sx, sy = self.arc_src.boundary_point(mx, my)
            arcade.draw_line(sx, sy, mx, my, ARC_PREVIEW_COLOR, 2)

    @staticmethod
    def _draw_arrowhead(sx: float, sy: float, ex: float, ey: float,
                        color) -> None:
        ang = math.atan2(ey - sy, ex - sx)
        for sign in (+1, -1):
            a = ang + math.pi + sign * ARC_HEAD_ANGLE
            hx = ex + math.cos(a) * ARC_HEAD_LEN
            hy = ey + math.sin(a) * ARC_HEAD_LEN
            arcade.draw_line(ex, ey, hx, hy, color, 2)

    def _stroke_for(self, node: Node):
        if node in self.selection:
            return SELECTED_STROKE
        if node is self.arc_src:
            return SELECTED_STROKE
        if isinstance(node, Transition) and self.graph.is_enabled(node):
            return ENABLED_STROKE
        return NODE_STROKE

    def _draw_nodes(self) -> None:
        # Places.
        for p in self.graph.places:
            arcade.draw_circle_filled(p.x, p.y, PLACE_RADIUS, NODE_FILL)
            arcade.draw_circle_outline(p.x, p.y, PLACE_RADIUS,
                                       self._stroke_for(p), 2)
            self._draw_tokens(p)
            t = self._cached_label(f"plabel:{p.id}", p.label, 12)
            t.x, t.y = p.x, p.y - PLACE_RADIUS - 18
            t.draw()
        # Transitions.
        for tr in self.graph.transitions:
            rect = arcade.LBWH(tr.x - TRANSITION_W / 2, tr.y - TRANSITION_H / 2,
                               TRANSITION_W, TRANSITION_H)
            arcade.draw_rect_filled(rect, TRANSITION_FILL)
            arcade.draw_rect_outline(rect, self._stroke_for(tr), 2)
            t = self._cached_label(f"tlabel:{tr.id}", tr.label, 12)
            t.x, t.y = tr.x, tr.y - TRANSITION_H / 2 - 18
            t.draw()
        # States.
        for s in self.graph.states:
            fill = STATE_ACTIVE_FILL if s.active else STATE_FILL
            rect = arcade.LBWH(s.x - STATE_W / 2, s.y - STATE_H / 2,
                               STATE_W, STATE_H)
            arcade.draw_rect_filled(rect, fill)
            arcade.draw_rect_outline(rect, self._stroke_for(s), 2)
            t = self._cached_label(f"slabel:{s.id}", s.label, 12,
                                   bold=True, color=TEXT_DARK)
            t.x, t.y = s.x, s.y - 7
            t.draw()

    def _draw_tokens(self, p: Place) -> None:
        n = p.tokens
        if n == 0:
            return
        if n <= 4:
            offsets = {
                1: [(0, 0)],
                2: [(-7, 0), (7, 0)],
                3: [(0, 7), (-7, -5), (7, -5)],
                4: [(-7, 7), (7, 7), (-7, -7), (7, -7)],
            }[n]
            for ox, oy in offsets:
                arcade.draw_circle_filled(p.x + ox, p.y + oy,
                                          TOKEN_RADIUS, NODE_STROKE)
        else:
            t = self._cached_label(f"ptok:{p.id}", str(n), 14,
                                   bold=True, color=NODE_STROKE)
            t.x, t.y = p.x, p.y - 7
            t.draw()

    def _draw_flying_tokens(self) -> None:
        for ft in self.simulator.flying:
            x, y = ft.pos
            arcade.draw_circle_filled(x, y, TOKEN_RADIUS + 1, ACCENT)

    def _draw_box_select(self) -> None:
        if self._box_start is None:
            return
        x0, y0 = self._box_start
        x1, y1 = self._box_now
        rect = arcade.LBWH(min(x0, x1), min(y0, y1),
                           abs(x1 - x0), abs(y1 - y0))
        arcade.draw_rect_filled(rect, RUBBER_BAND)
        arcade.draw_rect_outline(rect, RUBBER_BAND_BORDER, 1)

    def _draw_inspector_panel(self) -> None:
        if self.inspector:
            self.inspector.draw_background()
            self.inspector.draw_widgets()

    def _draw_toolbar(self) -> None:
        bar = arcade.LBWH(0, self.window.height - TOOLBAR_H,
                          self.window.width, TOOLBAR_H)
        arcade.draw_rect_filled(bar, PANEL_BG)
        arcade.draw_line(0, self.window.height - TOOLBAR_H,
                         self.window.width, self.window.height - TOOLBAR_H,
                         PANEL_BORDER, 1)
        for x0, y0, x1, y1, kind, label, action, _tip in self._hud_buttons:
            disabled = self._is_disabled_button(action)
            active = self._is_active_button(action)
            if disabled:
                bg = (50, 52, 58)
                fg = TEXT_DIM
            elif active:
                bg = ACCENT
                fg = TEXT_COLOR
            else:
                bg = (60, 64, 72)
                fg = TEXT_COLOR
            r = arcade.LBWH(x0, y0, x1 - x0, y1 - y0)
            arcade.draw_rect_filled(r, bg)
            arcade.draw_rect_outline(r, NODE_STROKE, 1)
            text = self._cached_label(f"btn:{label}", label, 11)
            text.color = fg
            text.x = (x0 + x1) / 2
            text.y = (y0 + y1) / 2 - 7
            text.draw()

    def _draw_status_bar(self) -> None:
        # Bottom strip.
        bar = arcade.LBWH(0, 0, self.window.width, 24)
        arcade.draw_rect_filled(bar, PANEL_BG)
        arcade.draw_line(0, 24, self.window.width, 24, PANEL_BORDER, 1)
        cam = self.camera_world
        zoom_pct = int(cam.zoom * 100) if cam else 100
        sel = len(self.selection)
        msg = (f"Tool: {self.tool.name}    "
               f"Sel: {sel}    "
               f"Nodes: {len(self.graph.places)}P "
               f"{len(self.graph.transitions)}T "
               f"{len(self.graph.states)}S    "
               f"Arcs: {len(self.graph.arcs)}    "
               f"Zoom: {zoom_pct}%")
        if self.tool is Tool.ARC and self.arc_src is not None:
            msg += "    [click target — Esc to cancel]"
        if self.simulator.running:
            msg += "    [SIM RUNNING]"
        status = self._cached_label("status", msg, 11, anchor_x="left")
        status.x, status.y = 12, 6
        status.draw()

        path_text = self.current_path or "(unsaved)"
        path_lbl = self._cached_label("path", path_text, 11,
                                      anchor_x="right", color=TEXT_DIM)
        path_lbl.x, path_lbl.y = self.window.width - 12, 6
        path_lbl.draw()

        # Transient flash (e.g. "saved").
        if self._status_msg and self._time < self._status_until:
            flash = self._cached_label("flash", self._status_msg, 11,
                                       bold=True, color=WARNING)
            flash.x, flash.y = self.window.width / 2, 6
            flash.draw()

    def _draw_empty_canvas_hint(self) -> None:
        """Big friendly hint shown when the canvas is empty."""
        if (self.graph.places or self.graph.transitions or self.graph.states
                or (self.help_overlay and self.help_overlay.is_open)
                or (self.path_entry and self.path_entry.is_open)):
            return
        # Center of the canvas area (excluding inspector panel).
        cx = (self.window.width - INSPECTOR_W) / 2
        cy = self.window.height / 2
        title = self._cached_label("hint:title", "Empty canvas", 22,
                                   bold=True, color=TEXT_DIM)
        title.x, title.y = cx, cy + 50
        title.draw()
        lines = [
            "Press 2 / 3 / 4 then click empty space to add a Place / Transition / State",
            "Press 5 then click two nodes to connect them with an arc",
            "Press H any time for the full keyboard reference",
        ]
        y = cy + 10
        for i, line in enumerate(lines):
            t = self._cached_label(f"hint:{i}", line, 12, color=TEXT_DIM)
            t.x, t.y = cx, y
            t.draw()
            y -= 20

    def _draw_tooltip(self) -> None:
        """Show a tooltip when hovering a toolbar button past the delay."""
        idx = self._hovered_btn_idx
        if idx is None:
            return
        if (self._time - self._hover_start_time) < self._tooltip_delay:
            return
        # Bail if any modal is up.
        if self.help_overlay and self.help_overlay.is_open:
            return
        if self.path_entry and self.path_entry.is_open:
            return
        x0, y0, x1, y1, _kind, _label, _action, tip = self._hud_buttons[idx]
        if not tip:
            return
        # Tooltip box just below the button.
        pad = 8
        font_size = 11
        # Approximate text width — we don't have exact measurement without
        # creating a Text object. ~6.2 px per char is good enough for sizing.
        tw = int(len(tip) * 6.2) + pad * 2
        th = 22
        tx = (x0 + x1) / 2 - tw / 2
        ty = y0 - th - 6
        # Keep on screen.
        if tx < 4:
            tx = 4
        if tx + tw > self.window.width - 4:
            tx = self.window.width - 4 - tw
        rect = arcade.LBWH(tx, ty, tw, th)
        arcade.draw_rect_filled(rect, (20, 22, 28))
        arcade.draw_rect_outline(rect, ACCENT, 1)
        # Cache by the tip text itself: only N distinct tooltips exist
        # (one per toolbar button), so we get a tiny stable cache pool.
        t = self._cached_label(f"tip:{tip}", tip, font_size)
        t.x, t.y = tx + tw / 2, ty + 5
        t.draw()

    def _cached_label(self, key: str, text: str, font_size: int,
                      bold: bool = False,
                      color=None,
                      anchor_x: str = "center") -> arcade.Text:
        """Return a cached arcade.Text. Re-render only if the string changed.

        arcade.draw_text is slow because it rebuilds glyph atlases per call.
        arcade.Text caches its rendered geometry. We index by key so the
        same logical slot can hold different strings (e.g. status bar).

        Color and anchor are applied on every call (cheap attribute writes);
        font_size and bold are baked in at first creation, so use distinct
        keys for distinct font configurations.

        Note: per-node label caches are keyed by node id. When a graph is
        replaced (via Load or examples menu), we clear the cache in `_load`
        and after assigning `self.graph` to avoid stale entries.
        """
        existing = self._cached_text.get(key)
        if existing is None:
            t = arcade.Text(text, 0, 0,
                            color if color is not None else TEXT_COLOR,
                            font_size,
                            anchor_x=anchor_x, bold=bold)
            self._cached_text[key] = t
            return t
        if existing.text != text:
            existing.text = text
        if color is not None:
            existing.color = color
        # anchor_x is set at construction time in arcade.Text; if it ever
        # changes for a given key the caller should use a distinct key.
        return existing

    def flash(self, msg: str, duration: float = 2.0) -> None:
        self._status_msg = msg
        self._status_until = self._time + duration

    # ---- input: mouse ----
    def _in_canvas(self, sx: float, sy: float) -> bool:
        if sy >= self.window.height - TOOLBAR_H:
            return False
        if sy < 24:
            return False
        if sx >= self.window.width - INSPECTOR_W:
            return False
        return True

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float) -> None:
        self.mouse_screen = (x, y)
        if self.camera_world:
            self.mouse_world = self.camera_world.screen_to_world(x, y)
        # Track hover over toolbar buttons for tooltip delay.
        idx = self._hud_hit_index(x, y)
        if idx != self._hovered_btn_idx:
            self._hovered_btn_idx = idx
            self._hover_start_time = self._time

    def on_mouse_press(self, x: float, y: float, button: int,
                       modifiers: int) -> None:
        # Overlays consume input first.
        if self.path_entry and self.path_entry.is_open:
            self.path_entry.on_mouse_press(x, y, button, modifiers)
            return
        if self.help_overlay and self.help_overlay.is_open:
            self.help_overlay.on_mouse_press(x, y, button, modifiers)
            return

        # HUD first.
        action = self._hud_hit(x, y)
        if action is not None:
            self._do_action(action)
            return

        # Inspector panel: let arcade.gui handle it.
        if self.inspector and self.inspector.in_panel(x, y):
            return

        if not self._in_canvas(x, y):
            return

        # Middle-click or space-drag: pan.
        if (button == arcade.MOUSE_BUTTON_MIDDLE or
                (self._space_held and button == arcade.MOUSE_BUTTON_LEFT)):
            self._pan_active = True
            return

        wx, wy = self.camera_world.screen_to_world(x, y) \
            if self.camera_world else (x, y)
        node = self.graph.hit_test(wx, wy)
        shift = bool(modifiers & arcade.key.MOD_SHIFT)

        if button == arcade.MOUSE_BUTTON_RIGHT:
            # Right-click selects without changing tool.
            self._set_selection({node} if node else set())
            return

        if self.tool is Tool.SELECT:
            if node is not None:
                if shift:
                    new_sel = set(self.selection)
                    if node in new_sel:
                        new_sel.discard(node)
                    else:
                        new_sel.add(node)
                    self._set_selection(new_sel)
                else:
                    if node not in self.selection:
                        self._set_selection({node})
                # Begin drag of the whole selection.
                self._drag_node = node
                self._drag_start_world = (wx, wy)
                self._drag_total_dx = 0.0
                self._drag_total_dy = 0.0
            else:
                # Start box-select.
                if not shift:
                    self._set_selection(set())
                self._box_start = (wx, wy)
                self._box_now = (wx, wy)

        elif self.tool is Tool.PLACE:
            if node is None:
                wx, wy = self._snap(wx, wy)
                self.history.push(AddNodeCmd(kind="place", x=wx, y=wy))
                # Select the newly created node.
                latest = self.graph.places[-1]
                self._set_selection({latest})

        elif self.tool is Tool.TRANSITION:
            if node is None:
                wx, wy = self._snap(wx, wy)
                self.history.push(AddNodeCmd(kind="transition", x=wx, y=wy))
                latest = self.graph.transitions[-1]
                self._set_selection({latest})

        elif self.tool is Tool.STATE:
            if node is None:
                wx, wy = self._snap(wx, wy)
                self.history.push(AddNodeCmd(kind="state", x=wx, y=wy))
                latest = self.graph.states[-1]
                self._set_selection({latest})

        elif self.tool is Tool.ARC:
            if node is None:
                self.arc_src = None
            elif self.arc_src is None:
                self.arc_src = node
                log_ui.info(f"arc src = {node.label}")
            else:
                # Validate before pushing the command — gives a clean log line.
                from .model import _VALID_ARCS
                if (self.arc_src.kind, node.kind) in _VALID_ARCS:
                    self.history.push(AddArcCmd(
                        src_kind=self.arc_src.kind, src_id=self.arc_src.id,
                        dst_kind=node.kind, dst_id=node.id,
                    ))
                else:
                    self.flash(f"arc {self.arc_src.kind}→{node.kind} not allowed")
                    log_ui.warning(
                        f"arc rejected: {self.arc_src.kind}->{node.kind}"
                    )
                self.arc_src = None

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float,
                      buttons: int, modifiers: int) -> None:
        self.mouse_screen = (x, y)
        if self.camera_world:
            self.mouse_world = self.camera_world.screen_to_world(x, y)

        if self._pan_active and self.camera_world:
            self.camera_world.pan(dx, dy)
            return

        # Apply per-frame motion to dragged nodes (visual only;
        # the command is pushed on release with the cumulative delta).
        if self._drag_node is not None and self.camera_world:
            world_dx = dx / self.camera_world.zoom
            world_dy = dy / self.camera_world.zoom
            for n in self.selection:
                n.x += world_dx
                n.y += world_dy
            self._drag_total_dx += world_dx
            self._drag_total_dy += world_dy
            return

        if self._box_start is not None and self.camera_world:
            self._box_now = self.camera_world.screen_to_world(x, y)
            return

    def on_mouse_release(self, x: float, y: float, button: int,
                         modifiers: int) -> None:
        if self._pan_active:
            self._pan_active = False
            return

        if self._drag_node is not None:
            # Coalesce the drag into one undoable command (and undo our
            # visual movement first so the command's `do` can apply it).
            if abs(self._drag_total_dx) > 0.5 or abs(self._drag_total_dy) > 0.5:
                # Roll back visual change so command re-applies it cleanly.
                for n in self.selection:
                    n.x -= self._drag_total_dx
                    n.y -= self._drag_total_dy
                # Apply snap to the final position.
                if SETTINGS.snap_to_grid and self._drag_node:
                    sx, sy = self._snap(
                        self._drag_node.x + self._drag_total_dx,
                        self._drag_node.y + self._drag_total_dy,
                    )
                    self._drag_total_dx = sx - self._drag_node.x
                    self._drag_total_dy = sy - self._drag_node.y
                targets = [(n.kind, n.id) for n in self.selection]
                self.history.push(MoveNodesCmd(
                    targets=targets,
                    dx=self._drag_total_dx,
                    dy=self._drag_total_dy,
                ))
            self._drag_node = None
            self._drag_total_dx = 0.0
            self._drag_total_dy = 0.0
            return

        if self._box_start is not None and self.camera_world:
            x0, y0 = self._box_start
            x1, y1 = self._box_now
            picked = self.graph.nodes_in_rect(x0, y0, x1, y1)
            if picked:
                self._set_selection(set(picked))
            self._box_start = None
            return

    def on_mouse_scroll(self, x: float, y: float,
                        scroll_x: float, scroll_y: float) -> None:
        if self.inspector and self.inspector.in_panel(x, y):
            return
        if not self._in_canvas(x, y):
            return

        # Ctrl+scroll on a place adjusts tokens; plain scroll zooms.
        wx, wy = self.camera_world.screen_to_world(x, y) \
            if self.camera_world else (x, y)
        node = self.graph.hit_test(wx, wy)
        if isinstance(node, Place):
            self.history.push(ChangeTokensCmd(
                place_id=node.id, delta=int(scroll_y),
            ))
            return

        # Zoom toward cursor.
        if self.camera_world and scroll_y != 0:
            factor = 1.15 if scroll_y > 0 else 1 / 1.15
            self.camera_world.zoom_at(x, y, factor)

    # ---- input: keyboard ----
    def on_key_press(self, symbol: int, modifiers: int) -> None:
        # Overlays consume keyboard first.
        if self.path_entry and self.path_entry.is_open:
            self.path_entry.on_key_press(symbol, modifiers)
            return
        if self.help_overlay and self.help_overlay.is_open:
            self.help_overlay.on_key_press(symbol, modifiers)
            return

        ctrl = bool(modifiers & arcade.key.MOD_CTRL)
        shift = bool(modifiers & arcade.key.MOD_SHIFT)

        if symbol == arcade.key.SPACE and not self._space_held:
            self._space_held = True
            return

        # H key opens help (no Ctrl).
        if symbol == arcade.key.H and not ctrl:
            self._do_action("help"); return

        if ctrl and symbol == arcade.key.S:
            self._do_action("save"); return
        if ctrl and symbol == arcade.key.O:
            self._do_action("load"); return
        if ctrl and symbol == arcade.key.Z and not shift:
            self._do_action("undo"); return
        if ctrl and (symbol == arcade.key.Y
                     or (symbol == arcade.key.Z and shift)):
            self._do_action("redo"); return
        if ctrl and symbol == arcade.key.A:
            self._set_selection(set(self.graph.all_nodes())); return
        if ctrl and symbol == arcade.key.D:
            self._set_selection(set()); return

        if symbol == arcade.key.KEY_1:
            self._set_tool(Tool.SELECT)
        elif symbol == arcade.key.KEY_2:
            self._set_tool(Tool.PLACE)
        elif symbol == arcade.key.KEY_3:
            self._set_tool(Tool.TRANSITION)
        elif symbol == arcade.key.KEY_4:
            self._set_tool(Tool.STATE)
        elif symbol == arcade.key.KEY_5:
            self._set_tool(Tool.ARC)
        elif symbol == arcade.key.F5:
            self._do_action("step")
        elif symbol == arcade.key.F6:
            self._do_action("reset")
        elif symbol == arcade.key.F:
            # Fire selected single transition.
            sel = list(self.selection)
            if len(sel) == 1 and isinstance(sel[0], Transition):
                self.simulator.fire_specific(sel[0])
        elif symbol in (arcade.key.DELETE, arcade.key.BACKSPACE):
            if self.selection:
                targets = [(n.kind, n.id) for n in self.selection]
                self.history.push(DeleteNodesCmd(targets=targets))
                self._set_selection(set())
        elif symbol == arcade.key.HOME:
            if self.camera_world:
                self.camera_world.reset()
        elif symbol == arcade.key.ESCAPE:
            if self.arc_src is not None:
                self.arc_src = None
                log_ui.info("arc cancelled")
            elif self.selection:
                self._set_selection(set())
            else:
                from .views_menu import MainMenuView
                self.window.show_view(MainMenuView())

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        if symbol == arcade.key.SPACE:
            self._space_held = False

    def on_text(self, text: str) -> None:
        # Route printable characters into the path-entry overlay when open.
        if self.path_entry and self.path_entry.is_open:
            self.path_entry.on_text(text)

    # ---- helpers ----
    def _snap(self, wx: float, wy: float) -> tuple[float, float]:
        if not SETTINGS.snap_to_grid:
            return wx, wy
        gs = SETTINGS.grid_size
        return round(wx / gs) * gs, round(wy / gs) * gs

    def _set_tool(self, tool: Tool) -> None:
        if tool is not self.tool:
            log_ui.info(f"tool = {tool.name}")
        self.tool = tool
        self.arc_src = None

    def _set_selection(self, sel: set) -> None:
        self.selection = sel
        # Update inspector target.
        if self.inspector:
            if len(sel) == 1:
                self.inspector.set_target(next(iter(sel)))
            else:
                self.inspector.set_target(None)

    def _do_action(self, action: str) -> None:
        if action == "tool_select": self._set_tool(Tool.SELECT)
        elif action == "tool_place": self._set_tool(Tool.PLACE)
        elif action == "tool_transition": self._set_tool(Tool.TRANSITION)
        elif action == "tool_state": self._set_tool(Tool.STATE)
        elif action == "tool_arc": self._set_tool(Tool.ARC)
        elif action == "save": self._save()
        elif action == "load": self._load()
        elif action == "export_pnml": self._export_pnml()
        elif action == "export_mermaid": self._export_mermaid()
        elif action == "undo":
            self.history.undo()
            self._set_selection(set())
        elif action == "redo":
            self.history.redo()
            self._set_selection(set())
        elif action == "step": self.simulator.step()
        elif action == "run": self.simulator.toggle_run()
        elif action == "reset": self.simulator.reset_to_initial()
        elif action == "help":
            if self.help_overlay:
                self.help_overlay.toggle()

    # ---- save / load with Tkinter-or-fallback path picking ----
    def _ask_path(self, kind: str, title: str, prompt: str,
                  default_name: str,
                  on_path: "callable") -> None:
        """Ask the user for a path. kind='open' or 'save'.

        Tries Tkinter first; if unavailable, opens the in-canvas overlay
        and calls on_path(path) on confirm. on_path receives None on cancel.
        """
        from . import dialogs
        if dialogs.tkinter_available():
            path = (dialogs.ask_open() if kind == "open"
                    else dialogs.ask_save(default_name=default_name))
            on_path(path)
            return
        # Fallback overlay.
        if self.path_entry is None:
            on_path(None)
            return
        import os
        default_path = os.path.join(os.getcwd(), default_name) \
            if kind == "save" else os.getcwd()
        self.path_entry.open(
            title=title,
            prompt=prompt,
            default_text=default_path,
            on_confirm=lambda p: on_path(p or None),
            on_cancel=lambda: on_path(None),
        )

    def _save(self) -> None:
        def cb(path):
            if not path:
                return
            from . import io_json
            try:
                io_json.save(self.graph, path)
                self.current_path = path
                self.flash(f"saved → {path}")
            except Exception as exc:
                log_ui.warning(f"save failed: {exc}")
                self.flash(f"save failed: {exc}")
        self._ask_path("save", "Save Petri net (JSON)",
                       "Enter a file path to save the graph:",
                       "net.json", cb)

    def _load(self) -> None:
        def cb(path):
            if not path:
                return
            from . import io_json, io_pnml
            try:
                if path.lower().endswith(".pnml"):
                    new_graph = io_pnml.load_pnml(path)
                else:
                    new_graph = io_json.load(path)
            except Exception as exc:
                log_ui.warning(f"load failed: {exc}")
                self.flash(f"load failed: {exc}")
                return
            self.graph = new_graph
            self.history = History(self.graph)
            self.simulator = Simulator(self.graph, self.history)
            self.simulator.capture_initial()
            if self.inspector:
                self.inspector.history = self.history
            self._set_selection(set())
            self.arc_src = None
            self.current_path = path
            # Drop per-node label caches; node ids in the new graph may
            # collide with old ones and inherit the wrong text.
            self._cached_text = {
                k: v for k, v in self._cached_text.items()
                if not (k.startswith("plabel:")
                        or k.startswith("tlabel:")
                        or k.startswith("slabel:")
                        or k.startswith("ptok:")
                        or k.startswith("arcw:"))
            }
            self.flash(f"loaded ← {path}")
        self._ask_path("open", "Open file (JSON or PNML)",
                       "Enter a path to a .json or .pnml file:",
                       "", cb)

    def _export_pnml(self) -> None:
        def cb(path):
            if not path:
                return
            from . import io_pnml
            try:
                io_pnml.save_pnml(self.graph, path,
                                  y_max=float(self.window.height))
                self.flash(f"exported PNML → {path}")
            except Exception as exc:
                log_ui.warning(f"PNML export failed: {exc}")
                self.flash(f"PNML export failed: {exc}")
        self._ask_path("save", "Export as PNML",
                       "Enter a path for the .pnml file:",
                       "net.pnml", cb)

    def _export_mermaid(self) -> None:
        def cb(path):
            if not path:
                return
            from . import io_mermaid
            try:
                io_mermaid.save_mermaid(self.graph, path)
                self.flash(f"exported Mermaid → {path}")
            except Exception as exc:
                log_ui.warning(f"Mermaid export failed: {exc}")
                self.flash(f"Mermaid export failed: {exc}")
        self._ask_path("save", "Export as Mermaid",
                       "Enter a path for the .mmd file:",
                       "net.mmd", cb)
