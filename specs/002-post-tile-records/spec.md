# Feature Specification: Post-Tile Map Records Reverse Engineering

**Feature Branch**: `002-post-tile-records`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Reverse engineering of post-tile records of map data. A .map file contains more than the tile grid, and the viewer currently reads only the grid. The decompressed stream is 1,214,559 bytes: a 193-byte header, the 1,183,000-byte tile array, and about 31,000 further bytes which the engine's map loader (sub_445F25, lines 41838–41958 of SAW_TD_NOTES.c) reads as a series of record tables. MapReader stops after the tile array. Editor screenshots show soldiers and items the viewer does not draw; their sprites come from the built-in archives People.obj, Can.obj, Token.obj and Turret.obj, and no tile word in any of the 96 maps references those archives, so the placements must come from the record tables (an inference, not yet verified). The decompilation gives the byte counts of each read loop, but nobody has worked out what the fields mean. Reverse engineer post-tile map data so further map information is accessible."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete Structural Decoding of the Post-Tile Data (Priority: P1)

As a reverse-engineering researcher, I want every byte that follows the tile array in a map file to be read into named record tables, so that no part of the map file is skipped and I have a reliable base for working out what the records mean.

**Why this priority**: Nothing else can be trusted until the table boundaries are right. A structure that accounts for every byte of every shipped map, with nothing left over and nothing missing, is the objective proof that the record sizes and counts are understood. It is also useful on its own: researchers can already dump and compare raw records between maps.

**Independent Test**: Load each shipped map and confirm that the decoded tables consume the data after the tile array exactly to the end of the stream, with the same table structure for every map of the same version.

**Acceptance Scenarios**:

1. **Given** any shipped version 21 map, **When** it is loaded, **Then** the data after the tile array is split into the record tables read by the game's map loader and the total of all table sizes equals the number of bytes remaining in the stream.
2. **Given** the version 19 demonstration map, whose stream is 20 bytes shorter, **When** it is loaded, **Then** its post-tile data is either decoded with the version differences identified, or reported as an unsupported record layout while the tile grid still loads and displays as it does today.
3. **Given** a map whose post-tile data is truncated or does not match the expected structure, **When** it is loaded, **Then** the tile grid still loads, the user is told which table could not be read, and the application does not crash.
4. **Given** a loaded map, **When** the researcher requests a dump of the post-tile data, **Then** every table is listed with its position in the file, record count, record size, and raw record contents.

---

### User Story 2 - Identify Placed Soldiers, Items, and Objectives (Priority: P2)

As a reverse-engineering researcher, I want the records that place soldiers, canisters and pickups, objective tokens, and turrets to be identified, with their map position and the sprite that represents them, so that I can see what the mission actually contains beyond terrain and scenery.

**Why this priority**: These placements are the most visible gap in the current knowledge: the Scenario Builder shows soldiers and items that no tile word accounts for. Confirming where they are stored turns today's inference into a verified fact and gives the meaning of the most important fields.

**Independent Test**: For the Airfield map, compare the decoded placements against the Scenario Builder screenshots and confirm that entities visible in the screenshots appear in the decoded data at matching cell coordinates.

**Acceptance Scenarios**:

1. **Given** the Airfield map, **When** its post-tile data is decoded, **Then** the soldiers visible near the aircraft in the Scenario Builder screenshot are present in the decoded data at cell coordinates consistent with the screenshot.
2. **Given** any shipped map, **When** its placed entities are listed, **Then** each entity reports its category (soldier, canister or pickup, objective token, turret, or unidentified), its grid position and level, and the sprite archive and frame used to draw it where that is known.
3. **Given** a record table with unused slots, **When** its entities are listed, **Then** only the slots that hold an actual placement are reported as entities, and the rule that distinguishes used from unused slots is documented.
4. **Given** all shipped maps, **When** their placements are decoded, **Then** every reported position lies inside the map's playable area or is flagged as an anomaly.

---

### User Story 3 - See Placed Entities in the Viewer (Priority: P3)

As a modder or player exploring a map, I want placed soldiers, items, and objective markers to appear on the map view and in the inspection tools, so that the visualizer shows the mission as the Scenario Builder does and not only the terrain.

**Why this priority**: This is the user-visible payoff, but it depends on the first two stories being correct. It is also the strongest end-to-end check: a soldier drawn in the wrong place or with the wrong sprite is immediately obvious.

