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
- `uint8  byte4`: Black-out mask (`0xFF` visible, `0x00` blacked out)
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
and $H$ taken from the last lines of the companion `.txt` mission file, is centered (the same
window is also stored in the post-tile records, section 1.7):
$$X_{min} = \lfloor (130 - W) / 2 \rfloor, \quad Y_{min} = \lfloor (100 - H) / 2 \rfloor$$
Cell coordinates remain absolute grid indices (as displayed by the Scenario Builder). Cells
outside the window hold default grass fill or stale leftovers and are not part of the map.

### 1.7 Post-Tile Record Tables (Offset `1,183,193`)
Version 21 streams continue with 19 fixed-size record tables totalling 31,366 bytes. The ones
with a confirmed role:

| Table | Slots × size | Content |
|---|---|---|
| Soldier positions | 40 × 14 | Cell index, hidden word, alternate cell index, `People.obj` frame |
| Soldiers | 40 × 424 | Per-soldier data: nationality, rank, controller, AI, primary and secondary training, facing, appearance, loadout as item slot indices; same slot order as the positions |
| Reinforcement tokens | 40 × 6 | Cell index, `Token.obj` frame (7 Allied, 8 German, 9 Neutral) |
| Reinforcements | 40 × 18 | Settings per token: nationality, character type, percentage, controller, AI, turn/token, entry condition, amount |
| Information tokens | 40 × 18 | Mission triggers and objectives: target, target type, radius, condition, causes, cell; slot = Token ID; drawn as a folder |
| Turret groups | 10 × 180 | State word and up to 20 parts of (cell index, `Turret.obj` frame) |
| Playable window | 1 × 18 | Max column, max row, min column, min row |
| Items | 500 × 18 | Mission item pool: holder type (5 soldier, 0 canister), holder (soldier slot or canister cell index), item class and kind |

Cell indices are $Z \times 13000 + Y \times 130 + X$; `0xFFFFFFFF` means none. The full layout
with per-field evidence status is `src/saw_map/formats/record_layout.py`; `--dump-records`
prints it for a map. Version 19 streams have a shorter, undecoded record block.

Soldier fields store the index into the Scenario Builder's dropdown lists:
- **Nationality** (bit codes): 1 American, 2 German, 4 Neutral, 8 French, 16 Italian.
- **Controller**: 0 Computer, 1 Human.
- **Rank** (0–18): Private, 1st Private, Lance Cpl, Sr Lance Cpl, Corporal, Sargeant, Senior Sgt,
  Sgt Major, Staff Sgt, 2nd Lieutenant, Lieutenant, Captain, Major, Lt Colonel, Brigadier,
  Maj General, Lt General, General, Col General.
- **Artificial Intelligence** (0–7): Follower, Guard, Hider, Mach Gunner, Medic, Seeker,
  Stationary, Wander.
- **Training** (0–6): None, Pistol, Submachinegun, Bolt Action, Semi/Automatic, Machinegun,
  Explosive.
- **Field Medic**: 0 or 1.
- **Appearance** (0–20): 0–7 American, 8–12 German, 13 Italian, 14 French, 15 male civilian,
  16 female civilian.
- **Loadout**: 8 inventory areas × 4 rows × 6 columns of item slot indices; a large item
  repeats over the grid cells it covers.
- **Facing** (0–7, screen directions, north = up): N, NE, E, SE, S, SW, W, NW.
- **Sprite**: the soldier's `People.obj` frame equals
  $8 \times \text{appearance} + (\text{facing} + 4) \bmod 8$ for 1,831 of 1,852 soldiers in the
  shipped maps (21 body types × 8 directions; within a body type the frames run S, SW, W, NW,
  N, NE, E, SE).

Information token fields:
- **Target type** ("Assign Token"): 0 Cell, 5 Character, 9 Item; the target is then the token's
  cell index, a soldier slot, or an item slot.
- **Condition** (0–4): None, Target Get, Target Eliminate, Target Destination, Trigger.
- **Causes** (0–3): None, Immediate Victory, Immediate Defeat, One Goal Met.

Reinforcement fields:
- **Character type** (German tokens, 0–4): Infantry, Grenadier, Officer, SS Infantry, SS Officer.
- **Artificial Intelligence**: index into the soldier list; only Seeker (5) and Wander (7) occur.
- **Entry condition** (0–6): Target Eliminate, Target Get, Target Destination, Sighted, Trigger,
  Turn Limit, Condition.
- **Turn/Token**: turn number for Turn Limit, token id for Condition.

The companion `.txt` mission file has 49 lines: lines 1–40 are the popup messages of
information tokens 0–39, line 41 is the mission briefing, lines 43–46 the objective states, and
lines 47–49 the playable width, height, and a number that changes on every save.

### 1.8 Cell Flags Used for Placement
| Bits of `dword5` | Meaning |
|---|---|
| 0 | Mission Exit cell |
| 4, with 12–17 | Item / canister drawn from `Can.obj`, frame in bits 12–17 |
| 5 | A soldier stands on the cell, or it is a soldier's alternate cell (dice) |
| 7 | An information token is on the cell |
| 9 | Land mine |
| 10 | A reinforcement token is on the cell |
| 23 | Lockable |
| 24–26 | Multiplayer marker 1–4 |
| 28–30 | Area effect marker (purpose unknown) |
| 31 | Medical |
| 18–20 | Floor cover level (section 1.5) |

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
