# Soldiers at War File Format Specifications

**Author**: Soldiers at War Map Visualizer Project  
**Date**: 2026-10-11  
**Status**: Summary of confirmed formats. The evidence, decompilation references, and open
questions live in [`REVERSE_ENGINEERING_INFO.md`](../REVERSE_ENGINEERING_INFO.md), which is the
canonical knowledge base.

This document summarizes the binary container layouts, data structures, and mathematical
transformations for *Soldiers at War* (SSI, 1998) as implemented by this project.

---

## 1. Binary Map Container (`.map`)

### 1.1 Container & Compression
Maps are stored in gzip-compressed files or uncompressed binary streams.
- **Magic Bytes**: `1F 8B 08` indicates gzip compression.
- **Decompressed Size**: `1,214,559` bytes for version 21 maps, `1,214,539` bytes for the
  version 19 `Menu/Demo.MAP`.

### 1.2 Header Layout (193 Bytes)

| Offset | Type | Field | Description |
|---|---|---|---|
| `0x00` | `uint16` | `version` | Stream version (`19`, `20` or `21`). |
| `0x02` | `char[8]` | `signature` | Null-terminated string `AMB_MAP\0`. |
| `0x0A` | `char[128]`| `tileset_name` | Null-terminated name of the companion tileset (`Sets/<name>.set`), e.g. `"Airfield"`. |
| `0x8A` | `uint8[55]`| `editor_state` | Scenario Builder cursor, scroll, brush, and view state. |

### 1.3 3D Tile Array (Offset `0xC1` / 193 Bytes)
The tile array comprises 7 vertical elevation layers ($Z = 0 \dots 6$), 100 rows ($Y = 0 \dots 99$), and 130 columns ($X = 0 \dots 129$).
- **Total Array Size**: $7 \times 100 \times 130 \times 13 = 1,183,000$ bytes.
- **Cell Stride**: 13 bytes per cell.
- **Cell Index Calculation**:  
  $$\text{cell\_index} = (Z \times 100 \times 130) + (Y \times 130) + X$$
- **Byte Offset in Stream**:  
  $$\text{offset} = 193 + (\text{cell\_index} \times 13)$$

### 1.4 Cell Layout (13 Bytes)
Each 13-byte cell consists of:
- `uint16 word0`: Floor / ground surface component
- `uint16 word1`: Left wall component
- `uint16 word2`: Right wall component
- `uint16 word3`: Clutter / object component
- `uint8  byte4`: Unknown attribute (`0xFF` or `0x00`)
- `uint32 dword5`: Flags; bits 18–20 hold the floor cover level

For each 16-bit component word:
- **Bit 15 (MSB)**: Presence flag (`(word >> 15) & 1`). $1 = \text{present}$, $0 = \text{absent}$ (the low bits of an absent word are meaningless).
- **Bits 7–14**: Sprite frame index (`(word >> 7) & 0xFF`), indexing into the target `.obj` archive.
- **Bits 0–6**: Object group index (`word & 0x7F`), indexing into the flat tileset registry (section 2.3).

### 1.5 Floor Cover Level
The engine draws `word0` only while `(dword5 >> 18) & 7` is greater than the active view level
($0 \dots 6$). The value is `7` for floors that are never hidden and otherwise the level of the
floor that covers the cell from above.

### 1.6 Playable Window
The stream always holds the full $130 \times 100$ grid. The playable $W \times H$ area, with $W$
and $H$ taken from the last lines of the companion `.txt` mission file, is centered:
$$X_{min} = \lfloor (130 - W) / 2 \rfloor, \quad Y_{min} = \lfloor (100 - H) / 2 \rfloor$$
Cell coordinates remain absolute grid indices (as displayed by the Scenario Builder). Cells
outside the window hold default grass fill or stale leftovers and are not part of the map.

---

## 2. Tileset Definitions (`.set`)

Companion `.set` files reside in `Sets/<name>.set` and are plain ASCII/Latin-1 text files. The
set used by a map is named in the map header.

### 2.1 Partition Counts Header
After a description line and a `Defs` line, the file contains an integer count line with 4
space-delimited numbers, optionally followed by a `#` comment:
```text
<num_surfaces> <num_left_walls> <num_right_walls> <num_clutter>
```
Example (`Airfield.set`):
```text
13 12 12 28
```

### 2.2 Asset Name Partitioning
Following the count line, the asset names are sequentially assigned:
1. `num_surfaces` names $\rightarrow$ Ground surfaces (`s*`), referenced by `word0`.
2. `num_left_walls` names $\rightarrow$ Left walls (`l*`), referenced by `word1`.
3. `num_right_walls` names $\rightarrow$ Right walls (`r*`), referenced by `word2`.
4. `num_clutter` names $\rightarrow$ Clutter/trees/objects (`c*`), referenced by `word3`.

Each entry directly corresponds to an archive in `Obj/<name>.obj`.

### 2.3 Flat Registry
The engine loads all entries into one table in file order, so the group index of a component
word is the position of the name in the whole list (for `Airfield.set`: surfaces 0–12, left
walls 13–24, right walls 25–36, clutter 37–64). Five built-in archives follow the set entries:
`Cgendam`, `Can`, `Token`, `People`, `Turret`.

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
- `uint16 unk0`: Unknown.
- `uint16 unk1`: Unknown.
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

Primary palettes are `Misc/Win.pal` and `Pic/DARKPAL.COL`.
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
- **Tile Dimensions**: $T_w = 128$ px, $T_h = 64$ px.
- **Elevation Displacement**: $E_{step} = 48$ px per elevation level $Z$.
- **Sprite Anchor Reference**: $(209, 322)$; a frame is placed at
  $(X_{screen} - 64 + \text{offset\_x} - 209,\; Y_{screen} + \text{offset\_y} - 322)$.

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
1. Floor (`0`, `word0`)
2. Left Wall (`1`, `word1`)
3. Right Wall (`2`, `word2`)
4. Clutter (`3`, `word3`)
