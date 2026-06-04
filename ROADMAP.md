# Petri Net Editor — Roadmap & Feature Documentation

A visual editor for **Petri nets and state machines** on a unified canvas,
built on Python 3.11 + Arcade 3.x.

---

## 1. Current state (v0.3.2)

| Area | State | Notes |
|---|---|---|
| Editing canvas | ✅ | Click-to-place, drag, arc tool, multi-select, box-select |
| Petri net semantics | ✅ | Standard P/T-net firing |
| State machines | ✅ | Unified canvas with hybrid arcs (see §3) |
| Toolbar / HUD | ✅ | Tools + Save / Load / PNML / Mermaid / Undo / Redo / Step / Run / Reset / ? |
| Hover tooltips | ✅ NEW | Toolbar buttons show tooltip after 0.4 s hover |
| Help overlay | ✅ NEW | H key (or ? button) opens keyboard reference |
| Empty-canvas hint | ✅ NEW | First-launch instructions on empty canvas |
| Splash screen | ✅ | Animated PN+SM glyph |
| Main menu | ✅ | New / Open / Examples / Options / About / Quit |
| Options panel | ✅ | Grid, snap, verbose log toggle |
| About / credits | ✅ | Authors, license, attributions |
| Examples library | ✅ NEW | Bundled JSONs, selectable from menu |
| Save / load JSON | ✅ | Native format, schema versioned |
| PNML import / export | ✅ NEW | ISO/IEC 15909-2; states preserved via toolspecific |
| Mermaid export | ✅ NEW | Lossy flowchart for documentation |
| File picker | ✅ | Tkinter when available, in-canvas overlay otherwise |
| Path-entry overlay | ✅ NEW | Modal text input replaces Tkinter when missing |
| Undo / redo | ✅ | Command stack; reset is undoable |
| Multi-select | ✅ | Shift-click toggles; box-select picks rectangle |
| Pan / zoom | ✅ | Wheel to cursor; middle/space-drag pan; Home resets |
| Grid + snap | ✅ | Dot grid, optional snap |
| Inspector panel | ✅ | Right sidebar — edits label / tokens / active flag |
| Step / run simulation | ✅ | F5 / Space; auto-fire every 600 ms |
| Animated firing | ✅ | Tokens slide along arcs over ~280 ms |
| Reset marking | ✅ | F6; undoable |
| Terminal log | ✅ | Compact format; verbose toggle |
| Cached text rendering | ✅ NEW | `arcade.Text` in toolbar (kills perf warning) |
| Reachability / deadlock | ❌ | M5 (NetworkX) |
| Invariants | ❌ | M5 (numpy) |
| Hierarchical nets | ❌ | Out of scope |
| Coloured Petri nets | ❌ | Out of scope |

---

## 2. Project layout

```
petri_editor/
├── main.py
├── README.md
├── ROADMAP.md
├── examples/
│   ├── producer_consumer.json
│   ├── traffic_light.json
│   ├── mtg_card_game.json
│   ├── dominion_deck_building.json
│   ├── biochemistry_cell_cycle.json
│   ├── krebs_cycle.json
│   └── cell_cycle_cdk.json
└── petri_editor/
    ├── __init__.py        ├── help_overlay.py
    ├── __main__.py        ├── inspector.py
    ├── theme.py           ├── path_entry.py
    ├── logger.py          ├── views_splash.py
    ├── model.py           ├── views_menu.py
    ├── commands.py        ├── views_options.py
    ├── io_json.py         ├── views_about.py
    ├── io_pnml.py         ├── views_examples.py
    ├── io_mermaid.py      └── views_editor.py
    ├── camera.py
    ├── simulator.py
    └── dialogs.py
```

---

## 3. Unified Petri-net + state-machine model

State machines are formally a constrained subclass of Petri nets, so the
editor uses one model with arc rules governing which formalism applies.

**Allowed arcs:**

| Source       | Destination  | Meaning                           |
|--------------|--------------|-----------------------------------|
| Place        | Transition   | PN consumption                    |
| Transition   | Place        | PN production                     |
| State        | State        | SM edge (renders/exports; not fired — see below) |
| State        | Transition   | Hybrid: SM enters PN sub-process  |
| Transition   | State        | Hybrid: PN signals state change   |

**Rejected:** place↔place, transition↔transition, place↔state.

**Hybrid firing:** a transition with incoming State arcs requires that
state to be active. Firing deactivates incoming States and activates
outgoing States. A State consumed as a transition input is therefore
deactivated on firing; to keep it active (a catalytic gate), give the
transition an arc back to that same State.

**Executability caveat:** the simulator only fires **Transition** nodes
(it iterates `graph.transitions`). A direct `State → State` arc is legal
and is drawn/exported, but the simulator never traverses it on its own, so
a state machine made only of `State → State` edges is inert. Build an
executable state machine as `State → Transition → State` — this is what
the `traffic_light`, `mtg_card_game`, `dominion` and `cell_cycle_cdk`
examples do.

---

