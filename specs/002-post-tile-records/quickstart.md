# Quickstart & Validation Guide: Post-Tile Records

**Feature**: `002-post-tile-records` | **Date**: 2026-10-11

Scenarios that prove the feature works end to end. Interfaces are defined in
[contracts/](contracts/) and entities in [data-model.md](data-model.md).

---

## 1. Prerequisites

- The environment of feature 001 (Python 3.12, `arcade`, `pygame`, `pillow`, `pytest`).
- The game files under `Research/SSI/Soldiers at War/` (read-only).

---

## 2. Automated Scenarios

### Scenario 1: Layout and reader unit tests
```bash
pytest tests/unit/test_record_layout.py tests/unit/test_records_reader.py tests/unit/test_entities.py -v
```
**Expected**: the version 21 layout totals 31,366 bytes; a synthetic stream built from the
layout round-trips field values; truncated and oversized streams yield `SIZE_MISMATCH`; an
unknown version yields `UNSUPPORTED_VERSION`; unused slots produce no entities.

### Scenario 2: Every shipped map is consumed exactly
```bash
pytest tests/integration/test_post_tile_records.py -v
```
**Expected** (SC-001, SC-002, SC-004):
- All 95 version 21 maps decode with status `DECODED` and zero unassigned bytes.
- `Menu/Demo.MAP` (version 19) loads its tile grid and reports `UNSUPPORTED_VERSION`.
- The stored playable window of every version 21 map equals the window of feature 001.
- At least 95% of in-use placement records resolve inside the playable window; the rest are
  listed as anomalies.

### Scenario 3: Airfield reference placements
Part of the same integration test.
**Expected** (SC-003): a `SOLDIER` entity exists at cell `(44, 41, 0)`; soldier slots 0–7 lie
within columns 87–95 and rows 63–70; an `ITEM` entity exists at `(35, 25, 0)`.

### Scenario 4: Full regression suite
```bash
pytest tests/ -v
```
**Expected**: all tests of feature 001 still pass.

---

## 3. Manual Scenarios

### Scenario 5: Diagnostic dump
```bash
python run_viewer.py "Research/SSI/Soldiers at War/Single_g/Airfield.map" --dump-records
```
**Expected**: the report of [cli-contract.md](contracts/cli-contract.md) §3 is printed, no
window opens, exit code `0`.

### Scenario 6: Entities in the viewer
```bash
python run_viewer.py "Research/SSI/Soldiers at War/Single_g/Airfield.map" --game-dir "Research/SSI/Soldiers at War"
```
1. Navigate to the aircraft on the central dirt area.
2. Compare with `Research/EditorScreenshots/airfield_airplane.png`: a soldier marker stands
   beside the aircraft at cell `(44, 41, 0)`.
3. Press `5`: all entity markers disappear and the terrain is unchanged (SC-008). Press `5`
   again to restore them.
4. Hover a soldier's cell with the sidebar open (`I`): the entity and its decoded fields are
   listed below the tile components.
5. Lower the view level with `Q` / `PageDown` below an elevated entity: it disappears with its
   level.
6. Press `F1`: the metadata dialog shows the entity count per category.

### Scenario 7: Map without decodable records
```bash
python run_viewer.py "Research/SSI/Soldiers at War/Menu/Demo.MAP" --game-dir "Research/SSI/Soldiers at War"
```
**Expected**: the map displays as before, a warning line reports the unsupported record
layout, and no entities are drawn.

### Scenario 8: Performance check
Load `Airfield.map` and `Mansion.map`.
**Expected** (SC-006): each opens within 2 seconds and panning stays smooth with entities
shown.

---

## 4. Documentation Check

Open `REVERSE_ENGINEERING_INFO.md` §9.
**Expected** (SC-007): every post-tile table is listed with position, slot count, record size,
and fields, each marked confirmed, hypothesis, or unknown; the earlier estimated table list is
gone or marked retracted.
