# Petri Net Editor — Audit Findings & Test Suite

## TL;DR

- **1 critical bug found and fixed**: nodes were unhashable, which would have crashed the editor on the first click of Place / Transition / State.
- **1 layout bug fixed**: the `?` button was clipped past the right edge of the toolbar at 1280-wide.
- **1 perf regression fixed**: the `draw_text is extremely slow` warning came from per-frame text draws in five hot paths that the v0.3.0 refactor missed.
- **137 unit tests added** across 9 files, covering every toolbar button, every menu button, every inspector widget, every keyboard shortcut, both file-dialog code paths, all I/O formats, undo/redo, and the new perf and layout invariants. All green.

## How to run

```bash
cd petri_editor
pip install pytest --break-system-packages   # or in a venv
python -m pytest tests/ -v
```

The tests do **not** require arcade or a display server — `tests/conftest.py` installs a minimal arcade stub so the real `EditorView`, `Inspector`, `History`, `Simulator`, and IO modules can be imported and exercised headlessly. The stub mocks only the OpenGL surface (drawing primitives, `Camera2D`, `Window`, `arcade.gui` widgets); every behaviour you care about is the real code.

## Findings

### 1. Critical — nodes were unhashable (crash on first click)

`Place`, `Transition`, `State`, `Arc` were declared `@dataclass`. Python's dataclass auto-generates `__eq__`, which silently removes `__hash__`. The editor stuffs nodes into sets in three places:

- `views_editor.py:590,597,604` — `self._set_selection({latest})` after click-place
- `views_editor.py:563-567` — `set(self.selection)` for shift-click
- `views_editor.py:748` — `set(self.graph.all_nodes())` for Ctrl+A

The first time anyone clicked Place / Transition / State, the app would have raised `TypeError: unhashable type: 'Place'`. The screenshot shows `Nodes: 0P 0T 0S` — you simply hadn't tried yet.

**Fix:** changed all four dataclasses to `@dataclass(eq=False)`. Identity equality is the right semantics for graph nodes anyway: two places at the same coordinates are still distinct objects, and `Graph.find_node_by_id` is the one place equality-by-id matters, which it handles explicitly.

**File touched:** `petri_editor/model.py`.

### 2. Toolbar overflow — `?` button clipped on 1280-wide windows

Visible in your screenshot. `_build_hud` packed buttons left-to-right with fixed widths, no overflow check. Total natural width was ~1284 px, so the `?` button hung 4 px off the right edge of a 1280 window.

**Fix:** `_build_hud` now does a two-pass layout. Pass 1 computes natural widths. If the run would overflow `window.width - 8`, all button widths are scaled down by a single factor (with a per-button minimum of 28 px so they remain clickable). Tested on 800 / 900 / 1024 / 1280 / 1440 widths.

**File touched:** `petri_editor/views_editor.py` (`_build_hud`).

### 3. Perf warning — `draw_text` still called every frame

The v0.3.0 ROADMAP claimed the toolbar was migrated to cached `arcade.Text`, and it was. But five other render paths still went straight through `arcade.draw_text`:

- `_draw_nodes` — labels for every Place, Transition, State (every frame)
- `_draw_arcs` — weight labels for every arc with weight > 1
- `_draw_tokens` — token count overflow when n > 4
- `_draw_status_bar` — status text + path + flash
- `_draw_empty_canvas_hint` — title + 3 hint lines
- `_draw_tooltip` — tooltip text

The status bar in particular fires every single frame, so the warning was guaranteed to surface.

**Fix:** generalized `_cached_label` to accept color and anchor, then routed all six paths through it. Also added cache eviction in `_load` so per-node label entries don't leak when a graph is replaced.

**File touched:** `petri_editor/views_editor.py` (`_cached_label`, `_draw_nodes`, `_draw_arcs`, `_draw_tokens`, `_draw_status_bar`, `_draw_empty_canvas_hint`, `_draw_tooltip`, `_load`).

### Known limitations not yet addressed (per ROADMAP M4–M6)

