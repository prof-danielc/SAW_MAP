# Soldiers at War (1998) Reverse-Engineering Knowledge Base

**Document File**: `REVERSE_ENGINEERING_INFO.md`  
**Repository**: Soldiers at War Map Visualizer  
**Status**: Living Document — Continuously Maintained  
**Last Updated**: October 2026 (Project v1.3.0)  

---

## 1. Engine & Game Background

*Soldiers at War* (published by Strategic Simulations, Inc. / SSI in 1998, developed by Random Games) is a turn-based tactical WW2 wargame utilizing a 2:1 dimetric isometric rendering engine.

### Engine Lineage
The underlying engine is known in reverse-engineering communities as the **Lupine / Ordoor Engine**. Four commercial games are known to share this exact engine and file format family:
1. **Wages of War: The Business of Battle** (1996)
2. **Soldiers at War** (1998)
3. **Warhammer 40,000: Chaos Gate** (1998, SSI / Random Games)
4. **Avalon Hill's Squad Leader** (2000, Hasbro / Random Games)

### Source Materials & Disassembly Reference
Findings documented here are reconstructed from:
- **x86 Decompiled Disassembly**: Hex-Rays / IDA Pro reconstruction (`SAW_TD_NOTES.c` from game executable `SAW.EXE`, ~152,700 lines of C disassembly).
- **Direct Asset Inspection**: Binary analysis of original game files in `Research/SSI/Soldiers at War/`.
- **Pre-existing Community Scripts**: `Research/sprite-view.py` and `Research/SaWFontReader/main.cpp`.

---

## 2. Binary Map Container (`.map`)

### 2.1 Compression & Stream Encapsulation
Maps are stored on disk either compressed with standard Gzip or as uncompressed raw binary streams.
- **Magic Bytes**: `1F 8B 08 00` indicates a Gzip stream.
- **Decompressed Size**: Approximately 1.2 MB (e.g., `1,214,559` bytes for `Airfield.map`).
- **Detection Logic**:
  If the first 2 bytes equal `0x1F 0x8B`, decompress via standard gzip (RFC 1952); otherwise, read stream directly.

### 2.2 Map Header (187 Bytes / Offset `0x00` – `0xBB`)
The decompressed map starts with an 187-byte header:

| Offset | Size (Bytes) | Type | Field Name | Description |
|---|---|---|---|---|
| `0x00` | 2 | `uint16` (LE) | `version` | Engine version: `20` or `21`. Checked in `sub_78925` / `sub_445F25` / `sub_4471BC`. |
| `0x02` | 8 | `char[8]` | `signature` | Null-terminated ASCII identifier: `"AMB_MAP\0"`. |
| `0x0A` | 128 | `char[128]` | `title` | Null-terminated mission title string (e.g., `"Airfield"`, stored in global `byte_554EE0`). |
| `0x8A` | 49 | `uint8[49]` | `header_params` | Camera start coords, elevation bounds, viewport flags, and mission state parameters. |

#### Detailed 49-Byte Header Parameter Breakdown (`0x8A` – `0xBB`)
As seen in `sub_445F25`:
- `0x8A` (2B): `word_8AECB0` (initial view coordinate X)
- `0x8C` (2B): `word_8AECB2` (initial view coordinate Y)
- `0x8E` (2B): `word_8AECB4`
- `0x90` (2B): `word_8AECB6`
- `0x92` (2B): `word_8AECB8`
- `0x94` (4B): `dword_8AECBC` (bounding flags)
- `0x98` (4B): `dword_8AECC0`
- `0x9C` (2B $\times$ 6 = 12B): `word_8AECC4` .. `word_8AECCE`
- `0xA8` (1B): `byte_8AECD0`
- `0xA9` (2B $\times$ 2 = 4B): `word_8AECD2`, `word_8AECD4`
- `0xAD` (4B $\times$ 2 = 8B): `dword_8AECF0`, `dword_8AECF4`
- `0xB5` (1B): `byte_8AECF8` (grid overlay / visual debug flag)
- `0xB6` (2B): `word_8AED06` (active elevation layer clamp)
- `0xB8` (2B): `word_555FE0` (rendering and visibility mask)
- `0xBA` (1B): `byte_543E68`

