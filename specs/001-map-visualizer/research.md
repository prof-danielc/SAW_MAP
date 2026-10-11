# Research & Technical Decisions: Soldiers at War Map Visualizer

**Feature**: `001-map-visualizer` | **Date**: 2026-10-11

## Overview

This document records the empirical discoveries, reverse-engineering findings, architectural decisions, and technology choices for the Soldiers at War Map Visualizer.

---

## 1. GUI Framework & Rendering Backend

### Decision
Use **Python 3.12** with **Arcade 3.3.1** as the primary hardware-accelerated rendering engine, with an explicit abstraction boundary (`IRenderer`) that allows **Pygame 2.6.1 (or pygame-ce)** as a drop-in fallback.

### Rationale
- **Arcade 3.3.1** is installed and operational in the user's environment. It provides native OpenGL sprite batching (`arcade.SpriteList`), smooth fractional camera transformations, and crisp nearest-neighbor integer scaling essential for retro pixel art.
- Both the user prompt and project principles mandate that the map data model, binary parsers, and coordinate transformations remain completely decoupled from any rendering engine. Defining an `IRenderer` interface isolates Arcade-specific textures/sprites from pure Python domain objects.
- **Pygame 2.6.1** is also installed and provides an immediate CPU-based surface rendering alternative if OpenGL context or display issues arise.

### Alternatives Considered
- **Pygame exclusively**: Viable, but standard software surface blitting on large isometric maps (up to 130x100 tiles across 7 layers = up to 91,000 potential cell draws) is significantly slower than Arcade's OpenGL batched draws.
- **PyQt / PySide6**: Excellent for complex tool sidebars, but adds heavy GUI overhead and less natural 60 FPS game-loop viewport integration.

---

## 2. Binary Map Container & Compression

### Empirical Observations
- Analysis of `Research/SSI/Soldiers at War/Single_g/Airfield.map` demonstrates gzip compression starting with magic bytes `1F 8B 08 00`.
- Decompressing `Airfield.map` yields exactly `1,214,559` bytes.
- The decompressed stream begins with:
  - `0x15 0x00`: 16-bit integer version `21` (also supports v20 as per decompiled `sub_445F25` / `sub_4471BC` in `SAW_TD_NOTES.c`; `Menu/Demo.MAP` is v19 with the same header and tile layout).
  - `AMB_MAP\0`: 8-byte ASCII null-terminated identifier.
  - 128-byte tileset name string buffer (e.g. `"Airfield"`); the engine opens `Sets/<name>.set` from it.
  - 55 bytes of editor state (cursor, scroll, brush, view level), giving a 193-byte header.
  - 3D Tile Array: 7 vertical layers $\times$ 100 rows $\times$ 130 columns $\times$ 13 bytes per cell = `1,183,000` bytes.
  - Followed by entity placement tables and canister records.

### Decision
Implement `MapReader` in `saw_map.formats.map_reader`:
1. Check first 2 bytes for gzip header (`1F 8B`); if present, decompress in-memory; otherwise treat as raw stream.
2. Validate version (`19`, `20` or `21`) and signature string `AMB_MAP`.
3. Support dynamic dimension bounds (extracted from the companion `.txt` mission file) up to the maximum 130 columns $\times$ 100 rows $\times$ 7 layers. The declared $W \times H$ area is centered inside the stored grid; cells keep absolute grid coordinates.
4. Emit diagnostic logs documenting all discovered header fields for reverse-engineering validation.

### Alternatives Considered
- Hardcoding static gzip-only: Rejected because modded or extracted maps might already be decompressed.
- Assuming fixed 100x100 bounds: Rejected because engine accommodates 20x20 up to 130x100.

> **Correction (2026-10-11)**: The header was first measured as 187 bytes. Recounting the read calls of `sub_445F25` gives 193 bytes; the 6-byte error scrambled every cell field and led to several wrong intermediate theories. See `REVERSE_ENGINEERING_INFO.md` §2.2 and §3.8.

---

## 3. Tile Structure & Bitfield Decoding

### Empirical Findings
In decompiled `SAW_TD_NOTES.c` (`sub_445F25`, `sub_4508F9` and `sub_451610`):
- Each cell contains 13 bytes:
  - Word 0 (2 bytes): Floor / Ground surface.
  - Word 1 (2 bytes): Left wall.
  - Word 2 (2 bytes): Right wall.
  - Word 3 (2 bytes): Clutter / Object / Cover.
  - Byte 4 (1 byte): Unknown attribute (`0xFF` / `0x00`).
  - Dword 5 (4 bytes): Flags; bits 18–20 hold the floor cover level.
- In `sub_4508F9`, component words are unpacked and passed to `sub_451610` as follows:
  - **Presence / Visibility**: `(word >> 15) & 1` (bit 15 set = active component).
  - **Sprite Frame Index**: `(word >> 7) & 0xFF` (bits 7–14 point to the frame in the referenced `.obj` file).
  - **Object Group Index**: `word & 0x7F` (bits 0–6 index the flat registry built from the active `.set` file).
- A floor is drawn only while its cover level is greater than the active view level.

### Decision
Implement `CellComponent` and `MapCell` data structures in `saw_map.maps.model`:
- Parse each 16-bit component word using `(word >> 15) & 1` (presence), `(word >> 7) & 0xFF` (frame), and `word & 0x7F` (group).
- Maintain clean representation of all four components per coordinate: `floor`, `left_wall`, `right_wall`, `clutter`.
- Resolve every group index through the flat registry (`.set` entries in file order, then the built-in archives `Cgendam`, `Can`, `Token`, `People`, `Turret`).
- A non-zero word with bit 15 cleared is normal (`0x0001` is the usual absent left wall) and is treated as absent.

