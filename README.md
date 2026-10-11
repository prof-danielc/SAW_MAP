# Soldiers at War (1998) Map Visualizer & Asset Inspector

A standalone, hardware-accelerated desktop map visualizer and asset inspector for **Soldiers at War** (SSI / Random Games, 1998). Built with Python 3.12, Arcade (OpenGL), Pygame fallback, and Pillow.

The tool parses original binary `.map` files, companion `.set` definitions, `.obj`/`.spr` sprite archives, and Autodesk `.pal`/`.col` palettes, rendering them in authentic 2:1 dimetric isometric or 2D orthogonal top-down projections with full interactive inspection capabilities.

---

## Features

- **Dual Rendering Backends**:
  - **Arcade 3.3.1 (Default)**: Hardware-accelerated OpenGL batched sprite rendering via `arcade.SpriteList` and `arcade.camera.Camera2D`.
  - **Pygame 2.6.1 (Fallback)**: CPU surface blitting fallback when OpenGL is unavailable or software rendering is preferred.
- **Accurate Binary Format Parsing**:
  - Auto-detects Gzip-compressed (`1F 8B`) and raw uncompressed `.map` streams.
  - Supports v19, v20 and v21 `AMB_MAP` streams (193-byte header).
  - Unpacks 3D tile arrays across 7 vertical elevation layers ($Z = 0 \dots 6$), 100 rows ($Y$), and 130 columns ($X$) with 13-byte cell strides, and locates the playable window centered inside that grid.
  - Resolves the tileset from the name stored in the map header, so custom maps built on generic sets load correctly.
  - Decompresses companion `.set` tileset partitions and `.obj`/`.spr` scanline RLE sprites.
  - Decodes the record tables that follow the tile array (version 21): soldiers with their alternate positions, reinforcement tokens and their settings, information tokens (mission triggers and objectives, with their popup text), canister contents, turret groups, and the stored playable window, with every byte of the map file accounted for.
- **Interactive Viewport & Controls**:
  - Smooth camera panning (WASD / Arrows / Mouse Drag) and fractional zoom (0.25x – 4.0x), cursor-centered on the mouse wheel.
  - Slicing and isolation of elevation layers ($0 \dots 6$).
  - Per-component visibility filtering (Floors, Left Walls, Right Walls, Clutter/Objects).
  - Engine-accurate floor culling: floors hidden under a higher level reappear as the view level is lowered.
  - Placed entities drawn with their original sprites, named after the Scenario Builder modes: soldiers (`People.obj`), their alternate positions (dice), reinforcement tokens and information tokens (`Token.obj`), items / canisters (`Can.obj`), and active turrets (`Turret.obj`); editor markers (mission exits, land mines, medical, lockable, multiplayer) can be shown separately.
  - Instant perspective toggling between Dimetric Isometric and 2D Top-Down.
  - Hot-swapping between daylight (`Win.pal`) and night/ambient (`Darkpal.col`) color palettes.
- **Inspection Tools & Overlays**:
  - **Tile Inspector Sidebar**: Real-time cell inspection displaying coordinates, attribute byte, cell flags DWORD, and all 4 component slots (Floor/Surface, Left Wall, Right Wall, Clutter/Object) with raw 16-bit hex words, resolved asset names, and sprite frame indices.
  - **Map Metadata Dialog**: Map name, version, dimensions, tileset partition counts, mission content counts (soldiers, reinforcement tokens, information tokens, ...), and the mission briefing text.
  - **Record Dump**: `--dump-records` prints every post-tile table and placed entity of a map without opening a window.
  - **Minimap Overlay**: Picture-in-picture 2D orthogonal tactical minimap featuring procedural terrain surface colors (snow, hangar stone, dirt, railroad tracks, wood, metal, grass) and interactive camera viewport diamond frustum.
  - **Status HUD**: Map name and size, view perspective, active elevation layer, zoom factor, and the hovered cell with its primary tile.
- **Strict Architecture Principles**:
  - Pure Python data models, format readers, and coordinate math are 100% decoupled from graphics engines.
  - Game assets in `Research/SSI/Soldiers at War/` are treated as strictly immutable and read-only.

---

## Installation & Requirements

### Prerequisites
- Python 3.10+ (tested on Python 3.12.3)
- Windows, Linux, or macOS

### Dependencies
Install the required packages:
```bash
pip install arcade pygame pillow pytest
```

Alternatively, install the project in editable mode:
```bash
pip install -e .
```

---

## Quickstart & Usage

Run the visualizer with a target map using the `run_viewer.py` launcher or Python module:

### 1. Launch with Arcade (Hardware-Accelerated OpenGL)
```bash
python run_viewer.py "Research/SSI/Soldiers at War/Single_g/Airfield.map" --game-dir "Research/SSI/Soldiers at War"
```

