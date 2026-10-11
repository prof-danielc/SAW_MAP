# Feature Specification: Soldiers at War Map Visualizer

**Feature Branch**: `001-map-visualizer`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Create a Python application that loads and visualizes a Soldiers at War game map file. The application should take the game map file name as an input command line parameter. The folder "Research" contains some things that might be useful. "sprite-view.py" is a reverse engineered application for viewing game sprites in python. An early version in C++ of sprite-view can be found in "Research/SaWFontReader". In "Research\SSI\Soldiers at War" many files can be useful, including "SAW_progress.txt", detailing some reverse engineering observations, "SAW_Game_NOTES.c" is the C decompilation of the game with some notes, and "SAW_TD_NOTES.c" is the map editor C decompilation with some notes."

## Clarifications

### Session 2026-10-11
- Q: How should the application locate supporting game assets (palettes, tilesets, and sprite archives) when loading a map file? (FR-005) → A: The application checks the current working directory first, and requires an explicit `--game-dir` command-line flag if assets reside in another directory.
- Q: Should the application support exporting the rendered map directly to an image file via command line in addition to interactive window viewing? (FR-014) → A: No, keep the application strictly focused on interactive GUI viewing only.
- Q: How should the visualizer determine which color palette to apply when rendering game sprites? (FR-006) → A: Attempt to auto-detect the palette from map or mission naming conventions, falling back to Win.pal, while providing an optional `--palette` CLI flag and an in-viewer toggle hotkey.
- Q: Should the visualizer support switching between the classic isometric perspective and a 2D top-down orthogonal view? (FR-007) → A: Support both perspectives via an in-viewer toggle hotkey between classic Isometric and 2D Top-Down grid view, and include a toggleable 2D top-down minimap corner overlay.
- Q: How should tile diagnostic and inspection details be displayed in the visualizer interface during exploration? (FR-011) → A: A lightweight bottom status bar displays hovered cell coordinates and tile IDs by default, with a toggleable detailed inspection sidebar (e.g., I key).
- Q: What binary container compression and magic signature does a Soldiers at War game map file use? (FR-003) → A: Treat container format and binary layouts as empirical research targets; system must dynamically inspect signatures, support gzip with uncompressed fallback, support v20/v21 headers, and provide diagnostic analysis logging.
- Q: How should the application handle map dimensions and grid cell allocation given that map dimensions vary between 20x20 and 130x100 across 7 elevation levels? (FR-004) → A: Dynamically bound the grid to the map's active dimensions (extracted from companion .txt or map headers), up to the maximum 130x100x7 engine ceiling.
- Q: In the reverse-engineered cell structure (word_559630), how should the 16-bit word entries for tile components (floor, left wall, right wall, clutter) be decoded? (FR-004) → A: Decode bit 15 as presence ((word >> 15) & 1), bits 7–14 as tileset index ((word >> 7) & 0xFF), and bits 0–6 as sprite frame index (word & 0x7F), accompanied by diagnostic logging to verify against decompilation findings.
- Q: How should the companion .set definition files be parsed to resolve map cell indices to sprite .obj files? (FR-005) → A: Parse the section count line (e.g., 13 12 12 28) to partition the definitions into surfaces (s), left walls (l), right walls (r), and clutter (c), mapping each entry to Obj/<name>.obj.
- Q: How does the reverse-engineered RLE algorithm in game sprite archives (.obj/.spr) decode transparent and opaque pixels? (FR-006) → A: Process row-based byte commands where 0x00 terminates the row, 0x80 skips transparent pixels, cmd & 0x80 copies literal bytes, and cmd < 0x80 repeats byte values, indexing into the 256-color RGB palette with full alpha transparency.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Command-Line Map Loading & Visualization (Priority: P1)

As a game modder, researcher, or player, I want to execute the application from the command line passing a Soldiers at War game map file, so that I can immediately inspect the rendered map layout in an interactive graphical window.

