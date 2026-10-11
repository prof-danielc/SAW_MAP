"""Unit tests for 16-bit cell component bitmask unpacking and domain models."""

import pytest
from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument, TilesetDefinition


def test_bitmask_unpacking_present_component():
    """Validates bitmask extraction when bit 15 is set.

    Example word: 0x8285
    Binary: 1 00000101 0000101 -> bit 15 = 1, group = 5, frame = 5
    """
    raw_word = (1 << 15) | (5 << 7) | 5
    comp = CellComponent.from_raw_word(ComponentType.FLOOR, raw_word)

    assert comp.is_present is True
    assert comp.tileset_group_index == 5
    assert comp.sprite_frame_index == 5
    assert comp.raw_word == raw_word
    assert comp.component_type == ComponentType.FLOOR


def test_bitmask_unpacking_absent_component():
    """Validates bitmask extraction when bit 15 is 0."""
    raw_word = (0 << 15) | (12 << 7) | 3
    comp = CellComponent.from_raw_word(ComponentType.LEFT_WALL, raw_word)

    assert comp.is_present is False
    assert comp.tileset_group_index == 12
    assert comp.sprite_frame_index == 3


def test_bitmask_boundary_values():
    """Validates maximum allowed values for group (8 bits = 255) and frame (7 bits = 127)."""
    raw_word = (1 << 15) | (255 << 7) | 127
    comp = CellComponent.from_raw_word(ComponentType.CLUTTER, raw_word)

    assert comp.is_present is True
    assert comp.tileset_group_index == 255
    assert comp.sprite_frame_index == 127

    # Zero word
    comp_zero = CellComponent.from_raw_word(ComponentType.RIGHT_WALL, 0)
    assert comp_zero.is_present is False
    assert comp_zero.tileset_group_index == 0
    assert comp_zero.sprite_frame_index == 0


def test_map_cell_is_empty():
    """Validates MapCell.is_empty method."""
    empty_comp = CellComponent.from_raw_word(ComponentType.FLOOR, 0)
    empty_cell = MapCell(
        x=10, y=10, z=0,
        floor=empty_comp,
        left_wall=CellComponent.from_raw_word(ComponentType.LEFT_WALL, 0),
        right_wall=CellComponent.from_raw_word(ComponentType.RIGHT_WALL, 0),
        clutter=CellComponent.from_raw_word(ComponentType.CLUTTER, 0),
    )
    assert empty_cell.is_empty() is True

    populated_cell = MapCell(
        x=10, y=10, z=0,
        floor=CellComponent.from_raw_word(ComponentType.FLOOR, (1 << 15) | 1),
        left_wall=empty_comp,
        right_wall=empty_comp,
        clutter=empty_comp,
    )
    assert populated_cell.is_empty() is False


def test_tileset_definition_resolve():
    """Validates asset name resolution across partitioned categories."""
    ts = TilesetDefinition(
        name="Airfield",
        surfaces=["sgrass", "shill"],
        left_walls=["lwood1", "lwood2"],
        right_walls=["rwood1"],
        clutter=["tree1", "crat1"],
    )

    assert ts.resolve_asset(ComponentType.FLOOR, 0) == "sgrass"
    assert ts.resolve_asset(ComponentType.FLOOR, 1) == "shill"
    assert ts.resolve_asset(ComponentType.FLOOR, 2) is None

    assert ts.resolve_asset(ComponentType.LEFT_WALL, 1) == "lwood2"
    assert ts.resolve_asset(ComponentType.RIGHT_WALL, 0) == "rwood1"
    assert ts.resolve_asset(ComponentType.CLUTTER, 1) == "crat1"
    assert ts.resolve_asset(ComponentType.CLUTTER, 99) is None


def test_map_document_validation():
    """Validates MapDocument boundary checks."""
    doc = MapDocument(
        title="TestMap",
        version="21",
        width=104,
        height=80,
        layer_count=7,
    )
    assert doc.title == "TestMap"
    assert doc.width == 104
    assert doc.height == 80

    # Invalid version
    with pytest.raises(ValueError, match="Unsupported map version"):
        MapDocument(title="Bad", version="19", width=50, height=50)

    # Invalid width
    with pytest.raises(ValueError, match="width 15 outside valid range"):
        MapDocument(title="Bad", version="21", width=15, height=50)

    # Invalid layer count
    with pytest.raises(ValueError, match="layer_count 5 must equal 7"):
        MapDocument(title="Bad", version="21", width=50, height=50, layer_count=5)
