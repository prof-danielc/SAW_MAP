# Internal API Contract: Post-Tile Records

**Feature**: `002-post-tile-records` | **Date**: 2026-10-11

Interfaces added to the existing package. Entity definitions are in
[data-model.md](../data-model.md); signatures here are the contract, bodies are not.

---

## 1. Layout Definition (`saw_map.formats.record_layout`)

```python
def get_layout(version: str) -> Optional[Sequence[TableLayout]]:
    """Returns the ordered table layouts for a stream version, or None if no layout is known."""

def layout_byte_size(layout: Sequence[TableLayout]) -> int:
    """Total bytes consumed by a layout (sum of slot_count * record_size)."""
```

**Guarantees**
- `layout_byte_size(get_layout("21")) == 31366`.
- Layout objects are immutable and import nothing from rendering or viewer packages.

---

## 2. Record Reader (`saw_map.formats.records_reader`)

```python
class RecordsReader:
    @classmethod
    def read(cls, data: bytes, start_offset: int, version: str) -> PostTileData:
        """Decodes the post-tile block of a decompressed map stream.

        Never raises for malformed input: the outcome is reported in PostTileData.status.
        """
```

**Behaviour**

| Condition | `status` | `tables` |
|---|---|---|
| Layout known and it consumes the remaining bytes exactly | `DECODED` | all tables |
| No layout for `version` | `UNSUPPORTED_VERSION` | empty |
| Remaining bytes differ from the layout size | `SIZE_MISMATCH` (detail states expected and actual sizes) | empty |
| No bytes after the tile array | `MISSING` | empty |

`MapReader.parse_map` calls `RecordsReader.read` after the tile array and attaches the result
to `MapDocument.post_tile`. A status other than `DECODED` is logged as a warning and never
turns into an exception or a non-zero exit code.

---

## 3. Entity Extraction (`saw_map.maps.entities`)

```python
def extract_entities(post_tile: PostTileData, map_doc: MapDocument) -> List[PlacedEntity]:
    """Builds placed entities from decoded tables, flagging anomalies."""
```

**Guarantees**
- Only records with `in_use == True` and a valid cell reference produce an entity.
- An entity outside the playable window carries the anomaly `"outside playable window"`.
- Returns an empty list when `post_tile.status` is not `DECODED`.
- Deterministic order: by source table in stream order, then by slot index.

---

## 4. Diagnostic Dump (`saw_map.diagnostics.records_report`)

```python
def format_records_report(map_doc: MapDocument, include_unused: bool = False) -> str:
    """Formats the post-tile tables and placed entities of a map as plain text."""
```

Output structure is specified in [cli-contract.md](cli-contract.md).

---

## 5. Rendering and Viewer Integration

- `DrawOrderStrategy.generate_render_list(..., show_entities: bool = True)` appends one
  `RenderItem` of type `ComponentType.ENTITY` per placed entity that passes the elevation
  filter. Existing parameters and behaviour are unchanged when the map has no entities.
- Backends draw an `ENTITY` item with its sprite when `sprite_archive` is set, otherwise with
  the category marker from `saw_map.rendering.fallback`.
- `CellInspector.inspect_cell(cell, tileset, entities=())` fills
  `CellInspectionInfo.entities`.
- `OverlayModel.get_map_metadata_lines` adds an entity count per category when
  `post_tile.status` is `DECODED`, or the status detail otherwise.

---

## 6. Viewer Input Contract (additions)

| Input Action | Primary Key | Function |
|---|---|---|
| **Toggle Entities** (`InputAction.TOGGLE_ENTITIES`) | `5` | Shows or hides placed soldiers, items, containers, and zones |

All existing bindings of feature 001 are unchanged.