**Why this priority**: This represents the core minimum viable product (MVP). Without the ability to load a map file and render its visual structure, no further analysis or editing can take place.

**Independent Test**: Execute the application via command line with a valid map file (e.g., `Airfield.map`); verify that an interactive visualizer window opens and renders the map terrain and layout within 2 seconds.

**Acceptance Scenarios**:

1. **Given** a valid Soldiers at War `.map` file path provided on the command line, **When** the application is launched, **Then** the application parses the map data and displays the complete map in an interactive graphical viewport.
2. **Given** an invalid, nonexistent, or corrupted map file path, **When** the application is launched, **Then** the application displays a clear, human-readable error message in the console explaining the issue and terminates gracefully without crashing.
3. **Given** a map file with associated companion files (such as `.set` and `.txt`), **When** the map is loaded, **Then** the application resolves companion files from the current working directory or the directory supplied via `--game-dir` to correctly resolve tiles and mission context.

---

### User Story 2 - Interactive Viewport Navigation (Priority: P2)

As a user exploring large game boards, I want to smoothly pan across the map and zoom in and out, so that I can examine both macro-level tactical terrain and fine-grained tile details.

**Why this priority**: Game maps can be up to 130x100 tiles spanning multiple screen resolutions; an interactive viewport with pan and zoom is essential to view areas beyond the default viewport frame.

**Independent Test**: Load a large map file; use drag/arrow navigation to move across all four quadrants and use the mouse wheel/keys to zoom between overview and close-up views without visual artifacts.

**Acceptance Scenarios**:

1. **Given** a map loaded in the viewer, **When** the user drags with the mouse or presses navigation keys, **Then** the viewport smoothly scrolls across the map boundaries.
2. **Given** a map loaded in the viewer, **When** the user scrolls the mouse wheel or presses zoom hotkeys, **Then** the camera zooms centered on the cursor or viewport center while preserving crisp rendering.
3. **Given** any zoom or pan state, **When** the user triggers a view reset command (e.g., press Home/R), **Then** the viewport resets to a centered overview framing the map.
4. **Given** the visualizer is open, **When** the user presses the view toggle hotkey (e.g., Tab or T), **Then** the display transitions between classic Isometric view and 2D Top-Down orthogonal grid view while preserving camera focus.
5. **Given** the visualizer is open, **When** the user toggles the minimap (e.g., M), **Then** a 2D top-down overview displays or hides in a corner overlay with an indicator of the current camera position.

---

### User Story 3 - Multi-Elevation Layer Filtering (Priority: P3)

As a researcher analyzing multi-story buildings and underground bunkers, I want to toggle individual elevation layers (levels 0 through 6) and structural element types, so that I can inspect floors occluded by upper levels and roofs.

**Why this priority**: Soldiers at War maps contain up to 7 vertical layers. Higher floors and roofs visually occlude lower floors and ground features, requiring vertical layer filtering to inspect interior layouts.

**Independent Test**: Load a map containing multi-level buildings (e.g., `Mansion.map`); step through elevation levels 0 to 6; verify that higher levels are hidden and lower-level interiors become visible.

**Acceptance Scenarios**:

1. **Given** a multi-elevation map, **When** the user changes the active maximum elevation level, **Then** all tiles and objects on layers higher than the selected level are hidden.
2. **Given** a multi-elevation map, **When** the user toggles specific structural categories (floors, left walls, right walls, or clutter/objects), **Then** the corresponding components are hidden or revealed in real time.
3. **Given** isolated layer viewing mode, **When** the user isolates a single layer, **Then** only tiles belonging strictly to that elevation level are displayed.

---

### User Story 4 - Tile Inspection & Metadata Diagnostic Display (Priority: P4)

As a reverse engineering researcher, I want to inspect individual tiles and view map metadata, so that I can see the exact tile coordinates, layer indices, sprite IDs, and tileset associations.

