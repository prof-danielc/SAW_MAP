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

---

## 9. Findings Established During Implementation

Tracing the engine's draw routines for the built-in archives (task T013) settled most of the
hypotheses of sections 4 and 5. Each rule was validated against all 95 version 21 maps; details
and counts are in `REVERSE_ENGINEERING_INFO.md` §3.7 and §9.2.

| Topic | Earlier status | Outcome |
|---|---|---|
| Soldier sprite | Unknown; plan was to draw markers | **Confirmed**: last field of the position table is the `People.obj` frame (`sub_435562`). Soldiers are drawn with their real sprites and match `airfield_airplane.png`. |
| Position table field 2 | Unknown | **Confirmed**: a non-zero value hides the soldier (`sub_435562`). |
| "Zone cells" table `T-559230` | Hypothesis | **Corrected**: it is the token table; the second field is a `Token.obj` frame (`sub_434FB0`). Its cells equal the cells with flag bit 10 in every map. |
| Containers `T-554A80` | Hypothesis | Cell field **confirmed** (equals the cells with flag bit 7 in every map); the role and other fields remain hypotheses. |
| "Groups" table `T-550538` | Unknown | **Confirmed**: turret groups of 9 parts drawn from `Turret.obj` (`sub_4352FD`); only groups with state 0 are drawn, which the Airfield screenshot corroborates. |
| Turret storage | Unknown | Resolved by the row above. |
| Canisters / pickups | Expected in a table | **Corrected**: ground objects are not in a table; cell flag bit 4 places a `Can.obj` frame taken from flag bits 12–17 (`sub_43505D`). |
| Editor markers | Not anticipated | Cell flag bits 0, 9, 23, 24–26, 28–30, 31 draw `Token.obj` markers. Exposed as a separate, default-off category. |
| Soldier side | Hypothesis | Still a hypothesis. |
| Item table | Hypothesis | Still a hypothesis; only slots with a cell are shown, as sprite-less markers. |
| Version 19 layout | Unknown | Still unknown; reported as unsupported (task T035 deferred). |

### Decisions revised
- **Sprites instead of markers for soldiers**: the condition set in section 4 (a frame rule that
  reproduces the editor screenshot) was met, so soldiers, tokens, containers, ground objects,
  and active turrets are drawn with their original sprites. Only placed items, whose sprite is
  unknown, use the placeholder marker.
- **Two toggles instead of one**: placed entities (key `5`, on by default) and editor markers
  (key `6`, off by default), because some markers cover thousands of cells.
- **Entity categories**: `SOLDIER`, `TOKEN`, `CONTAINER`, `GROUND_OBJECT`, `TURRET`, `ITEM`,
  `MARKER` replace the provisional list of the data model.

---

## 10. Second Screenshot Set (dice, ammo, exits, reinforcements, folders)

A further set of Scenario Builder screenshots prompted a second pass. The editor's own mode
names (switch at lines 79854–79917 of `SAW_TD_NOTES.c`) and its placement handler
(lines 39380–39800) settled the naming; details are in `REVERSE_ENGINEERING_INFO.md` §3.7,
§9.2, and §10.2.

| Observation | Finding | Status |
|---|---|---|
| Dice on three cells; clicking one shows "Character Stats" | The fourth field of the soldier position table is an **alternate cell** for the soldier. The dice cells are the alternate cells of soldiers 16, 22, 23; the Character ID is the slot index. | Confirmed |
| Character Stats of ID 23 | Soldier record: nationality (confirmed), controller, AI, encumbrance (hypotheses). A per-soldier percentage sits in the first soldier array (hypothesis). Loadout words are item slot indices (confirmed). | Mixed |
| Ammo on the floor at `(76, 14, 0)` | Already decoded: cell flag bit 4 with a `Can.obj` frame. The editor calls these "Item" / "Canister". | Confirmed |
| Blue outlined cells along the map edge | **Mission Exit** cells, cell flag bit 0 (editor mode 12). Previously labelled "tile mark". | Confirmed |
| Cross tokens with a "German Reinforcements" dialog | The token table holds reinforcement tokens (frame 7 Allied, 8 German, 9 Neutral). Table `T-883800` holds their settings by slot: nationality and percentage confirmed, the rest hypotheses. | Mixed |
| Orange folder | Table `T-554A80` holds **Info** items (editor mode 10), not containers. | Confirmed |
| Folder at `(63, 50, 0)` in `airfield_folder_2.png` | Not present in either research copy of `Airfield.map`; probably placed during the screenshot session, since "Info" is a placement mode. | Open |
| Cell byte `+8` | The editor's "Black Out" mode clears its bits: it is a black-out mask. | Confirmed role; bit meanings unknown |

