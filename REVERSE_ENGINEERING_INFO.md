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

### 3.2 13-Byte Cell Layout & In-Memory Representation

In the raw binary map stream, each cell occupies exactly 13 bytes. When loaded into memory by routine `sub_41820` (lines 41826–41837 in `SAW_TD_NOTES.c`), the engine unpacks each cell into a 16-byte aligned in-memory record:

```c
// Decompiled from sub_41820 (SAW_TD_NOTES.c, lines 41826-41837):
for ( i = 0; i < 7; ++i ) {             // 7 Elevation Layers (Z)
  for ( j = 0; j < 100; ++j ) {         // 100 Rows (Y)
    for ( k = 0; k < 130; ++k ) {       // 130 Columns (X)
      // Read 8 bytes: 4 x 16-bit component words (offset +0, +2, +4, +6)
      sub_4060C6((int)(&word_559630[104000 * i] + 1040 * j + 8 * k), 8, file_ptr);
      // Read 1 byte: elevation attribute (offset +8)
      sub_4060C6((int)(&word_559630[104000 * i + 4] + 1040 * j + 8 * k), 1, file_ptr);
      // Read 4 bytes: flags DWORD (offset +12)
      sub_4060C6((int)(&word_559630[104000 * i + 6] + 1040 * j + 8 * k), 4, file_ptr);
    }
  }
}
```

#### Binary vs In-Memory Offset Mapping

| Stream Offset | In-Memory Offset | Type | Engine Symbol | Description |
|---|---|---|---|---|
| `+0` | `+0` | `uint16` (LE) | `word_559630` | `word0`: Ceiling / Roof / Upper Cut-Away component |
| `+2` | `+2` | `uint16` (LE) | `word_559632` | `word1`: Left Wall component |
| `+4` | `+4` | `uint16` (LE) | `word_559634` | `word2`: Right Wall component |
| `+6` | `+6` | `uint16` (LE) | `word_559636` | `word3`: Procedural Ground Surface component |
| `+8` | `+8` | `uint8` | `*(cell + 8)` | `byte4`: Terrain / elevation byte attribute |
| — | `+9 .. +11` | `uint8[3]` | — | 3-byte internal runtime padding (aligns flags to 4 bytes) |
| `+9` | `+12` | `uint32` (LE) | `dword_55963C` | `dword5`: Flags, roof elevation, visibility, LOS mask |

---

### 3.3 16-Bit Component Word Bitmask Decoding & Editor Packing

All 4 component words (`word0` .. `word3`) share an identical 16-bit bitfield layout:

```
Bit 15 (MSB)        Bits 14 .. 7                Bits 6 .. 0 (LSB)
+-------------------+---------------------------+---------------------------+
|   Presence Flag   |    Sprite Frame Index     |    Object Group Index     |
|   (1 = Present)   |        (0 .. 255)         |   (0 .. 127 in Registry)  |
+-------------------+---------------------------+---------------------------+
```

#### Extraction Bitwise Math:
- **Presence Flag** (Bit 15): `(raw_word >> 15) & 1` (`1 = Present`, `0 = Absent`)
- **Sprite Frame Index** (Bits 7..14): `(raw_word >> 7) & 0xFF` (Index within target `.obj` archive, $0 \dots 255$)
- **Object Group Index** (Bits 0..6): `raw_word & 0x7F` (Index into flat registry `dword_7C58B0`, $0 \dots 127$)