- Arcs aren't clickable (only nodes hit-test).
- No recent-files menu.
- No arc-weight editing in the Inspector (it's read-only).
- No delete-confirmation flow even when `confirm_on_delete` is on.
- Help / Inspector / overlay views still use `arcade.draw_text` directly. These are drawn rarely (only when open / on demand), so the warning won't fire from them, but they could be migrated for consistency.

## Test inventory

| File | Tests | Covers |
|---|---|---|
| `test_smoke.py` | 2 | Editor constructs, HUD has all 15 expected actions |
| `test_tool_buttons.py` | 23 | Select / Place / Transition / State / Arc — dispatch, active-state highlight, canvas behaviour, illegal-arc rejection, weight increment, undo |
| `test_io_buttons.py` | 14 | Save / Load / PNML export / Mermaid export — successful write, cancel, failure handling, round-trip, PNML-by-extension auto-routing, history reset on load |
| `test_undo_redo_buttons.py` | 12 | Disabled state on empty stack, undo/redo dispatch, redo-clears-on-new-action, long sequence round-trip, undo through token deltas |
| `test_sim_and_help_buttons.py` | 15 | Step fires enabled transition, Run toggles & auto-fires & auto-stops on deadlock, Reset restores marking & is undoable & clears flying tokens, Help opens/toggles |
| `test_menu_buttons.py` | 17 | Menu: New / Open (with and without Tk) / Examples / Options / About / Quit / Esc; Options: every toggle, grid-size +/-, clamping, verbose-log → logger level, Back, Esc |
| `test_inspector_and_keys.py` | 34 | Inspector wiring per node kind, token +/- buttons, Active toggle, label rename (commit / empty rejection / no-op for unchanged), keyboard shortcuts 1–5, Ctrl+A/D/Z/Y/Shift+Z/S/O, Delete, Backspace, Home, F, F5, F6, Esc-three-step-dance, help-overlay dismiss |
| `test_toolbar_layout.py` | 9 | Buttons fit at 800/900/1024/1280/1440, minimum width, no overlaps, `?` is last and hittable |
| `test_perf_caching.py` | 11 | Six hot draw paths produce zero `arcade.draw_text` calls; cached labels update in place on rename; per-node cache evicts on Load while preserving non-node entries |
| **Total** | **137** | |

## What good unit tests caught here

The hashability bug is the kind of thing an interactive smoke run rarely surfaces if you don't happen to click Place. A unit-test for `tool_place` → `_canvas_click` instantly raised `TypeError`. The toolbar clipping was visible in the screenshot but invisible to integration tests because the rendering itself didn't fail; we now have a numeric assertion that catches it. The perf warning was advisory — never a test failure — so we now have explicit tests that count `draw_text` calls.

---

# Addendum — v0.3.2 examples & semantics audit

This pass focused on the **bundled examples** and the **documented vs. actual
simulator semantics**, and added three requested examples. Baseline suite was
137 green before changes; it is **194 green** after (a new
`tests/test_examples.py` parametrizes structural checks across all 7 nets).

## Findings

### A. Critical — `State → State` arcs are inert (silent deadlock)

The simulator only fires **Transition** nodes (`simulator` iterates
`graph.transitions`; `Graph.is_enabled`/`fire` are defined for transitions).
A direct `State → State` arc is a legal, drawable, exportable edge, but nothing
ever traverses it on its own.

Consequence: the previous `mtg_card_game` example modelled its turn-phase ring
as eight `State → State` arcs with **zero transitions on that ring**. Pressing
run never advanced the phase — "Untap step" stayed active forever and the net
sat deadlocked. The only executable SM pattern is `State → Transition → State`
(as in `traffic_light`).

The `model.py` docstring described `State → State` as an "SM transition",
implying executability. **Fixed** by:
- rebuilding `mtg_card_game` so the phase ring runs through eight "advance"
  transitions (`State → Transition → State`); zones remain a token-conserving
  P/T net. It now cycles indefinitely instead of deadlocking.
- correcting the `model.py` docstring and `ROADMAP.md` §3 to state the
  executability rule explicitly, plus a note that a State consumed as a
  transition input is **deactivated** on firing (arc it back to keep it active
  — the catalytic-gate pattern the new cell-cycle example relies on).

### B. Version drift

`petri_editor/__init__.py` reported `0.3.0` while the package ships as `0.3.2`,
and `README`/`ROADMAP` headers and example lists were stale (listed only
producer-consumer + traffic-light). **Fixed**: version bumped to `0.3.2`;
README gained a "What's new in v0.3.2" section; ROADMAP header, layout tree and
known-limitations updated.

### C. Layout overlap in `biochemistry_cell_cycle`

The "Mitogenic signal" place (780, 380) overlapped the "G2/M checkpoint"
transition (820, 420). **Fixed**: checkpoint nudged to (880, 420). The example
is otherwise a valid hybrid feature demo (phosphorylation cycle, ligand-induced
receptor dimerization via a weight-2 arc, and a transition-driven
G1→S→G2→M→G0 phase ring) and was kept.

### D. PNML export of States (documentation gap, not a bug)

PNML export writes a `State` as a `<place>` carrying a tool-specific
`kind=state` annotation, so nets round-trip losslessly **within this editor**,
but a strict external P/T tool sees the resulting `state → state` edges as
illegal `place → place` arcs. Now documented under ROADMAP "Known limitations":
use Mermaid for documenting hybrid/SM nets; reserve PNML for pure P/T nets when
targeting other tools.

## New examples added

All three were built programmatically through the real `Graph.add_arc` (which
asserts arc legality), saved with `io_json.save`, and pass every check in
`tests/test_examples.py`.

| File | Size | Model | Behaviour |
|---|---|---|---|
| `dominion_deck_building.json` | 5P 9T 3S 18A | Deck zones (draw pile, hand, in play, discard, supply) as a token-conserving P/T cycle; turn phases (Action→Buy→Cleanup) as an executable `State→Transition→State` ring | Cycles indefinitely |
| `krebs_cycle.json` | 13P 8T 0S 24A | Pure P/T net: 8 intermediates on a ring (oxaloacetate = catalytic carrier), 8 enzyme reactions, Acetyl-CoA input, NADH/FADH2/GTP/CO2 sinks | Consumes 1 Acetyl-CoA per turn → 3 NADH, 1 FADH2, 1 GTP, 2 CO2; halts when Acetyl-CoA is exhausted (biologically faithful) |
| `cell_cycle_cdk.json` | 6P 8T 5S 30A | Hybrid: phases G1/S/G2/M/G0 as states; cyclin-CDK complexes and APC/C as places; checkpoints (restriction point, G2/M, anaphase) as transitions; cyclins catalytic-gated, APC/C preserved | One canonical cycle returns to G1 with cyclins consumed and one growth factor spent; arrests in G1/G0 when mitogens run out (mitogen-dependent, as in biology) |

## How this was verified

`tests/test_examples.py` discovers every `examples/*.json` and asserts, per net:
arc legality + no self-loops + positive weights; all arc endpoints resolve to
live nodes; no node bounding-box overlap (6 px pad); at most one active state;
at least one transition enabled at the initial marking (the net must *do*
something); and PNML round-trip + Mermaid export with matching node/arc counts.
