# Soldiers at War (1998) Reverse-Engineering Knowledge Base

**Document File**: `REVERSE_ENGINEERING_INFO.md`  
**Repository**: Soldiers at War Map Visualizer  
**Status**: Living Document — Continuously Maintained  
**Last Updated**: 2026-10-11 (193-byte header correction; post-tile record tables; information tokens)  

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

### 2.2 Map Header (193 Bytes / Offset `0x00` – `0xC0`)
The decompressed map starts with a 193-byte header. Its size follows directly from the
sequence of `sub_4060C6` read calls in `sub_445F25` (lines 41801–41826 of `SAW_TD_NOTES.c`):
2 + 8 + 128 bytes, then 55 bytes of editor/view state.

| Offset | Size (Bytes) | Type | Field Name | Description |
|---|---|---|---|---|
| `0x00` | 2 | `uint16` (LE) | `version` | Stream version: `21` in 95 of the 96 shipped maps, `19` in `Menu/Demo.MAP`. Version `20` is accepted by the engine (`sub_78925` / `sub_445F25` / `sub_4471BC`) but no sample exists. |
| `0x02` | 8 | `char[8]` | `signature` | Null-terminated ASCII identifier: `"AMB_MAP\0"`. |
| `0x0A` | 128 | `char[128]` | `tileset_name` | Null-terminated **tileset name** (global `byte_554EE0`), e.g. `"Airfield"`, `"Generic3"`. It is passed to the tileset loader `sub_443D4A` right after the map is read (line 41984), which opens `Sets/<name>.set`. It is *not* a mission title: `Custom_g/Bloody Farm.MAP` stores the name of the generic set it was built with. |
| `0x8A` | 55 | `uint8[55]` | `editor_state` | Scenario Builder cursor, scroll, brush, and view state. |

#### Detailed 55-Byte Editor State Breakdown (`0x8A` – `0xC0`)
Destination addresses are computed from the pointer arithmetic of each read call
(`&word_8AECB0 + n` is a `WORD*`, i.e. address `0x8AECB0 + 2n`).

| Offset | Size | Destination | Notes |
|---|---|---|---|
| `0x8A` | 2 | `word_8AECB0` | Cursor / view coordinate X (Airfield: 50) |
| `0x8C` | 2 | `word_8AECB2` | Cursor / view coordinate Y (Airfield: 46) |
| `0x8E` | 2 | `word_8AECB4` | Cursor level (incremented by `sub_43CF72`; Airfield: 0) |
| `0x90` | 2 | `word_8AECB6` | (Airfield: 51) |
| `0x92` | 2 | `word_8AECB8` | (Airfield: 47) |
| `0x94` | 4 | `0x8AECC4` | Scroll offset X (signed; Airfield: −96) |
| `0x98` | 4 | `0x8AECC8` | Scroll offset Y (signed; Airfield: −38) |
| `0x9C` | 2 × 6 | `0x8AECCC` .. `0x8AECD6` | Last is `word_8AECD6`, the editor brush sprite frame |
| `0xA8` | 1 | `byte_8AECD8` | Editor brush object group |
| `0xA9` | 2 | `0x8AECDA` | |
| `0xAB` | 2 | `word_8AECDC` | Editor brush presence bit |
| `0xAD` | 4 | `dword_8AECF0` | |
| `0xB1` | 4 | `dword_8AECF4` | |
| `0xB5` | 1 | `byte_8AECF8` | Grid overlay / visual debug flag |
| `0xB6` | 2 | `word_8AED06` | Active view level (see §3.7) |
| `0xB8` | 2 | `word_555FE0` | Render feature mask |
| `0xBA` | 2 | `word_6BCDB0` | Editor active component slot (0..3) |
| `0xBC` | 2 | `word_543E60` | |
| `0xBE` | 2 | `word_543E64` | |
| `0xC0` | 1 | `byte_543E68` | |

> [!IMPORTANT]
> Earlier revisions of this document listed a 187-byte header: the three 2-byte reads at
> `0xBA`–`0xBF` had been overlooked. Reading the tile array 6 bytes early shifts every field
> of the 13-byte cell and produced a number of false conclusions, listed in §3.8.

---

## 3. 3D Tile Array & Cell Structure

### 3.1 Dimensions & Offsets
Immediately following the 193-byte header (at byte offset `193` / `0xC1`):
- **Elevation Layers ($Z$)**: Exactly 7 layers ($Z = 0 \dots 6$).
- **Grid Rows ($Y$)**: Exactly 100 rows ($Y = 0 \dots 99$).
- **Grid Columns ($X$)**: Exactly 130 columns ($X = 0 \dots 129$).
- **Total Cell Allocation**: $7 \times 100 \times 130 = 91,000$ cells.
- **Cell Stride**: 13 bytes per cell.
- **Total Tile Array Byte Size**: $91,000 \times 13 = 1,183,000$ bytes.
- **Array Byte Range**: `193` through `1,183,192` (ends at `0x120E38`).

#### Cell Offset Index Formula
$$\text{cell\_index} = (Z \times 100 \times 130) + (Y \times 130) + X$$
$$\text{byte\_offset} = 193 + (\text{cell\_index} \times 13)$$

### 3.2 13-Byte Cell Layout & In-Memory Representation

In the raw binary map stream, each cell occupies exactly 13 bytes. When loaded into memory by `sub_445F25` (lines 41827–41837 in `SAW_TD_NOTES.c`), the engine unpacks each cell into a 16-byte aligned in-memory record:

```c
// Decompiled from sub_445F25 (SAW_TD_NOTES.c, lines 41827-41837):
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
| `+0` | `+0` | `uint16` (LE) | `word_559630` | `word0`: Floor / ground surface component (a floor on level $Z \ge 1$ is the roof of the level below) |
| `+2` | `+2` | `uint16` (LE) | `word_559632` | `word1`: Left Wall component |
| `+4` | `+4` | `uint16` (LE) | `word_559634` | `word2`: Right Wall component |
| `+6` | `+6` | `uint16` (LE) | `word_559636` | `word3`: Clutter / object component |
| `+8` | `+8` | `uint8` | `byte_559638` | `byte4`: Black-out mask. The Scenario Builder's "Black Out" mode clears bits of this byte (§3.7). Only `0xFF` (visible) and `0x00` (blacked out) occur in the 96 shipped maps |
| — | `+9 .. +11` | `uint8[3]` | — | 3-byte internal runtime padding (aligns flags to 4 bytes) |
| `+9` | `+12` | `uint32` (LE) | `dword_55963C` | `dword5`: Flags. Bits 18–20 hold the floor cover level (§3.7); `0x001F0000` is the default value |

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
// Renders word0 (floor) if present and the cover-level condition is met (see §3.7):
sub_451610(*v15 & 0x7F, ((unsigned __int16)*v15 >> 7) & 0xFF, a2, v13);
```
And at lines 45164–45168 of `SAW_TD_NOTES.c`:
```c
if ( (*(_WORD *)(v14 + 2) >> 15) & 1 ) // Word 1 (Left wall)
  sub_451610(*(_WORD *)(v14 + 2) & 0x7F, (*(_WORD *)(v14 + 2) >> 7) & 0xFF, a2, v13);
if ( (*(_WORD *)(v14 + 4) >> 15) & 1 ) // Word 2 (Right wall)
  sub_451610(*(_WORD *)(v14 + 4) & 0x7F, (*(_WORD *)(v14 + 4) >> 7) & 0xFF, a2, v13);
if ( (*(_WORD *)(v14 + 6) >> 15) & 1 ) // Word 3 (Clutter / object)
  sub_451610(*(_WORD *)(v14 + 6) & 0x7F, (*(_WORD *)(v14 + 6) >> 7) & 0xFF, a2, v13);
```
Where `sub_451610(a1, a2, a3, a4)` takes:
- Parameter `a1`: `*v & 0x7F` = Object registry index into `dword_7C58B0[a1]`.
- Parameter `a2`: `(*v >> 7) & 0xFF` = Sprite frame index within archive.
- Parameters `a3`, `a4`: Screen coordinate anchors $(X, Y)$.

#### Direct Decompilation Proof 2: Scenario Builder Editor Tile Packing
At lines 40479–40487 of `SAW_TD_NOTES.c` (inside `sub_442144`), the map editor serializes a user-placed tile into cell memory:
```c
*(&word_559630[104000 * a3] + 1040 * a2 + 8 * a1 + word_6BCDB0) =
    ((unsigned __int8)word_8AECD6 << 7) | (byte_8AECD8 & 0x7F) | (word_8AECDC << 15);
```
- `word_6BCDB0`: Target word slot ($0 \dots 3$).
- `word_8AECD6`: Selected sprite frame index $\rightarrow$ shifted left by 7 (`<< 7`).
- `byte_8AECD8`: Selected object group index $\rightarrow$ masked with `0x7F` (`& 0x7F`).
- `word_8AECDC`: Component presence bit $\rightarrow$ shifted left by 15 (`<< 15`).

