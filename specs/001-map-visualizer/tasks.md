# Implementation Tasks: Soldiers at War Original Map Viewer

**Feature**: `001-map-visualizer` | **Date**: 2026-10-11 | **Plan**: [specs/001-map-visualizer/plan.md](specs/001-map-visualizer/plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, directory structure, dependencies, and diagnostic logging

- [X] T001 Create project package directory structure per implementation plan in `src/saw_map/{assets,formats,maps,geometry,rendering,viewer,diagnostics}` and `tests/{unit,integration,contract}`
- [X] T002 Initialize Python project configuration and dependencies (`arcade>=3.3.1`, `pillow>=10.2.0`, `pygame>=2.6.1`, `pytest>=7.4.4`) in `pyproject.toml`
- [X] T003 [P] Implement configurable structured diagnostic logger with `--log-level` support in `src/saw_map/diagnostics/logger.py`
- [X] T004 [P] Create package export definitions in `src/saw_map/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models, geometry transformations, and binary decoders required before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Create core domain models (`MapDocument`, `MapCell`, `CellComponent`, `ComponentType`, `TilesetDefinition`) with validation constraints ($20 \le \text{width} \le 130$, $20 \le \text{height} \le 100$, 7 layers) in `src/saw_map/maps/model.py`
- [X] T006 [P] Implement forward and inverse dimetric isometric coordinate transformations (`IsometricTransform`) in `src/saw_map/geometry/transform.py`
- [X] T007 [P] Implement unit tests verifying coordinate forward/inverse round-trip accuracy in `tests/unit/test_geometry.py`
- [X] T008 [P] Implement Autodesk 776-byte palette reader (`PaletteReader`) loading 256 RGB tuples in `src/saw_map/formats/palette_reader.py`
- [X] T009 [P] Implement unit tests for palette decoding against `Win.pal` in `tests/unit/test_palette.py`
- [X] T010 [P] Implement row-based RLE sprite decoder (`SpriteReader`) handling scanline codes (`0x00` end-of-row, `0x80` transparent run, `cmd & 0x80` copy, `cmd < 0x80` repeat) and alpha masks in `src/saw_map/formats/sprite_reader.py`
- [X] T011 [P] Implement unit tests for sprite archive RLE stream decoding and alpha mask creation in `tests/unit/test_rle_decoder.py`
- [X] T012 [P] Implement companion `.set` definition parser (`TilesetParser`) partitioning into surfaces, left walls, right walls, and clutter in `src/saw_map/formats/set_parser.py`
- [X] T013 [P] Implement unit tests for `.set` line count partitioning in `tests/unit/test_set_parser.py`
- [X] T014 Implement gzip/raw container auto-detection and v20/v21 `AMB_MAP` stream parser (`MapReader`) in `src/saw_map/formats/map_reader.py`
- [X] T015 [P] Implement unit tests for 16-bit cell component bitmask unpacking (`presence = word >> 15 & 1`, `group = word >> 7 & 0xFF`, `frame = word & 0x7F`) in `tests/unit/test_bitfield.py`
- [X] T016 Implement recursive read-only file scanner and cataloger (`AssetInventory`) in `src/saw_map/assets/inventory.py`
- [X] T017 [P] Implement central asset manager (`AssetLoader` implementing `IAssetLoader`) with RGBA texture caching in `src/saw_map/assets/loader.py`
- [X] T018 Implement depth-sorting draw-order strategy (`DrawOrderStrategy`) sorting by `(layer_z, x + y, component_type, y)` in `src/saw_map/rendering/draw_order.py`
- [X] T019 [P] Define abstract renderer interface (`IRenderer`) in `src/saw_map/rendering/backend_base.py`

**Checkpoint**: Core domain models, geometry transformations, and binary decoders complete and verified by headless unit tests.

---

## Phase 3: User Story 1 - Command-Line Map Loading & Visualization (Priority: P1) 🎯 MVP

**Goal**: Load a Soldiers at War game map file from the command line, resolve companion assets, and render the map in an interactive graphical window within 2 seconds.

**Independent Test**: Run `python -m saw_map.main "Research/SSI/Soldiers at War/Single_g/Airfield.map" --game-dir "Research/SSI/Soldiers at War"` and verify that the window opens displaying the rendered isometric map at 60 FPS.

### Tests for User Story 1

- [X] T020 [P] [US1] Contract test for CLI argument parsing, missing file exit code `1`, and `--help` in `tests/contract/test_cli.py`
- [X] T021 [P] [US1] Integration test verifying full decompression and dimension parsing of `Airfield.map` (104x80) in `tests/integration/test_map_reading.py`

### Implementation for User Story 1

- [X] T022 [US1] Implement primary Arcade 3.3.1 hardware-accelerated renderer (`ArcadeRenderer` implementing `IRenderer`) with batched sprite lists in `src/saw_map/rendering/arcade_backend.py`
- [X] T023 [P] [US1] Implement fallback Pygame 2.6.1 software surface renderer (`PygameRenderer` implementing `IRenderer`) in `src/saw_map/rendering/pygame_backend.py`
- [X] T024 [US1] Implement distinctive colored placeholder geometry generator for missing or unresolved sprite assets in `src/saw_map/rendering/fallback.py`
- [X] T025 [US1] Implement CLI entry point, argument parsing (`--game-dir`, `--palette`, `--backend`, `--diagnostics`), and exit code handling in `src/saw_map/main.py`
- [X] T026 [US1] Create standalone executable entry point script `run_viewer.py` at repository root

**Checkpoint**: User Story 1 delivers a complete, independently testable MVP capable of loading and displaying game maps from the command line.

---

## Phase 4: User Story 2 - Interactive Viewport Navigation & Perspectives (Priority: P2)

**Goal**: Smoothly pan across large maps, zoom centered on the cursor, switch between Isometric and 2D Top-Down grid perspectives, and toggle a corner minimap overlay.

**Independent Test**: Launch visualizer with `Airfield.map`, drag mouse to pan across all four quadrants, scroll to zoom, press `Tab`/`T` to toggle top-down view, and press `M` to toggle the minimap overlay.

### Tests for User Story 2

- [X] T027 [P] [US2] Unit tests for camera coordinate transformations, zoom bounds ($0.25\times \dots 4.0\times$), and view resets in `tests/unit/test_camera.py`

### Implementation for User Story 2

- [X] T028 [US2] Implement Camera state manager with cursor-centered zoom and dragging in `src/saw_map/viewer/camera.py`
- [X] T029 [US2] Implement keyboard and mouse event routing (Arrow keys, WASD, mouse drag, mouse wheel, reset `Home`/`R`) in `src/saw_map/viewer/input_handler.py`
- [X] T030 [US2] Implement 2D Top-Down orthogonal grid rendering mode alongside classic Isometric projection in `src/saw_map/rendering/arcade_backend.py`
- [X] T031 [US2] Implement toggleable 2D top-down minimap corner overlay with active camera bounding rectangle in `src/saw_map/viewer/minimap.py`
- [X] T032 [US2] Integrate perspective toggle (`Tab`/`T`) and minimap toggle (`M`) event handlers into `src/saw_map/viewer/input_handler.py`

**Checkpoint**: User Story 2 delivers full camera navigation, dual-perspective projection, and minimap orientation.

---

## Phase 5: User Story 3 - Multi-Elevation Layer Filtering (Priority: P3)

**Goal**: Filter rendering across the 7 vertical elevation levels (0 through 6) and toggle individual structural components (floors, walls, clutter) to inspect occluded structures.

**Independent Test**: Load `Mansion.map`, press `PageDown`/`Q` to lower visible elevation from level 6 to level 1, and verify upper floors hide to reveal ground floor interiors.

### Tests for User Story 3

- [X] T033 [P] [US3] Unit tests for elevation filtering and component visibility bitmasks in `tests/unit/test_layer_filter.py`

### Implementation for User Story 3

- [X] T034 [US3] Implement elevation range filtering ($Z = 0 \dots 6$, hotkeys `PageUp`/`PageDown`/`E`/`Q`) in `src/saw_map/rendering/draw_order.py`
- [X] T035 [US3] Implement structural component visibility toggles (Floors `1`, Left Walls `2`, Right Walls `3`, Clutter `4`) in `src/saw_map/rendering/arcade_backend.py`
- [X] T036 [US3] Implement single-layer isolation mode hotkey in `src/saw_map/viewer/input_handler.py`

**Checkpoint**: User Story 3 provides comprehensive vertical inspection for multi-story buildings and underground rooms.

---

## Phase 6: User Story 4 - Tile Inspection & Diagnostic Overlays (Priority: P4)

**Goal**: Inspect hovered tile coordinates `(X, Y, Z)` in a bottom status bar, view deep sprite attributes in a toggleable inspection sidebar (`I`), cycle color palettes (`P`), and view map metadata.

**Independent Test**: Move the mouse across the map; verify the bottom status bar updates cell coordinates and tile IDs; press `I` to open the sidebar and inspect sprite dimensions; press `P` to cycle palettes.

### Tests for User Story 4

- [X] T037 [P] [US4] Integration test for mouse-cursor grid cell picking at arbitrary camera zoom and pan offsets in `tests/integration/test_picking.py`

### Implementation for User Story 4

- [X] T038 [US4] Implement hovered cell detection using inverse isometric projection in `src/saw_map/viewer/inspector.py`
- [X] T039 [US4] Implement lightweight bottom status bar displaying hovered `(X, Y, Z)`, elevation, and component IDs in `src/saw_map/viewer/overlays.py`
- [X] T040 [US4] Implement toggleable inspection sidebar (`I` key) displaying sprite dimensions, flags, and tileset associations in `src/saw_map/viewer/overlays.py`
- [X] T041 [US4] Implement runtime palette cycling hotkey (`P`) switching between `Win.pal` and ambient palettes in `src/saw_map/viewer/input_handler.py`
- [X] T042 [US4] Implement map metadata overlay dialog (hotkey `F1`/`H`) displaying map title, dimensions, tilesets used, and mission summary in `src/saw_map/viewer/overlays.py`

**Checkpoint**: User Story 4 equips researchers with complete diagnostic and reverse-engineering inspection tools.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Multi-map validation, discovery reporting, format documentation, and regression tests

- [X] T043 [P] Implement asset inventory and discovery report generator in `src/saw_map/diagnostics/report.py`
- [X] T044 [P] Add integration test loading multiple original maps (`Cassino.map`, `Normandy.map`, `Mansion.map`) in `tests/integration/test_multi_maps.py`
- [X] T045 Execute full validation scenario workflow per `quickstart.md`
- [X] T046 [P] Document reverse-engineering findings and binary format specifications in `docs/formats.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — **BLOCKS all user stories**.
- **User Story 1 (Phase 3, MVP)**: Depends on Foundational (Phase 2).
- **User Story 2 (Phase 4)**: Depends on User Story 1 (Phase 3).
- **User Story 3 (Phase 5)**: Depends on User Story 2 (Phase 4).
- **User Story 4 (Phase 6)**: Depends on User Story 2 & 3 (Phases 4 & 5).
- **Polish (Phase 7)**: Depends on User Stories 1–4.

### Parallel Opportunities

- **Setup**: `T003` and `T004` can run in parallel after `T001`.
- **Foundational**:
  - Models (`T005`), Geometry math (`T006`), Palette reader (`T008`), Sprite decoder (`T010`), Set parser (`T012`), and Scanner (`T016`) are in separate modules and can be developed in parallel.
  - Tests (`T007`, `T009`, `T011`, `T013`, `T015`, `T017`, `T019`) can run in parallel.
- **User Story 1**: Contract test (`T020`) and Integration test (`T021`) can run in parallel before implementation.
- **User Story 2**: Camera test (`T027`) and minimap overlay (`T031`) can run in parallel.
- **User Story 3**: Layer filter tests (`T033`) can run in parallel with component toggle development.
- **User Story 4**: Picking test (`T037`) can run in parallel with overlay development.

---

## Parallel Example: Foundational Phase

```bash
# Launch decoders and pure math modules in parallel:
Task: "Implement forward and inverse dimetric isometric coordinate transformations in src/saw_map/geometry/transform.py"
Task: "Implement Autodesk 776-byte palette reader in src/saw_map/formats/palette_reader.py"
Task: "Implement row-based RLE sprite decoder in src/saw_map/formats/sprite_reader.py"
Task: "Implement companion .set definition parser in src/saw_map/formats/set_parser.py"

# Launch headless unit tests in parallel:
Task: "Implement unit tests in tests/unit/test_geometry.py"
Task: "Implement unit tests in tests/unit/test_palette.py"
Task: "Implement unit tests in tests/unit/test_rle_decoder.py"
Task: "Implement unit tests in tests/unit/test_set_parser.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (`T001`–`T004`).
2. Complete Phase 2: Foundational (`T005`–`T019`) — verify all unit tests pass headlessly.
3. Complete Phase 3: User Story 1 (`T020`–`T026`).
4. **STOP and VALIDATE**: Launch `run_viewer.py` with `Airfield.map` and verify the map opens and displays properly.

### Incremental Delivery

1. Setup + Foundational $\rightarrow$ Verified core engine math and decoders.
2. User Story 1 $\rightarrow$ Working CLI application that loads and visualizes maps (**MVP**).
3. User Story 2 $\rightarrow$ Fluid camera navigation, isometric/orthogonal view toggle, and minimap.
4. User Story 3 $\rightarrow$ 7-layer vertical inspection and structural category toggles.
5. User Story 4 $\rightarrow$ Real-time coordinate picking, bottom status bar, and inspection sidebar.
6. Polish $\rightarrow$ Multi-map regression validation and format documentation.