### 2. Launch with Pygame (Software Surface Fallback)
```bash
python run_viewer.py "Research/SSI/Soldiers at War/Single_g/Airfield.map" --game-dir "Research/SSI/Soldiers at War" --backend pygame
```

### 3. Dump the Post-Tile Records of a Map
```bash
python run_viewer.py "Research/SSI/Soldiers at War/Single_g/Airfield.map" --dump-records
```

### 4. Module CLI Invocation
```bash
python -m saw_map.main "Research/SSI/Soldiers at War/Single_g/Airfield.map" --game-dir "Research/SSI/Soldiers at War"
```

### CLI Command Options

| Option | Short | Default | Description |
|---|---|---|---|
| `MAP_FILE` | — | *(Optional)* | Path to the `.map` file (e.g. `Airfield.map`). |
| `--game-dir` | `-g` | `auto` | Root directory containing `Obj/`, `Sets/`, `Misc/`. |
| `--backend` | `-b` | `arcade` | Rendering backend: `arcade` or `pygame`. |
| `--palette` | `-p` | `Win.pal` | Path to custom `.pal` or `.col` palette file. |
| `--layer` | `-l` | `6` | Initial maximum visible elevation layer (`0`..`6`). |
| `--view` | `-v` | `isometric` | Initial view perspective: `isometric` or `top-down`. |
| `--diagnostics` | `-d` | `False` | Enable verbose reverse-engineering inspection output. |
| `--maximize` | — | `False` | Start visualizer window in maximized mode. |
| `--dump-records` | — | `False` | Print the post-tile record tables and placed entities, then exit. |
| `--dump-unused` | — | `False` | With `--dump-records`, also list unused record slots. |
| `--log-level` | — | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `--help` | `-h` | — | Show help message and exit. |

---

## Key Bindings & Controls

The visualizer provides a unified set of controls across both the Arcade and Pygame backends:

### 1. Viewport Navigation & Camera

| Control | Action | Description |
|---|---|---|
| <kbd>W</kbd> / <kbd>Up Arrow</kbd> | **Pan Up** | Move the camera up in world space; pan keys scroll continuously while held and can be combined for diagonals |
| <kbd>S</kbd> / <kbd>Down Arrow</kbd> | **Pan Down** | Move the camera down in world space |
| <kbd>A</kbd> / <kbd>Left Arrow</kbd> | **Pan Left** | Move the camera left in world space |
| <kbd>D</kbd> / <kbd>Right Arrow</kbd> | **Pan Right** | Move the camera right in world space |
| **Left Mouse Drag** | **Mouse Pan** | Click and drag the left mouse button to freely pan the view |
| <kbd>+</kbd> / <kbd>=</kbd> / <kbd>Num +</kbd> | **Zoom In** | Increase magnification (up to 4.0x) |
| <kbd>-</kbd> / <kbd>Num -</kbd> | **Zoom Out** | Decrease magnification (down to 0.25x) |
| **Mouse Wheel** | **Scroll Zoom** | Scroll up to zoom in, scroll down to zoom out, centered on the cursor |
| <kbd>Home</kbd> / <kbd>R</kbd> | **Reset View** | Reset camera position to the center of the playable map and zoom to 1.0x |

### 2. Elevation Slicing & Layer Filtering

| Control | Action | Description |
|---|---|---|
| <kbd>Page Up</kbd> / <kbd>E</kbd> | **Elevation Up** | Increase maximum visible layer ($Z \le \text{layer}$) |
| <kbd>Page Down</kbd> / <kbd>Q</kbd> | **Elevation Down** | Decrease maximum visible layer ($Z \le \text{layer}$) |
| <kbd>L</kbd> | **Isolate Layer** | Toggle isolation mode: renders **only** the current active layer |

### 3. Perspectives, Overlays & Inspection

| Control | Action | Description |
|---|---|---|
| <kbd>Tab</kbd> / <kbd>T</kbd> | **Toggle Perspective** | Switch between Dimetric Isometric (2:1 diamond) and 2D Top-Down |
| <kbd>M</kbd> | **Toggle Minimap** | Show or hide picture-in-picture minimap overlay. Soldiers appear as dots: allied green, enemy red, civilian blue |
| <kbd>G</kbd> | **Toggle Cell Grid** | Show or hide the cell grid, painted on the border of every floor sprite, so it follows slopes, raised terrain and roofs and is covered by whatever stands in front |
| <kbd>I</kbd> | **Toggle Inspector** | Show or hide tile property sidebar |
| <kbd>F1</kbd> / <kbd>H</kbd> | **Toggle Map Metadata** | Show or hide the map metadata and mission briefing dialog |
| <kbd>P</kbd> | **Cycle Palette** | Switch between daylight (`Win.pal`) and night/ambient (`Darkpal.col`) |
| <kbd>F11</kbd> / <kbd>F</kbd> | **Toggle Fullscreen / Maximize** | Toggle window between fullscreen and normal windowed mode |
| **Mouse Hover** | **Inspect Tile** | The tile under the cursor is shown in the status bar and sidebar. Its floor sprite is tinted and outlined, following the sprite's shape; a cell without a floor gets a plain diamond instead |
| <kbd>Esc</kbd> | **Exit** | Close the application |

