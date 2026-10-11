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
  Position and People.obj frame of each soldier; parallel to the soldiers table.
  source: sub_445F25 lines 41856-41860 (dword_554F60)
  fields: cell:CELL_REF(CONFIRMED) hidden:U16(CONFIRMED) field_12:U16(UNKNOWN) aux_cell:CELL_REF(HYPOTHESIS) frame:U16(CONFIRMED)
  slot   0: cell=(87, 70, 0) hidden=0 field_12=65535 aux_cell=None frame=3
  ...

PLACED ENTITIES: 113
  INFO          (92, 67, 0)  Token.obj:5      T-554A80[0]    assigned=Cell target=(92, 67, 0) condition=None causes=None radius=15 message=You open up your notebook ...
  SOLDIER       (44, 41, 0)  People.obj:88    T-554F60[17]   hidden=False nationality=2 controller=Computer rank=Sargeant ai=Guard primary=Submachinegun secondary=Semi/Automatic encumbrance=30 facing=4 appearance=11 percentage=100 alternate_cell=(51, 47, 0)
  ...
EDITOR MARKERS (cell flags): 27
  mission exit: 27 cells
ANOMALIES: 0
```

**Rules**
- Every table of the layout appears, including tables whose fields are all unknown.
- Each field is shown with its kind and evidence status.
- Unused slots are omitted unless `--dump-unused` is given; the header line always states how
  many slots are in use.
- `BYTES` fields print as hexadecimal.
- Word arrays print their first 12 values.
- Editor markers are summarised as a count per kind, not listed per cell.
- When the status is not `DECODED`, the report consists of the first two lines, with the status
  detail on the second.

---

## 4. Viewer Log Lines

When the viewer loads a map, one line reports the outcome:

```text
[INFO] Post-tile records decoded: 19 tables, 113 placed entities
[WARNING] Post-tile records not decoded: unsupported record layout for version 19
```
