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
  - Supports Engine v20 and v21 `AMB_MAP` headers (187 bytes).
  - Unpacks 3D tile arrays across 7 vertical elevation layers ($Z = 0 \dots 6$), 100 rows ($Y$), and 130 columns ($X$) with 13-byte cell strides.
  - Decompresses companion `.set` tileset partitions and `.obj`/`.spr` scanline RLE sprites.
- **Interactive Viewport & Controls**:
  - Smooth camera panning (WASD / Arrows / Mouse Drag) and fractional zoom (0.25x – 4.0x).
  - Slicing and isolation of elevation layers ($0 \dots 6$).
  - Per-component visibility filtering (Floors, Left Walls, Right Walls, Clutter/Objects).
  - Instant perspective toggling between Dimetric Isometric and 2D Top-Down.
  - Hot-swapping between daylight (`Win.pal`) and night/ambient (`Darkpal.col`) color palettes.
- **Inspection Tools & Overlays**:
  - **Tile Inspector Sidebar**: Real-time cell inspection displaying coordinates, elevation attribute, cell flags DWORD, and all 4 component slots (Roof/Ceiling/Mask, Left Wall, Right Wall, Ground Surface/Clutter) with raw 16-bit hex words, resolved asset names, and sprite frame indices.
  - **Minimap Overlay**: Picture-in-picture 2D orthogonal tactical minimap featuring procedural terrain surface colors (snow, hangar stone, dirt, railroad tracks, wood, metal, grass) and interactive camera viewport diamond frustum.
  - **Status HUD**: Real-time camera coordinates, zoom factor, active elevation layer, and rendering backend indicator.
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

### 3. Module CLI Invocation
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
| `--log-level` | — | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `--help` | `-h` | — | Show help message and exit. |

---

## Key Bindings & Controls

The visualizer provides a unified set of controls across both the Arcade and Pygame backends:

### 1. Viewport Navigation & Camera

| Control | Action | Description |
|---|---|---|
| <kbd>W</kbd> / <kbd>Up Arrow</kbd> | **Pan Up** | Move the camera up in world space |
| <kbd>S</kbd> / <kbd>Down Arrow</kbd> | **Pan Down** | Move the camera down in world space |
| <kbd>A</kbd> / <kbd>Left Arrow</kbd> | **Pan Left** | Move the camera left in world space |
| <kbd>D</kbd> / <kbd>Right Arrow</kbd> | **Pan Right** | Move the camera right in world space |
| **Left Mouse Drag** | **Mouse Pan** | Click and drag the left mouse button to freely pan the view |
| <kbd>+</kbd> / <kbd>=</kbd> / <kbd>Num +</kbd> | **Zoom In** | Increase magnification (up to 4.0x) |
| <kbd>-</kbd> / <kbd>Num -</kbd> | **Zoom Out** | Decrease magnification (down to 0.25x) |
| **Mouse Wheel** | **Scroll Zoom** | Scroll up to zoom in, scroll down to zoom out |
| <kbd>Home</kbd> / <kbd>R</kbd> | **Reset View** | Reset camera position to map center and zoom to 1.0x |

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
| <kbd>M</kbd> | **Toggle Minimap** | Show or hide picture-in-picture minimap overlay |
| <kbd>I</kbd> | **Toggle Inspector** | Show or hide tile property sidebar |
| <kbd>P</kbd> | **Cycle Palette** | Switch between daylight (`Win.pal`) and night/ambient (`Darkpal.col`) |
| <kbd>F11</kbd> / <kbd>F</kbd> | **Toggle Fullscreen / Maximize** | Toggle window between fullscreen and normal windowed mode |
| **Left Mouse Click** | **Inspect Tile** | Select tile under cursor to inspect its layers and components in sidebar |
| <kbd>Esc</kbd> | **Exit** | Close the application |

### 4. Structural Component Visibility Filters

| Control | Action | Description |
|---|---|---|
| <kbd>1</kbd> | **Toggle Roofs / Ceilings** | Show or hide roof, ceiling, and upper cutaway components (`word0`) |
| <kbd>2</kbd> | **Toggle Left Walls** | Show or hide left wall components (`word1`) |
| <kbd>3</kbd> | **Toggle Right Walls** | Show or hide right wall components (`word2`) |
| <kbd>4</kbd> | **Toggle Surface / Clutter** | Show or hide procedural ground surface and clutter components (`word3`) |

---

## Project Structure

```text
SAW_MAP/
├── .specify/memory/
│   └── constitution.md         # Project constitution & governing principles (v1.3.0)
├── docs/
│   ├── formats.md              # File format specifications & layout tables
│   └── discovery_report.md     # Asset discovery audit (1,736 files cataloged)
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
│   └── unit/                   # RLE, bitfield, palette, camera, geometry unit tests
├── REVERSE_ENGINEERING_INFO.md # Comprehensive reverse-engineering reference
├── run_viewer.py               # Root quickstart execution script
├── pyproject.toml              # Project metadata & build configuration
└── README.md                   # Project documentation & user guide
```

---

## Reverse Engineering Documentation

Detailed reverse-engineering documentation, disassembly analyses from `SAW_TD_NOTES.c`, opcode tables, and memory structures are documented in:
- [`REVERSE_ENGINEERING_INFO.md`](REVERSE_ENGINEERING_INFO.md) — Comprehensive reverse-engineering knowledge base covering the Lupine/Ordoor engine, decompression, 13-byte cell bitmasks, scanline RLE, and post-tile array mission records.
- [`docs/formats.md`](docs/formats.md) — Specification tables for containers, headers, and coordinate transformations.

---

## Running the Test Suite

Run the full automated test suite with `pytest`:
```bash
pytest tests/ -v
```

All 45 automated tests verify:
- Binary map parsing across multiple original maps (`Airfield`, `Cassino`, `Normandy`, `Mansion`).
- Bitfield component unpacking and presence masks.
- Forward and inverse dimetric isometric projection math with sub-pixel picking accuracy.
- Scanline RLE decoding and alpha mask transparency.
- Autodesk COL/PAL palette loading and RGBA image conversions.
- Camera transformations, elevation slicing, and component filtering.