#### Direct Decompilation Proof 1: Rendering Routine `sub_4508F9`
At line 45087 of `SAW_TD_NOTES.c`:
```c
// Renders word0 if present and roof layer condition met:
sub_451610(*v15 & 0x7F, ((unsigned __int16)*v15 >> 7) & 0xFF, a2, v13);
```
And at lines 45164–45168 of `SAW_TD_NOTES.c`:
```c
if ( (*(_WORD *)(v14 + 2) >> 15) & 1 ) // Word 1 (Left wall)
  sub_451610(*(_WORD *)(v14 + 2) & 0x7F, (*(_WORD *)(v14 + 2) >> 7) & 0xFF, a2, v13);
if ( (*(_WORD *)(v14 + 4) >> 15) & 1 ) // Word 2 (Right wall)
  sub_451610(*(_WORD *)(v14 + 4) & 0x7F, (*(_WORD *)(v14 + 4) >> 7) & 0xFF, a2, v13);
if ( (*(_WORD *)(v14 + 6) >> 15) & 1 ) // Word 3 (Procedural Surface)
  sub_451610(*(_WORD *)(v14 + 6) & 0x7F, (*(_WORD *)(v14 + 6) >> 7) & 0xFF, a2, v13);
```
Where `sub_451610(a1, a2, a3, a4)` takes:
- Parameter `a1`: `*v & 0x7F` = Object registry index into `dword_7C58B0[a1]`.
- Parameter `a2`: `(*v >> 7) & 0xFF` = Sprite frame index within archive.
- Parameters `a3`, `a4`: Screen coordinate anchors $(X, Y)$.

#### Direct Decompilation Proof 2: Scenario Builder Editor Tile Packing `sub_40479`
At lines 40479–40487 of `SAW_TD_NOTES.c`, the map editor serializes a user-placed tile into cell memory:
```c
*(&word_559630[104000 * a3] + 1040 * a2 + 8 * a1 + word_6BCDB0) =
    ((unsigned __int8)word_8AECD6 << 7) | (byte_8AECD8 & 0x7F) | (word_8AECDC << 15);
```
- `word_6BCDB0`: Target word slot ($0 \dots 3$).
- `word_8AECD6`: Selected sprite frame index $\rightarrow$ shifted left by 7 (`<< 7`).
- `byte_8AECD8`: Selected object group index $\rightarrow$ masked with `0x7F` (`& 0x7F`).
- `word_8AECDC`: Component presence bit $\rightarrow$ shifted left by 15 (`<< 15`).

This confirms the bitfield formula with 100% mathematical certainty.

---

### 3.4 Flat Tileset Object Registry Architecture (`dword_7C58B0`)

In the game executable, tileset assets are NOT separated into isolated lists at runtime. Instead, `sub_41130` / `sub_41164` (lines 41157–41235 in `SAW_TD_NOTES.c`) loads all `.obj` files into a single, flat, 128-element pointer table `dword_7C58B0[128]`:

```c
// Decompiled from sub_41164 (SAW_TD_NOTES.c, lines 41157-41232):
sscanf(&v11, "%d %d %d %d", &word_543E9C, &word_543EA0, &word_543EA4, &word_543EA8);
v46 = word_543E9C + word_543EA0 + word_543EA4 + word_543EA8; // total .set files
for ( i = 0; v46 > i; ++i ) {
  sub_517F56(&obj_name); // Loads Obj/<name>.obj into dword_7C58B0[i]
}
// Append engine built-in global objects:
sub_517F56("Cgendam.obj"); // dword_7C58B0[v46 + 0]
sub_517F56("Can.obj");     // dword_7C58B0[v46 + 1]
sub_517F56("Token.obj");   // dword_7C58B0[v46 + 2]
sub_517F56("People.obj");  // dword_7C58B0[v46 + 3]
sub_517F56("Turret.obj");  // dword_7C58B0[v46 + 4]
```

