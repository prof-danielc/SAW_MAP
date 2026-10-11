# Soldiers at War File Format Specifications & Reverse-Engineering Findings

**Author**: Soldiers at War Map Visualizer Project  
**Date**: October 2026  
**Status**: Confirmed & Empirically Verified  

This document details the reverse-engineered binary container layouts, data structures, and mathematical transformations for *Soldiers at War* (SSI, 1998).

---

## 1. Binary Map Container (`.map`)

### 1.1 Container & Compression
Maps are stored in gzip-compressed files or uncompressed binary streams.
- **Magic Bytes**: `1F 8B 08` indicates gzip compression.
- **Decompressed Size**: Approximately 1.2 MB (e.g., `1,214,559` bytes for `Airfield.map`).

### 1.2 Header Layout (187 Bytes)

| Offset | Type | Field | Description |
|---|---|---|---|
| `0x00` | `uint16` | `version` | Engine version (`20` or `21`). |
| `0x02` | `char[8]` | `signature` | Null-terminated string `AMB_MAP\0`. |
| `0x0A` | `char[128]`| `title` | Null-terminated mission title string (e.g. `"Airfield"`). |
| `0x8A` | `uint8[49]`| `header_params` | View bounding flags, camera start coordinates, and mission state parameters. |

### 1.3 3D Tile Array (Offset `0xBB` / 187 Bytes)
The tile array comprises 7 vertical elevation layers ($Z = 0 \dots 6$), 100 rows ($Y = 0 \dots 99$), and 130 columns ($X = 0 \dots 129$).
- **Total Array Size**: $7 \times 100 \times 130 \times 13 = 1,183,000$ bytes.
- **Cell Stride**: 13 bytes per cell.
- **Cell Index Calculation**:  
  $$\text{cell\_index} = (Z \times 100 \times 130) + (Y \times 130) + X$$
- **Byte Offset in Stream**:  
  $$\text{offset} = 187 + (\text{cell\_index} \times 13)$$

### 1.4 Cell Component Bitmask (13 Bytes)
Each 13-byte cell consists of:
- `uint16 word0`: Floor / Terrain component
- `uint16 word1`: Left Wall component
- `uint16 word2`: Right Wall component
- `uint16 word3`: Clutter / Object / Cover component
- `uint8  byte4`: Elevation attribute byte ($0 \dots 255$)
- `uint32 dword5`: Occlusion and visibility bitflags

For each 16-bit component word:
- **Bit 15 (MSB)**: Presence flag (`(word >> 15) & 1`). $1 = \text{present}$, $0 = \text{empty}$.
- **Bits 7–14**: Tileset group index (`(word >> 7) & 0xFF`), indexing into the companion `.set` category.
- **Bits 0–6**: Sprite frame index (`word & 0x7F`), indexing into the target `.obj` archive.

---

## 2. Tileset Definitions (`.set`)

Companion `.set` files reside in `Sets/<name>.set` and are plain ASCII/Latin-1 text files.

### 2.1 Partition Counts Header
The file contains an integer count line with 4 space-delimited numbers:
```text
<num_surfaces> <num_left_walls> <num_right_walls> <num_clutter>
```
Example (`Airfield.set`):
```text
13 12 12 28
```

### 2.2 Asset Name Partitioning
Following the header line, the asset names are sequentially assigned:
1. `num_surfaces` names $\rightarrow$ Ground surfaces (`s*`), mapped to `word0`.
2. `num_left_walls` names $\rightarrow$ Left walls (`l*`), mapped to `word1`.
3. `num_right_walls` names $\rightarrow$ Right walls (`r*`), mapped to `word2`.
4. `num_clutter` names $\rightarrow$ Clutter/trees/objects (`c*`), mapped to `word3`.

Each entry directly corresponds to an archive in `Obj/<name>.obj`.

---

## 3. Sprite Archives (`.obj` / `.spr`)

Sprite archives store collections of indexed pixel frames with scanline RLE compression.

### 3.1 Archive Header (32 Bytes)
- `uint32 sprite_count`: Number of sprite frames.
- `uint32 index_table_offset`: Byte offset from file start to index table.
- `uint32 index_table_size`: Byte size of index table.
- `uint32 sprite_array_offset`: Byte offset to sprite payload array.
- `uint32 sprite_array_size`: Byte size of sprite payload array.
- `uint8[12] reserved`: Alignment padding.

### 3.2 Index Table Entries (8 Bytes each)
- `uint32 relative_offset`: Byte offset relative to `sprite_array_offset`.
- `uint32 sprite_byte_size`: Total byte size of sprite header and RLE payload.

### 3.3 Sprite Frame Header (24 Bytes)
- `uint16 offset_x`: Anchor X offset.
- `uint16 offset_y`: Anchor Y offset.
- `uint16 width`: Frame width in pixels.
- `uint16 height`: Frame height in pixels.
- `uint16 unk0`: Compression / rendering flag.
- `uint16 unk1`: Attribute flags.
- `uint32 data_size`: Byte length of RLE stream.
- `uint8[8] padding`: Reserved.

### 3.4 Scanline RLE Stream Decoding
For each row $h = 0 \dots \text{height} - 1$:
Read command byte `cmd`:
- `cmd == 0x00`: **End of Scanline**. Advance to next row.
- `cmd == 0x80`: **Transparent Pixel Run**. Next byte is `length`. Advance write pointer by `length` pixels with alpha = 0.
- `cmd & 0x80`: **Literal Copy Run**. `length = cmd & 0x7F`. Copy next `length` bytes directly to pixel buffer; set alpha = 255.
- `cmd < 0x80`: **Repeated Byte Run**. `length = cmd`. Read next 1 byte `val`; repeat `val` for `length` pixels; set alpha = 255.

---

## 4. Color Palettes (`.pal` / `.col`)

Palettes reside in `Misc/` (e.g., `Win.pal`, `Darkpal.col`).
- **Format**: Autodesk Animator 256-color palette.
- **File Size**: Exactly 776 bytes.
- **Header (8 Bytes)**:
  - `uint32 file_size`: `776` (`0x00000308`)
  - `uint16 format_major`: `0xB123`
  - `uint16 format_minor`: `0`
- **Payload (768 Bytes)**: 256 RGB tuples, each color consisting of 3 unsigned 8-bit bytes ($0 \dots 255$).

---

## 5. Dimetric Isometric Projection & Geometry

- **Aspect Ratio**: 2:1 dimetric isometric diamond projection.
- **Tile Dimensions**: $T_w = 64$ px, $T_h = 32$ px.
- **Elevation Displacement**: $E_{step} = 16$ px per elevation level $Z$.

### 5.1 World to Screen Transformation
$$X_{screen} = (X - Y) \times \frac{T_w}{2}$$
$$Y_{screen} = (X + Y) \times \frac{T_h}{2} - Z \times E_{step}$$

### 5.2 Screen to World Transformation (Inverse)
Let $Y'_{screen} = Y_{screen} + Z \times E_{step}$:
$$X = \frac{X_{screen} / (T_w / 2) + Y'_{screen} / (T_h / 2)}{2}$$
$$Y = \frac{Y'_{screen} / (T_h / 2) - X_{screen} / (T_w / 2)}{2}$$

### 5.3 Depth Sorting Strategy
Back-to-front rendering sort key:
$$\text{sort\_key} = (Z, X + Y, \text{component\_type}, Y)$$
Component priorities:
1. Floor (`0`)
2. Left Wall (`1`)
3. Right Wall (`2`)
4. Clutter (`3`)
