# Implementation Plan: Post-Tile Map Records Reverse Engineering

**Branch**: `002-post-tile-records` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-post-tile-records/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Decode the 31,366 bytes that follow the tile array in a *Soldiers at War* map so that the
mission content (soldiers, items, containers, zones) becomes inspectable and visible in the
viewer.

Phase 0 research already established the table boundaries: the read sequence of the engine's
loader, transcribed as 19 blocks, consumes all 95 version 21 maps exactly. It also confirmed
that soldier positions are stored there and that the playable window is stored explicitly in
the file. The technical approach is a declarative table layout driving one generic reader, a
separate extraction step that turns records into placed entities with anomaly flags, and
integration of those entities into the existing render list, inspector, metadata dialog, and
CLI. Field meanings are added incrementally, each graded confirmed, hypothesis, or unknown.

## Technical Context

**Language/Version**: Python 3.12 (as feature 001)

**Primary Dependencies**: Standard library (`struct`, `dataclasses`, `enum`) for decoding; existing `arcade >= 3.3.1`, `pygame >= 2.6.1`, `pillow >= 10.2.0` for display. No new dependencies.

**Storage**: Read-only access to original game files under the game directory; nothing is written.

**Testing**: `pytest` — unit tests with synthetic streams built from the layout, integration tests over all shipped maps, contract tests for the new CLI flag.

**Target Platform**: Windows 10/11 desktop (cross-platform as feature 001)

**Project Type**: Desktop CLI application with GUI viewport (existing single package `saw_map`)

**Performance Goals**: Map load stays under 2 seconds; viewport stays at 60 FPS with entities shown. Post-tile decoding adds a 31 KB parse to a 1.2 MB stream.

**Constraints**: Decoding and entity extraction must not import Arcade or Pygame. Raw bytes of every record are preserved. A failed post-tile decode never prevents the tile grid from loading. No sprite is drawn for an entity unless its archive and frame are confirmed.

**Scale/Scope**: 19 tables, 31,366 bytes, at most 40 soldiers, 40 containers, 40 zone cells, and 500 item slots per map; 96 shipped maps (95 version 21, 1 version 19).

**Unknowns resolved in Phase 0** (see [research.md](research.md)): table boundaries, cell reference encoding, playable window location, soldier position table. **Unknowns carried into implementation as graded hypotheses**: item, container, and zone semantics; soldier sprite frame; version 19 layout; tables 4, 6, 7, 11, 17, 19 and the mission parameter blocks.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against Constitution v1.3.0.

| Principle | Requirement | Plan Compliance | Status |
|---|---|---|---|
| **I. Code Quality & Maintainability** | Parsers decoupled from UI; documented interfaces; explicit error handling; no dead code | Layout, reader, and entity extraction live in `formats/` and `maps/` with no rendering imports. Decode outcome is an explicit status, never a swallowed exception. | **PASS** |
| **II. Rigorous Testing Standards** | Unit, integration, and parity tests; deterministic; 85% coverage of core logic | Synthetic-stream unit tests for the reader; integration test asserting exact byte consumption on every shipped map; reference placement checks on Airfield. | **PASS** |
| **III. User Experience Consistency** | Uniform shortcuts; actionable error feedback | Entity toggle on key `5` beside toggles `1`–`4`, routed through the shared `InputHandler`; undecodable records produce a plain-language warning. | **PASS** |
| **IV. Performance Requirements** | 60 FPS, load under 2 s, indexed lookups | Entities indexed by cell for inspection; fewer than 600 extra render items per map. | **PASS** |
| **V. Version Control Discipline** | Task branch, small conventional commits, no game assets committed | Work proceeds on branch `002-post-tile-records`; `Research/` stays git-ignored. See note below. | **PASS (with note)** |
| **VI. Reverse-Engineering Knowledge Tracking** | Discoveries recorded in `REVERSE_ENGINEERING_INFO.md` in the same unit of work; hypotheses demarcated | Every table and field carries an evidence status in code and in the knowledge base; §9 is replaced; the Phase 0 findings are scheduled as the first documentation task. | **PASS** |
| **Quality Gates** | Tests pass; docs updated with API and format changes | `quickstart.md` scenarios, README controls table, CLI contract, and knowledge base updated within the feature. | **PASS** |

