# CLI Contract: Post-Tile Records

**Feature**: `002-post-tile-records` | **Date**: 2026-10-11

Additions to the command-line interface defined in
`specs/001-map-visualizer/contracts/cli-contract.md`. Everything there remains valid.

---

## 1. New Option

| Option | Type | Default | Description |
|---|---|---|---|
| `--dump-records` | Flag | `False` | Print the post-tile record tables and placed entities of `MAP_FILE` to standard output and exit without opening a window |
| `--dump-unused` | Flag | `False` | With `--dump-records`, also list unused record slots |

```bash
python -m saw_map.main "Research/SSI/Soldiers at War/Single_g/Airfield.map" --dump-records
```

`--dump-records` needs no game directory, renderer, or display.

---

## 2. Exit Codes

| Situation | Exit code |
|---|---|
| Dump printed, post-tile data decoded | `0` |
| Dump printed, post-tile data not decoded (unsupported version, size mismatch, missing) — the report states why | `0` |
| `MAP_FILE` missing | `1` (unchanged) |
| Header or tile array invalid | `2` (unchanged) |

An undecodable post-tile block is a reported condition, not a failure, because the map itself
is valid (FR-004).

---

## 3. Report Format

Plain text, one section per table in stream order, then the entity list.

```text
POST-TILE DATA: Airfield (version 21)
Status: DECODED | offset 1183193 | 31366 bytes | 19 tables | 0 bytes unassigned

[T-554F60] soldier_positions (CONFIRMED) | offset 1184153 | 40 slots x 14 bytes | 40 in use
  fields: cell:CELL_REF(CONFIRMED) field_01:U16(UNKNOWN) field_02:U16(UNKNOWN) target:CELL_REF(HYPOTHESIS) field_04:U16(UNKNOWN)
  slot  0: cell=(87, 70, 0) field_01=0 field_02=65535 target=None field_04=3
  slot  1: cell=(91, 69, 0) ...
  ...

PLACED ENTITIES: 43
  SOLDIER   (44, 41, 0)  T-554F60[17]  side=2
  ITEM      (35, 25, 0)  T-892AD0[0]
  ...
ANOMALIES: 0
```

**Rules**
- Every table of the layout appears, including tables whose fields are all unknown.
- Each field is shown with its kind and evidence status.
- Unused slots are omitted unless `--dump-unused` is given; the header line always states how
  many slots are in use.
- `BYTES` fields print as hexadecimal.
- When the status is not `DECODED`, the report consists of the first two lines, with the status
  detail on the second.

---

## 4. Viewer Log Lines

When the viewer loads a map, one line reports the outcome:

```text
[INFO] Post-tile records decoded: 19 tables, 43 placed entities (40 soldiers, 1 item, 2 containers)
[WARNING] Post-tile records not decoded: unsupported record layout for version 19
```