**Independent Test**: Open the Airfield map in the viewer and compare the area around the aircraft with the Scenario Builder screenshot; the same soldiers and items should be visible at the same cells.

**Acceptance Scenarios**:

1. **Given** a map with placed entities, **When** it is displayed, **Then** each identified entity is drawn at its cell and level, using its original sprite where the sprite is known and a distinctive labelled marker otherwise.
2. **Given** the viewer is showing a map, **When** the user toggles entity display, **Then** all placed entities are hidden or shown without affecting terrain, walls, or scenery.
3. **Given** the cursor is over a cell that holds a placed entity, **When** the user inspects the cell, **Then** the inspection panel lists the entity's category and its decoded fields alongside the existing tile information.
4. **Given** the elevation filter is lowered below an entity's level, **When** the map is redrawn, **Then** that entity is hidden together with the rest of its level.
5. **Given** the map metadata dialog is opened, **When** post-tile data was decoded, **Then** it summarises how many entities of each category the map contains.

---

### User Story 4 - Documented, Evidence-Graded Field Knowledge (Priority: P4)

As a future contributor, I want the layout of every post-tile table written down with each field marked as confirmed, hypothesised, or unknown, so that I can build on the work without repeating it and without mistaking guesses for facts.

**Why this priority**: The project has already been misled once by plausible but unverified format claims. Recording what was checked, and how, is what keeps the next round of work from inheriting new errors.

**Independent Test**: Pick any documented field and follow its stated evidence (a decompilation reference, a cross-map observation, or a screenshot match) to confirm the claim independently.

**Acceptance Scenarios**:

1. **Given** the reverse-engineering knowledge base, **When** a reader looks up a post-tile table, **Then** they find its position, record count, record size, and a field list in which every field carries a status of confirmed, hypothesis, or unknown.
2. **Given** a field marked confirmed, **When** the reader checks its entry, **Then** it cites the evidence that confirms it.
3. **Given** the earlier estimated table list in the knowledge base, **When** this work is complete, **Then** every earlier estimate has been either confirmed, corrected, or explicitly retracted.

---

### Edge Cases

- **Shorter version 19 stream**: The demonstration map has 20 fewer bytes after the tile array. The system must not read it with the version 21 layout and silently produce shifted records.
- **Unused record slots**: Tables appear to have a fixed number of slots regardless of how many entities a map contains. Unused slots must not be reported as entities at the grid origin or with garbage values.
- **Entities outside the playable area**: Maps that were resized after authoring may contain stale placements outside the playable window. These must be flagged, not drawn over the map edge.
- **References that cannot be resolved**: A record may point to a sprite frame, item type, or other table entry that does not exist. The entity must still be listed, with the unresolved reference shown.
- **Several entities on one cell**: More than one placement can share a cell (for example a soldier standing on a pickup). All of them must be listed and inspectable.
- **Maps with no placements**: A map with empty tables must load and display exactly as it does today.
- **Records whose meaning stays unknown**: Tables or fields that cannot be interpreted must still be preserved and shown as raw values, never dropped.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read all data that follows the tile array in a map file into separate record tables whose boundaries follow the read sequence of the game's own map loader.
- **FR-002**: System MUST verify, for every map it loads, that the decoded tables account for exactly the bytes between the end of the tile array and the end of the stream, and MUST report any shortfall or surplus.
- **FR-003**: System MUST preserve the raw bytes of every record, including records and fields whose meaning is unknown, so that no information from the file is discarded.
- **FR-004**: System MUST keep loading and displaying the tile grid when the post-tile data is missing, truncated, of an unsupported version, or structurally inconsistent, and MUST tell the user what could not be decoded.
- **FR-005**: System MUST handle the version 19 stream explicitly: either decode it with its differences from version 21 identified, or report its post-tile data as unsupported. It MUST NOT apply the version 21 layout to it unverified.
- **FR-006**: System MUST identify which record tables place soldiers, canisters and pickups, objective tokens, and turrets on the map.
- **FR-007**: System MUST expose, for each placed entity, its category, grid column, grid row, elevation level, and the sprite archive and frame that represent it, wherever these have been determined.
- **FR-008**: System MUST distinguish used record slots from unused ones and report only used slots as placed entities.
- **FR-009**: System MUST flag placed entities whose position lies outside the map's playable area or whose references cannot be resolved, instead of hiding them or failing.
- **FR-010**: System MUST provide a diagnostic listing of the post-tile data for a map, showing each table's file position, record count, record size, and per-record field values.
- **FR-011**: System MUST draw identified placed entities on the map view at their cell and level, in correct depth order with the surrounding terrain and scenery, using the original sprite where known and a distinctive marker otherwise.
- **FR-012**: Users MUST be able to show and hide placed entities independently of the existing floor, wall, and clutter toggles.
- **FR-013**: System MUST include placed entities in cell inspection, listing every entity on the inspected cell with its decoded fields.
- **FR-014**: System MUST apply the existing elevation filtering and single-level isolation to placed entities.
- **FR-015**: System MUST summarise the decoded mission content (entity counts per category) in the map metadata display.
- **FR-016**: The reverse-engineering knowledge base MUST document every post-tile table and field with an explicit status of confirmed, hypothesis, or unknown, and MUST cite the evidence for every confirmed item.
- **FR-017**: Every earlier estimate about the post-tile tables in the knowledge base MUST be confirmed, corrected, or retracted as part of this work.
- **FR-018**: System MUST treat the original game files as read-only; decoding MUST NOT modify, rewrite, or re-save any map file.