## 4. Keyboard / mouse reference

In-app: press **H** any time to see this list inside the editor.

| Key / mouse | Action |
|---|---|
| `1` … `5` | Select / Place / Transition / State / Arc tool |
| Click empty canvas | Add node (per current tool) |
| Click node | Select it |
| Shift-click | Toggle in selection |
| Drag empty canvas | Box-select |
| Drag node | Move whole selection |
| Middle-drag / Space-drag | Pan |
| Wheel | Zoom toward cursor |
| Wheel over a place | Add / remove tokens |
| `F` | Fire selected transition |
| `F5` | Step (one random enabled fire) |
| `Space` | Toggle run |
| `F6` | Reset to initial marking |
| `Delete` / `Backspace` | Delete selection |
| `Ctrl+S` / `Ctrl+O` | Save / Open |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo |
| `Ctrl+A` / `Ctrl+D` | Select all / Deselect |
| `Home` | Reset camera |
| **`H`** | **Toggle help overlay** |
| `Esc` | Cancel arc → clear selection → menu |

---

## 5. Import / export formats

### 5.1 JSON (native, v2 schema)

Round-trip safe; versioned.

```json
{
  "format": "petri-editor", "version": 2,
  "places":      [{"id": 1, "label": "P1", "tokens": 3, "x": 100, "y": 200}],
  "transitions": [{"id": 1, "label": "T1", "x": 200, "y": 200}],
  "states":      [{"id": 1, "label": "S1", "active": true, "x": 200, "y": 100}],
  "arcs": [{"src": {"kind": "place", "id": 1},
            "dst": {"kind": "transition", "id": 1}, "weight": 1}]
}
```

### 5.2 PNML (ISO/IEC 15909-2)

Standard PNML interchange. Read by CPN Tools, WoPeD, Snoopy, TINA, ProM.

- Y is flipped (PNML is down-positive, Arcade up-positive).
- States are exported as places with a `<toolspecific tool="petri-editor">`
  block carrying `<kind>state</kind>`. Other tools see plain places.
- High-level constructs (colours, hierarchy, inhibitor arcs) are not
  supported.

The output is hand-written XML rather than `xml.etree.ElementTree` because
ET sometimes mis-renders the `<n>` element under default-namespace
contexts in certain Python builds. This bypasses the bug.

### 5.3 Mermaid (lossy export)

Maps onto Mermaid's `flowchart` because there's no native PN diagram type:

```
flowchart LR
    P1((Producer ready •))
    T1[produce]
    P1 --> T1
```

- Places → `((label))` with token bullets
- Transitions → `[label]`
- States → `([label])`, active states get a CSS class
- Arc weight becomes an edge label when > 1

What is lost: exact coordinates, large token counts, inhibitor/reset arcs.
Use for embedding in Markdown or wiki — not as a save format.

---

## 6. Terminal log

```
[HH:MM:SS] LEVEL  area: message
```

Areas: `model`, `ui`, `io`, `sim`, `history`. Toggle DEBUG verbosity in
Options.

---

## 7. Next steps

### M4 — Polish
- Recent-files menu item
- Arc weight editing in the inspector
- Arc selection (currently only nodes are clickable)
- Hover highlight on nodes
- Confirmation dialog for delete (when option enabled)
- Disk-backed config at `~/.config/petri_editor/config.json`

### M5 — Analysis (NetworkX)
- Reachability graph (BFS over markings)
- Deadlock detection (terminal markings)
- Boundedness check
- Liveness (per-transition fireability)
- Place/transition invariants (numpy)

### M6 — Stretch
- Inhibitor and reset arcs (`Arc.kind` field)
- Per-transition priority and guards
- Hierarchical nets (PNML hl spec)
- SVG export for figures

---

## 8. Dependencies

**Required:** Python 3.11+, `arcade>=3.0`.

**Optional:** Tkinter (stdlib). If missing, the editor falls back to an
in-canvas modal text-entry overlay automatically — no code change.

**Planned:** `networkx`, `numpy` (M5).

**Not required:** Mermaid library, `lxml`, matplotlib.

---

## 9. Known limitations

- **`State → State` arcs are not executed by the simulator.** Only
  Transition nodes fire, so a state machine built purely from `State →
  State` edges is inert. Build executable SMs as `State → Transition →
  State` (see §3).
- **PNML exports a State as a `<place>`** (tagged with a tool-specific
  `kind=state` annotation). It round-trips losslessly *within this editor*,
  but a strict external P/T tool will see the resulting `state → state`
  edges as illegal `place → place` arcs. Export hybrid/SM nets to Mermaid
  for documentation; reserve PNML for pure P/T nets when targeting other
  tools.
- Inspector shows arc weight read-only; re-clicking with the Arc tool
  increments existing arcs by 1.
- Single-active-state SM invariant is not validated.
- Run-mode capped at ~3 fires/sec by animation duration (280 ms).
- No autosave.
- PNML output uses verbose `<n>` elements; legacy parsers expecting `<n>`
  may reject — most modern tools accept both.
