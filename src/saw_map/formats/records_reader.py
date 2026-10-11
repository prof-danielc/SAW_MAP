"""Generic reader for the post-tile record tables of a Soldiers at War map stream.

Driven by the declarative layouts of saw_map.formats.record_layout. Never raises for
malformed input: the outcome is reported through PostTileData.status so that the tile
grid of a map stays usable when its records cannot be decoded.
"""

from __future__ import annotations

import struct
from typing import Any, Dict, Sequence

from saw_map.diagnostics.logger import get_logger
from saw_map.formats.record_layout import get_layout, layout_byte_size
from saw_map.maps.records import (
    DecodeStatus,
    FieldKind,
    FieldSpec,
    PostTileData,
    Record,
    RecordTable,
    TableLayout,
    decode_cell_index,
)

logger = get_logger("formats.records_reader")


class RecordsReader:
    """Decodes the post-tile block of a decompressed map stream."""

    @classmethod
    def read(cls, data: bytes, start_offset: int, version: str) -> PostTileData:
        """Decodes the record tables that follow the tile array.

        Args:
            data: Complete decompressed map stream.
            start_offset: Offset of the first byte after the tile array.
            version: Stream version string from the map header (e.g. "21").

        Returns:
            PostTileData whose status tells whether and why decoding succeeded or not.
        """
        byte_size = max(0, len(data) - start_offset)
        result = PostTileData(start_offset=start_offset, byte_size=byte_size)

        if byte_size == 0:
            result.status = DecodeStatus.MISSING
            result.status_detail = "the stream ends after the tile array"
            return result

        layout = get_layout(version)
        if layout is None:
            result.status = DecodeStatus.UNSUPPORTED_VERSION
            result.status_detail = f"unsupported record layout for version {version}"
            return result

        expected = layout_byte_size(layout)
        if expected != byte_size:
            result.status = DecodeStatus.SIZE_MISMATCH
            result.status_detail = (
                f"version {version} layout needs {expected:,} bytes but the stream holds {byte_size:,}"
            )
            return result

        offset = start_offset
        for table_layout in layout:
            result.tables.append(cls._read_table(data, offset, table_layout))
            offset += table_layout.byte_size

        result.layout_version = version
        result.status = DecodeStatus.DECODED
        logger.debug(f"Decoded {len(result.tables)} post-tile tables ({byte_size:,} bytes)")
        return result

    @classmethod
    def _read_table(cls, data: bytes, offset: int, layout: TableLayout) -> RecordTable:
        """Reads all slots of one table."""
        table = RecordTable(layout=layout, offset=offset)
        size = layout.record_size
        for slot in range(layout.slot_count):
            start = offset + slot * size
            raw = bytes(data[start : start + size])
            values = cls._decode_fields(raw, layout.fields)
            table.records.append(
                Record(slot_index=slot, raw=raw, values=values, in_use=cls._is_in_use(raw, values, layout))
            )
        return table

    @staticmethod
    def _decode_fields(raw: bytes, fields: Sequence[FieldSpec]) -> Dict[str, Any]:
        """Decodes the fields of one record in stream order."""
        values: Dict[str, Any] = {}
        pos = 0
        for spec in fields:
            if spec.kind == FieldKind.U16:
                value: Any = struct.unpack_from("<H", raw, pos)[0]
            elif spec.kind == FieldKind.U32:
                value = struct.unpack_from("<I", raw, pos)[0]
            elif spec.kind == FieldKind.I32:
                value = struct.unpack_from("<i", raw, pos)[0]
            elif spec.kind == FieldKind.CELL_REF:
                value = decode_cell_index(struct.unpack_from("<I", raw, pos)[0])
            elif spec.kind == FieldKind.U16_ARRAY:
                value = struct.unpack_from(f"<{spec.size // 2}H", raw, pos)
            else:
                value = raw[pos : pos + spec.size]
            values[spec.name] = value
            pos += spec.size
        return values

    @staticmethod
    def _is_in_use(raw: bytes, values: Dict[str, Any], layout: TableLayout) -> bool:
        """Applies the table's rule that distinguishes used slots from unused ones."""
        if layout.unused_when_all_ff and raw.count(0xFF) == len(raw):
            return False
        if layout.used_cell_field is not None and values.get(layout.used_cell_field) is None:
            return False
        return True