Both routines agree on the bitfield formula, and it is confirmed empirically: with it, every one of the 2,238,969 present words in the 96 shipped maps selects an existing frame of an existing archive.

---

### 3.4 Flat Tileset Object Registry Architecture (`dword_7C58B0`)

In the game executable, tileset assets are NOT separated into isolated lists at runtime. Instead, the tileset loader `sub_443D4A` (lines 41157–41235 in `SAW_TD_NOTES.c`) loads all `.obj` files into a single, flat, 128-element pointer table `dword_7C58B0[128]`:

```c
// Condensed from sub_443D4A (SAW_TD_NOTES.c, lines 41157-41232):
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

The five built-in archives are loaded in the order `Cgendam`, `Can`, `Token`, `People`, `Turret`
(lines 41209–41229). The loader records the registry index of four of them in globals:
`word_543EE0` = Can, `word_543EE8` = Token, `word_543EE4` = People, `word_543EEC` = Turret.
`Specials.obj` is loaded earlier through a different routine (`sub_518171`) and is not part of
this registry.

#### Flat Registry Index Partitioning (`Airfield.set` Example)
- **Surfaces (`0 .. 12`, 13 objects)**: `sgrass`, `shill`, `ssnow1`, `sdirt`, `sstone1`, `sstone3`, `swood1`, `swood2`, `smetal1`, `strack2`, `sgen`, `sgen`, `sgen`.
- **Left Walls (`13 .. 24`, 12 objects)**: `lwood1`, `lmetal1`, `lmetal2`, `lmetal3`, `ldrtwall`, `lcave`, `lbeam2`, `lbarb`, `lrail2`, `lgen`, `lgen`, `lgen`.
- **Right Walls (`25 .. 36`, 12 objects)**: `rwood1`, `rmetal1`, `rmetal2`, `rmetal3`, `rdrtwall`, `rcave`, `rbeam2`, `rbarb`, `rrail2`, `rgen`, `rgen`, `rgen`.
- **Tileset Clutter (`37 .. 64`, 28 objects)**: `snwtree1`, `crock4`, `csnow1`, `ctran`, `ctran2`, `cwood1`, `cangle`, `cfurn2`, `cfurn3`, `cfiller`, `cfiller3`, `cwrhouse`, `cradio`, `ckitchn1`, `cbunks`, `carm`, `csandbag`, `cgun1`, `cgun2`, `cvehic1a`, `cvehic2`, `cplane1`, `cplane2`, `csnow2`, `sherman`, `hellcat`, `panzerIV`, `tiger`.
- **Built-in Engine Objects (`65 .. 69`, 5 objects)**: `Cgendam`, `Can`, `Token`, `People`, `Turret`.

`raw_word & 0x7F` indexes directly into `dword_7C58B0`, so technically any word can reference
any registry entry. In practice the editor keeps each word inside its own partition (§3.5).

---

### 3.5 Component Roles in the 13-Byte Cell

Each of the four words maps one-to-one onto one partition of the `.set` file. This was
verified over all 91,000 cells of all 96 shipped maps (2,238,969 present words):

| Word | Role | Registry partition referenced | Exceptions found |
|---|---|---|---|
| `word0` | Floor / ground surface | Surfaces only | none |
| `word1` | Left wall | Left walls only | none |
| `word2` | Right wall | Right walls only | none |
| `word3` | Clutter / object | Tileset clutter | 16 words (in `Paris`, `Normandy`, and `Special3` maps) reference a non-clutter entry |

Further observations:
- No present word references a frame index beyond the frame count of its archive, and none
  references the built-in engine objects (soldiers, canisters, and turrets are placed through
  the post-tile records of §9, not through tile words).
- Multi-tile objects are stored as one `word3` per occupied cell, each selecting its own
  frame. The Ju 52 in `Airfield.map` spans levels 0 and 1 with `cplane2` frames laid out in
  sequence (e.g. row $Y=44$, $Z=1$, $X = 43 \dots 48$ holds frames 58, 56, 54, 51, 48, 44).
- A floor on level $Z \ge 1$ doubles as the roof or ceiling of level $Z-1$; there is no
  separate roof component.
- Absent words are not always zero. `word1` is `0x0001` in most cells of original maps
  (bit 15 clear, so the component is absent). Only bit 15 decides presence.
- Cells outside the playable window (§4) hold the editor's default fill: a layer-0 `word0`
  of surface group 0 with a random frame 0..3, and nothing else.

---

### 3.6 Targeted Verification: Tile `(20, 18, 0)` on `Airfield.map`

The tile at grid coordinates $(X=20, Y=18, Z=0)$ in `Airfield.map` was examined in hex and
compared with original SSI Scenario Builder editor screenshots:

#### 1. Binary Cell Bytes at Offset `193 + ((0 * 100 * 130) + (18 * 130) + 20) * 13 = 30,873`:
```text
Raw Bytes: 82 81 01 00 00 00 25 93 FF 00 00 1F 00
```
- `word0 = 0x8182` (Floor):
  - Presence (Bit 15): `1` (Present)
  - Group Index (Bits 0..6): `0x8182 & 0x7F = 2` $\rightarrow$ `Airfield.set` Surface 2 = **`ssnow1.obj`**
  - Frame Index (Bits 7..14): `(0x8182 >> 7) & 0xFF = 3` $\rightarrow$ **Sprite Frame 3**
- `word1 = 0x0001` (Left wall absent; presence bit 15 is 0)
- `word2 = 0x0000` (Right wall absent)
- `word3 = 0x9325` (Clutter): present, group `0x25 = 37` $\rightarrow$ `snwtree1.obj`, frame `38`
- `byte4 = 0xFF`
- `dword5 = 0x001F0000` (default flags; cover level bits 18–20 = 7)

#### 2. Visual Alignment with Editor Screenshots:
- In `Research/EditorScreenshots/airfield_tile_20_18_0_level_0.png`, the wireframe cursor box hovers over $(20, 18, 0)$ displaying snow with a small curved ridge at the bottom of the diamond.
- In `Research/EditorScreenshots/airfield_tile_20_18_0_level_0_tile_window.png`, the tile options window highlights this specific snow ridge tile.
- In `Research/EditorScreenshots/airfield_tile_20_18_0_level_0_tile.png`, the isolated sprite is an exact pixel-level match to Frame 3 of `ssnow1.obj` (`width=128, height=63, ox=209, oy=322`).

#### 3. Whole-Map Verification:
Drawing every present word of `Airfield.map` with the plain rule of §3.3 reproduces the
Scenario Builder screenshots `airfield_map_level_7.png`, `airfield_map_level_1.png` (including
the black voids where level-0 terrain is absent under the hills), and `airfield_airplane.png`
(the Ju 52 at cursor cell $(45, 42, 0)$).

---

### 3.7 Floor Cover Level (`dword5` Bits 18–20)

`sub_4508F9` draws `word0` only under this condition (line 45087):
```c
if ( ((*(_DWORD *)(v14 + 12) >> 18) & 7) > word_8AED06 && ((unsigned __int16)*v15 >> 15) & 1 && word_555FE0 & 1 )
```
`word_8AED06` is the active view level ($0 \dots 6$; the editor shows it as `Level: 1..7`,
initialised to 6 and set by `sub_43C795`).

Empirical distribution of `(dword5 >> 18) & 7` for cells with a present floor, over all 96 maps:
- The value is always greater than the cell's own level $Z$ (range $Z+1 \dots 7$).
- `7` is the default (about 85% of floors): the floor is drawn at every view level.
- A smaller value $c$ means the floor stops being drawn once the view level reaches $c$.

**Interpretation (hypothesis)**: $c$ is the level of the lowest floor that covers this cell from
above. When the view level is $\ge c$ that upper floor is drawn and hides the lower one, so the
engine skips it. When the view is sliced below $c$ the upper floor is not drawn and the lower
floor becomes visible. The rule is confirmed by the decompilation; only the "covering floor"
reading of the stored value is inferred.

Walls (`word1`, `word2`) and clutter (`word3`) are not subject to this test.

#### Cell Flag Bit Map (`dword5`)

The remaining draw-related bits are read by `sub_43505D`, `sub_434FB0`, and `sub_4508F9`. Each
marker is drawn only when the matching bit of the editor view mask `word_555FE0` is set, so most
of them are editor aids. `0x001F0000` (bits 16–20 set) is the value of a plain cell.

The "Editor mode" column gives the Scenario Builder mode that sets the bit, read from the
placement handler (lines 39380–39800) and the mode-name switch (lines 79854–79917).

| Bits | Meaning | Engine draw | Status |
|---|---|---|---|
| 0 | **Mission Exit** cell (editor mode 12) | `Token.obj` frame 6 (blue diamond outline) | Confirmed (mode 12 sets `|= 1`; cells line the map edge in `airfield_information_token.png`) |
| 1 | Unknown | Extra call `sub_43CCF8` after the floor | Unknown |
| 4 | **Item / Canister** present (editor modes 9 and 18) | `Can.obj` frame = bits 12–17; the Canister dialog offers "American / German / Generic Dead Body" or "Canister" as the appearance | Confirmed (901 cells in 95 maps, every frame valid; `(76, 14, 0)` in `airfield_ammo.png`, `(35, 25, 0)` in `airfield_objective_2.png`) |
| 5 | **Character** on the cell, or a character's alternate cell (editor modes 5, 6, 7) | `People.obj` frame from the soldier table, or the dice `Token.obj` frame 11 on an alternate cell (§9.2) | Confirmed (every soldier cell and every alternate cell carries it) |
| 7 | **Information token** on the cell (editor mode 10, "Info") | `Token.obj` frame 5 (orange folder) | Confirmed (cells equal the information token table cells in all 95 maps) |
| 8 | Alternate draw | Walls and clutter drawn through `sub_4447D5` instead of `sub_451610` | Unknown purpose |
| 9 | **Land Mine** (editor mode 11) | `Token.obj` frame 4, raised 24 px on some floor types | Confirmed (mode 11 sets `|= 0x200`) |
| 10 | **Reinforcement token** on the cell (editor modes 14–16) | `Token.obj` frame from the token table (§9.2) | Confirmed (cells equal the token table cells in all 95 maps) |
| 12–17 | `Can.obj` frame of the ground object | used with bit 4 | Confirmed |
| 16–17 | Unknown | set in every cell | Unknown |
| 18–20 | Floor cover level | see above | Confirmed rule |
| 23 | **Lockable** (editor mode 23) | `Token.obj` frame 12 (padlock) | Confirmed |
| 24–26 | **Multiplayer** marker $n$ = 1–4 (editor modes 25–28) | `Token.obj` frame $n - 1$ (soldier icons 1–4) | Confirmed; presumably the start cells of players 1–4 |
| 28–30 | Area effect $n$ (5 seen) | `Token.obj` frame $n + 12$ (fire, smoke, cloud sprites) | Confirmed draw; purpose unknown |
| 31 | **Medical** (editor mode 17) | `Token.obj` frame 10 (red cross) | Confirmed |

A cell with bit 5 and no soldier standing on it is a character's **alternate cell**: there
`sub_435562` finds no matching position and draws the dice, `Token.obj` frame 11.

**Black Out (editor mode 21)** does not use `dword5`: it clears bits of `byte4`
(`byte_559638`, case 21 of the placement handler, line 39774 ff.). About a quarter of all cells in the shipped maps have
`byte4 = 0x00`, typically building interiors. What the eight individual bits stand for is
unknown, since only `0xFF` and `0x00` occur.

---

### 3.8 Retracted Findings (187-Byte Header Artifacts)

The following statements appeared in earlier revisions of this document. All of them were
artifacts of reading the tile array 6 bytes early (see §2.2) and are **false**:

- "Ground surfaces are stored in `word3`." They are stored in `word0`.
- "`word0` holds roof / cut-away masks with frame numbers 254 and 255." No present word in any
  map has a frame index $\ge 200$; the `0xFF` was `byte4` of the previous cell.
- "Clutter objects are encoded in `dword5` bits 24–31 with their frame in `word0 & 0x7F`."
  Clutter is an ordinary `word3`. The misread `dword5` was assembled from `word3` and `byte4`.
- "Intact walls and fences are stored with frame 254/255 and drawn with frame 0." Walls are
  ordinary `word1` / `word2` values with real frame indices.
- "Surface 0 (`sgrass`) is substituted with `ssnow1` on winter maps." No substitution exists;
  the snow in `Airfield.map` is surface group 2 (`ssnow1`) stored in `word0`.
- "Global engine clutter occupies 13 registry slots including `Specials` and `Newtree1..7`."
  Only the five archives of §3.4 are appended.

---

## 4. Companion Mission Text Files (`.txt`) & Playable Window

Every `.map` is paired with an ASCII `.txt` file of the same name (e.g. `Single_g/Airfield.txt`).
This file is read by `sub_451B7D` in `SAW_TD_NOTES.c`:

### Structure
1. Lines 1–40: the popup message of each information token, line $N + 1$ for Token ID $N$
   (§9.2); empty when the token has no text. All 95 version 21 mission files have 49 lines.
2. Line 41: the mission briefing. Line 42 is empty.
3. 4 lines formatted `<index> : <status>` (e.g., `1 : 0`, `2 : 0` representing objectives).
4. Playable map width (e.g. `104` for `Airfield`).
5. Playable map height (e.g. `80` for `Airfield`).
6. An integer that changes each time the map is saved (`15839` in `Airfield.txt`, `18275` after re-saving the same map); a checksum or save stamp, not a mission seed. Absent in the version-19 `Menu/Demo.txt`.

### Playable Window Placement
The binary `.map` buffer always stores the full $130 \times 100 \times 7$ grid. The playable
$W \times H$ area is **centered** inside it:
$$X_{min} = \lfloor (130 - W) / 2 \rfloor, \quad Y_{min} = \lfloor (100 - H) / 2 \rfloor$$

| Declared size | Window X range | Window Y range |
|---|---|---|
| $130 \times 100$ | 0 .. 129 | 0 .. 99 |
| $104 \times 80$ | 13 .. 116 | 10 .. 89 |
| $78 \times 60$ | 26 .. 103 | 20 .. 79 |
| $52 \times 40$ | 39 .. 90 | 30 .. 69 |
| $26 \times 20$ | 52 .. 77 | 40 .. 59 |

Evidence:
- In 89 of the 96 shipped maps all authored content (walls, clutter, non-default floors) lies
  inside this centered window, give or take one cell on the edges. The other 7 files are the
  resized maps listed below.
- `sub_4508F9` rejects cells below a minimum column/row (`word_550318 > x || word_55031C > y`,
  line 45071), which is how the engine skips the border.
- The Scenario Builder shows absolute grid indices: tile $(20, 18, 0)$ of §3.6 and the
  aircraft cursor cell $(45, 42, 0)$ of `airfield_airplane.png` are indices into the full
  $130 \times 100$ grid.

Outside the window the grid holds default grass fill (§3.5). A few maps were evidently authored
at a larger size and shrunk afterwards, leaving stale content outside the declared window:
`Mansion` (declared $104 \times 80$, leftovers across the full grid), `Normandy` / `Faceoff`
(declared $78 \times 60$, leftovers in the $104 \times 80$ window), and a handful of cells in
`Frost Valley` and `IRONFIST`. Rendering only the declared window gives clean map edges for all
of them.

> [!NOTE]
> The window is also stored explicitly in the map stream (§9.3): four integers hold the maximum
> and minimum column and row, and they equal the centered window above for all 95 version 21
> maps. The visualizer reads those values and uses the `.txt` rule only as a fallback. The code
> that copies them into `word_550318` / `word_55031C` has not been located.

---

## 5. Companion Tileset Definitions (`.set`)

Located in `Sets/<name>.set` (e.g., `Sets/Airfield.set`), these are plain-text ASCII files that bind numerical tileset indices to sprite archives in `Obj/`.

### 5.1 Partition Count Header Line
Which set a map uses is given by the name stored in the map header (§2.2). The file starts with
a free-text description line and a `Defs` line; the next line (ignoring empty lines) specifies
4 integer counts. A trailing `#` comment is allowed on any line (e.g. `13 11 11 28 # s l r c`
in `Messina.set`), and `#comment---` lines separate nothing in particular:
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
- `0x00` (2B, `uint16`): `offset_x` (anchor X offset; see §8.1)
- `0x02` (2B, `uint16`): `offset_y` (anchor Y offset; see §8.1)
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

