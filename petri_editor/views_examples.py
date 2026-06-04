"""Examples view — lists bundled JSON nets and opens them in the editor.

Looks for an `examples/` directory next to the package root or next to
the user's working directory. First match wins.
"""

from __future__ import annotations

from pathlib import Path

import arcade
import arcade.gui

from .logger import log_ui
from .theme import BG_COLOR, TEXT_COLOR, TEXT_DIM


# Display titles keyed by filename stem (overrides the auto title-cased stem).
TITLES = {
    "mtg_card_game": "Magic: the Gathering",
    "biochemistry_cell_cycle": "Biochemistry — cell cycle",
    "dominion_deck_building": "Dominion (deck-builder)",
    "krebs_cycle": "Krebs cycle (citric acid)",
    "cell_cycle_cdk": "Cell cycle — CDK control",
}

# Short descriptions keyed by filename (without extension).
DESCRIPTIONS = {
    "producer_consumer":
        "Classic producer/consumer Petri net — 5 places, 4 transitions, 1 token cycle.",
    "traffic_light":
        "State machine: Green → Yellow → Red → Green, single active state.",
    "mtg_card_game":
        "Turn phases as an executable state machine (state→transition→state "
        "'advance' steps); card zones (library, hand, battlefield, graveyard, "
        "stack) as a token-conserving place/transition net.",
    "biochemistry_cell_cycle":
        "Hybrid feature demo: a phosphorylation cycle, ligand-induced receptor "
        "dimerization (weight-2 arc), and a G1→S→G2→M→G0 phase ring driven "
        "through transitions.",
    "dominion_deck_building":
        "Deck-builder loop: deck zones (draw pile, hand, in play, discard, "
        "supply) as a token-conserving place/transition net (draw, play, "
        "discard, reshuffle, gain); turn phases (Action→Buy→Cleanup) as an "
        "executable state-machine ring.",
    "krebs_cycle":
        "Citric acid cycle as a pure place/transition net: 8 intermediates on "
        "a ring with oxaloacetate as the catalytic carrier, 8 enzyme reactions, "
        "Acetyl-CoA input and NADH/FADH2/GTP/CO2 product sinks.",
    "cell_cycle_cdk":
        "Cyclin/CDK control of the cell cycle: phases G1/S/G2/M/G0 as states; "
        "cyclin-CDK complexes and APC/C as places; checkpoints "
        "(restriction point, G2/M, anaphase) as transitions. Mitogen-driven.",
}


def find_examples_dir() -> Path | None:
    candidates = [
        Path.cwd() / "examples",
        Path(__file__).resolve().parent.parent / "examples",
    ]
    for p in candidates:
        if p.is_dir():
            return p
    return None


class ExamplesView(arcade.View):
    def __init__(self) -> None:
        super().__init__()
        self.background_color = BG_COLOR
        self.ui = arcade.gui.UIManager()
        self.dir = find_examples_dir()
        anchor = self.ui.add(arcade.gui.UIAnchorLayout())
        stack = arcade.gui.UIBoxLayout(space_between=10, align="left")

        if self.dir is None:
            stack.add(arcade.gui.UILabel(
                text="No examples/ directory found.",
                font_size=13, text_color=TEXT_DIM,
            ))
        else:
            files = sorted(self.dir.glob("*.json"))
            if not files:
                stack.add(arcade.gui.UILabel(
                    text="examples/ is empty.",
                    font_size=13, text_color=TEXT_DIM,
                ))
            else:
                for f in files:
                    stack.add(self._row(f))

        back = arcade.gui.UIFlatButton(text="Back to menu",
                                       width=200, height=36)
        back.on_click = self._on_back
        stack.add(arcade.gui.UISpace(height=12, width=1))
        stack.add(back)

        anchor.add(child=stack, anchor_x="center_x", anchor_y="center_y")

    def _row(self, f: Path) -> arcade.gui.UIBoxLayout:
        row = arcade.gui.UIBoxLayout(vertical=False, space_between=10)
        title = TITLES.get(f.stem, f.stem.replace("_", " ").title())
        desc = DESCRIPTIONS.get(f.stem, "")
        text = f"{title}  —  {desc}" if desc else title
        btn = arcade.gui.UIFlatButton(text=text, width=820, height=40)
        btn.on_click = lambda _e, path=str(f): self._open(path)
        row.add(btn)
        return row

    def _open(self, path: str) -> None:
        from . import io_json
        from .views_editor import EditorView
        log_ui.info(f"examples: open {path}")
        try:
            graph = io_json.load(path)
        except Exception as exc:
            log_ui.warning(f"examples open failed: {exc}")
            return
        self.window.show_view(EditorView(graph=graph, current_path=path))

    def _on_back(self, _event) -> None:
        from .views_menu import MainMenuView
        self.window.show_view(MainMenuView())

    def on_show_view(self) -> None:
        self.ui.enable()

    def on_hide_view(self) -> None:
        self.ui.disable()

    def on_draw(self) -> None:
        self.clear()
        cx = self.window.width / 2
        arcade.draw_text("Examples", cx, self.window.height - 80,
                         TEXT_COLOR, 28, anchor_x="center", bold=True)
        sub = "click an example to open it in the editor"
        if self.dir is not None:
            sub += f"  ·  source: {self.dir}"
        arcade.draw_text(sub, cx, self.window.height - 110,
                         TEXT_DIM, 11, anchor_x="center")
        self.ui.draw()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == arcade.key.ESCAPE:
            self._on_back(None)
