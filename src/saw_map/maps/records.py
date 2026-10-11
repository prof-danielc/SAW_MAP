"""Domain models for the post-tile record tables of a Soldiers at War map.

Describes the data that follows the 3D tile array in the map stream: record tables,
their reverse-engineered field layouts with evidence grading, and the placed entities
(soldiers, tokens, info items, turrets, ...) derived from them.

Decoupled from all UI and rendering libraries (Arcade, Pygame).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Grid dimensions of the stored cell array (shared with the tile array)
GRID_WIDTH = 130
GRID_HEIGHT = 100
GRID_LAYERS = 7
CELLS_PER_LAYER = GRID_WIDTH * GRID_HEIGHT
TOTAL_CELLS = CELLS_PER_LAYER * GRID_LAYERS


def decode_cell_index(index: int) -> Optional[Tuple[int, int, int]]:
    """Converts a linear cell index (z * 13000 + y * 130 + x) into (x, y, z).

    Returns None for values outside the grid, including the 0xFFFFFFFF "no cell" marker.
    """
    if not 0 <= index < TOTAL_CELLS:
        return None
    z, rest = divmod(index, CELLS_PER_LAYER)
    y, x = divmod(rest, GRID_WIDTH)
    return (x, y, z)


def encode_cell_index(x: int, y: int, z: int) -> int:
    """Converts grid coordinates into the linear cell index used by the map stream."""
    return z * CELLS_PER_LAYER + y * GRID_WIDTH + x


class EvidenceStatus(str, Enum):
    """How well the interpretation of a table or field is established."""
    CONFIRMED = "CONFIRMED"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


class DecodeStatus(str, Enum):
    """Outcome of decoding the post-tile block of a map stream."""
    DECODED = "DECODED"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    SIZE_MISMATCH = "SIZE_MISMATCH"
    MISSING = "MISSING"


class FieldKind(str, Enum):
    """Binary encoding of a record field (all little-endian)."""
    U16 = "U16"
    U32 = "U32"
    I32 = "I32"
    BYTES = "BYTES"
    CELL_REF = "CELL_REF"
    U16_ARRAY = "U16_ARRAY"


class EntityCategory(str, Enum):
    """Kind of object placed on the map by the post-tile data or cell flags.

    Names follow the Scenario Builder modes: SOLDIER ("Character"), RELOCATION
    ("Relocate Char.", the alternate cell of a soldier, shown as a dice), TOKEN
    (reinforcement tokens), INFO ("Info" items, shown as a folder), CANISTER
    ("Item" / "Canister" objects drawn from Can.obj), TURRET ("Turrent"), ITEM (item
    pool slots carrying a cell), and MARKER (editor markers stored in cell flags).
    """
    SOLDIER = "SOLDIER"
    RELOCATION = "RELOCATION"
    TOKEN = "TOKEN"
    INFO = "INFO"
    CANISTER = "CANISTER"
    TURRET = "TURRET"
    ITEM = "ITEM"
    MARKER = "MARKER"


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """Layout and evidence grading of one field of a record.

    Attributes:
        name: Field name; generic (field_NN) while the meaning is unknown.
        kind: Binary encoding.
        size: Size in bytes.
        status: Evidence status of the field's interpretation.
        note: Evidence citation (required for CONFIRMED) or reasoning.
    """
    name: str
    kind: FieldKind
    size: int
    status: EvidenceStatus = EvidenceStatus.UNKNOWN
    note: str = ""

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError(f"Field '{self.name}' must have a positive size.")
        if self.status == EvidenceStatus.CONFIRMED and not self.note:
            raise ValueError(f"Confirmed field '{self.name}' must cite its evidence in 'note'.")


@dataclass(frozen=True, slots=True)
class TableLayout:
    """Static description of one record table of the post-tile block.

    Attributes:
        table_id: Stable identifier derived from the engine's destination global.
        working_name: Provisional readable name.
        slot_count: Fixed number of record slots.
        fields: Fields in stream order.
        status: Evidence status of the table's interpretation.
        source_reference: Where in the decompilation the layout was transcribed from.
        used_cell_field: Name of a CELL_REF field that must hold a valid cell for a slot
            to count as in use, or None.
        unused_when_all_ff: If True, a slot whose bytes are all 0xFF is unused.
        description: What the table is believed to hold.
    """
    table_id: str
    working_name: str
    slot_count: int
    fields: Tuple[FieldSpec, ...]
    status: EvidenceStatus = EvidenceStatus.UNKNOWN
    source_reference: str = ""
    used_cell_field: Optional[str] = None
    unused_when_all_ff: bool = False
    description: str = ""

    @property
    def record_size(self) -> int:
        """Size in bytes of one record."""
        return sum(f.size for f in self.fields)

    @property
    def byte_size(self) -> int:
        """Size in bytes of the whole table."""
        return self.slot_count * self.record_size


@dataclass(slots=True)
class Record:
    """One slot of a record table, with raw bytes preserved."""
    slot_index: int
    raw: bytes
    values: Dict[str, Any]
    in_use: bool = True


@dataclass(slots=True)
class RecordTable:
    """A decoded record table and its position in the stream."""
    layout: TableLayout
    offset: int
    records: List[Record] = field(default_factory=list)

    @property
    def used_records(self) -> List[Record]:
        """Records whose slot holds actual data."""
        return [r for r in self.records if r.in_use]


@dataclass
class PostTileData:
    """Everything decoded from the map stream after the tile array."""
    start_offset: int
    byte_size: int
    layout_version: str = ""
    status: DecodeStatus = DecodeStatus.MISSING
    status_detail: str = ""
    tables: List[RecordTable] = field(default_factory=list)

    @property
    def is_decoded(self) -> bool:
        """True if the block was decoded with every byte accounted for."""
        return self.status == DecodeStatus.DECODED

    def get_table(self, table_id: str) -> Optional[RecordTable]:
        """Retrieves a decoded table by its identifier, or None."""
        for table in self.tables:
            if table.layout.table_id == table_id:
                return table
        return None


@dataclass(slots=True)
class PlacedEntity:
    """Something standing on the map: a soldier, token, info item, turret part, ...

    Attributes:
        category: Kind of entity.
        x, y, z: Absolute grid cell and elevation level.
        source: Where it was decoded from (table id, or "cell flags").
        slot_index: Slot in the source table, or -1 for cell-flag entities.
        label: Short human-readable description.
        sprite_archive: Archive that draws it, when established; None draws a marker.
        sprite_frame: Frame within the archive.
        attributes: Further decoded properties.
        anomalies: Problems found while decoding (e.g. outside the playable window).
    """
    category: EntityCategory
    x: int
    y: int
    z: int
    source: str
    slot_index: int = -1
    label: str = ""
    sprite_archive: Optional[str] = None
    sprite_frame: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    anomalies: List[str] = field(default_factory=list)