### Decisions revised
- Entity categories renamed to the editor's terms: `CONTAINER` → `INFO`, `GROUND_OBJECT` →
  `CANISTER`; new category `RELOCATION` for alternate soldier cells, drawn as the dice.
- Marker labels follow the editor modes: mission exit, land mine, medical, lockable,
  multiplayer marker.
- Reinforcement settings and soldier attributes are attached to their entities and shown in
  the sidebar.

---

## 11. Objective Cell (35, 25, 0) of Airfield

Screenshots `airfield_objective_1..4.png` show a canister holding "1. Map" and an "Information
Token" dialog (Token ID 3, Item "Map", Condition Target Get, Causes One Goal Met, radius 0, with
a popup text). Details are in `REVERSE_ENGINEERING_INFO.md` §9.2.

| Finding | Status |
|---|---|
| Table `T-554A80` holds **information tokens**: mission triggers and objectives. The slot index is the Token ID (slot 3 is on this cell). | Confirmed |
| The popup text of Token ID $N$ is line $N + 1$ of the companion `.txt` file. Line 4 of `Airfield.txt` is the text of token 3 word for word; line 1 belongs to token 0. Line 41 is the briefing. | Confirmed for Airfield; all 95 mission files have the same 49-line structure |
| Record fields: condition (9 = Target Get), radius, causes (1 = One Goal Met), and a target reference. | Hypotheses (one dialog) |
| Items of the item table that carry a cell lie in the canister on that cell; item slot 0 is the "Map". | Confirmed |

### Decisions revised
- The `INFO` entity is labelled "information token N" and carries condition, causes, radius, and
  the popup message; the sidebar shows an abbreviated message.
- `MapDocument.token_messages` holds the 40 message lines; `mission_text` is now the briefing
  only (line 41), no longer every line before the objective block.

---

## 12. Character Stats Fields

The user supplied the rank and training of three more Airfield characters and the full contents
of the six dropdown lists of the Character Stats dialog. Comparing them with the soldier records
of those characters (IDs 9, 10, 39) and of ID 23 resolved the open fields: every stored value is
the index into its dropdown list.

| Field | Outcome | Status |
|---|---|---|
| Rank | Memory offset `+284`; 13 / 7 / 8 / 6 for Lt Colonel / Sgt Major / Staff Sgt / Senior Sgt | Confirmed (4 of 4) |
| Primary and secondary training | Offsets `+318` and `+322`; all eight values match | Confirmed |
| Artificial intelligence | Offset `+292`, alphabetical list; Guard = 1 and Seeker = 5 verified | Confirmed for those two; rest by list order |
| Controller | Offset `+290`; 0 Computer, 1 Human | Confirmed |
| Nationality | 1 American, 2 German, 4 Neutral, 8 French, 16 Italian | 8 and 16 assigned by list order |
| Facing and appearance | Offsets `+796` and `+12`; `People.obj` frame = 8 × appearance + (facing + 4) mod 8 for 1,831 of 1,852 soldiers | Confirmed |

Still unknown in the soldier record: offsets `+300`, `+306`, `+308`, and where the Field Medic
checkbox is stored.

### Decision
Soldier and reinforcement entities expose these values by name (for example `rank=Lt Colonel`),
using the dropdown lists as lookup tables; values outside a list are shown as numbers.

---

## 13. Controlled Edit: Field Medic, Facing, and the Session Folder

The user confirmed AI "Stationary" for Character ID 9, gave the facing of three characters, and
saved an edited copy of the map (`Airfield_MEDIC.MAP`, in the installed game folder) after
ticking "Field Medic" for ID 9. Diffing the decompressed streams gave:

| Finding | Status |
|---|---|
| **Field Medic** is the 32-bit field at memory offset `+300` of the soldier record (0 → 1; the only change in the soldier table). | Confirmed |
| **Facing** values are screen directions clockwise from north: 0 N … 7 NW (IDs 9, 10, 39 face S, SE, SW with values 4, 3, 5). | Confirmed |
| AI list order: Stationary = 6 for ID 9. | Confirmed (third verified entry) |
| The folder at `(63, 50, 0)` was placed in the editing session; it is information token 1 in the saved copy. A cell-assigned token stores its own cell as target. | Confirmed |
| `S-884828` changed to the edited character's cell: probably the cell last selected in the editor. | Hypothesis |
| The last line of the mission `.txt` changed on save: a checksum or stamp, not a seed. | Hypothesis |

The installed `Airfield.map` is byte-identical to the research copy. The edited map is not part
of the repository or the automated tests, because it lives outside `Research/`.

