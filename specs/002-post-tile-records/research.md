# Research & Technical Decisions: Post-Tile Map Records

**Feature**: `002-post-tile-records` | **Date**: 2026-10-11

Phase 0 research for the plan. Findings are graded **Confirmed** (decompilation plus data
agree, or data alone is conclusive), **Hypothesis** (fits the data seen so far, not proven),
or **Unknown**. Exploration was done with throwaway scripts outside the repository; nothing
here is implemented yet.

Table names of the form `T-xxxxxx` use the address of the destination global in
`SAW_TD_NOTES.c`. Working names in quotes are provisional.

---

## 1. Record Table Boundaries (version 21)

### Findings — Confirmed
Transcribing the read calls of `sub_445F25` (lines 41838–41983) in order gives 19 blocks. Their
sizes sum to 31,366 bytes, which is exactly `1,214,559 − 1,183,193`. Parsed with this layout,
**all 95 version 21 maps are consumed to the last byte with nothing left over.**

| # | Destination | Slots × size | Bytes | Stream record layout (little-endian) |
|---|---|---|---|---|
| 1 | `dword_554A80` | 40 × 18 | 720 | `u32, u16, u16, u16, u16, u16, u32` |
| 2 | `dword_559230` | 40 × 6 | 240 | `u32, u16` |
| 3 | `dword_554F60` | 40 × 14 | 560 | `u32, u16, u16, u32, u16` (memory order differs: stored at +8, +6, +12, +0, +4) |
| 4 | `word_550538` | 10 × 180 | 1,800 | `6 × u16`, `40 bytes`, `4 × u16`, `20 × (u32, u16)` |
| 5 | `dword_543F18`, `543F14`, `543F1C`, `543F20`, `word_543E6C` | 1 × 18 | 18 | `4 × i32, u16` |
| 6 | `unk_558FE8` | 8 × 8 | 64 | `8 bytes` |
| 7 | `dword_550328` | 8 × 8 | 64 | `8 bytes` |
| 8 | `word_884828` | 1 × 6 | 6 | `3 × u16` |
| 9 | `unk_847E50` | 40 × 424 | 16,960 | 10 scalar fields (22 bytes), `4 × u32`, `u16`, `8 × 4 × 6 × u16` (in memory each record is 1,760 bytes) |
| 10 | `unk_847E50 + 70400` | 2 × 80 | 160 | `80 bytes` each (reads as `40 × u16`) |
| 11 | `word_883800` | 40 × 18 | 720 | `9 × u16` |
| 12 | `word_884750` (head) | 1 × 16 | 16 | `u16, u16, u16, u32, u32, u16` |
| 13 | `word_884750 + 12` | 8 × 8 | 64 | `u32, u16, u16` |
| 14 | `word_884750 + 44` | 1 × 16 | 16 | `4 × u16`, `8 bytes` |
| 15 | `word_884750 + 53` | 8 × 12 | 96 | `6 bytes, 6 bytes` |
| 16 | `word_884750 + 101` | 1 × 6 | 6 | `3 × u16` |
| 17 | `word_8923C0` | 100 × 6 | 600 | `3 × u16` |
| 18 | `word_892AD0` | 500 × 18 | 9,000 | `u16, u32, u16, u16, u16, u16, u32` |
| 19 | `dword_559530` / `559570` / `5595B0` / `5595F0` | 8 × 32 | 256 | `4 × 8 bytes` |

### Decision
Describe the layout declaratively (one ordered list of table definitions with field
definitions) and drive a single generic reader from it.

### Rationale
The layout is the reverse-engineered knowledge; keeping it as data makes it reviewable against
the decompilation line by line, lets the diagnostic dump and the documentation be generated
from the same source, and makes a second layout for another stream version cheap to add.

### Alternatives considered
- Hand-written reader code per table: rejected, duplicates the layout in code and in docs.
- Reading only the tables needed for display: rejected, FR-001 to FR-003 require every byte to
  be accounted for and preserved.

