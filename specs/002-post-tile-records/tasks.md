# Implementation Tasks: Post-Tile Map Records Reverse Engineering

**Feature**: `002-post-tile-records` | **Date**: 2026-10-11 | **Plan**: [plan.md](plan.md)

**Input**: Design documents from `/specs/002-post-tile-records/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Tests**: Included. The constitution (principle II) requires automated tests with every capability.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Branch and verification baseline

- [X] T001 Create feature branch `002-post-tile-records` from the committed `master` and confirm the feature 001 test suite passes (78 tests)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Record model shared by every user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Create record domain models (`PostTileData`, `TableLayout`, `FieldSpec`, `RecordTable`, `Record`, `PlacedEntity`, `DecodeStatus`, `EvidenceStatus`, `FieldKind`, `EntityCategory`) and cell index helpers in `src/saw_map/maps/records.py`
- [X] T003 Extend `MapDocument` with `post_tile`, `entities`, `set_entities()`, `entities_at()` and add `ComponentType.ENTITY` in `src/saw_map/maps/model.py`

**Checkpoint**: Record model importable without any rendering dependency.

---

## Phase 3: User Story 1 - Complete Structural Decoding of the Post-Tile Data (Priority: P1) 🎯 MVP

**Goal**: Every byte after the tile array is read into named record tables, with the outcome reported as an explicit status.

**Independent Test**: `pytest tests/unit/test_records_reader.py tests/integration/test_post_tile_records.py::test_every_v21_map_is_consumed_exactly`

### Tests for User Story 1

- [X] T004 [P] [US1] Unit tests for the version 21 layout (31,366 bytes, 19 tables, record sizes, evidence notes), cell index round trip, synthetic-stream decoding, and non-raising failure statuses in `tests/unit/test_records_reader.py`
- [X] T005 [P] [US1] Integration test asserting exact byte consumption of all 95 version 21 maps and `UNSUPPORTED_VERSION` for `Menu/Demo.MAP` in `tests/integration/test_post_tile_records.py`
- [X] T006 [P] [US1] Contract tests for `--dump-records` / `--dump-unused` (exit code 0, report content, unsupported version not a failure) in `tests/contract/test_cli.py`

### Implementation for User Story 1

- [X] T007 [US1] Transcribe the read sequence of `sub_445F25` into the declarative version 21 layout with field kinds, evidence status, and source references in `src/saw_map/formats/record_layout.py`
- [X] T008 [US1] Implement the generic `RecordsReader` (status `DECODED` / `UNSUPPORTED_VERSION` / `SIZE_MISMATCH` / `MISSING`, raw bytes preserved, used-slot rules) in `src/saw_map/formats/records_reader.py`
- [X] T009 [US1] Call the reader from `MapReader.parse_map`, log undecodable records as a warning, and take the playable window from the stored bounds with the `.txt` rule as fallback in `src/saw_map/formats/map_reader.py`
- [X] T010 [US1] Implement the plain-text records report in `src/saw_map/diagnostics/records_report.py`
- [X] T011 [US1] Add `--dump-records` and `--dump-unused` to the CLI (no game directory or display needed) in `src/saw_map/main.py`
- [X] T012 [US1] Integration test that the stored playable window equals the centered mission-file window on every version 21 map in `tests/integration/test_post_tile_records.py`

**Checkpoint**: All shipped maps decode structurally; the dump lists every table.

---

## Phase 4: User Story 2 - Identify Placed Soldiers, Items, and Objectives (Priority: P2)

**Goal**: Records that place soldiers, tokens, containers, turrets, and ground objects are identified with position and sprite.

**Independent Test**: `pytest tests/unit/test_entities.py tests/integration/test_post_tile_records.py::test_airfield_reference_placements`

### Research for User Story 2

- [X] T013 [US2] Trace the engine draw routines for built-in archives (`sub_435562` People, `sub_434FB0` Token table, `sub_4352FD` Turret groups, `sub_43505D` cell-flag markers and Can.obj) in `SAW_TD_NOTES.c` and validate each rule against all 95 maps
- [X] T014 [US2] Verify soldier sprites and positions against `Research/EditorScreenshots/airfield_airplane.png` and the inactive turret group against `airfield_map_level_7.png`

### Tests for User Story 2

- [X] T015 [P] [US2] Unit tests for entity extraction (unused slots, soldiers with side and hidden flag, tokens, containers, turret groups, items, cell-flag entities, anomalies) in `tests/unit/test_entities.py`
- [X] T016 [P] [US2] Integration tests for sprite frame validity and anomaly rate across all maps, record cells versus engine cell flags, and Airfield reference placements in `tests/integration/test_post_tile_records.py`

### Implementation for User Story 2

- [X] T017 [US2] Implement `extract_entities()` for containers, tokens, soldiers (joined with the soldier table by slot), turret parts, and placed items, with anomaly flags, in `src/saw_map/maps/entities.py`
- [X] T018 [US2] Implement cell-flag entities (Can.obj ground objects, Token.obj editor markers) in `src/saw_map/maps/entities.py`
- [X] T019 [US2] Attach extracted entities to the map document and log the placement summary in `src/saw_map/formats/map_reader.py`

**Checkpoint**: Airfield yields 40 soldiers, 32 tokens, 2 containers with zero anomalies.

---

## Phase 5: User Story 3 - See Placed Entities in the Viewer (Priority: P3)

**Goal**: Entities are drawn on the map, can be toggled, and appear in the inspection tools.

**Independent Test**: `pytest tests/unit/test_entities.py::test_draw_order_entity_filters tests/integration/test_overlays_rendering.py`, then quickstart Scenario 6.

### Tests for User Story 3

- [X] T020 [P] [US3] Unit tests for entity render items (ordering, toggles, elevation filter, isolation, hidden entities) and for entity toggles, inspection, status bar, sidebar lines, and metadata summary in `tests/unit/test_entities.py`
- [X] T021 [P] [US3] Extend headless backend tests with entity and marker toggles and an inspected soldier cell in `tests/integration/test_overlays_rendering.py`

### Implementation for User Story 3

- [X] T022 [US3] Add `show_entities` / `show_markers` to `Camera` in `src/saw_map/viewer/camera.py` and `TOGGLE_ENTITIES` / `TOGGLE_MARKERS` to `InputHandler` in `src/saw_map/viewer/input_handler.py`
- [X] T023 [US3] Emit entity render items after the clutter of their cell, honouring toggles, elevation filtering, isolation, and the engine's hidden rules, in `src/saw_map/rendering/draw_order.py`
- [X] T024 [P] [US3] Add the entity placeholder marker colour in `src/saw_map/rendering/fallback.py`
- [X] T025 [US3] Bind keys `5` / `6`, pass the toggles to the render list, key placeholder textures by category, and list cell entities in the sidebar in `src/saw_map/rendering/arcade_backend.py`
- [X] T026 [US3] Apply the same changes to `src/saw_map/rendering/pygame_backend.py`
- [X] T027 [US3] Pass cell entities through `CellInspector.inspect_cell` and make entity-only cells pickable in `src/saw_map/viewer/inspector.py`
- [X] T028 [US3] Add entity lines, the status bar entity label, and the mission content summary of the metadata dialog in `src/saw_map/viewer/overlays.py`

**Checkpoint**: The viewer shows the soldier beside the Ju 52 as the Scenario Builder does.

---

## Phase 6: User Story 4 - Documented, Evidence-Graded Field Knowledge (Priority: P4)

**Goal**: Every post-tile table and field is documented with its evidence status; earlier estimates are corrected.

**Independent Test**: Quickstart "Documentation Check".

- [X] T029 [US4] Replace §9 of `REVERSE_ENGINEERING_INFO.md` with the confirmed table list, field tables with evidence status, and the retraction of the earlier estimates
- [X] T030 [US4] Document the cell flag bits, the built-in archive draw rules, and the stored playable window; update open questions in `REVERSE_ENGINEERING_INFO.md`
- [X] T031 [P] [US4] Add the post-tile section and cell flag table to `docs/formats.md`
- [X] T032 [P] [US4] Update `README.md` (features, keys `5` / `6`, `--dump-records`, test description)
- [X] T033 [US4] Bring `research.md`, `data-model.md`, and the contracts of this feature in line with what the implementation established

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T034 Run the full test suite and the quickstart scenarios; confirm load time and feature 001 behaviour are unchanged
- [ ] T035 (Optional, deferred) Transcribe the older map reader to obtain the version 19 record layout for `Menu/Demo.MAP`

---

## Phase 8: Follow-up Investigation (second screenshot set)

**Purpose**: Explain the dice, ammo, outlined cells, reinforcement tokens, and folders shown in the additional Scenario Builder screenshots

- [X] T036 [US2] Map the Scenario Builder mode names and placement handler to cell flag bits and tables (`SAW_TD_NOTES.c` lines 39380–39800 and 79854–79917)
- [X] T037 [US2] Decode the soldier alternate cell (dice), nationality, controller, AI, encumbrance, per-soldier percentage, and loadout references; decode the reinforcement settings table in `src/saw_map/formats/record_layout.py`
- [X] T038 [US2] Rename entity categories to the editor's terms (`INFO`, `CANISTER`), add `RELOCATION` entities, attach reinforcement and soldier attributes, and relabel markers in `src/saw_map/maps/records.py` and `src/saw_map/maps/entities.py`
- [X] T039 [US3] Show entity attributes in the sidebar, update the metadata summary, and label the cell byte as black-out mask in `src/saw_map/viewer/overlays.py` and both backends
- [X] T040 [P] [US2] Tests for relocation entities, reinforcement attributes, loadout references, and the screenshot cells in `tests/unit/test_entities.py` and `tests/integration/test_post_tile_records.py`
- [X] T041 [US4] Record the findings and the open folder discrepancy in `REVERSE_ENGINEERING_INFO.md`, `docs/formats.md`, `README.md`, and this feature's documents
- [X] T047 [US2] Decode the soldier portrait number (`Portrait.obj` frame = 3 × portrait), verify it against the outfitting screenshot and all maps, and expose it on soldier entities
- [X] T046 [US2] Decode information token target type, condition, and causes and the reinforcement character type, controller, AI, entry condition, and turn/token from the editor's dropdown lists; correct the information token field order; expose all values by name; add cross-map validation tests
- [X] T045 [US2] Decode the item holder fields, canister contents, loadout grid, and civilian appearances from the controlled edit `Airfield_CIVILIANS.MAP`; place canister items as `ITEM` entities and report item counts on canisters; retract the item 'cell' field
- [X] T044 [US2] Decode the Field Medic flag from a controlled map edit, name the facing values from the user's observations, expose both on soldier entities, and document the diff of `Airfield_MEDIC.MAP`
- [X] T043 [US2] Decode rank, controller, AI, primary and secondary training, facing, and appearance of soldier records from the Character Stats dropdown lists; expose them by name on soldier entities; add value-range and frame-formula tests
- [X] T042 [US2] Decode information tokens (Token ID, condition, causes, radius, popup text from the mission file) and canister contents from `airfield_objective_1..4.png`; split token messages from the briefing in `src/saw_map/formats/map_reader.py`, update `record_layout.py`, `entities.py`, `overlays.py`, tests, and documentation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — blocks all user stories.
- **User Story 1 (Phase 3, MVP)**: Depends on Foundational.
- **User Story 2 (Phase 4)**: Depends on User Story 1 (decoded tables).
- **User Story 3 (Phase 5)**: Depends on User Story 2 (entities).
- **User Story 4 (Phase 6)**: Depends on User Stories 1–2 for content; can proceed alongside User Story 3.
- **Polish (Phase 7)**: Depends on all stories. T035 is independent and optional.

### Parallel Opportunities

- T004, T005, T006 (different test files) can be written in parallel before T007–T011.
- T015 and T016 can be written in parallel.
- T024 is independent of T022–T023; T025 and T026 touch different backends and can proceed in parallel after T023.
- T031 and T032 touch different documents.

---

## Parallel Example: User Story 1

```bash
# Write the three test files together:
Task: "Unit tests for layout and reader in tests/unit/test_records_reader.py"
Task: "Integration test for exact consumption in tests/integration/test_post_tile_records.py"
Task: "Contract tests for --dump-records in tests/contract/test_cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 and Phase 2.
2. Phase 3: layout, reader, dump.
3. **STOP and VALIDATE**: `--dump-records` on Airfield shows 19 tables and 0 bytes unassigned.

### Incremental Delivery

1. User Story 1 → every byte of the map file is accounted for.
2. User Story 2 → soldiers, tokens, containers, turrets identified and verified against screenshots.
3. User Story 3 → entities visible and inspectable in the viewer.
4. User Story 4 → knowledge base updated and earlier estimates retracted.