**Why this priority**: Reverse engineers and tool builders need granular diagnostic information to verify decoding accuracy and match in-game tile indices with decompiled source logic.

**Independent Test**: Hover over any tile on the map; verify that an on-screen overlay or status bar shows the grid coordinates `(X, Y, Z)`, tile component IDs, and active tileset names.

**Acceptance Scenarios**:

1. **Given** the visualizer is running, **When** the user moves the cursor over any map position, **Then** the bottom status bar immediately updates to display the hovered cell coordinates `(X, Y, Z)`, elevation, and component IDs.
2. **Given** the visualizer is running, **When** the user toggles the inspection panel (e.g., I key), **Then** a detailed inspection sidebar opens or closes, displaying full sprite dimensions, component flags, and active tileset references for the focused tile.
3. **Given** the visualizer is running, **When** the user toggles the map metadata overlay, **Then** the application displays map-level properties (internal map title, dimensions, detected tilesets, mission brief text).

---

### Edge Cases

- **Missing Asset Dependencies**: If a referenced sprite (`.obj`), tileset (`.set`), or palette file (`.pal`/`.col`) is missing or cannot be located, the system MUST render distinctive fallback placeholder tiles (e.g., colored geometric bounding boxes with index labels) rather than crashing.
- **Missing Asset Directory Flag**: If game assets are not found in the current working directory and `--game-dir` is not specified, the system MUST output a clear guidance message indicating that `--game-dir` is required to locate game assets.
- **File Compression Handling**: Game maps are gzip-compressed binary streams. If a map file is already uncompressed or uses unexpected gzip wrapper variants, the system MUST attempt direct parsing after decompression fallback.
- **Extreme Map Dimensions**: System MUST support the entire valid game engine dimension range (from 20x20 up to 130x100 tiles across 7 elevations) without buffer overflows, coordinate wrapping, or memory exhaustion.
- **Sparse and Empty Layers**: Many maps have unpopulated upper layers (e.g., empty levels 4-6). The system MUST handle empty cells without performance penalty or rendering artifacts.
- **Window Resizing**: When the window is resized or maximized, the viewport MUST adjust aspect ratio without stretching, distorting tile proportions, or resetting the current camera position.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a map file path as a primary command-line argument, and support explicit `--game-dir` (asset root path) and `--palette` (color palette file path) flags.
- **FR-002**: System MUST validate input files and report specific, actionable error messages if a file is missing, unreadable, or not a recognized map format.
- **FR-003**: System MUST dynamically inspect input file signatures without rigid format assumptions, auto-detecting compression (gzip vs uncompressed streams), validating version headers (supporting version 20 and 21 `AMB_MAP` variants), and emitting detailed reverse-engineering diagnostic logs.
- **FR-004**: System MUST parse the 3D map tile grid spanning up to 7 vertical layers and dynamically bound the active grid by the map's declared dimensions (up to 130 columns by 100 rows). For each cell, the system MUST decode 16-bit component words (floor, left wall, right wall, clutter) extracting presence bit 15 (`>> 15 & 1`), tileset group index bits 7–14 (`>> 7 & 0xFF`), and sprite frame index bits 0–6 (`& 0x7F`), with diagnostic analysis logging.
- **FR-005**: System MUST resolve companion game data files (`.txt` mission briefings, `.set` tile definition lists, `.obj` sprites, and `.pal` palettes) by checking the current working directory first, and falling back to `--game-dir`. For `.set` files, the system MUST parse the section count header line to partition names into surfaces (`s`), left walls (`l`), right walls (`r`), and clutter (`c`), mapping each name to its respective archive in `Obj/<name>.obj`. If assets cannot be resolved, clear CLI feedback MUST prompt the user to supply `--game-dir`.
- **FR-006**: System MUST decode game sprite archives (`.obj`/`.spr`) using row-based RLE commands (byte `0x00` end-of-row, `0x80` transparent pixel skip, `cmd & 0x80` literal copy, and `cmd < 0x80` repeated pixel) mapped to 256-color palettes (`.pal`/`.col`). The system MUST auto-detect intended palettes from mission conventions, fall back to `Win.pal`, support `--palette` CLI override, and provide an in-viewer toggle hotkey (e.g., P) to cycle palettes at runtime.
- **FR-007**: System MUST render map tiles in standard isometric view with depth sorting, and support toggling between Isometric and 2D Top-Down orthogonal view via an in-viewer hotkey (e.g., Tab or T). The system MUST also provide a toggleable 2D top-down minimap corner overlay (e.g., M) indicating the active camera position.
- **FR-008**: System MUST provide interactive viewport panning (via mouse drag and directional keys) and zooming (via mouse scroll wheel and keyboard shortcuts).
- **FR-009**: System MUST allow users to filter rendering by elevation level (selecting active level or maximum visible level from 0 to 6).
- **FR-010**: System MUST allow users to toggle visibility of tile sub-components (floors, walls, clutter/objects).
- **FR-011**: System MUST display contextual diagnostic information for hovered tiles (coordinates X, Y, Z, component indices, and tileset name) in a lightweight bottom status bar, and provide a toggleable detailed inspection sidebar (e.g., I key) for in-depth cell attributes.
- **FR-012**: System MUST display map summary metadata (dimensions, map name, tilesets used).
- **FR-013**: System MUST use graceful fallback graphics for any missing, corrupt, or unparsed sprite assets, ensuring visualizer continuity.