This is the visualizer's painter's-algorithm ordering; it follows the per-cell draw sequence of `sub_4508F9` (floor, left wall, right wall, clutter) but the engine's exact cell traversal order has not been transcribed.

---

## 9. Post-Tile Record Tables

Immediately following the 1,183,000-byte tile array (offset `1,183,193` / `0x120E39`), the map
loader `sub_445F25` reads a fixed sequence of record tables (lines 41838–41983).

### 9.1 Table Boundaries (version 21) — Confirmed

The read calls, transcribed in order, total **31,366 bytes**, which is exactly
`1,214,559 − 1,183,193`. Decoded with this layout, all 95 version 21 maps are consumed to the
last byte. Table ids use the address of the destination global.

| # | Table id | Working name | Slots × size | Bytes | Stream record layout | Status |
|---|---|---|---|---|---|---|
| 1 | `T-554A80` | information tokens | 40 × 18 | 720 | `u32 target, u16 target type, u16 radius, u16, u16 condition, u16 causes, cell` | Confirmed (radius: hypothesis) |
| 2 | `T-559230` | reinforcement tokens | 40 × 6 | 240 | `cell, u16 frame` | Confirmed |
| 3 | `T-554F60` | soldier positions | 40 × 14 | 560 | `cell, u16 hidden, u16, alternate cell, u16 frame` | Confirmed |
| 4 | `T-550538` | turret groups | 10 × 180 | 1,800 | `u16 state, 5 × u16, 40 bytes, 4 × u16, 20 × (cell, u16 frame)` | Confirmed |
| 5 | `S-543F18` | playable window | 1 × 18 | 18 | `i32 max_x, i32 max_y, i32 min_x, i32 min_y, u16` | Confirmed |
| 6 | `T-558FE8` | — | 8 × 8 | 64 | `8 bytes` | Unknown |
| 7 | `T-550328` | — | 8 × 8 | 64 | `8 bytes` | Unknown |
| 8 | `S-884828` | editor selection | 1 × 6 | 6 | `u16 x, u16 y, u16` | Hypothesis: cell last selected in the editor |
| 9 | `T-847E50` | soldiers | 40 × 424 | 16,960 | `10 scalars (22 bytes), 4 × u32, u16, 192 × u16` | Role confirmed; fields mostly unknown |
| 10 | `S-847E50B` | soldier arrays | 2 × 80 | 160 | `40 × u16` | Hypothesis: appearance percentage per soldier, then a 0/1 flag per soldier |
| 11 | `T-883800` | reinforcements | 40 × 18 | 720 | `u16 nationality, character type, percentage, controller, ai, turn/token, entry condition, amount, u16` | Confirmed |
| 12–16 | `S-884750A` … `S-884750E` | mission parameters | — | 198 | five blocks of 16, 8 × 8, 16, 8 × 12, and 6 bytes | Unknown |
| 17 | `T-8923C0` | — | 100 × 6 | 600 | `3 × u16` | Unknown |
| 18 | `T-892AD0` | items | 500 × 18 | 9,000 | `u16 holder type, u32 holder, u16, u16 class, u16 kind, u16, u32` | Holder confirmed; class and kind hypotheses |
| 19 | `T-559530` | — | 8 × 32 | 256 | `4 × 8 bytes` | Unknown |