**Note on principle V**: the working tree is on `master` with the feature 001 corrections and
the feature 002 specification uncommitted. Before implementation starts, that work must be
committed and the `002-post-tile-records` branch created. This is a precondition for
`/speckit-implement`, not a design violation.

**Post-design re-check**: the Phase 1 artifacts introduce no new dependency, no rendering
import in the decoding path, and no undocumented interface. All gates still pass.

## Project Structure

### Documentation (this feature)

```text
specs/002-post-tile-records/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── records-api-contract.md
│   └── cli-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/saw_map/
├── formats/
│   ├── record_layout.py        # NEW: declarative table and field layouts per stream version
│   ├── records_reader.py       # NEW: generic post-tile reader producing PostTileData
│   └── map_reader.py           # CHANGED: calls the reader, uses the stored playable window
├── maps/
│   ├── records.py              # NEW: PostTileData, TableLayout, FieldSpec, RecordTable, Record, enums
│   ├── entities.py             # NEW: PlacedEntity and extract_entities()
│   └── model.py                # CHANGED: MapDocument.post_tile / entities, ComponentType.ENTITY
├── rendering/
│   ├── draw_order.py           # CHANGED: entity render items and show_entities filter
│   ├── fallback.py             # CHANGED: category markers for entities
│   ├── arcade_backend.py       # CHANGED: draw entity items, key 5, sidebar entity lines
│   └── pygame_backend.py       # CHANGED: same as Arcade backend
├── viewer/
│   ├── camera.py               # CHANGED: show_entities flag
│   ├── input_handler.py        # CHANGED: TOGGLE_ENTITIES action
│   ├── inspector.py            # CHANGED: entities in CellInspectionInfo
│   └── overlays.py             # CHANGED: entity summary in metadata lines
├── diagnostics/
│   └── records_report.py       # NEW: text dump of tables and entities
└── main.py                     # CHANGED: --dump-records / --dump-unused

tests/
├── unit/
│   ├── test_records_reader.py  # NEW (layout and reader)
│   └── test_entities.py        # NEW
├── integration/
│   └── test_post_tile_records.py   # NEW: all maps, Airfield reference placements
└── contract/
    └── test_cli.py             # CHANGED: --dump-records behaviour

REVERSE_ENGINEERING_INFO.md     # CHANGED: §9 rewritten, §4 window source, §11 open questions
docs/formats.md                 # CHANGED: post-tile section
README.md                       # CHANGED: features, key 5, dump flag
```

**Structure Decision**: Extend the existing single package `saw_map`, following its established
split: binary knowledge in `formats/`, domain data in `maps/`, drawing in `rendering/`,
interaction in `viewer/`, text reports in `diagnostics/`. No new package or project is added.

## Implementation Milestones

### Milestone 1: Structural decoding (User Story 1)
- Record model, version 21 layout, generic reader with explicit decode status.
- `MapReader` attaches `PostTileData`; the playable window is taken from the stored values with
  the `.txt` rule as fallback.
- `--dump-records` report.
- Tests: layout size, synthetic round trip, size mismatch, unknown version, exact consumption
  of all shipped maps, window parity with feature 001.
- Knowledge base: replace §9 with the confirmed table list.

### Milestone 2: Placement identification (User Story 2)
- Entity extraction for soldiers (positions joined with soldier records), then items,
  containers, and zone cells, each behind its evidence status.
- Used-slot rules per table; anomaly flags for out-of-window positions and unresolved
  references.
- Tests: Airfield reference placements, anomaly rate across all maps.
- Research tasks: soldier sprite frame rule, item and container field meanings, turret storage.

### Milestone 3: Viewer integration (User Story 3)
- Entity render items, markers, `show_entities` toggle on key `5`.
- Inspector and metadata dialog show entities.
- Tests: draw-order filtering, input action, headless frames on both backends.

### Milestone 4: Documentation and closure (User Story 4)
- Field tables with evidence status in the knowledge base; retract or confirm earlier estimates.
- `docs/formats.md`, README, and feature 001 contracts cross-referenced.
- Optional: transcribe the older reader for the version 19 layout.

## Complexity Tracking

*No constitutional violations identified.*
