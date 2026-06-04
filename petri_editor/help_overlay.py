"""Modal help overlay (toggled by H key or the ? button).

Renders a centered panel with controls + tips. Consumes input while open
so the editor doesn't react to clicks behind it.
"""

from __future__ import annotations

import arcade

from .theme import (
    ACCENT, NODE_STROKE, PANEL_BG, PANEL_BORDER, TEXT_COLOR, TEXT_DIM,
)


HELP_SECTIONS = [
    ("How to add elements", [
        "1. Press 2 (Place), 3 (Transition), or 4 (State) — toolbar lights up",
        "2. Click an empty spot on the canvas to drop the node",
        "3. Press 5 (Arc), click source node, then click target node",
        "4. Press 1 to return to Select tool, drag nodes to move them",
    ]),
    ("Tools", [
        "1   Select   — click to pick, drag to move, shift-click multi-select",
        "2   Place    — Petri-net circle (holds tokens)",
        "3   Trans.   — Petri-net bar (fires when enabled)",
        "4   State    — state-machine node (active / inactive)",
        "5   Arc      — connect two nodes (rules enforced)",
    ]),
    ("Editing", [
        "Drag empty canvas       — box-select",
        "Wheel on a place        — add / remove tokens",
        "Wheel elsewhere         — zoom toward cursor",
        "Middle-drag / Space-drag — pan",
        "Home                    — reset camera",
        "Delete / Backspace      — remove selection",
        "Ctrl+Z / Ctrl+Y         — undo / redo",
        "Ctrl+A / Ctrl+D         — select all / clear",
        "Ctrl+S / Ctrl+O         — save / open JSON",
    ]),
    ("Simulation", [
        "F      — fire selected transition (if enabled)",
        "F5     — step (fire one random enabled)",
        "Space  — toggle continuous run",
        "F6     — reset to initial marking",
    ]),
    ("Tips", [
        "Enabled transitions glow green; click + F to fire one.",
        "Arcs allowed: Place↔Transition, State↔State, State↔Transition.",
        "Edit labels and tokens in the right Inspector panel.",
        "Esc cancels arc-in-progress, then clears selection, then exits to menu.",
    ]),
]


class HelpOverlay:
    def __init__(self, window: arcade.Window) -> None:
        self.window = window
        self.is_open = False

    def toggle(self) -> None:
        self.is_open = not self.is_open

    def close(self) -> None:
        self.is_open = False

    # ---- input handling (returns True if consumed) ----
    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if not self.is_open:
            return False
        if symbol in (arcade.key.ESCAPE, arcade.key.H,
                      arcade.key.RETURN, arcade.key.SPACE):
            self.is_open = False
        return True

    def on_mouse_press(self, x: float, y: float, button: int,
                       modifiers: int) -> bool:
        if not self.is_open:
            return False
        self.is_open = False
        return True

    # ---- drawing ----
    def draw(self) -> None:
        if not self.is_open:
            return
        # Dim background.
        full = arcade.LBWH(0, 0, self.window.width, self.window.height)
        arcade.draw_rect_filled(full, (0, 0, 0, 160))

        pw = min(820, self.window.width - 80)
        ph = min(620, self.window.height - 80)
        cx = self.window.width / 2
        cy = self.window.height / 2
        panel = arcade.LBWH(cx - pw / 2, cy - ph / 2, pw, ph)
        arcade.draw_rect_filled(panel, PANEL_BG)
        arcade.draw_rect_outline(panel, PANEL_BORDER, 2)

        arcade.draw_text("Keyboard & Mouse Reference",
                         cx, cy + ph / 2 - 32,
                         TEXT_COLOR, 18, anchor_x="center", bold=True)

        # Two-column layout for sections.
        col_w = pw / 2 - 24
        left_x = cx - pw / 2 + 24
        right_x = cx + 12

        y_left = cy + ph / 2 - 70
        y_right = cy + ph / 2 - 70

        # Distribute: longest sections on the left.
        lengths = [(i, len(s[1])) for i, s in enumerate(HELP_SECTIONS)]
        lengths.sort(key=lambda t: -t[1])
        # Greedy bin-packing into two columns.
        col_assignment = [None] * len(HELP_SECTIONS)
        left_total = right_total = 0
        for idx, length in lengths:
            if left_total <= right_total:
                col_assignment[idx] = "L"
                left_total += length + 2
            else:
                col_assignment[idx] = "R"
                right_total += length + 2

        for i, (heading, items) in enumerate(HELP_SECTIONS):
            if col_assignment[i] == "L":
                x = left_x; y_ref = y_left
            else:
                x = right_x; y_ref = y_right
            arcade.draw_text(heading, x, y_ref,
                             ACCENT, 13, bold=True)
            yy = y_ref - 22
            for line in items:
                arcade.draw_text(line, x, yy, TEXT_COLOR, 11)
                yy -= 16
            yy -= 8
            if col_assignment[i] == "L":
                y_left = yy
            else:
                y_right = yy

        arcade.draw_text("Press H, Esc, or click anywhere to close",
                         cx, cy - ph / 2 + 18,
                         TEXT_DIM, 11, anchor_x="center")