---

## 3. 3D Tile Array & Cell Structure

### 3.1 Dimensions & Offsets
Immediately following the 187-byte header (at byte offset `187` / `0xBB`):
- **Elevation Layers ($Z$)**: Exactly 7 layers ($Z = 0 \dots 6$).
- **Grid Rows ($Y$)**: Exactly 100 rows ($Y = 0 \dots 99$).
- **Grid Columns ($X$)**: Exactly 130 columns ($X = 0 \dots 129$).
- **Total Cell Allocation**: $7 \times 100 \times 130 = 91,000$ cells.
- **Cell Stride**: 13 bytes per cell.
- **Total Tile Array Byte Size**: $91,000 \times 13 = 1,183,000$ bytes.
- **Array Byte Range**: `187` through `1,183,186` (ends at `0x120E32`).

#### Cell Offset Index Formula
$$\text{cell\_index} = (Z \times 100 \times 130) + (Y \times 130) + X$$
$$\text{byte\_offset} = 187 + (\text{cell\_index} \times 13)$$

### 3.2 13-Byte Cell Layout

| Relative Offset | Type | Field | Description |
|---|---|---|---|
| `+0` | `uint16` (LE) | `word0` | Floor / Ground Surface component |
| `+2` | `uint16` (LE) | `word1` | Left Wall component |
| `+4` | `uint16` (LE) | `word2` | Right Wall component |
| `+6` | `uint16` (LE) | `word3` | Clutter / Object / Foliage / Vehicle component |
| `+8` | `uint8` | `byte4` | Elevation attribute / terrain type ($0 \dots 255$) |
| `+9` | `uint32` (LE) | `dword5` | Visibility, occlusion, line-of-sight bitflags |

### 3.3 16-Bit Component Word Bitmask Decoding
Empirically confirmed from decompiled drawing routines `sub_451610`, `sub_4508F9`, and `sub_4447D5`:

```
Bit 15 (MSB)        Bits 14 .. 7                Bits 6 .. 0 (LSB)
+-------------------+---------------------------+---------------------------+
|   Presence Flag   |    Tileset Group Index    |    Sprite Frame Index     |
|   (1 = Present)   |       (0 .. 255)          |        (0 .. 127)         |
+-------------------+---------------------------+---------------------------+
```

- **Bit 15 (Presence Flag)**:
  $$\text{is\_present} = (\text{word} \gg 15) \ \& \ 1$$
  - `1`: Component exists and must be rendered.
  - `0`: Component is absent/empty.
- **Bits 7–14 (Tileset Group Index)**:
  $$\text{tileset\_group\_index} = (\text{word} \gg 7) \ \& \ 0\text{xFF}$$
  Indexes into the partitioned asset list defined in the companion `.set` file.
- **Bits 0–6 (Sprite Frame Index)**:
  $$\text{sprite\_frame\_index} = \text{word} \ \& \ 0\text{x}7\text{F}$$
  Indexes into the sprite frames contained inside the resolved `.obj` archive.

---

## 4. Companion Mission Text Files (`.txt`)

Every `.map` is paired with an ASCII `.txt` file of the same name (e.g. `Single_g/Airfield.txt`).  
This file is read by `sub_451B7D` in `SAW_TD_NOTES.c`:

### Structure
1. **Lines 1–40**: 40 lines of mission briefings and diary strings.
2. **Lines 41–42**: Mission objectives summary text.
3. **Lines 43–46**: 4 lines formatted `<index> : <status>` (e.g., `1 : 0`, `2 : 0` representing objectives).
4. **Line 47**: Active map grid width (e.g. `104` for `Airfield`).
5. **Line 48**: Active map grid height (e.g. `80` for `Airfield`).
6. **Line 49**: Mission seed / parameter integer (e.g. `15839`).

> [!NOTE]
> While the binary `.map` buffer always allocates the maximum $130 \times 100 \times 7$ grid, the game engine clamps the playable and scrollable bounds to the dimensions specified in the `.txt` file.

---

## 5. Companion Tileset Definitions (`.set`)