#### Flat Registry Index Partitioning (`Airfield.set` Example)
- **Surfaces (`0 .. 12`, 13 objects)**: `sgrass`, `shill`, `ssnow1`, `sdirt`, `sstone1`, `sstone3`, `swood1`, `swood2`, `smetal1`, `strack2`, `sgen`, `sgen`, `sgen`.
- **Left Walls (`13 .. 24`, 12 objects)**: `lwood1`, `lmetal1`, `lmetal2`, `lmetal3`, `ldrtwall`, `lcave`, `lbeam2`, `lbarb`, `lrail2`, `lgen`, `lgen`, `lgen`.
- **Right Walls (`25 .. 36`, 12 objects)**: `rwood1`, `rmetal1`, `rmetal2`, `rmetal3`, `rdrtwall`, `rcave`, `rbeam2`, `rbarb`, `rrail2`, `rgen`, `rgen`, `rgen`.
- **Tileset Clutter (`37 .. 64`, 28 objects)**: `snwtree1`, `crock4`, `csnow1`, `ctran`, `ctran2`, `cwood1`, `cangle`, `cfurn2`, `cfurn3`, `cfiller`, `cfiller3`, `cwrhouse`, `cradio`, `ckitchn1`, `cbunks`, `carm`, `csandbag`, `cgun1`, `cgun2`, `cvehic1a`, `cvehic2`, `cplane1`, `cplane2`, `csnow2`, `sherman`, `hellcat`, `panzerIV`, `tiger`.
- **Global Engine Clutter (`65 .. 77`, 13 objects)**: `Cgendam`, `Can`, `Token`, `People`, `Turret`, `Specials`, `Newtree1` .. `Newtree7`.

Because `raw_word & 0x7F` indexes directly into `dword_7C58B0`, any component word can point to any object category in the flat registry.

---

### 3.5 Component Roles in the 13-Byte Grid Array

Binary inspection of all 91,000 cells in `Airfield.map` and decompiled drawing routines clarify the distinct role of each word slot:

1. **Procedural Ground Surface (`word3` / Offset `+6`)**:
   - In the binary map's 13-byte grid array, all procedural ground surface variations are stored in **`word3`**.
   - In `Airfield.map`, `word3` has 19,180 active surface cells across layer 0:
     - Group 0 (`sgrass` $\rightarrow$ rendered as winter snow `ssnow1`): flat snow variations (frames 0..10).
     - Group 2 (`ssnow1`): procedural snow ridges, transitions, and hill slopes.
     - Group 3 (`sdirt`), Group 4 (`sstone1` / hangar floor), Group 9 (`strack2` / railway).
2. **Ceiling / Roof / Cut-Away Mask (`word0` / Offset `+0`)**:
   - `word0` contains ceiling and roof components, rendered in `sub_4508F9` only when `((flags >> 18) & 7) > word_8AED06` (current elevation slicing layer).
   - At ground level (elevation 0), `word0` values like `0xFE00` and `0xFF93` carry frame numbers `254` and `255`, representing roof height boundaries rather than drawable sprites (`frame >= 200` are culled).
3. **Walls (`word1` & `word2` / Offsets `+2`, `+4`)**:
   - Bit 15 indicates wall presence (`1 = Present`, `0 = Absent`). Passability/LOS masks (e.g., `0x001F`) have Bit 15 = 0.
4. **Post-Grid Map Clutter**:
   - Editor-placed clutter objects (trees `snwtree1`, hangars, planes `cplane1`, vehicles, barbed wire fences `lbarb`/`rbarb`) are stored in the post-grid records following the $7 \times 100 \times 130 \times 13$ array.

---

### 3.6 Targeted Verification: Tile `(20, 18, 0)` on `Airfield.map`

The tile at grid coordinates $(X=20, Y=18, Z=0)$ in `Airfield.map` was examined in hex and compared with original SSI Scenario Builder editor screenshots:

#### 1. Binary Cell Bytes at Offset `187 + ((0 * 100 * 130) + (18 * 130) + 20) * 13 = 30,847`:
```text
Raw Bytes: 93 FF 00 00 1F 00 82 81 01 00 00 00 25
```
- `word0 = 0xFF93` (Roof/boundary attribute, frame 255, not rendered at layer 0)
- `word1 = 0x0000` (Left wall empty)
- `word2 = 0x001F` (Right wall empty; presence bit 15 is 0)
- `word3 = 0x8182` (Ground surface):
  - Binary: `1000 0001 1000 0010`
  - Presence (Bit 15): `1` (Present)
  - Group Index (Bits 0..6): `0x8182 & 0x7F = 2` $\rightarrow$ `Airfield.set` Surface 2 = **`ssnow1.obj`**
  - Frame Index (Bits 7..14): `(0x8182 >> 7) & 0xFF = 3` $\rightarrow$ **Sprite Frame 3**
