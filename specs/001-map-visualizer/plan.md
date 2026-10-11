# Implementation Plan: Soldiers at War Original Map Viewer

**Branch**: `001-map-visualizer` | **Date**: 2026-10-11 | **Spec**: [specs/001-map-visualizer/spec.md](specs/001-map-visualizer/spec.md)

**Input**: Feature specification from `/specs/001-map-visualizer/spec.md`

---

## Summary

Implement a standalone Python desktop application for inspecting, reverse-engineering, and visualizing the original maps and graphical assets of *Soldiers at War*. The application features a modular architecture that completely decouples binary file decoding and isometric geometry transformations from GUI presentation. Rendering is driven by **Arcade 3.3.1** (with an explicit fallback to **Pygame 2.6.1** via an `IRenderer` abstraction), while **Pillow** handles palette application, alpha transparency compositing, and pixel-level inspection.

---

## Technical Context

**Language/Version**: Python 3.12.3

**Primary Dependencies**:
- `arcade >= 3.3.1` (Primary hardware-accelerated OpenGL viewport)
- `pygame >= 2.6.1` (Secondary/fallback rendering backend)
- `pillow >= 10.2.0` (Image decoding, palette manipulation, alpha compositing)
- Standard library: `struct`, `gzip`, `argparse`, `pathlib`, `logging`, `typing`

**Storage**: File-based read-only access to original game directories (`Obj/`, `Sets/`, `Misc/`, `Single_g/`). Originals are never modified.

**Testing**: `pytest >= 7.4.4` (Tiers: Unit tests with synthetic fixtures, Integration tests with research game data, Contract tests for CLI).

**Target Platform**: Windows 10/11 desktop (cross-platform compatible across Linux and macOS).

**Project Type**: Desktop CLI application with hardware-accelerated GUI viewport.

**Performance Goals**:
- $\ge 60$ FPS viewport rendering during panning, zooming, and layer cycling ($\le 16.6\text{ ms}$ frame render time).
- Sub-2 second load time for full standard maps (e.g. `Airfield.map`).
- Sub-500 millisecond graceful exit on invalid CLI parameters.

**Constraints**:
- Absolute decoupling: Map models, binary parsers, and coordinate transformations MUST run without importing or initializing Arcade/Pygame display surfaces.
- Memory efficiency: Decoded sprite frames and palettes must be cached to prevent redundant RLE decoding during rendering loops.

**Scale/Scope**:
- 7 vertical elevation layers.
- Map dimensions from 20x20 up to 130x100 tiles (up to 91,000 potential cells).
- Supports full catalog of Soldiers at War sprite archives (65+ archives per mission).

---

## Constitution Check

*GATE: Evaluated against Constitution v1.0.0. All gates PASS.*

| Constitutional Pillar | Requirement | Plan Compliance | Status |
|---|---|---|---|
| **I. Code Quality & Maintainability** | Modular decoupling; domain parsers isolated from UI/storage; explicit typing & error handling; zero dead code. | Architecture strictly separates `formats/`, `maps/`, `geometry/`, and `rendering/`. All public APIs typed and documented. | **PASS** |
| **II. Rigorous Testing Standards** | Deterministic unit tests; integration tests with reference data; core logic coverage baseline $\ge 85\%$. | Headless unit test suite for math/decoders; integration tests for `.map`/`.set`/`.obj`; zero GUI dependency for CI tests. | **PASS** |
| **III. User Experience Consistency** | Responsive non-blocking interactions; clear actionable error messages; predictable controls & navigation. | Standardized keyboard/mouse controls; bottom status bar; exit codes $0-4$ with human-readable error messages. | **PASS** |
| **IV. Performance Requirements** | 60 FPS viewport rendering budget; $<2\text{s}$ initial load; optimal spatial lookups. | Arcade OpenGL batched rendering (`SpriteList`); cached RGBA textures; dynamic dimension bounding. | **PASS** |
| **Quality Gates** | Automated test suite execution; benchmark regression checks; documentation parity. | Comprehensive test plan; design artifacts (`data-model.md`, `contracts/`, `quickstart.md`) synchronized. | **PASS** |

---

## Project Structure

### Documentation (this feature)