Located in `Sets/<name>.set` (e.g., `Sets/Airfield.set`), these are plain-text ASCII files that bind numerical tileset indices to sprite archives in `Obj/`.

### 5.1 Partition Count Header Line
Line 5 (ignoring comments/empty lines) specifies 4 integer counts:
```text
<num_surfaces> <num_left_walls> <num_right_walls> <num_clutter>
```
*Example (`Airfield.set`)*:
```text
Defs
13 12 12 28
```

### 5.2 Sequential Category Partitioning
Following the header count line, asset names are assigned strictly in sequence:
1. First `num_surfaces` names $\rightarrow$ Ground surfaces (`s*`, mapped to `word0`).
2. Next `num_left_walls` names $\rightarrow$ Left walls (`l*`, mapped to `word1`).
3. Next `num_right_walls` names $\rightarrow$ Right walls (`r*`, mapped to `word2`).
4. Remaining `num_clutter` names $\rightarrow$ Clutter and objects (`c*` or named objects, mapped to `word3`).

Each name resolves to `Obj/<name>.obj` (case-insensitive on Windows).

---

## 6. Sprite Archives (`.obj` / `.spr`)

Sprite archives store multiple indexed sprite frames compressed with scanline-based RLE.

### 6.1 Archive File Header (32 Bytes)
- `0x00` (4B, `uint32`): `sprite_count` (total number of frames)
- `0x04` (4B, `uint32`): `index_table_offset` (absolute byte offset from file start)
- `0x08` (4B, `uint32`): `index_table_byte_size` (`sprite_count * 8`)
- `0x0C` (4B, `uint32`): `sprite_array_offset` (absolute byte offset to frame payload start)
- `0x10` (4B, `uint32`): `sprite_array_byte_size` (total byte length of all frames)
- `0x14` (12B): Reserved zero padding (32-byte header alignment)

### 6.2 Index Table Entry (8 Bytes each)
- `0x00` (4B, `uint32`): `relative_offset` (relative to `sprite_array_offset`)
- `0x04` (4B, `uint32`): `sprite_byte_size` (total size of 24B frame header + compressed payload)

### 6.3 Sprite Frame Header (24 Bytes)
- `0x00` (2B, `uint16`): `offset_x` (anchor X offset relative to tile diamond top)
- `0x02` (2B, `uint16`): `offset_y` (anchor Y offset relative to tile diamond top)
- `0x04` (2B, `uint16`): `width` (frame width in pixels)
- `0x06` (2B, `uint16`): `height` (frame height in pixels)
- `0x08` (2B, `uint16`): `unk0` (compression mode / format identifier)
- `0x0A` (2B, `uint16`): `unk1` (attribute flags)
- `0x0C` (4B, `uint32`): `data_size` (byte length of compressed RLE payload)
- `0x10` (8B): Reserved padding

### 6.4 Scanline RLE Stream Decoding
Decoded row-by-row for $h = 0 \dots \text{height} - 1$:
Read command byte `cmd`:
- **`cmd == 0x00`**: **End of Scanline**. Advance to next row.
- **`cmd == 0x80`**: **Transparent Skip Run**. Read next byte `length`. Advance write pointer by `length` pixels with $\text{alpha} = 0$.
- **`cmd & 0x80` (`cmd >= 0x81`)**: **Literal Copy Run**. Read `length = cmd & 0x7F`. Copy next `length` bytes directly to pixel buffer; set $\text{alpha} = 255$.
- **`cmd < 0x80`**: **Repeated Byte Run**. `length = cmd`. Read next 1 byte `val`; repeat `val` for `length` pixels; set $\text{alpha} = 255$.

---

## 7. Color Palettes (`.pal` / `.col`)

Primary palettes are `Misc/Win.pal` and `Pic/DARKPAL.COL`.
- **Format**: Autodesk Animator 256-color palette (COL / PAL format).
- **Exact File Size**: 776 bytes.
- **8-Byte Header**:
  - `0x00` (4B, `uint32`): `file_size` = `776` (`0x00000308`)
  - `0x04` (2B, `uint16`): `format_major` = `0xB123`
  - `0x06` (2B, `uint16`): `format_minor` = `0`
