"""Unit tests for post-tile record layouts and the generic records reader."""

import struct
from typing import Dict, Tuple

import pytest

from saw_map.formats.record_layout import (
    TABLE_INFO_ITEMS,
    TABLE_ITEMS,
    TABLE_SOLDIER_POSITIONS,
    TABLE_TOKENS,
    TABLE_WINDOW,
    get_layout,
    layout_byte_size,
)
from saw_map.formats.records_reader import RecordsReader
from saw_map.maps.records import (
    DecodeStatus,
    EvidenceStatus,
    FieldKind,
    FieldSpec,
    decode_cell_index,
    encode_cell_index,
)

V21_BYTES = 31366


def build_block(patches: Dict[Tuple[str, int], bytes]) -> bytes:
    """Builds a zero-filled version 21 post-tile block with selected records replaced."""
    out = bytearray()
    for table in get_layout("21"):
        for slot in range(table.slot_count):
            record = patches.get((table.table_id, slot), bytes(table.record_size))
            assert len(record) == table.record_size
            out += record
    return bytes(out)


def test_v21_layout_size_and_uniqueness():
    """The version 21 layout totals the bytes that follow the tile array in shipped maps."""
    layout = get_layout("21")
    assert layout is not None
    assert layout_byte_size(layout) == V21_BYTES
    assert len(layout) == 19
    ids = [t.table_id for t in layout]
    assert len(set(ids)) == len(ids)
    for table in layout:
        names = [f.name for f in table.fields]
        assert len(set(names)) == len(names), table.table_id
        assert table.source_reference, table.table_id


def test_layout_record_sizes_match_decompiled_read_sequence():
    """Record sizes follow the read calls of the engine's loader."""
    sizes = {t.table_id: (t.slot_count, t.record_size) for t in get_layout("21")}
    assert sizes[TABLE_INFO_ITEMS] == (40, 18)
    assert sizes[TABLE_TOKENS] == (40, 6)
    assert sizes[TABLE_SOLDIER_POSITIONS] == (40, 14)
    assert sizes["T-550538"] == (10, 180)
    assert sizes[TABLE_WINDOW] == (1, 18)
    assert sizes["T-847E50"] == (40, 424)
    assert sizes[TABLE_ITEMS] == (500, 18)


def test_confirmed_fields_cite_evidence():
    """Every confirmed field carries an evidence note; unknown versions have no layout."""
    for table in get_layout("21"):
        for spec in table.fields:
            if spec.status == EvidenceStatus.CONFIRMED:
                assert spec.note, f"{table.table_id}.{spec.name}"
    assert get_layout("19") is None

    with pytest.raises(ValueError, match="must cite its evidence"):
        FieldSpec("x", FieldKind.U16, 2, EvidenceStatus.CONFIRMED)


def test_cell_index_round_trip():
    """Validates the linear cell index used by record tables."""
    assert decode_cell_index(encode_cell_index(44, 41, 0)) == (44, 41, 0)
    assert decode_cell_index(9187) == (87, 70, 0)
    assert decode_cell_index(20219) == (69, 55, 1)
    assert decode_cell_index(0xFFFFFFFF) is None
    assert decode_cell_index(91000) is None


def test_reader_decodes_synthetic_block():
    """Field values, raw bytes, and slot usage are decoded from a synthetic stream."""
    soldier = struct.pack("<IHHIH", encode_cell_index(44, 41, 0), 0, 0xFFFF, 0xFFFFFFFF, 88)
    token = struct.pack("<IH", encode_cell_index(75, 88, 0), 8)
    window = struct.pack("<4iH", 117, 90, 13, 10, 0)
    unused_info_item = b"\xFF" * 18
    block = build_block({
        (TABLE_SOLDIER_POSITIONS, 17): soldier,
        (TABLE_TOKENS, 0): token,
        (TABLE_TOKENS, 1): struct.pack("<IH", 0xFFFFFFFF, 3),
        (TABLE_WINDOW, 0): window,
        (TABLE_INFO_ITEMS, 5): unused_info_item,
    })
    prefix = b"\x00" * 100
    result = RecordsReader.read(prefix + block, len(prefix), "21")

    assert result.status == DecodeStatus.DECODED
    assert result.is_decoded
    assert result.byte_size == V21_BYTES
    assert sum(t.layout.byte_size for t in result.tables) == result.byte_size
    assert result.tables[0].offset == 100

    soldiers = result.get_table(TABLE_SOLDIER_POSITIONS)
    record = soldiers.records[17]
    assert record.raw == soldier
    assert record.values == {"cell": (44, 41, 0), "hidden": 0, "field_12": 0xFFFF, "alternate_cell": None, "frame": 88}
    assert record.in_use is True

    tokens = result.get_table(TABLE_TOKENS)
    assert tokens.records[0].in_use is True
    assert tokens.records[1].in_use is False  # no valid cell
    assert 1 not in [r.slot_index for r in tokens.used_records]

    assert result.get_table(TABLE_WINDOW).records[0].values["min_x"] == 13
    assert result.get_table(TABLE_INFO_ITEMS).records[5].in_use is False
    assert result.get_table("T-000000") is None


def test_reader_reports_instead_of_raising():
    """Unknown versions, wrong sizes, and missing data yield a status, never an exception."""
    block = build_block({})

    unsupported = RecordsReader.read(block, 0, "19")
    assert unsupported.status == DecodeStatus.UNSUPPORTED_VERSION
    assert "version 19" in unsupported.status_detail
    assert unsupported.tables == []

    truncated = RecordsReader.read(block[:-20], 0, "21")
    assert truncated.status == DecodeStatus.SIZE_MISMATCH
    assert "31,366" in truncated.status_detail and "31,346" in truncated.status_detail
    assert truncated.tables == []

    oversized = RecordsReader.read(block + b"\x00", 0, "21")
    assert oversized.status == DecodeStatus.SIZE_MISMATCH

    missing = RecordsReader.read(b"\x00" * 10, 10, "21")
    assert missing.status == DecodeStatus.MISSING
    assert missing.byte_size == 0