`cell` is a 32-bit linear cell index, $Z \times 13000 + Y \times 130 + X$, the same index as the
tile array; `0xFFFFFFFF` means "no cell".

The complete field list, with the evidence status and decompilation reference of every field,
is the declarative layout in `src/saw_map/formats/record_layout.py`. Running the viewer with
`--dump-records` prints every table of a map with those names.

> [!IMPORTANT]
> **Retracted**: earlier revisions listed seven estimated tables here (for example "Soldier /
> Unit Records, 40 × 1,760 bytes = 70,400 bytes" and "Triggers / Zones"). 1,760 bytes is the
> in-memory record stride; only 424 bytes per soldier are stored. The estimated names and sizes
> are superseded by the table above.

### 9.2 Placement Tables — Confirmed from the Draw Routines

The engine draws the built-in archives from these tables. Each rule below was read from the
decompilation and then checked against all 95 version 21 maps.

**Soldiers — `T-554F60` joined with `T-847E50` by slot** (`sub_435562`, line 36481)
- The routine searches the 40 slots for `dword_554F68[4i]` equal to the drawn cell index (the
  first stream field) and requires `word_554F66[8i] == 0` (the `hidden` field).
- It draws `People.obj` frame `word_554F64[8i]` (the last stream field) at the cell's anchor.
- Data check: all 1,853 frames are below the 168 frames of `People.obj`; every soldier cell
  carries cell flag bit 5; 26 soldiers have a non-zero `hidden` value.
- Screenshot check: in `Airfield.map` slot 17 is at `(44, 41, 0)` with frame 88, a soldier in
  camouflage, and appears at that position beside the Ju 52 in `airfield_airplane.png`.
- The slot index is the editor's **Character ID** (`airfield_dices_3_character.png` shows ID 23).
- **Alternate cell (confirmed)**: the fourth stream field of `T-554F60` (`dword_554F60[4i]`,
  memory offset `+0`) is a second position for the soldier, written by the editor's character
  relocation mode (mode 7, line 39636 ff.). The editor marks it with the dice. In Airfield 13 soldiers
  have one, and the dice of `airfield_dices_1.png`, `_2.png`, `_3.png` at `(51, 42, 0)`,
  `(56, 25, 0)`, `(69, 50, 0)` are the alternate cells of slots 16, 22, and 23. All 276
  alternate cells in the 95 maps carry cell flag bit 5. How the game chooses between the two
  positions has not been traced.
- **Soldier record fields** (`T-847E50`). The Character Stats dialog has six dropdown lists, and
  each stored value is the index into its list. Checked against the dialog values of four
  Airfield characters: ID 9 at `(37, 24, 0)` (Lt Colonel, Pistol / Submachinegun), ID 10 at
  `(36, 23, 0)` (Sgt Major, Submachinegun / Semi/Automatic), ID 39 at `(38, 27, 0)` (Staff Sgt,
  Semi/Automatic / Pistol), and ID 23 at `(90, 38, 0)` (German, Computer, Guard, Senior Sgt,
  Bolt Action / Submachinegun, percentage 100, encumbrance 30).

  | Field (memory offset) | IDs 9 / 10 / 39 / 23 | Meaning | Status |
  |---|---|---|---|
  | `+280` nationality | 2 / 2 / 2 / 2 | Bit codes: 1 American, 2 German, 4 Neutral, 8 French, 16 Italian | Confirmed for 1, 2, 4 (reinforcement table; civilians added in the editor are 4). 8 and 16 follow the list order and are supported by the body types they use (see appearance) |
  | `+284` rank | 13 / 7 / 8 / 6 | Index into: Private, 1st Private, Lance Cpl, Sr Lance Cpl, Corporal, Sargeant, Senior Sgt, Sgt Major, Staff Sgt, 2nd Lieutenant, Lieutenant, Captain, Major, Lt Colonel, Brigadier, Maj General, Lt General, General, Col General | Confirmed (4 of 4; all maps use 0–18) |
  | `+290` controller | 0 / 0 / 0 / 0 | 0 Computer, 1 Human | Confirmed (1 for the 8 player soldiers of Airfield) |
  | `+292` ai | 6 / 5 / 1 / 1 | Index into: Follower, Guard, Hider, Mach Gunner, Medic, Seeker, Stationary, Wander | Confirmed for Stationary (ID 9), Guard (ID 23), and Seeker (reinforcement dialog); the others by list order; all maps use 0–7 |
  | `+318` primary training | 1 / 2 / 4 / 3 | Index into: None, Pistol, Submachinegun, Bolt Action, Semi/Automatic, Machinegun, Explosive | Confirmed (4 of 4; all maps use 0–6) |
  | `+322` secondary training | 2 / 4 / 1 / 2 | Same list | Confirmed (4 of 4) |
  | `+724` encumbrance | 30 / 30 / 30 / 30 | Encumbrance | Hypothesis (matches the one dialog value seen; range 17–32) |
  | `+300` field medic | 0 / 0 / 0 / 0 | The "Field Medic" checkbox: 0 or 1 | Confirmed by a controlled edit (see below) |
  | `+796` facing | 4 / 3 / 5 / 5 | Screen direction, clockwise from north: 0 N, 1 NE, 2 E, 3 SE, 4 S, 5 SW, 6 W, 7 NW (north = up, south = bottom of the screen) | Confirmed: IDs 9, 10, 39 face S, SE, SW in the editor |
  | `+12` appearance | 12 / 11 / 11 / 11 | Body type 0–20. Usage in the 95 maps: 0–7 American, 8–12 German, 13 Italian (all 102 soldiers of nationality 16), 14 French, 15 male civilian, 16 female civilian (Neutral and French), 17–20 rare | Confirmed by the frame formula below; 15 and 16 confirmed by the civilians edit |
  | `+306` | — | `0xFFFF` in 1,822 of 1,853 soldiers, 0 otherwise | Unknown |
  | `+308` portrait | 82 / 72 / 73 / 80 | Portrait number; the picture is `Portrait.obj` frame $3 \times \text{portrait}$. `0xFFFF` = none (characters newly created with the editor) | Confirmed (see below) |
  | `+326` (192 words) | — | Loadout: indices into the item table | Confirmed (all 27,813 non-empty words in 95 maps reference an in-use item slot) |

> [!NOTE]
> **Soldier sprite frame formula.** `People.obj` has 168 frames = 21 body types × 8 directions.
> The soldier's sprite frame equals
> $$\text{frame} = 8 \times \text{appearance} + (\text{facing} + 4) \bmod 8$$
> for **1,831 of 1,852 soldiers** in the 95 version 21 maps. Within a body type the frames
> therefore run S, SW, W, NW, N, NE, E, SE. The frame stored in the position table is redundant
> with the two soldier fields; the 21 exceptions are presumably records edited inconsistently.

- **Portrait (confirmed)**: `Obj/portrait.obj` has 287 frames, three per portrait number $p$:
  frame $3p$ is the normal picture, $3p + 1$ the same face on red stripes, and $3p + 2$ a
  darkened version. Portraits 0–67 have all three; from 68 on the second and third frames are
  2 × 2 pixel placeholders, so the stride of three still holds. Frames 285 and 286 (portrait
  95) are the "KIA" and "DISCHARGED" pictures.
  - Screenshot check: Character ID 23 stores 80, and the face on its outfitting screen
    (`airfield_dices_3_character_outfitting.png`) is frame 240.
  - Data check: all 1,785 stored values in the 95 maps select a full-size frame at $3p$; the
    other 68 soldiers hold `0xFFFF`.
  - Usage by nationality: American soldiers use portraits 0–67 (402 of 404 with a portrait);
    German and Italian soldiers 68–83 and 87–88; Neutral and French characters mostly 84–86.

- **Controlled edit (`Airfield_MEDIC.MAP`)**: the user ticked "Field Medic" for Character ID 9
  in the Scenario Builder and saved the map under a new name. Compared with `Airfield.map`, the
  decompressed stream differs in 40 bytes:
  - Soldier record 9, stream offset 8 (memory `+300`): `0 → 1`. This is the only change in
    the soldier table, so it is the Field Medic flag. Four soldiers in the shipped maps have it.
  - A new information token in slot 1 at `(63, 50, 0)` with flag bit 7 on that cell: the folder
    of `airfield_folder_2.png`, placed during the editing session. Its record is the cell index
    in both `target` and `cell` and zero elsewhere, which confirms that a cell-assigned token
    stores its own cell as target.
  - `S-884828`: `57, 49 → 37, 24`, the cell of the edited character (hypothesis: the cell last
    selected in the editor).
  - 18 bytes of the header's editor state (cursor, scroll, brush, active mode `10 → 5`).
  - The companion `.txt` is identical except for its last line (`15839 → 18275`).

- **Controlled edit (`Airfield_CIVILIANS.MAP`)**: the user removed the two characters at
  `(91, 66, 0)` and `(93, 67, 0)` and added a male civilian at `(91, 66, 0)` and a female
  civilian at `(92, 66, 0)`. Compared with `Airfield.map`, 319 bytes differ:
  - The editor reused the freed slots: Character IDs 6 and 7 now hold the civilians. Slot 7's
    position moved to `(92, 66, 0)`; cell flag bit 5 was cleared on `(93, 67, 0)` and set on
    `(92, 66, 0)`.
  - Civilian records: nationality 4 (Neutral), controller Computer, AI 2 (Hider), no training,
    rank Private / 1st Private, encumbrance 30, facing 5 (SW), appearance 15 (male) and 16
    (female). Their frames, 121 and 129, satisfy the frame formula.
  - The portrait (`+308`) changed from 39 and 65 to `0xFFFF` (none), and the second soldier
    array changed from 1 to 0 for both slots.
  - All 16 items held by the removed soldiers (holder 6 or 7) were freed to `0xFF`, and the
    loadout grids of both slots were emptied. This is what identified the item holder fields.
  - `S-884828` became `93, 67`, the last cell clicked, as in the first edit.
  - The mission `.txt` again differs only in its last line (`15839 → 16419`).
- **Appearance percentage (hypothesis)**: the first array of `S-847E50B` holds one value per
  soldier, 100 for ID 23 as in the dialog; values range from 5 to 100 over all maps.

**Reinforcement tokens — `T-559230` with `T-883800` by slot** (`sub_434FB0`, line 36363; lookup `sub_447F93`, line 42494)
- For a cell with flag bit 10 the routine finds the slot with that cell and draws `Token.obj`
  frame `word_559234[4i]`.
- Data check: the cells of used slots equal the cells with flag bit 10 in every map. Frames in
  shipped maps: 8 (cross, 1,261 slots), 9 (flag, 128), 7 (star, 23).
- The editor writes the frame from its mode (cases 14–16 of the placement handler): "A Reinforce" → 7,
  "G Reinforce" → 8, "N Reinforce" → 9. They are American, German, and Neutral reinforcement
  entry points. Airfield has 32 German tokens, the "GermanTokens 32" of
  `airfield_reinforcement_token_2.png`.
- `T-883800` holds the settings of each token, slot for slot. For the token at `(75, 88, 0)`
  (slot 0) the record is `2, 3, 50, 0, 5, 0, 0, 1, 0` and the dialog shows Amount 1, Character
  Type SS Infantry, Percentage 50, Controller Computer, AI Seeker, Entry Condition Target
  Eliminate, Turn/Token 0:

  | Word | Slot 0 | Meaning | Status |
  |---|---|---|---|
  | 0 | 2 | Nationality (1 / 2 / 4 pair exactly with frames 7 / 8 / 9 in all 95 maps) | Confirmed |
  | 1 | 3 | Character type, index into the dialog's list. For German tokens: Infantry, Grenadier, Officer, SS Infantry, SS Officer (German tokens use 0–4; American tokens 0–7 and Neutral tokens 0–1, whose lists are not known) | Confirmed for the German list |
  | 2 | 50 | Percentage | Confirmed |
  | 3 | 0 | Controller: 0 Computer, 1 Human (0 in every used slot) | Confirmed |
  | 4 | 5 | Artificial intelligence, index into the soldier AI list; the dialog offers only Seeker and Wander and the data holds only 5 and 7 | Confirmed |
  | 5 | 0 | "Turn/Token": a turn number with entry condition Turn Limit (0–30), a token id with Condition (0–30), 1 with Trigger, 0 otherwise | Confirmed |
  | 6 | 0 | Entry condition, index into: Target Eliminate, Target Get, Target Destination, Sighted, Trigger, Turn Limit, Condition (values 0, 1, 4, 5, 6 occur; Turn Limit and Condition account for 1,151 of 1,412 tokens) | Confirmed |
  | 7 | 1 | Amount (1–6 over all maps) | Confirmed |
  | 8 | 0 | Always 0 | Unknown |

**Information tokens — `T-554A80`** (mission triggers and objectives)
- Written by the editor's "Info" mode (mode 10, line 39522 ff.), which stores the record and
  sets cell flag bit 7; the editor's dialog for them is titled "Information Token". Earlier
  revisions called this table "containers"; the editor's "Canister" mode places `Can.obj`
  objects through cell flags instead (§3.7).
- Unused slots are all `0xFF`. The last stream field is the cell.
- Data check: the cells of used slots equal the cells with flag bit 7 in every map (550 slots),
  where the engine draws the orange folder, `Token.obj` frame 5.
- **The slot index is the Token ID.** `airfield_objective_3.png` shows the token on
  `(35, 25, 0)` with Token ID 3, and that cell belongs to slot 3. The mission-ending screen
  lists the same token as "3. Target Get, One Goal Met, ITEM=Map Rad=0".
- **Popup text (confirmed for Airfield)**: line $N + 1$ of the companion `.txt` file is the
  message of Token ID $N$. Line 4 of `Airfield.txt` is word for word the "Popup Message Text" of
  token 3 in `airfield_objective_4.png` ("Searching through the office you stumble upon the
  map..."), and line 1 ("You open up your notebook and double-check the mission
  objectives...") belongs to token 0, which sits among the player's soldiers at `(92, 67, 0)`
  (`airfield_folder_1.png`). Over all maps 145 used tokens have a message and 405 have none.
- **Fields (confirmed)**. Each list value is the index into the dialog's dropdown list. Stream
  record of Airfield token 3: `56, 9, 0, 0, 1, 3, cell`; its dialog shows Assign Token: Item
  "1. Map", Condition Target Get, Causes One Goal Met, Token Radius 0.

  | Field | Token 3 | Token 0 | Meaning | Evidence over the 550 used slots of 95 maps |
  |---|---|---|---|---|
  | `target` (u32) | 56 | 8802 | What the token is assigned to, read according to `target_type` | Type 0: the token's own cell index in 348 of 348. Type 5: a soldier slot in use in 192 of 192. Type 9: an item slot in use in 10 of 10 (token 3 → slot 56, the Map in the canister) |
  | `target_type` | 9 | 0 | "Assign Token": 0 Cell, 5 Character, 9 Item | Character targets pair with Target Eliminate (142) or Target Get (50); item targets always with Target Get |
  | `radius` | 0 | 15 | Token Radius | 0–32; hypothesis (one dialog value) |
  | (word) | 0 | 0 | Always 0 | Unknown |
  | `condition` | 1 | 0 | Index into: None, Target Get, Target Eliminate, Target Destination, Trigger | Only values 0–4 occur |
  | `causes` | 3 | 0 | Index into: None, Immediate Victory, Immediate Defeat, One Goal Met | Only values 0, 2, 3 occur (no shipped token causes an immediate victory) |
  | `cell` | (35, 25, 0) | (92, 67, 0) | Position | Equals the cells with flag bit 7 |

  The item holder types of `T-892AD0` use the same codes for cell (0) and character (5).

> [!NOTE]
> `airfield_folder_2.png` shows a folder at `(63, 50, 0)` that is absent from the shipped
> `Airfield.map` (the installed file is byte-identical to the research copy). It was placed
> during the screenshot session: the editor was in "Info" mode, in which a click on an empty
> cell places an information token. The token is present in the user's later save
> `Airfield_MEDIC.MAP` (see the controlled edit above).

**Turret groups — `T-550538`** (`sub_4352FD`, line 36425)
- The routine considers only groups whose first word (`state`) is 0, compares the drawn cell
  with the part cells, and draws `Turret.obj` frame `word_550570[170g + 6i]`.
- Every group in shipped maps has exactly 9 parts covering 3 × 3 cells, with frames
  $10k + 1 \dots 10k + 9$ (all below the 320 frames of `Turret.obj`).
- Screenshot check: the single Airfield group has `state = 1` and is not visible in
  `airfield_map_level_7.png`, in agreement with the rule. Groups with a non-zero state are
  therefore decoded but not drawn.

**Ground objects and editor markers** come from cell flags, not from a table; see the flag
bit map in §3.7.

**Items — `T-892AD0`** (mission item pool)
- 500 slots; unused slots are all `0xFF` (186 of 500 in Airfield). Stream record:
  `u16 holder_type, u32 holder, u16, u16 item_class, u16 item_kind, u16, u32`.
- **Holder (confirmed)**: every item is held either by a soldier or by a canister.

  | `holder_type` | `holder` | Evidence |
  |---|---|---|
  | 5 | Soldier slot (Character ID) | 10,529 of 10,546 such items appear in exactly that soldier's loadout. Removing soldiers 6 and 7 in the editor freed exactly the items whose holder was 6 or 7 (controlled edit below). |
  | 0 | Cell index of a canister | All 4,072 such items lie on a cell with the canister flag (§3.7). 885 of the 902 canister objects in the 95 maps hold at least one item. |

- **Canister contents**: the items whose holder is the canister's cell. In Airfield the canister
  at `(35, 25, 0)` holds item slot 56, class 5 kind 7, the "1. Map" of the Canister dialog in
  `airfield_objective_2.png`, and information token 3 names slot 56 as its target. The object at
  `(76, 14, 0)` of `airfield_ammo.png` holds two items of class 4 kind 23.
- **Loadout grid**: the 192 loadout words of a soldier are 8 inventory areas × 4 rows × 6
  columns (loop at lines 41910–41915). Each word is an item slot; an item larger than one grid
  cell repeats its slot over the cells it covers (a rifle fills 4 × 2 cells).
- `item_class` (1–5) and `item_kind` are hypotheses: no name table has been matched yet. The
  loader special-cases class 1 (line 41974). The two remaining words are always `0xFFFF`.
- **Retracted**: an earlier revision read the last 32-bit field as "the cell of the canister
  holding the item". That field is not a position; the canister cell is the `holder` field.

### 9.3 Playable Window — Confirmed

Block 5 (`dword_543F18`, `dword_543F14`, `dword_543F1C`, `dword_543F20`) holds the exclusive
maximum column and row and the inclusive minimum column and row of the playable area. In
`Airfield.map` the values are `117, 90, 13, 10`. For all 95 version 21 maps they equal the
window obtained by centering the dimensions of the companion `.txt` file (§4).

### 9.4 Version 19

`Menu/Demo.MAP` (version 19) has 31,346 bytes after the tile array, 20 fewer than version 21.
Which fields are absent is unknown; the older reader has not been transcribed. The visualizer
reports its records as an unsupported layout and loads the tile grid normally.

---

## 10. Scenario Builder Editor Discoveries (`Research/EditorScreenshots`)

Direct verification against original SSI Scenario Builder editor screenshots (`SAW_TD.exe`):

### 10.1 Layer Slicing Visual Progression
- **Level 1 (`airfield_map_level_1.png` / Layer $Z=0$)**:
  - Displays the foundational ground plane: snow base (`ssnow1`), brown mud/dirt hex (`sdirt`), 4 grey tarmac hangar bases (`sstone1`), railway line (`strack2`), and wooden barracks floors (`swood1`).
  - Clutter objects on the ground include the lower fuselage of the transport aircraft, supply crates, oil drums, light vehicles (`cvehic1a`), and boundary fences.
  - Black voids appear where level-0 terrain does not exist (under the raised snow hills, whose surface floors are on level 1).
  - Editor status bar format: `Zoom: 1/10 | Res: 640x480 | Mode: Tile | Hug: Off | Level: 1 | <hover_x>,<hover_y>,<z> | 104x80x7`.
- **Level 2 (`airfield_map.png` / Layers $Z \le 1$)**:
  - Clutter components on layer $Z=1$ add the aircraft wings, propellers, and tail assembly, completing the Ju 52 transport aircraft (`cplane2`).
  - Lower structural wall segments become visible.
- **Level 7 (`airfield_map_level_7.png` / Layers $Z \le 6$)**:
  - Full vaulted hangar roofs, pitched wooden barracks roofs, watchtowers, and train tunnel covers are rendered, showing the fully enclosed mission environment.

### 10.2 Built-in Engine Object Archives
The tileset loader `sub_443D4A` appends five built-in `.obj` archives directly after the
tileset's clutter partition (order and evidence in §3.4):
- `+0`: `Cgendam.obj` (Generic damage overlays)
- `+1`: `Can.obj` (Ammo crates, supply canisters, and ground pickups)
- `+2`: `Token.obj` (Mission objective tokens)
- `+3`: `People.obj` (Soldiers placed on the map)
- `+4`: `Turret.obj` (Anti-aircraft flak guns, machine gun nests)

No tile word in any shipped map references these indices. Soldiers, reinforcement tokens,
information tokens, and turrets are placed by the post-tile record tables (§9.2); items and canisters
(`Can.obj`) and the editor markers (`Token.obj`) are placed by cell flag bits (§3.7).
`Cgendam.obj` has no known placement in map files.

#### Scenario Builder Modes
The status bar "Mode" names and their internal ids (switch at lines 79854–79917):
0 Tile, 1 Left Object, 2 Right Object, 3 Center Object, 4 ALL Object, 5 Character,
6 Relocate Char., 9 Item, 10 Info, 11 Land Mine, 12 Mission Exit, 13 Multiplayer,
14 A Reinforce, 15 G Reinforce, 16 N Reinforce, 17 Medical, 18 Canister, 19 Nothing,
21 Black Out, 22 Turrent, 23 Lockable. "Info" is the placement mode for information tokens;
clicking an existing object in it opens that object's dialog.

#### Screenshot Cross-Checks (second set)
| Screenshot | Shows | Decoded as |
|---|---|---|
| `airfield_dices_1/2/3.png` | Dice at `(51, 42, 0)`, `(56, 25, 0)`, `(69, 50, 0)` | Alternate cells of soldiers 16, 22, 23 |
| `airfield_dices_3_character.png` | Character ID 23: German, Computer, Senior Sgt., Guard, Bolt Action / Submachinegun, 100 %, encumbrance 30 | Soldier slot 23: nationality 2, controller 0, rank 6, ai 1, training 3 / 2, percentage 100, encumbrance 30 |
| `airfield_ammo.png` | Ammo on the floor at `(76, 14, 0)` | Cell flag bit 4, `Can.obj` frame 48; a canister holding two items |
| `airfield_information_token.png` | Blue diamond outlines along the map edge at level 1 | Mission Exit cells (flag bit 0), 27 in the map |
| `airfield_reinforcement_token_1/2.png` | Three crosses at `(74–76, 88, 0)`; 32 German tokens; amount 1, SS Infantry, 50 %, Computer, Seeker, Target Eliminate, turn/token 0 | Token slots 0–2, frame 8; reinforcement record of slot 0: `2, 3, 50, 0, 5, 0, 0, 1, 0` |
| `airfield_folder_1.png` | Folder at `(92, 67, 0)` | Information token 0 (radius 15, notebook text) |
| `airfield_objective_1.png`, `_2.png` | Canister at `(35, 25, 0)` holding "1. Map" | Canister flag with `Can.obj` frame 48; item slot 56 held by that cell |
| `airfield_objective_3.png`, `_4.png` | Information Token ID 3: Item "Map", Target Get, One Goal Met, radius 0, popup text | Information token slot 3 (`target_type` 9, `target` 56, `condition` 1, `causes` 3, `radius` 0); text = line 4 of `Airfield.txt` |
| `airfield_folder_2.png` | Folder at `(63, 50, 0)` | Placed during the editing session; saved as information token 1 in `Airfield_MEDIC.MAP` (§9.2) |

### 10.3 Default Ground Fill
- A word with bit 15 clear is absent, whatever its low bits (`0x0000`, `0x0001`).
- Cells outside the playable window carry the editor's default fill on layer 0: `word0` with
  surface group 0 and a frame in 0..3 (`0x8000`, `0x8080`, `0x8100`, `0x8180`).

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
   Bits 1, 8, 16–17 and the area effect marker on bits 28–30 (§3.7); any line-of-sight or
   movement flags.
2. **Black-Out Mask (`byte4`)**:
   What the eight bits of the mask stand for, and how the game reveals blacked-out cells.
3. **Soldier Records (`T-847E50`)**:
   The remaining scalar `+306`; when the highlighted and darkened portrait frames are used; how
   the game picks between a soldier's position
   and its alternate cell, and the role of the appearance percentage. Further controlled edits
   in the Scenario Builder (change one value, save under a new name, diff) are the quickest way
   to settle these.
4. **Unidentified Tables**:
   `T-558FE8`, `T-550328`, `T-8923C0`, `T-559530`, the second soldier array, and the mission
   parameter blocks (victory conditions, weather, and start time are expected there).
5. **Information Tokens, Items, and Reinforcements**:
   The always-zero word of `T-554A80` and confirmation of the radius; the names behind item
   class and kind, and the last field of the item record; the character type lists of American
   and Neutral reinforcement tokens.
6. **Turret Group State**:
   What a non-zero state means (inactive, destroyed, or scripted) and when it changes.
7. **Version 19 / 20 Streams**:
   Which post-tile fields differ from version 21 (20-byte size difference for version 19).
8. **Playable Window Globals**:
   The code that copies the stored window (§9.3) into `word_550318` / `word_55031C`.
9. **Alternate Draw Routine `sub_4447D5`**:
   Used for walls and clutter when `dword5` bit 8 is set.
10. **Sound & Ambience Triggers**:
    Mapping of sound effect identifiers triggered by ambient clutter objects and door interactions.
11. **Mini-map Format (`minimap.col` / `Data/minimap.col`)**:
    Decompression and packing of pre-baked minimap overhead thumbnails.

---

## 12. Decompiled Engine Routines & Global Variables Cross-Reference Table

All references refer to the decompiled `SAW.EXE` / `SAW_TD.EXE` disassembly (`Research/SSI/Soldiers at War/SAW_TD_NOTES.c`, 152,700 lines of C):

### 12.1 Key Functions

| Function Name | Line in `SAW_TD_NOTES.c` | Virtual Address | Role & Architectural Purpose |
|---|---|---|---|
| `sub_442144` | 40418 | `0x00442144` | **Editor Tile Serializer**: Packs user-selected frame (`<< 7`), group (`& 0x7F`), and presence (`<< 15`) into cell slot `word_6BCDB0`. |
| `sub_4060C6` | 7154 | `0x004060C6` | **File Reader**: Buffered binary `fread` wrapper reading `.map` container bytes into memory. |
| `sub_407256` | 7314 | `0x00407256` | **Sprite Blitter**: Performs transparent-keyed scanline blit of a decoded `.obj` frame into the DirectDraw backbuffer. |
| `sub_443D4A` | 41033 | `0x00443D4A` | **Tileset Loader**: Called with the header tileset name; parses `.set` file counts, sequentially loads `.obj` archives into `dword_7C58B0`, and appends the five built-in archives. |
| `sub_433F3A` | 36109 | `0x00433F3A` | **Isometric Projection**: Converts grid $(X, Y, Z)$ into 2D screen coordinates with $T_w=128, T_h=64, E_{step}=48$. |
| `sub_444AFF` | 41462 | `0x00444AFF` | **Frame Anchor X Getter**: Returns internal `offset_x` from sprite frame header: `**(_WORD **)(obj + 4 * frame)`. |
| `sub_444B29` | 41468 | `0x00444B29` | **Frame Anchor Y Getter**: Returns internal `offset_y` from sprite frame header: `*(_WORD *)(*(obj + 4 * frame) + 2)`. |
| `sub_444B54` | 41474 | `0x00444B54` | **Frame Anchor X Setter**: Overwrites internal `offset_x` anchor during runtime offset recalibration. |
| `sub_444B7D` | 41484 | `0x00444B7D` | **Frame Anchor Y Setter**: Overwrites internal `offset_y` anchor during runtime offset recalibration. |
| `sub_445F25` | 41777 | `0x00445F25` | **Map Reader**: Unpacks the 193-byte header (lines 41801–41826), the 3D cell array ($7 \times 100 \times 130 \times 13$ bytes) into 16-byte memory records (lines 41827–41837), and the mission entity tables that follow. |
| `sub_4508F9` | 45053 | `0x004508F9` | **Cell Render Dispatcher**: Walks a cell column upwards, skips cells below the minimum column/row, tests the floor cover level against `word_8AED06`, and issues drawing calls to `sub_451610`. |
| `sub_434FB0` | 36363 | `0x00434FB0` | **Token Table Draw**: For a cell with flag bit 10, draws the `Token.obj` frame of the matching token slot. |
| `sub_43505D` | 36388 | `0x0043505D` | **Cell Flag Marker Draw**: Draws `Token.obj` markers and the `Can.obj` ground object selected by cell flag bits. |
| `sub_4352FD` | 36425 | `0x004352FD` | **Turret Part Draw**: Draws the `Turret.obj` frame of the turret group part standing on a cell (groups with state 0 only). |
| `sub_435562` | 36481 | `0x00435562` | **Soldier Draw**: Draws the `People.obj` frame of the soldier whose position equals the cell, unless its hidden word is set. |
| `sub_447F93` | 42494 | `0x00447F93` | **Token Slot Lookup**: Returns the token table slot for a cell. |
| `sub_43C795` | 38526 | `0x0043C795` | **View Level Setter**: Clamps and stores the active view level in `word_8AED06`. |
| `sub_451610` | 45238 | `0x00451610` | **Draw Call Dispatcher**: Resolves `dword_7C58B0[a1]` by flat group index `a1 = W & 0x7F` and draws frame `a2 = (W >> 7) & 0xFF` at $(X + \Delta X, Y + \Delta Y)$. |
| `sub_451B7D` | 45363 | `0x00451B7D` | **Mission Text Parser**: Parses companion `.txt` file, extracting the playable width and height. |
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
| `word_559636[]` | `uint16[]` | In-memory pointer to Word 3 (Clutter / object) within the cell array. |
| `dword_55963C[]` | `uint32[]` | In-memory pointer to DWORD 5 (cell flags, cover level in bits 18–20) within the cell array. |
| `word_8AED06` | `int16` | **Active View Level** ($0 \dots 6$, default 6). A floor is drawn only while its cover level (`dword5` bits 18–20) is greater than this value. |
| `word_550318`, `word_55031C` | `int16` | Minimum drawable column and row (start of the playable window). |
| `byte_554EE0[128]` | `char[128]` | Tileset name read from the map header. |
| `dword_554F60[]` | 16-byte records | Soldier position table: `+0` alternate cell, `+4` `People.obj` frame, `+6` hidden word, `+8` cell index. |
| `dword_559230[]` | 8-byte records | Reinforcement token table: `+0` cell index, `+4` `Token.obj` frame. |
| `word_883800[]` | 18-byte records | Reinforcement settings, one record per token slot. |
| `dword_554A80[]` | 28-byte records | Information token table (18 bytes stored); cell index at `+16`; the slot index is the Token ID. |
| `byte_559638[]` | byte per cell | Black-out mask (`byte4` of the cell). |
| `word_550538[]` | 340-byte records | Turret groups: `+0` state, `+0x34` part cell indices, `+0x38` part frames (6-byte stride). |
| `unk_847E50` | 1,760-byte records | Soldier records; 424 bytes of each are stored in the map stream. |
| `dword_543F18`, `543F14`, `543F1C`, `543F20` | `int` | Stored playable window: max column, max row, min column, min row. |
| `word_6BCDB0` | `int16` | **Active Component Slot**: Currently selected editor sub-component index ($0 = \text{word0}, 1 = \text{word1}, 2 = \text{word2}, 3 = \text{word3}$). Stored in the map header at `0xBA`. |
| `word_555FE0` | `uint16` | **Render Feature Mask**: Bit 0 = render floors (`word0`); Bit 1 = render walls and clutter (`word1` .. `word3`); Bit 2 and Bit 11 = further overlays. |
| `word_543F04` | `int16` (64) | Isometric tile half-width in pixels ($T_w / 2 = 64$). |
| `word_543F08` | `int16` (32) | Isometric tile half-height in pixels ($T_h / 2 = 32$). |
| `word_543F0C` | `int16` (48) | Elevation layer displacement step in pixels ($E_{step} = 48$). |
| `word_543E4C` | `int` | DirectDraw backbuffer surface handle passed to blitting routines. |
| `word_543E9C` | `int16` | Count of surface objects from the count line of the `.set` file. |
| `word_543EA0` | `int16` | Count of left wall objects from the count line of the `.set` file. |
| `word_543EA4` | `int16` | Count of right wall objects from the count line of the `.set` file. |
| `word_543EA8` | `int16` | Count of clutter objects from the count line of the `.set` file. |
| `word_543EE0` | `int16` | Flat registry index of built-in `Can.obj`. |
| `word_543EE4` | `int16` | Flat registry index of built-in `People.obj`. |
| `word_543EE8` | `int16` | Flat registry index of built-in `Token.obj`. |
| `word_543EEC` | `int16` | Flat registry index of built-in `Turret.obj`. |

---

## 13. Minimap Generation & Cell Inspection Semantics

### 13.1 Minimap Architecture and 2D Orthogonal Projection

Visual analysis of scenario editor screenshots (`Research/EditorScreenshots/airfield_minimap.png`) confirmed that the Soldiers at War minimap is an orthogonal top-down 2D projection of the playable window (§4) of the logical grid. The color classes below are this project's own approximation, chosen by archive name; they are not extracted from the game:

1. **Grid-to-Pixel Mapping**:
   Each map cell $(X, Y)$ maps directly to a discrete pixel block. Unlike the 2:1 isometric diamond rendering used in the main viewport, the minimap axes are orthogonal: rectangular structures (such as aircraft hangars) align directly with horizontal and vertical minimap raster lines.

2. **Surface Class Color Mapping**:
   The visualizer groups surface archive names into distinct RGB color classes:
   - **Snow** (`ssnow1`, `csnow1`, `csnow2`): Light grey / off-white `RGB(210, 215, 220)`.
   - **Stone / Concrete / Hangars** (`sstone1`, `sstone3`, `sgen`, `cwrhouse`): Medium/dark stone grey `RGB(90, 95, 100)`.
   - **Dirt Courtyard & Roads** (`sdirt`, `sdirt2`, `spath`, `sroad`): Mud brown `RGB(130, 90, 50)`.
   - **Railroad Steel Tracks** (`strack2`, `lrail2`, `rrail2`): Charcoal steel `RGB(55, 55, 60)`.
   - **Wood Decks & Flooring** (`swood1`, `swood2`, `cwood1`): Wood tan/brown `RGB(150, 110, 70)`.
   - **Metal Plates** (`smetal1`, `lmetal1`): Slate blue/grey `RGB(115, 125, 135)`.
   - **Foliage / Grass** (`sgrass`): Field green `RGB(70, 120, 60)`.
   - **Wall Outlines / Structures**: Dark boundary accent `RGB(45, 45, 50)`.
   - **Unmapped / Void Cells**: Background dark `RGB(10, 12, 16)`.

3. **Camera Viewport Diamond Frustum**:
   The camera viewport indicator on the minimap is calculated by inverse-projecting the 4 screen corners through the isometric camera transform:
   $$world\_sx = -camera.x + \frac{corner\_x}{zoom}, \quad world\_sy = -camera.y + \frac{corner\_y}{zoom}$$
   $$(gx, gy) = \text{iso\_transform.screen\_to\_world\_float}(world\_sx, world\_sy, z)$$
   Projecting these 4 vertices onto the minimap produces the characteristic white rotated diamond frustum observed in `airfield_minimap.png`.

---

### 13.2 Cell Inspection & 4-Slot Semantics

In Soldiers at War, each cell stores 4 16-bit component words at offsets `+0`, `+2`, `+4`, `+6`:

| Slot | Offset | Semantic Role | Notes & Observations |
|---|---|---|---|
| **Slot 0** | `+0` | **Floor / Ground Surface** | Word 0 references the surface partition of the tileset (e.g. `0x8182` = group 2 `ssnow1.obj`, frame 3 at tile `(20, 18, 0)`). On upper levels it is the floor of that level and the roof of the one below. |
| **Slot 1** | `+2` | **Left Wall Structure** | Word 1 encodes left wall segments (`lwood1`, `lmetal1`, `ldrtwall`, `lbarb`). Usually `0x0001` when absent. |
| **Slot 2** | `+4` | **Right Wall Structure** | Word 2 encodes right wall segments (`rwood1`, `rmetal1`, `rdrtwall`, `rbarb`). |
| **Slot 3** | `+6` | **Clutter / Object** | Word 3 references the clutter partition (trees, vehicles, aircraft pieces, furniture). |
| **Byte 4** | `+8` | **Unknown Attribute** | `0xFF` or `0x00` (§11). |
| **DWORD 5** | `+9` | **Cell Flags** | Cover level in bits 18–20 (§3.7); other bits open. |

---

### 13.3 Primary Tile Name Resolution

The visualizer labels a cell with one "primary tile", the first present component in this order:

1. **Floor (Slot 0)**: e.g. `ssnow1.obj (Frame 3)` for tile `(20, 18, 0)`, matching the tile
   highlighted by the Scenario Builder in `airfield_tile_20_18_0_level_0_tile_window.png`.
2. **Clutter (Slot 3)**: for cells without a floor, such as aircraft pieces on level 1.
3. **Left wall (Slot 1)**, then **right wall (Slot 2)**.

The primary tile is exhibited as `Tile Name: <archive>.obj (Frame <frame>)` in cyan in the
sidebar, and as `[<archive>.obj:<frame>]` in the bottom HUD status bar. This ordering is a
display choice of the visualizer, not engine behavior.

---

### 13.4 Top-Down Raycast Picking & Selection Geometry

1. **Elevation-Slicing Raycast**:
   - In 2.5D isometric engines, cursor picking at screen position $(sx, sy)$ must not blindly evaluate against the active elevation clamp $Z_{\text{max}}$.
   - Upper layers consist mostly of empty air cells (no present word).
   - The picker projects downwards through visible elevation layers $Z \in [Z_{\text{max}} \dots 0]$:
     - At each plane $z$, calculates $(gx, gy) = \text{iso\_transform.screen\_to\_world}(world\_sx, world\_sy, z)$.
     - Queries whether cell $(gx, gy, z)$ lies inside the playable window and has any present word (`has_visual_content()`).
     - The first non-empty visual cell hit along the ray is selected (e.g. hitting $(20, 18, 0)$ from $Z=6$).
     - If no elevated structures exist, the ray reaches the base ground plane ($Z=0$).

2. **Inspected Tile Selection Geometry**:
   - For any inspected cell $(hx, hy, hz)$, the exact geometric diamond tile boundaries are:
     $$\text{Top} = (sx, sy)$$
     $$\text{Right} = (sx + 64, sy + 32)$$
     $$\text{Bottom} = (sx, sy + 64)$$
     $$\text{Left} = (sx - 64, sy + 32)$$
     where $(sx, sy) = \text{world\_to\_screen}(hx, hy, hz)$.
   - In top-down mode, this projects to an orthogonal square of size $32 \times 32$ pixels.
   - Rendered with a semi-transparent cyan fill (`RGBA(0, 230, 255, 45)`) and bright cyan outline (`RGBA(0, 230, 255, 240)`), dynamically anchored to the inspected tile's actual elevation layer $hz$.

---

### 13.5 Unified Camera Space & Minimap Frustum Projection

1. **Camera Center Invariant**:
   - The camera model defines `(-camera.x, -camera.y)` as the 2D world point $(world\_sx, world\_sy)$ positioned at the physical viewport center.
   - In Pygame (CPU software surface, $Y$-down):
     $$\text{center} = (\text{width}/2 + \text{camera.x} \cdot \text{zoom}, \text{height}/2 + \text{camera.y} \cdot \text{zoom})$$
   - In Arcade (OpenGL hardware accelerated, $Y$-up):
     $$\text{world\_camera.position} = (-\text{camera.x}, \text{camera.y})$$
   - This alignment ensures identical panning deltas across both backends:
     - `UP / W`: `camera.pan(0, +step)` (moves viewport North).
     - `DOWN / S`: `camera.pan(0, -step)` (moves viewport South).
     - `LEFT / A`: `camera.pan(+step, 0)` (moves viewport West).
     - `RIGHT / D`: `camera.pan(-step, 0)` (moves viewport East).

2. **Minimap Frustum Projection Parity**:
   - In `calculate_viewport_polygon()`, corner offsets $(cx, cy)$ relative to screen center transform to world space:
     - Pygame ($Y$-down): $world\_sy = -\text{camera.y} + (cy / \text{zoom})$.
     - Arcade ($Y$-up, `invert_y=True`): $world\_sy = -\text{camera.y} - (cy / \text{zoom})$ (since screen $+cy$ in Arcade is visually Northwards).
   - Minimap Y mapping ($gy$ taken relative to the playable window origin):
     - Pygame: $py = \text{frame\_y} + (gy / \text{map\_h}) \cdot \text{frame\_h}$.
     - Arcade: $py = \text{frame\_y} + ((\text{map\_h} - gy) / \text{map\_h}) \cdot \text{frame\_h}$.
   - Result: In both backends, advancing forwards ('W') moves the diamond frustum upwards towards row 0 (North) in complete visual parity with the Scenario Builder.