- **768-Byte Payload**:
  256 consecutive 3-byte RGB tuples ($R, G, B \in [0, 255]$).

---

## 8. Dimetric Isometric Geometry & Projection

*Soldiers at War* utilizes a classic 2:1 dimetric isometric diamond projection.

### 8.1 Spatial Constants
- **Tile Diamond Width ($T_w$)**: 64 pixels
- **Tile Diamond Height ($T_h$)**: 32 pixels
- **Elevation Displacement ($E_{step}$)**: 16 pixels per elevation layer $Z$ (defined as `word_543F0C` in `sub_4508F9`).

### 8.2 Forward Transformation (World to Screen)
Given grid coordinates $(X, Y)$ and elevation layer $Z$:
$$X_{screen} = (X - Y) \times \frac{T_w}{2} = (X - Y) \times 32$$
$$Y_{screen} = (X + Y) \times \frac{T_h}{2} - Z \times E_{step} = (X + Y) \times 16 - Z \times 16$$

### 8.3 Inverse Transformation (Screen to World / Mouse Picking)
Given screen coordinates $(X_{screen}, Y_{screen})$ on elevation plane $Z$:
$$Y'_{screen} = Y_{screen} + Z \times 16$$
$$X = \frac{X_{screen} / 32 + Y'_{screen} / 16}{2}$$
$$Y = \frac{Y'_{screen} / 16 - X_{screen} / 32}{2}$$

Integer grid coordinates are obtained via floor: $\lfloor X \rfloor, \lfloor Y \rfloor$.

### 8.4 Depth Sorting & Render Order
To guarantee correct visual occlusion without a depth buffer, sprites must be rendered in strict back-to-front order using a 4-tuple composite key:
$$\text{sort\_key} = (Z, X + Y, \text{component\_priority}, Y)$$

Component draw priority within a cell:
1. `0` = Floor / Ground Surface (`word0`)
2. `1` = Left Wall (`word1`)
3. `2` = Right Wall (`word2`)
4. `3` = Clutter / Objects / Foliage (`word3`)

---

## 9. Post-Tile Array Records in Map Stream

Immediately following the 1,183,000-byte tile array (offset `1,183,187` / `0x120E33`), `sub_445F25` unpacks mission state structures:

| Table | Count | Record Size | Total Size | Global Array | Hypothesized Purpose |
|---|---|---|---|---|---|
| Canisters / Containers | 40 | 18 bytes | 720 bytes | `dword_554A80` | Ammo boxes, item crates, ground pickups |
| Interactive Objects | 40 | 6 bytes | 240 bytes | `dword_559230` | Doors, levers, explosive barrels |
| Triggers / Zones | 40 | 14 bytes | 560 bytes | `dword_554F60` | Extraction areas, reinforcement triggers |
| Waypoints / Squad Nodes | 10 | 340 bytes | 3,400 bytes | `word_550538` | AI patrol paths and squad waypoint lists |
| Soldier / Unit Records | 40 | 1,760 bytes | 70,400 bytes | `unk_847E50` | Placed soldiers, equipment, health, stats |
| AI Nodes | 40 | 18 bytes | 720 bytes | `word_883800` | Tactical navigation graph nodes |
| Mission Parameters | — | ~4,000 bytes | ~4,000 bytes | `word_884750` | Victory condition rules, faction alignments |

---

## 10. Open Research Questions & Future Reverse-Engineering Targets

1. **Cell Flag Bits (`dword5`)**:
   Exact bitmask mapping for line-of-sight obstruction, movement penalties, and dynamic lighting/shadowing flags stored in `dword5`.
2. **Soldier Entity Schemas (`unk_847E50`)**:
   Detailed field layout for the 1,760-byte soldier placement record, including soldier nationality, starting inventory, and initial facing direction.
3. **Sound & Ambience Triggers**:
   Mapping of sound effect identifiers triggered by ambient clutter objects and door interactions.
4. **Mini-map Format (`minimap.col` / `Data/minimap.col`)**:
   Decompression and packing of pre-baked minimap overhead thumbnails.