### 4. Structural Component Visibility Filters

| Control | Action | Description |
|---|---|---|
| <kbd>1</kbd> | **Toggle Floors** | Show or hide floor and ground surface components (`word0`), including upper-level floors and roofs |
| <kbd>2</kbd> | **Toggle Left Walls** | Show or hide left wall components (`word1`) |
| <kbd>3</kbd> | **Toggle Right Walls** | Show or hide right wall components (`word2`) |
| <kbd>4</kbd> | **Toggle Clutter / Objects** | Show or hide clutter and object components (`word3`) |
| <kbd>5</kbd> | **Toggle Entities** | Show or hide placed soldiers, alternate positions, reinforcement tokens, information tokens, canisters, and turrets |
| <kbd>6</kbd> | **Toggle Editor Markers** | Show or hide the Scenario Builder markers stored in cell flags: mission exits, land mines, medical, lockable, multiplayer (off by default) |

---

## Project Structure

```text
SAW_MAP/
├── .specify/memory/
│   └── constitution.md         # Project constitution & governing principles (v1.3.0)
├── docs/
│   ├── formats.md              # File format specifications & layout tables
│   └── discovery_report.md     # Asset discovery audit (1,736 files cataloged)
├── specs/002-post-tile-records/ # Specification, plan, and tasks of the record decoding feature
├── specs/001-map-visualizer/
│   ├── spec.md                 # Feature specification
│   ├── plan.md                 # Architecture & implementation plan
│   ├── tasks.md                # Executed implementation tasks
│   └── research.md             # Reverse-engineering discoveries & technical decisions
├── src/saw_map/
│   ├── assets/                 # Asset loading, indexing & sprite caching
│   ├── diagnostics/            # Logging and diagnostic reporters
│   ├── formats/                # Binary map, set, sprite, and palette readers
│   ├── geometry/               # Coordinate transformation math (pure Python)
│   ├── maps/                   # Domain models (MapDocument, MapCell, CellComponent)
│   ├── rendering/              # Arcade & Pygame backends, depth sorting
│   ├── viewer/                 # Camera, input handling, minimap, inspector, overlays
│   └── main.py                 # CLI entry point
├── tests/
│   ├── contract/               # CLI argument & contract tests
│   ├── integration/            # Multi-map loading & mouse picking tests
│   └── unit/                   # RLE, bitfield, palette, camera, geometry, input unit tests
├── REVERSE_ENGINEERING_INFO.md # Comprehensive reverse-engineering reference
├── run_viewer.py               # Root quickstart execution script
├── pyproject.toml              # Project metadata & build configuration
└── README.md                   # Project documentation & user guide
```

---

## Reverse Engineering Documentation

Detailed reverse-engineering documentation, disassembly analyses from `SAW_TD_NOTES.c`, opcode tables, and memory structures are documented in:
- [`REVERSE_ENGINEERING_INFO.md`](REVERSE_ENGINEERING_INFO.md) — Comprehensive reverse-engineering knowledge base covering the Lupine/Ordoor engine, decompression, the 193-byte header, 13-byte cell bitmasks, the playable window, scanline RLE, and post-tile array mission records.
- [`docs/formats.md`](docs/formats.md) — Specification tables for containers, headers, and coordinate transformations.

One result worth knowing when reading soldier data: a soldier's sprite frame in `People.obj` equals `8 × appearance + (facing + 4) mod 8` for 1,831 of 1,852 soldiers in the shipped maps, where facing runs N, NE, E, SE, S, SW, W, NW (0–7, north = up on screen).

---

## Running the Test Suite

Run the full automated test suite with `pytest`:
```bash
pytest tests/ -v
```

The automated tests verify:
- Binary map parsing across multiple original maps (`Airfield`, `Cassino`, `Normandy`, `Mansion`), and that every tile word of every shipped map references a valid tileset entry.
- Input action dispatching, overlay text, and headless frame rendering on both backends.
- Post-tile record decoding: exact byte consumption of every version 21 map, placement tables checked against the engine's cell flags, and reference placements on `Airfield`.
- Bitfield component unpacking, presence masks, and floor cover levels.
- Forward and inverse dimetric isometric projection math with sub-pixel picking accuracy.
- Scanline RLE decoding and alpha mask transparency.
- Autodesk COL/PAL palette loading and RGBA image conversions.
- Camera transformations, elevation slicing, and component filtering.