### Key Entities *(include if feature involves data)*

- **Post-Tile Data Block**: Everything in the map stream after the tile array. Has a start position, a total size, and an ordered list of record tables. Its size depends on the stream version.
- **Record Table**: A run of fixed-size records read together by the game's loader. Has a position in the file, a slot count, a record size, a working name, and an evidence status for its interpretation.
- **Record**: One slot of a table. Holds its raw bytes and whatever fields have been identified, and is either in use or unused.
- **Field**: A named part of a record with a position, a size, a decoded value, and a status of confirmed, hypothesis, or unknown.
- **Placed Entity**: A record interpreted as something standing on the map: a soldier, a canister or pickup, an objective token, a turret, or an unidentified placement. Has a grid position, an elevation level, and where known the sprite that draws it and further attributes such as side or facing.
- **Mission Parameters**: Records that describe the mission as a whole and are not tied to a cell, such as victory conditions or deployment settings, to the extent they can be identified.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of shipped version 21 maps, the decoded record tables account for every byte after the tile array, with zero bytes unassigned and zero bytes read past the end.
- **SC-002**: 100% of shipped maps, including the version 19 demonstration map, still load and display their tile grid; none fails because of post-tile decoding.
- **SC-003**: Every soldier and item that is clearly visible in the available Scenario Builder screenshots of the Airfield map appears in the decoded data at a matching cell.
- **SC-004**: At least 95% of the in-use records in the tables identified as placement tables resolve to a position inside the playable area and to an existing sprite frame; every remaining record is individually listed as an anomaly.
- **SC-005**: A user can find out which soldiers and items a map contains and where they stand, using only the viewer, in under one minute.
- **SC-006**: Loading a standard map with post-tile decoding enabled still completes within the existing 2-second budget, and viewport navigation remains smooth with entities displayed.
- **SC-007**: 100% of post-tile tables and fields in the knowledge base carry an evidence status, and no statement about them is left as an unverified estimate without being labelled as such.
- **SC-008**: Showing placed entities introduces no visual change to maps when entity display is switched off.

## Assumptions

- The placement of soldiers, pickups, tokens, and turrets is stored in the post-tile data. This is an inference from the fact that no tile word in any shipped map references the built-in sprite archives; confirming or refuting it is part of this feature. If it is refuted, User Stories 2 and 3 are re-scoped to whatever the records do contain.
- The game's own loader routine in the available decompilation is the authoritative source for table boundaries, and the cross-check against all 96 shipped maps is the authoritative test.
- The goal is to make the information accessible for viewing and inspection. Complete interpretation of every field is not required: soldier statistics, inventories, scripting, and artificial-intelligence data may remain raw or hypothesised as long as they are preserved and labelled.
- Displaying placed entities in the viewer (User Story 3) is in scope as the lowest functional priority, since the stated aim is that the information becomes accessible, and the viewer is the project's means of access.
- Verification material is limited to what is already in the research folder: the decompilations, the shipped maps, and the existing Scenario Builder screenshots. No new screenshots or live debugging sessions are assumed.
- Only the Airfield map has reference screenshots, so screenshot-based verification is limited to that map; other maps are verified by consistency checks.
- **Out of Scope**: Editing or saving maps, decoding saved games, reproducing game logic (line of sight, combat, scripting behaviour), and animating entities.