- `byte4 = 0x01` (Elevation / terrain attribute)
- `dword5 = 0x25000000` (Flags)

#### 2. Visual Alignment with Editor Screenshots:
- In `Research/EditorScreenshots/airfield_tile_20_18_0_level_0.png`, the wireframe cursor box hovers over $(20, 18, 0)$ displaying snow with a small curved ridge at the bottom of the diamond.
- In `Research/EditorScreenshots/airfield_tile_20_18_0_level_0_tile_window.png`, the tile options window highlights this specific snow ridge tile.
- In `Research/EditorScreenshots/airfield_tile_20_18_0_level_0_tile.png`, the isolated sprite is an exact pixel-level match to Frame 3 of `ssnow1.obj` (`width=128, height=63, ox=209, oy=322`).

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
Empirically extracted from coordinate projection routine `sub_433F3A` and elevation drawing in `sub_4508F9`:
- **Tile Diamond Width ($T_w$)**: **128 pixels** (half-width `word_543F04 = 64`).
- **Tile Diamond Height ($T_h$)**: **64 pixels** (half-height `word_543F08 = 32`).
- **Elevation Displacement ($E_{step}$)**: **48 pixels** per elevation layer $Z$ (`word_543F0C = 48`).
- **Master Anchor Reference Origin**: **$(209, 322)$**. All sprite frames in `.obj` / `.spr` files record internal `offset_x` and `offset_y` coordinates relative to this master reference point (applied in `sub_451610`):
  $$\Delta X = \text{offset\_x} - 209$$
  $$\Delta Y = \text{offset\_y} - 322$$
  - Standard ground tiles have `offset_x = 209, offset_y = 322` ($\Delta X = 0, \Delta Y = 0$).
  - Vertical wall frames have `offset_y = 274` ($\Delta Y = -48$, positioning the wall exactly 48 pixels above the floor plane).
  - Trees, foliage, and clutter specify unique offsets (e.g. $\Delta X = +44, \Delta Y = -45$) ensuring trunks seat precisely at the diamond apex.

### 8.2 Forward Transformation (World to Screen)
Given grid coordinates $(X, Y)$ and elevation layer $Z$:
$$X_{screen} = (X - Y) \times \frac{T_w}{2} = (X - Y) \times 64$$
$$Y_{screen} = (X + Y) \times \frac{T_h}{2} - Z \times E_{step} = (X + Y) \times 32 - Z \times 48$$

In screen pixel space (top-left origin, Y down), the top apex of cell $(X, Y)$'s diamond is at $(X_{screen}, Y_{screen})$. The sprite's top-left bounding box is placed at:
$$P_X = X_{screen} - 64 + \Delta X$$
$$P_Y = Y_{screen} + \Delta Y$$