---

## 4. Companion `.set` Files & Asset Association

### Empirical Findings
- In `Research/SSI/Soldiers at War/Sets/Airfield.set`:
  ```text
  Defs
  13 12 12 28
  sgrass
  shill
  ...
  lwood1
  ...
  rwood1
  ...
  snwtree1
  ```
- The count line contains 4 counts: Surfaces (13), Left walls (12), Right walls (12), Clutter (28). It may carry a trailing `#` comment (`Messina.set`).
- The set belonging to a map is named by the 128-byte string in the map header.
- Each name corresponds directly to an `.obj` archive in `Research/SSI/Soldiers at War/Obj/<name>.obj`.
- Category prefixes:
  - `s*` = Ground Surface / Floor.
  - `l*` = Left Wall.
  - `r*` = Right Wall.
  - `c*` / Named items = Clutter / Cover / Vehicles / Trees.

### Decision
Implement `TilesetParser` in `saw_map.formats.set_parser`:
1. Parse count header line to define partition offsets for the 4 component groups.
2. Resolve each identifier against the `Obj/` directory.
3. If an `.obj` file is missing, instantiate a placeholder sprite with distinctive diagnostic markings.

---

## 5. Sprite Format (`.obj`/`.spr`) & Palette Decoding

### Empirical Findings
- Reconstructed from `Research/sprite-view.py` and `Research/SaWFontReader/main.cpp`:
  - **Archive Header** (32 bytes):
    - `sprite_count` (uint32)
    - `index_table_offset` (uint32)
    - `index_table_size` (uint32)
    - `sprite_array_offset` (uint32)
    - `sprite_array_size` (uint32)
    - 12 reserved padding bytes
  - **Index Table**: Array of entries with `relative_offset` (uint32) and `byte_size` (uint32).
  - **Sprite Header** (24 bytes):
    - `offset_x` (uint16), `offset_y` (uint16), `width` (uint16), `height` (uint16), `unk0` (uint16), `unk1` (uint16), `data_size` (uint32), 8 bytes padding.
  - **RLE Data**:
    - `0x00`: End of scanline.
    - `0x80`: Transparent pixel run; next byte is skip length.
    - `cmd & 0x80`: Literal pixel run; copy `cmd & 0x7F` bytes.
    - `cmd < 0x80`: Repeated pixel run; repeat next byte `cmd` times.
- Palettes:
  - Autodesk COL/PAL format (`Win.pal`, `Darkpal.col` = 776 bytes: 8-byte header + 256 $\times$ 3 RGB bytes).
  - Values map 8-bit palette indices to 24-bit RGB, combined with RLE alpha (0 = transparent, 255 = opaque).

### Decision
Implement `SpriteReader` in `saw_map.formats.sprite_reader` and `PaletteReader` in `saw_map.formats.palette_reader`:
- Parse archives into pure RGBA Pillow images (`PIL.Image`).
- Support palette swapping at runtime (e.g. `Win.pal` $\leftrightarrow$ `Darkpal.col`) without re-decoding RLE geometry.
- Cache decoded RGBA images to prevent redundant decoding during viewport rendering.

---

## 6. Isometric Projection & Coordinate Geometry

### Mathematical Model
In Soldiers at War, the grid uses a diamond dimetric isometric orientation:
- Standard Tile Dimensions: Width $T_w = 128$ pixels, Height $T_h = 64$ pixels (2:1 aspect ratio).
- Elevation step: Vertical displacement $E_{step} = 48$ pixels per layer $Z$.
- Sprite frames are anchored relative to the reference point $(209, 322)$ stored in their headers.
- **World to Screen**:
  $$X_{screen} = (X - Y) \times \frac{T_w}{2}$$
  $$Y_{screen} = (X + Y) \times \frac{T_h}{2} - Z \times E_{step}$$
- **Screen to World (Inverse)**:
  For a given elevation plane $Z$, let $Y'_{screen} = Y_{screen} + Z \times E_{step}$:
  $$X = \frac{X_{screen} / (T_w / 2) + Y'_{screen} / (T_h / 2)}{2}$$
  $$Y = \frac{Y'_{screen} / (T_h / 2) - X_{screen} / (T_w / 2)}{2}$$

### Decision
Implement `IsometricTransform` in `saw_map.geometry.transform`:
- Independent of UI rendering.
- Includes forward transformation (`world_to_screen`), inverse transformation (`screen_to_world`), and tile bounding box tests.
- 100% unit-tested with synthetic coordinate fixtures.

---

## 7. Draw Ordering & Depth Sorting

### Problem
In isometric projections, rendering back-to-front prevents visual artifacts:
- Lower elevation layers must be drawn before higher elevation layers.
- Within the same elevation layer, tiles further back (smaller $X + Y$) must be drawn before tiles closer to the camera (larger $X + Y$).
- Within a single cell, Ground Floor must render before Left Wall, Left Wall before Right Wall, and Walls before Clutter/Objects.

### Decision
Implement `DrawOrderStrategy` in `saw_map.rendering.draw_order`:
- Sort key: `(layer_z, x + y, component_priority, y)`
  - `component_priority`: Floor (0) $\rightarrow$ Left Wall (1) $\rightarrow$ Right Wall (2) $\rightarrow$ Clutter (3).
- Supports filtering: skip any layer above `max_visible_layer` or any disabled component category.
- Applies the engine's floor cover rule: a floor whose cover level is $\le$ the visible level is skipped (not applied in single-layer isolation).