### Correction to earlier documentation
`REVERSE_ENGINEERING_INFO.md` §9 lists 7 tables with estimated sizes (for example "Soldier /
Unit Records, 40 × 1,760 bytes = 70,400 bytes"). 1,760 is the in-memory stride; only 424 bytes
per soldier are stored in the file. §9 is to be replaced by the table above (FR-017).

---

## 2. Cell References

### Findings — Confirmed
Several tables hold a 32-bit value that decodes to a valid in-map cell with
$$\text{index} = Z \times 13000 + Y \times 130 + X$$
the same linear index used for the tile array. `0xFFFFFFFF` marks "no cell".

### Decision
Provide one shared cell-index decoder and treat `0xFFFFFFFF` (and `0xFFFF` for 16-bit
references) as the empty value.

---

## 3. Playable Window Stored in the File

### Findings — Confirmed
Block 5 holds four 32-bit integers. In `Airfield.map` they are `117, 90, 13, 10`: the exclusive
maximum column and row and the minimum column and row of the playable window. For **all 95
version 21 maps** these values equal the window obtained by centering the width and height of
the companion `.txt` file.

This closes the open question recorded in feature 001 (the centering formula was empirical):
the window is stored explicitly in the map file.

### Decision
Read the playable window from block 5 when post-tile data is decoded, and keep the `.txt`
centering rule only as the fallback when post-tile data is unavailable (version 19, truncated
stream).

### Rationale
The map file is then self-sufficient; a map copied without its `.txt` still displays correctly.

### Alternatives considered
- Keep using the `.txt` only: rejected, it is a second source for a fact the map itself states.

---

## 4. Where Soldiers Are Placed

### Findings
- **Confirmed**: table 3 (`dword_554F60`, 40 slots) holds a cell reference per slot. In
  `Airfield.map` all 40 decode to cells inside the playable window. Slot 17 is at cell
  `(44, 41, 0)`, next to the aircraft cursor cell `(45, 42, 0)` of
  `Research/EditorScreenshots/airfield_airplane.png`, where a soldier stands.
- **Confirmed**: table 9 (`unk_847E50`, 40 slots) holds the per-soldier data. Its first field is
  `1` for slots 0–7 and `2` for slots 8–39 in Airfield; slots 0–7 of table 3 form one cluster
  around `(87–95, 63–70)` and the others are spread over the base. That matches 8 attackers
  and 32 defenders.
- **Hypothesis**: tables 3 and 9 are parallel (slot *n* of one belongs to slot *n* of the
  other), and the first field of table 9 is the side.
- **Hypothesis**: the last `u16` of table 3 (values such as 3, 13, 28, 89, 95) selects
  appearance or facing; the second `u32` of table 3 (a cell reference or `0xFFFFFFFF`) is a
  movement or patrol target.
- **Unknown**: which `People.obj` frame draws a given soldier; the meaning of most table 9
  scalars; the `8 × 4 × 6` word block of table 9 (values such as 287, 296 repeated, likely
  equipment loadouts referring to table 18).

The central assumption of the specification (placements live in the post-tile data) is
therefore **confirmed for soldiers**.

### Decision
Implement soldier placement from table 3 positions joined with table 9 by slot index. Draw
soldiers with a labelled marker coloured by side until the sprite frame rule is confirmed;
switch to `People.obj` sprites only once a frame mapping reproduces the editor screenshots.

### Rationale
Position and side are solid; the sprite frame is not. A marker in the right place is correct
information, while a guessed sprite would be a wrong claim presented as fact (constitution
principle VI, hypothesis discipline).

---

## 5. Items, Containers, and Zones

### Findings
- **Hypothesis (strong)**: table 18 (`word_892AD0`, 500 slots) is the mission item pool. 186 of
  500 slots are all `0xFFFF…` in Airfield (unused). Slot 0 carries a cell reference,
  `(35, 25, 0)`; the mission goal of Airfield is "Target Get, ITEM=Map". The loader contains a
  special case on the fifth field (`word_892ADA == 1`).
- **Hypothesis (strong)**: table 1 (`dword_554A80`, 40 slots) is placed containers. Unused
  slots are all `0xFF`. Airfield uses 2 slots; one of them ends with the cell `(35, 25, 0)`,
  the same cell as item slot 0.
- **Hypothesis**: table 2 (`dword_559230`, 40 slots) is map zone cells. Used slots have type
  `8` and lie in short runs along the map edges (`(74–76, 88)`, `(39–43, 10)`,
  `(115, 45–48)`), which fits entry or exit cells; type `3` slots carry no valid cell.
- **Unknown**: tables 4, 6, 7, 11, 17, 19 and the mission parameter blocks 12–16. Table 11 has
  40 slots and may be per-soldier behaviour settings; table 4 has 10 slots with a 20-entry
  list of (cell, value) pairs.
- **Unknown**: where turrets are stored, and whether any shipped map uses `Turret.obj`.

### Decision
Stage the semantic work: soldiers first (section 4), then items and containers, then zones.
Every table that is not yet understood is still read, preserved, and listed in the dump with
generic field names.

### Rationale
Matches the priority order of the specification and keeps each step independently verifiable.

---

## 6. Version 19 Stream

### Findings
`Menu/Demo.MAP` is 20 bytes shorter than a version 21 stream. Its header and tile array are
identical in layout. **Unknown**: which post-tile fields are absent. `sub_445F25` is the
version 21 reader; the routine for the older layout (the spec for feature 001 cites
`sub_4471BC`) has not been transcribed.

### Decision
Version 19 post-tile data is reported as "unsupported record layout" and left undecoded; the
tile grid loads as today, with the `.txt` window fallback. Transcribing the older reader is a
separate, optional task; if it yields a layout that consumes the stream exactly, it is added as
a second layout definition.

### Rationale
FR-005 forbids applying the version 21 layout unverified, and one demonstration map does not
justify blocking the feature.

---

## 7. Integration into the Existing Viewer

### Decision
- Post-tile decoding lives in the `formats` and `maps` packages and stays free of any rendering
  dependency, like the existing parsers.
- Placed entities enter the existing render list as a fifth component category drawn after
  clutter within a cell, so depth sorting, elevation filtering, and isolation apply unchanged.
- A new camera flag and input action toggle entity display (key `5`, next to the component
  toggles `1`–`4`).
- The cell inspector and the metadata dialog read entities from the map document.
- A command-line flag prints the post-tile dump and exits without opening a window.

### Rationale
Reuses the abstractions introduced in feature 001 (render items, `InputHandler`,
`OverlayModel`) instead of adding parallel paths in each backend.

### Alternatives considered
- A separate overlay pass drawn above the whole map: rejected, entities would not be occluded
  by walls and roofs in front of them.
- A separate dump tool script: rejected, the project exposes one CLI and the constitution asks
  for consistent interfaces.

---

## 8. Performance

### Findings
The post-tile block is 31 KB; decoding it is negligible next to the 1.18 MB tile array (about
0.5 s per map today). At most 40 soldiers plus a few dozen items are added to a render list of
10,000–25,000 items.

### Decision
No special optimisation. The existing 2-second load and 60 FPS budgets are kept as acceptance
checks.