### 8.3 Inverse Transformation (Screen to World / Mouse Picking)
Given screen coordinates $(X_{screen}, Y_{screen})$ on elevation plane $Z$:
$$Y'_{screen} = Y_{screen} + Z \times 48$$
$$X = \frac{X_{screen} / 64 + Y'_{screen} / 32}{2}$$
$$Y = \frac{Y'_{screen} / 32 - X_{screen} / 64}{2}$$

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

## 10. Scenario Builder Editor Discoveries (`Research/EditorScreenshots`)

Direct verification against original SSI Scenario Builder editor screenshots (`SAW_TD.exe`):

### 10.1 Layer Slicing Visual Progression
- **Level 1 (`airfield_map_level_1.png` / Layer $Z=0$)**:
  - Displays the foundational ground plane: snow base (`ssnow1`), brown mud/dirt hex (`sdirt`), 4 grey tarmac hangar bases (`sstone1`), railway line (`strack2`), and wooden barracks floors (`swood1`).
  - Clutter objects on the ground include bare fuselages of the transport aircraft, supply crates, oil drums, light vehicles (`cvehic1a`), and boundary fences.
  - Editor status bar format: `Zoom: 1/10 | Res: 640x480 | Mode: Tile | Hug: Off | Level: 1 | <hover_x>,<hover_y>,<z> | 104x80x7`.
- **Level 2 (`airfield_map.png` / Layers $Z \le 1$)**:
  - Clutter components on layer $Z=1$ add the aircraft wings, propellers, and tail assemblies, fully assembling the 3 German transport aircraft (`cplane1` / `cplane2`).
  - Lower structural wall segments become visible.
- **Level 7 (`airfield_map_level_7.png` / Layers $Z \le 6$)**:
  - Full vaulted hangar roofs, pitched wooden barracks roofs, watchtowers, and train tunnel covers are rendered, showing the fully enclosed mission environment.

### 10.2 Global Engine Clutter Assets (`GLOBAL_CLUTTER`)
Decompiled routine `sub_443D4A` in `SAW_TD_NOTES.c` demonstrates that the engine appends built-in global `.obj` archives directly after the tileset's clutter partition:
- `+0`: `People.obj` (Soldiers placed on the map, 168 frames)
- `+1`: `Can.obj` (Ammo crates, supply canisters, and ground pickups, 64 frames)
- `+2`: `Turret.obj` (Anti-aircraft flak guns, machine gun nests, 320 frames)
- `+3`: `Token.obj` (Mission objective tokens, e.g. classified map item, 44 frames)
- `+4`: `Specials.obj` (Special interactive mission objects, 45 frames)
- `+5`: `Cgendam.obj` (Generic damage overlays, 8 frames)
- `+6 .. +12`: `Newtree1.obj` .. `Newtree7.obj` (Bare winter trees and deciduous foliage)

In `Airfield.map`, groups 28 (`People`), 29 (`Can`), 30 (`Turret`), 31 (`Token`), and 38..40 (`Newtree4`..`Newtree6`) represent placed soldier units, weapons, and winter trees.

### 10.3 Default Ground Surface & Winter Weather Substitution
- `0x0000`: Denotes empty/void cells outside playable boundary.
- `0xFF00`: Denotes default ground terrain (Surface index 0). In winter scenarios where `ssnow1` is present in the tileset definition and weather conditions specify snow (e.g. `Snow: 85`), Surface 0 (`sgrass`) is substituted with `ssnow1`.
- Non-zero words with high-byte `0xFF`: `surface_id = w & 0x7F`, variation bit `frame_id = (w >> 7) & 1`.

### 10.4 Minimap & Mission Meta-Properties
- **Minimap (`airfield_minimap.png`)**:
  - Direct 2D orthogonal projection of surface classes: snow (white/grey), dirt/trench (brown), structures (dark grey), void (black).
  - Red markers represent Axis units; green markers represent Allied deployment zone.
  - Active camera viewport represented as a dimetric frustum trapezoid outline.
- **Mission Setup (`airfield_setup.png`)**:
  - Start Time: `6:00 AM`. Weather: `Clear: 15%`, `Rain: 0%`, `Snow: 85%`.
  - Radio Support: Allied Air Support 100% (2 sorties).
- **Mission Completion (`airfield_ending.png`)**:
  - Victory Perspective: American.
  - Extraction rule: `Leave Map`.
  - Primary goal: `3. Target Get, One Goal Met, ITEM=Map Rad=0`.
- **Weapons Locker (`airfield_weapons_locker.png`)**:
  - Pre-mission Allied inventory: Colt M1911A1, OSS M1942, Thompson M1A1, M1 Carbine, M2 Carbine, M1 Garand, BAR A2, M9A1 Bazooka, satchel charges, rifle grenades, and combat knives.

### 10.5 Editor UI Layout & Status Bar Mechanics
- **Native Resolution**: Fixed 640x480 standard VGA raster.
- **Top Application Chrome**:
  - Menu Bar ($Y \in [0, 19]$): Classic Win32 menus (`File`, `Edit`, `Level`, `View`, `Tools`, `Help`).
  - Toolbar ($Y \in [20, 48]$): 24x24 icon tool strip (Tile selector, elevation picker, wall tools, object tools).
- **Bottom Status Bar ($Y \in [456, 475]$, height 20 px)**:
  - Standard three-pane status strip:
    - Pane 1 (Left): Zoom level, resolution, and current edit mode (`Zoom: 1/10 | Res: 640x480 | Mode: Tile | Hug: Off`).
    - Pane 2 (Center): Active elevation layer ($Z+1$) and cursor tile coordinate (`Level: 1 | 16,11,0`).
    - Pane 3 (Right): Dimension bounds (`104x80x7`).
- **Viewport Alignment & Scaling**:
  - When running in modern multi-resolution environments, HUD overlays require decoupled 1:1 screen projection cameras (`gui_camera`) to prevent OpenGL viewport clamping or letterbox drift when windows are resized, unmaximized, or maximized.

---

## 11. Open Research Questions & Future Reverse-Engineering Targets

1. **Cell Flag Bits (`dword5`)**:
   Exact bitmask mapping for line-of-sight obstruction, movement penalties, and dynamic lighting/shadowing flags stored in `dword5`.
2. **Soldier Entity Schemas (`unk_847E50`)**:
   Detailed field layout for the 1,760-byte soldier placement record, including soldier nationality, starting inventory, and initial facing direction.
3. **Sound & Ambience Triggers**:
   Mapping of sound effect identifiers triggered by ambient clutter objects and door interactions.
4. **Mini-map Format (`minimap.col` / `Data/minimap.col`)**:
   Decompression and packing of pre-baked minimap overhead thumbnails.

---

## 12. Decompiled Engine Routines & Global Variables Cross-Reference Table

All references refer to the decompiled `SAW.EXE` / `SAW_TD.EXE` disassembly (`Research/SSI/Soldiers at War/SAW_TD_NOTES.c`, 152,700 lines of C):

### 12.1 Key Functions

| Function Name | Line in `SAW_TD_NOTES.c` | Virtual Address | Role & Architectural Purpose |
|---|---|---|---|
| `sub_40479` | 40479 | `0x0040479` | **Editor Tile Serializer**: Packs user-selected frame (`<< 7`), group (`& 0x7F`), and presence (`<< 15`) into cell slot `word_6BCDB0`. |
| `sub_4060C6` | 41820 | `0x004060C6` | **File Reader**: Buffered binary `fread` wrapper reading `.map` container bytes into memory. |
| `sub_407256` | 45251 | `0x00407256` | **Sprite Blitter**: Performs transparent-keyed scanline blit of a decoded `.obj` frame into the DirectDraw backbuffer. |
| `sub_41130` | 41130 | `0x0041130` | **Tileset Loader**: Parses `.set` file counts, sequentially loads `.obj` archives into `dword_7C58B0`, and loads global engine clutter. |
| `sub_41820` | 41820 | `0x0041820` | **Map Reader**: Unpacks 187-byte header and 3D cell array ($7 \times 100 \times 130 \times 13$) into 16-byte memory records. |
| `sub_433F3A` | 41341 | `0x00433F3A` | **Isometric Projection**: Converts grid $(X, Y, Z)$ into 2D screen coordinates with $T_w=128, T_h=64, E_{step}=48$. |
| `sub_444AFF` | 41462 | `0x00444AFF` | **Frame Anchor X Getter**: Returns internal `offset_x` from sprite frame header: `**(_WORD **)(obj + 4 * frame)`. |
| `sub_444B29` | 41468 | `0x00444B29` | **Frame Anchor Y Getter**: Returns internal `offset_y` from sprite frame header: `*(_WORD *)(*(obj + 4 * frame) + 2)`. |
| `sub_444B54` | 41474 | `0x00444B54` | **Frame Anchor X Setter**: Overwrites internal `offset_x` anchor during runtime offset recalibration. |
| `sub_444B7D` | 41480 | `0x00444B7D` | **Frame Anchor Y Setter**: Overwrites internal `offset_y` anchor during runtime offset recalibration. |
| `sub_445F25` | 41880 | `0x00445F25` | **Post-Grid Reader**: Unpacks mission entities (doors, triggers, waypoints, units) located after the 1,183,000-byte tile array. |
| `sub_4508F9` | 45053 | `0x004508F9` | **Cell Render Dispatcher**: Evaluates elevation slicing, tests roof cut-away against `word_8AED06`, and issues drawing calls to `sub_451610`. |
| `sub_451610` | 45238 | `0x00451610` | **Draw Call Dispatcher**: Resolves `dword_7C58B0[a1]` by flat group index `a1 = W & 0x7F` and draws frame `a2 = (W >> 7) & 0xFF` at $(X + \Delta X, Y + \Delta Y)$. |
| `sub_451B7D` | 45280 | `0x00451B7D` | **Mission Text Parser**: Parses companion `.txt` file, extracting active grid width (line 47) and height (line 48). |
| `sub_517F56` | 142075 | `0x00517F56` | **Sprite Archive Decoder**: Parses `.obj` binary file, allocates frame offset table, decodes scanline RLE, and registers in `dword_7C58B0`. |
| `sub_521349` | 144947 | `0x00521349` | **Asset Association Parser**: Parses `.asn` files associating sprite objects with palette tables. |

### 12.2 Key Global Variables & Memory Structures

| Symbol | Address / Type | Description & Semantic Meaning |
|---|---|---|
| `dword_7C58B0[128]` | `int[128]` | **Flat Object Registry**: Contiguous table of pointers to loaded `.obj` sprite archives. Indexed by `W & 0x7F`. |
| `word_7A1916` | `uint16` | **Registry Object Count**: Number of `.obj` archives currently loaded into `dword_7C58B0` ($0 \dots 127$). |
| `word_559630[]` | `uint16[]` | **Cell Memory Buffer**: In-memory 3D cell array. Cell stride is 16 bytes (8 bytes words, 1 byte elevation, 3 bytes pad, 4 bytes flags). |
| `word_559632[]` | `uint16[]` | In-memory pointer to Word 1 (Left wall) within the cell array. |
| `word_559634[]` | `uint16[]` | In-memory pointer to Word 2 (Right wall) within the cell array. |
| `word_559636[]` | `uint16[]` | In-memory pointer to Word 3 (Procedural Ground Surface) within the cell array. |
| `dword_55963C[]` | `uint32[]` | In-memory pointer to DWORD 5 (Cell Flags / Roof Elevation / Visibility) within the cell array. |
| `word_8AED06` | `int16` | **Elevation Slicing Clamp**: Active maximum elevation layer ($0 \dots 6$, default 6). Cells with roof layer above this clamp have roofs drawn; below are cut away. |
| `word_6BCDB0` | `int16` | **Active Component Slot**: Currently selected sub-component index ($0 = \text{word0}, 1 = \text{word1}, 2 = \text{word2}, 3 = \text{word3}$). |
| `word_555FE0` | `uint16` | **Render Feature Mask**: Bit 0 = render roofs (`word0`); Bit 1 = render walls/floors (`word1` .. `word3`); Bit 2 = elevation slicing. |
| `word_543F04` | `int16` (64) | Isometric tile half-width in pixels ($T_w / 2 = 64$). |
| `word_543F08` | `int16` (32) | Isometric tile half-height in pixels ($T_h / 2 = 32$). |
| `word_543F0C` | `int16` (48) | Elevation layer displacement step in pixels ($E_{step} = 48$). |
| `word_543E4C` | `int` | DirectDraw backbuffer surface handle passed to blitting routines. |
| `word_543E9C` | `int16` | Count of surface objects loaded from line 5 of `.set` file. |
| `word_543EA0` | `int16` | Count of left wall objects loaded from line 5 of `.set` file. |
| `word_543EA4` | `int16` | Count of right wall objects loaded from line 5 of `.set` file. |
| `word_543EA8` | `int16` | Count of clutter objects loaded from line 5 of `.set` file. |
| `word_543EE0` | `int16` | Flat registry index of global `People.obj`. |
| `word_543EE4` | `int16` | Flat registry index of global `Turret.obj`. |
| `word_543EE8` | `int16` | Flat registry index of global `Can.obj`. |
| `word_543EEC` | `int16` | Flat registry index of global `Token.obj`. |