### Key Entities *(include if feature involves data)*

- **Map Document**: Represents the parsed game map, containing metadata (internal map name, dimensions $W \times H$, version), active layer definitions, and the 3D cell matrix.
- **Map Cell**: A discrete 3D spatial coordinate $(X, Y, Z)$ consisting of:
  - Floor/Ground surface identifier and flags
  - Left wall identifier and flags
  - Right wall identifier and flags
  - Clutter/Object identifier and flags
  - Spatial attributes (occlusion, height, visibility)
- **Tileset Definition**: An associated list of sprite collections defining which `.obj` files map to surface, wall, and clutter indices for a given mission.
- **Sprite Asset**: Decoded graphic asset with dimensions, transparency mask, and color values mapped from the 256-color palette.
- **Palette**: A 256-color RGB lookup table defining the color values for 8-bit game graphics.
- **Camera / Viewport**: The active viewing transformation defining position offset, zoom magnification, window bounds, and active layer visibility filters.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The map visualizer window opens and renders the complete map within 2 seconds of command invocation for standard map files.
- **SC-002**: Viewport interactions (panning, zooming) maintain smooth, fluid visual response (>60 FPS) without stutter or input lag on standard systems.
- **SC-003**: 100% of valid game map files in the game repository load and display without application crashes or unhandled exceptions.
- **SC-004**: When supplied with an invalid or missing file path, the application exits cleanly with an informative error message in under 500 milliseconds.
- **SC-005**: Users can inspect all 7 vertical elevation layers independently, enabling unobstructed view of lower-level floors and subterranean rooms.
- **SC-006**: Fallback indicators are rendered for 100% of missing or unrecognized sprite assets without interrupting the visualization session.

## Assumptions & Scope Boundaries
 
- Binary map format structures and container signatures are treated as research targets to be dynamically analyzed, validated, and logged rather than rigidly assumed.
- Supporting game assets (`.set` definitions, `.obj` sprite files, and `.pal` color palettes) reside in the current working directory or within the path passed to `--game-dir`.
- The application runs on a desktop environment with Python 3.8+ and standard graphic display capability.
- Default visual projection is isometric, matching the original Soldiers at War game and tactical editor perspective.
- **Out of Scope**: Headless/batch image export to disk and in-app map editing or saving are explicitly out of scope for this feature.
