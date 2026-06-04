# Petri Net Editor

Visual editor for **Petri nets and state machines**, on a unified canvas.

Built with Python 3.11 + Arcade 3.x.

## Quick start

```bash
pip install "arcade>=3.0"
python main.py
```

Press **H** at any time inside the editor for the keyboard reference.

## What it does

- Draw places (circles), transitions (bars), and states (rounded
  rectangles) on the same canvas.
- Connect them with directed arcs; the editor enforces legal arc
  combinations (place↔transition, state↔state, hybrid state↔transition).
- Add tokens to places, mark states active/inactive.
- Step or run the simulation; tokens animate along arcs.
- Save and load as JSON; export as **PNML** (interop with CPN Tools,
  WoPeD, …) or **Mermaid** (for documentation).
- Full undo/redo across every operation.

## What's new in v0.3.2

- **Five new bundled examples**, all audited and self-tested:
  - **Magic: the Gathering** — turn phases now form an *executable* state
    machine (the old phase ring was inert; see below); card zones remain a
    token-conserving place/transition net.
  - **Dominion (deck-builder)** — deck zones as a place/transition cycle
    (draw, play, discard, reshuffle, gain), turn phases as an executable
    state-machine ring.
  - **Krebs / citric acid cycle** — pure place/transition net, oxaloacetate
    as the catalytic ring carrier, with NADH/FADH2/GTP/CO2 product sinks.
  - **Cell cycle — CDK control** — phases G1/S/G2/M/G0 as states, cyclin-CDK
    complexes and APC/C as places, checkpoints as transitions.
  - The biochemistry cell-cycle demo had a node-overlap nudge.
- **Simulator semantics clarified** (docs + model docstring): only
  Transition nodes fire. A direct `State -> State` arc renders and exports
  but is **never executed by the simulator** — build executable state
  machines as `State -> Transition -> State`. A State consumed as a
  transition input is deactivated on firing; arc it back to keep it active.
- **`tests/test_examples.py`** discovers every bundled net and asserts arc
  legality, no node overlaps, ≤1 active state, an enabled transition at
  start, and PNML/Mermaid round-trip parity.
- **Version metadata** corrected to 0.3.2 (was mislabeled 0.3.0).

## What's new in v0.3.0

- **H key opens an in-app help overlay** with the full controls reference.
- **Tooltips** on toolbar buttons after a short hover delay.
- **Empty-canvas hint** explaining how to add the first element.
- **PNML import / export** (ISO/IEC 15909-2) — round-trips state-machine
  nodes via tool-specific annotation.
- **Mermaid export** for embedding nets in Markdown / wikis.
- **Examples menu** wired up; bundled producer-consumer and traffic-light.
- **Tkinter fallback**: when Tkinter is missing, file paths are entered
  via an in-canvas modal text input — no install required.
- **Performance**: toolbar now uses cached `arcade.Text` (kills the
  `draw_text is extremely slow` warning).

## Controls cheat sheet

```
Tools          1 Select   2 Place   3 Transition   4 State   5 Arc
Click          add node (per tool) / select / pick arc endpoint
Drag           move selection (or box-select on empty canvas)
Wheel          zoom toward cursor
Wheel on place add/remove tokens
Middle / Space pan
F              fire selected transition
F5 / Space     step / run-toggle simulation
F6             reset marking
Ctrl+S / Ctrl+O   save / open
Ctrl+Z / Ctrl+Y   undo / redo
Ctrl+A / Ctrl+D   select all / deselect
Delete         delete selection
H              toggle in-app help
Esc            cancel arc → clear selection → return to menu
Home           reset camera
```

## How to add elements (quick)

1. Press `2` (Place), `3` (Transition), or `4` (State).
2. Click empty canvas to drop a node.
3. Press `5` (Arc), click source node, then click target.
4. Press `1` to switch to the Select tool, then drag to move nodes.

## Project layout

```
main.py                 # entry point
examples/               # bundled JSON nets (selectable from menu)
petri_editor/
  model.py              # Place, Transition, State, Arc, Graph
  commands.py           # Command pattern + History (undo/redo)
  io_json.py            # native JSON, versioned schema
  io_pnml.py            # PNML import/export (hand-written XML out)
  io_mermaid.py         # Mermaid flowchart export
  camera.py             # pan/zoom math
  simulator.py          # step/run/animation engine
  inspector.py          # right-sidebar property editor
  dialogs.py            # Tkinter file pickers (with availability probe)
  path_entry.py         # in-canvas modal text input (fallback)
  help_overlay.py       # H-key keyboard reference panel
  logger.py             # terminal logging
  theme.py              # palette + sizes
  views_*.py            # splash / menu / options / about / examples / editor
```

## Documentation

See `ROADMAP.md` for the full feature inventory, JSON schema, hybrid arc
semantics, PNML/Mermaid export details, and the M4–M6 plan (NetworkX-based
analysis, arc weight editing, recent files, etc.).

## License

MIT — fork, adapt, ship.