### Method note
Changing one value in the Scenario Builder, saving under a new name, and diffing against the
original isolates a field in a single step. It is the recommended way to settle the remaining
unknowns (information token condition and causes lists, reinforcement entry condition and turn,
soldier offsets `+306` and `+308`).

---

## 14. Controlled Edit: Removing Soldiers and Adding Civilians

The user saved `Airfield_CIVILIANS.MAP` after removing the characters at `(91, 66, 0)` and
`(93, 67, 0)` and adding a male and a female civilian. The diff against `Airfield.map`
(319 bytes) is described in `REVERSE_ENGINEERING_INFO.md` §9.2.

| Finding | Status |
|---|---|
| **Item holder**: the first two fields of an item record say who holds it: type 5 with a soldier slot, or type 0 with a canister's cell index. Removing two soldiers freed exactly their items. Verified on all maps (10,529 of 10,546 carried items sit in their holder's loadout; all 4,072 canister items lie on canister cells). | Confirmed |
| **Canister contents** are the items held by the canister's cell; 885 of 902 canisters hold items. The earlier reading of the item record's last field as a cell is retracted. | Confirmed |
| Information token 3 targets item slot 56, the Map in the canister. | Confirmed |
| **Loadout** is a grid of 8 areas × 4 rows × 6 columns of item slots. | Confirmed (loader loop and the freed entries) |
| Civilians: nationality 4, AI Hider, appearance 15 (male) and 16 (female). Appearance usage over all maps: 0–7 American, 8–12 German, 13 Italian, 14 French. | Confirmed for 15 and 16; the rest from usage |
| The editor reuses freed character slots; new characters get `0xFFFF` at offset `+308` (original soldiers have 0–89), so that field may select a predefined character. | Hypothesis |
| Second soldier array: 1 → 0 when the two player soldiers were replaced. | Hypothesis: marks player-squad members |

### Decisions revised
- `ITEM` entities are now the items held by canisters (12 in Airfield), placed on the
  canister's cell; canisters report how many items they hold.
- Item record fields renamed to `holder_type`, `holder`, `item_class`, `item_kind`.

---

## 15. Dropdown Lists of the Token Dialogs

The user supplied the dropdown lists of the Information Token and Reinforcement dialogs. As
with the character fields, every stored value is the index into its list; this also showed that
two information token fields had been named the wrong way round.

| Finding | Status |
|---|---|
| Information token word 2 is the **target type** (0 Cell, 5 Character, 9 Item), not the condition. The target then validates on every used slot: own cell (348 of 348), soldier in use (192 of 192), item in use (10 of 10). This confirms the user's supposition that a token can be assigned to a cell, a character, or an item. | Confirmed |
| Word 5 is the **condition** (None, Target Get, Target Eliminate, Target Destination, Trigger) and word 6 the **causes** (None, Immediate Victory, Immediate Defeat, One Goal Met). Token 3 holds 1 and 3. | Confirmed |
| Reinforcement **character type** indexes Infantry, Grenadier, Officer, SS Infantry, SS Officer for German tokens. | Confirmed for German tokens |
| Reinforcement **AI** uses the soldier list indices (5 Seeker, 7 Wander), which also confirms Wander = 7. | Confirmed |
| Reinforcement word 6 is the **entry condition** (seven-entry list) and word 5 the **Turn/Token** value: a turn for Turn Limit, a token id for Condition. | Confirmed |
| Controller and amount of the reinforcement record. | Confirmed |

Corrected field order of the information token record: `target, target_type, radius, (0),
condition, causes, cell`. The earlier assignment (condition at word 2 with value 9, causes at
word 5 with value 1) was a misreading based on one dialog and is superseded.

---

## 16. Soldier Portrait

The user described the layout of `Portrait.obj` (sets of three sprites per character up to
sprite 203, single portraits after that) and proposed that soldier offset `+308` selects the
portrait.

| Finding | Status |
|---|---|
| Offset `+308` is the **portrait number** $p$; the picture is `Portrait.obj` frame $3p$. Character ID 23 holds 80 and its outfitting screenshot shows frame 240. | Confirmed |
| All 1,785 stored values in the 95 maps select a full-size frame at $3p$; `0xFFFF` (68 soldiers, and every character newly created with the editor) means no portrait. | Confirmed |
| The archive keeps a stride of three throughout: from portrait 68 on, the second and third frames exist as 2 × 2 pixel placeholders, which is why the later portraits look like single sprites in a viewer. | Confirmed |
| American soldiers use portraits 0–67, German and Italian 68–83 and 87–88, civilians mostly 84–86. | Observation over all maps |

The soldier entity now carries `portrait=Portrait.obj:<frame>`.

