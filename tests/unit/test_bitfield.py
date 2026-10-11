"""Unit tests for 16-bit cell component bitmask unpacking and domain models."""

import pytest
from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument, TilesetDefinition


def test_bitmask_unpacking_present_component():
    """Validates bitmask extraction when bit 15 is set.

    Example word: 0x8182 (airfield tile at 20, 18, 0)
    Binary: 1 00000011 0000010 -> bit 15 = 1, frame = 3, group = 2 (ssnow1)
    """
    raw_word = (1 << 15) | (3 << 7) | 2
    comp = CellComponent.from_raw_word(ComponentType.FLOOR, raw_word)

    assert comp.is_present is True
    assert comp.tileset_group_index == 2
    assert comp.sprite_frame_index == 3
    assert comp.raw_word == raw_word
    assert comp.component_type == ComponentType.FLOOR


def test_bitmask_unpacking_absent_component():
    """Validates bitmask extraction when bit 15 is 0."""
    raw_word = (0 << 15) | (3 << 7) | 12
    comp = CellComponent.from_raw_word(ComponentType.LEFT_WALL, raw_word)

    assert comp.is_present is False
    assert comp.tileset_group_index == 12
    assert comp.sprite_frame_index == 3


def test_bitmask_boundary_values():
    """Validates maximum allowed values for group (7 bits = 127) and frame (8 bits = 255)."""
    raw_word = (1 << 15) | (255 << 7) | 127
    comp = CellComponent.from_raw_word(ComponentType.CLUTTER, raw_word)

    assert comp.is_present is True
    assert comp.tileset_group_index == 127
    assert comp.sprite_frame_index == 255

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


def test_floor_empty_and_surface_unpacking():
    """Validates reverse-engineered floor word conventions (0x0000 = empty; 0xFFxx = surface with variations)."""
    # 0x0000 is empty
    comp_zero = CellComponent.from_raw_word(ComponentType.FLOOR, 0x0000)
    assert comp_zero.is_present is False

    # 0x8182: present, group=2 (ssnow1), frame=3
    comp_target = CellComponent.from_raw_word(ComponentType.FLOOR, 0x8182)
    assert comp_target.is_present is True
    assert comp_target.tileset_group_index == 2
    assert comp_target.sprite_frame_index == 3

    # 0xFF93: present, group=19, frame=255
    comp_mask = CellComponent.from_raw_word(ComponentType.FLOOR, 0xFF93)
    assert comp_mask.is_present is True
    assert comp_mask.tileset_group_index == 19
    assert comp_mask.sprite_frame_index == 255


def test_tileset_global_clutter_and_winter_snow_resolution():
    """Validates winter snow replacement on surface 0 and GLOBAL_CLUTTER resolution."""
    ts = TilesetDefinition(
        name="Airfield",
        surfaces=["sgrass", "shill", "ssnow1", "sdirt"],
        left_walls=["lwood1"],
        right_walls=["rwood1"],
        clutter=["snwtree1", "crock4"],
    )

    # In winter tileset containing ssnow1, surface 0 (sgrass) resolves to ssnow1
    assert ts.resolve_asset(ComponentType.FLOOR, 0) == "ssnow1"
    assert ts.resolve_asset(ComponentType.FLOOR, 1) == "shill"
    assert ts.resolve_asset(ComponentType.FLOOR, 2) == "ssnow1"
    assert ts.resolve_asset(ComponentType.FLOOR, 3) == "sdirt"

    # Clutter from tileset
    assert ts.resolve_asset(ComponentType.CLUTTER, 0) == "snwtree1"
    assert ts.resolve_asset(ComponentType.CLUTTER, 1) == "crock4"

    # Global clutter extension (group_idx >= 2)
    assert ts.resolve_asset(ComponentType.CLUTTER, 2) == "People"
    assert ts.resolve_asset(ComponentType.CLUTTER, 3) == "Can"
    assert ts.resolve_asset(ComponentType.CLUTTER, 4) == "Turret"
    assert ts.resolve_asset(ComponentType.CLUTTER, 5) == "Token"
    assert ts.resolve_asset(ComponentType.CLUTTER, 6) == "Specials"
    assert ts.resolve_asset(ComponentType.CLUTTER, 7) == "Cgendam"
    assert ts.resolve_asset(ComponentType.CLUTTER, 8) == "Newtree1"