```text
specs/001-map-visualizer/
├── spec.md              # Feature specification with clarifications
├── plan.md              # Implementation plan (this file)
├── research.md          # Reverse-engineering discoveries & architectural decisions
├── data-model.md        # Entity definitions, field validations, and relationships
├── quickstart.md        # Runnable verification and testing guide
├── contracts/           # Interface contracts
│   ├── cli-contract.md  # CLI argument syntax, options, and exit codes
│   └── api-contracts.md # Abstract interfaces (IMapParser, IAssetLoader, IRenderer)
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code Layout

```text
src/
└── saw_map/
    ├── __init__.py
    ├── main.py                     # Application entry point and CLI parser
    ├── assets/                     # Asset inventory, discovery, cache
    │   ├── __init__.py
    │   ├── inventory.py            # Recursive read-only file scanner & cataloger
    │   └── loader.py               # Central asset manager (IAssetLoader)
    ├── formats/                    # Format-specific reverse-engineered parsers
    │   ├── __init__.py
    │   ├── map_reader.py           # Gzip/raw decompression & .map parser (IMapParser)
    │   ├── set_parser.py           # Companion .set definition parser
    │   ├── sprite_reader.py        # .obj/.spr RLE sprite archive decoder
    │   └── palette_reader.py       # .pal/.col 256-color palette reader
    ├── maps/                       # Core map data models
    │   ├── __init__.py
    │   └── model.py                # MapDocument, MapCell, CellComponent
    ├── geometry/                   # Mathematical coordinate transformations
    │   ├── __init__.py
    │   └── transform.py            # Isometric forward & inverse screen transforms
    ├── rendering/                  # Visual rendering backends & draw order
    │   ├── __init__.py
    │   ├── draw_order.py           # Depth-sorting & layer filter strategy
    │   ├── backend_base.py         # Abstract IRenderer interface
    │   ├── arcade_backend.py       # Primary Arcade 3.3.1 OpenGL hardware renderer
    │   └── pygame_backend.py       # Secondary Pygame 2.6.1 surface fallback renderer
    ├── viewer/                     # Viewport camera, inputs, and UI chrome
    │   ├── __init__.py
    │   ├── camera.py               # Camera state, zoom limits, panning
    │   ├── input_handler.py        # Event routing (keyboard/mouse mappings)
    │   └── overlays.py             # Bottom status bar, minimap, inspection sidebar
    └── diagnostics/                # Inspection logging and discovery reports
        ├── __init__.py
        ├── logger.py               # Configurable diagnostic logger
        └── report.py               # Inventory & map summary reporter

tests/
├── unit/
│   ├── test_geometry.py            # Coordinate transformations & inverse math
│   ├── test_bitfield.py            # Tile cell component word unpacking
│   ├── test_rle_decoder.py         # Sprite RLE decoding and alpha masking
│   ├── test_palette.py             # Palette reader & RGB verification
│   └── test_set_parser.py          # .set partition line parsing
├── integration/
│   ├── test_map_reading.py         # Real .map decompression and dimension verification
│   ├── test_sprite_loading.py      # Real .obj decoding with Win.pal
│   └── test_asset_inventory.py     # Directory scanning & catalog verification
└── contract/
    └── test_cli.py                 # Argument parsing and error exit codes
```

**Structure Decision**: A clean single-package modular structure (`saw_map`) located under `src/` adhering to the user's explicit architectural guidelines (`assets`, `formats`, `maps`, `geometry`, `rendering`, `viewer`, `diagnostics`), paired with tiered automated test directories under `tests/`.

---

## Implementation Milestones

### Milestone 1: Repository & Asset Discovery
- Implement `saw_map.assets.inventory`: Recursively scan game directories without modifying files; record relative paths, sizes, and formats.
- Implement `saw_map.diagnostics.report`: Generate summary inventory reports of discovered `.map`, `.set`, `.obj`, `.spr`, `.pal`, `.col`, and `.txt` files.
- Automated tests in `tests/integration/test_asset_inventory.py`.

### Milestone 2: Representative Asset Decoders
- Implement `saw_map.formats.palette_reader`: Load 776-byte Autodesk COL / PAL files (`Win.pal`, `Darkpal.col`) into 256 RGB tuples.
- Implement `saw_map.formats.sprite_reader`: Decode 32-byte header, index table, 24-byte sprite header, and RLE command byte streams with alpha masks into Pillow RGBA images.
- Automated unit tests in `tests/unit/test_palette.py` and `tests/unit/test_rle_decoder.py`.

### Milestone 3: Map Format Discovery & Parsing
- Implement `saw_map.formats.map_reader`: Detect gzip vs raw stream, parse version 20/21 `AMB_MAP` headers, and unpack 3D tile matrices.
- Implement `saw_map.formats.set_parser`: Partition `.set` entries into surfaces, walls, and clutter.
- Implement `saw_map.maps.model`: Build `MapDocument`, `MapCell`, and `CellComponent` models with bitmask decoders.
- Automated tests in `tests/unit/test_bitfield.py`, `tests/unit/test_set_parser.py`, and `tests/integration/test_map_reading.py`.

### Milestone 4: Isometric Geometry & First Map Rendering
- Implement `saw_map.geometry.transform`: Dimetric isometric forward and inverse transformations.
- Implement `saw_map.rendering.draw_order`: Depth sorting by `(layer_z, x + y, component_type)`.
- Implement `saw_map.rendering.arcade_backend` and `pygame_backend`: Bind `MapDocument` and render visible tiles with cached sprites.
- Automated tests in `tests/unit/test_geometry.py`.

### Milestone 5: Interactive Viewport Inspection
- Implement `saw_map.viewer.camera`: Pan, zoom, and reset transformations.
- Implement `saw_map.viewer.input_handler`: Mouse drag, mouse wheel, keyboard shortcuts for layers, perspectives, and palette toggles.
- Implement `saw_map.viewer.overlays`: Bottom status bar with hovered cell `(X, Y, Z)`, 2D minimap corner overlay, and toggleable inspection sidebar.

### Milestone 6: Fidelity, Robustness & CLI Integration
- Implement `saw_map.main`: CLI parser with `--game-dir`, `--palette`, `--layer`, `--view`, `--diagnostics`, and clean exit codes.
- Implement fallback rendering for missing sprite assets.
- Complete contract tests in `tests/contract/test_cli.py` and end-to-end integration tests.

---

## Complexity Tracking

*No constitutional violations identified. The modular multi-layer design directly satisfies the requirement of complete backend-agnostic decoupling.*
