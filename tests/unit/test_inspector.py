"""Unit tests for cell inspection and 4-slot component decomposition."""

import pytest
from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument, TilesetDefinition
from saw_map.viewer.camera import ViewPerspective
from saw_map.viewer.inspector import CellInspector, CellInspectionInfo


@pytest.fixture
def sample_tileset() -> TilesetDefinition:
    """Fixture providing a mock tileset definition matching Airfield.set."""
    return TilesetDefinition(
        name="Airfield",
        surfaces=["sgrass", "shill", "ssnow1", "sdirt", "sstone1", "sstone3", "swood1", "swood2", "smetal1", "strack2"],
        left_walls=["lwood1", "lmetal1", "lmetal2"],
        right_walls=["rwood1", "rmetal1", "rmetal2"],
        clutter=["snwtree1", "crock4", "csnow1"],
    )


def test_inspect_cell_tile_20_18_0(sample_tileset: TilesetDefinition):
    """Validates decomposition of Airfield tile (20, 18, 0) components."""
    # w0 = 0xFF93 (presence=1, frame=255, group=19) -> Height Mask
    comp0 = CellComponent.from_raw_word(ComponentType.FLOOR, 0xFF93)
    # w1 = 0x0000 (presence=0) -> Empty Left Wall
    comp1 = CellComponent.from_raw_word(ComponentType.LEFT_WALL, 0x0000)
    # w2 = 0x001F (presence=0) -> Empty Right Wall
    comp2 = CellComponent.from_raw_word(ComponentType.RIGHT_WALL, 0x001F)
    # w3 = 0x8182 (presence=1, frame=3, group=2) -> ssnow1 ground surface
    comp3 = CellComponent.from_raw_word(ComponentType.CLUTTER, 0x8182)

    cell = MapCell(
        x=20,
        y=18,
        z=0,
        floor=comp0,
        left_wall=comp1,
        right_wall=comp2,
        clutter=comp3,
        elevation_attr=1,
        flags=0x25000000,
    )

    info = CellInspector.inspect_cell(cell, sample_tileset)

    assert info.coord == (20, 18, 0)
    assert info.elevation_attr == 1
    assert info.flags == 0x25000000
    assert len(info.components) == 4

    # Slot 0: Roof / Ceiling mask
    slot0 = info.components[0]
    assert slot0.slot_name == "Roof / Ceiling"
    assert slot0.is_present is True
    assert slot0.raw_word == 0xFF93
    assert slot0.is_mask is True
    assert slot0.sprite_frame_index == 255
    assert "Mask" in slot0.semantic_role

    # Slot 1: Left Wall (empty)
    slot1 = info.components[1]
    assert slot1.slot_name == "Left Wall"
    assert slot1.is_present is False
    assert slot1.status_label == "EMPTY"

    # Slot 2: Right Wall (empty)
    slot2 = info.components[2]
    assert slot2.slot_name == "Right Wall"
    assert slot2.is_present is False
    assert slot2.status_label == "EMPTY"

    # Slot 3: Procedural Ground Surface (ssnow1, frame 3)
    slot3 = info.components[3]
    assert slot3.slot_name == "Surface / Clutter"
    assert slot3.is_present is True
    assert slot3.raw_word == 0x8182
    assert slot3.tileset_group_index == 2
    assert slot3.sprite_frame_index == 3
    assert slot3.asset_name == "ssnow1"
    assert slot3.semantic_role == "Ground Surface"
    assert "ssnow1" in slot3.details_line

    # Primary tile identification
    assert info.primary_tile_name == "ssnow1.obj"
    assert info.primary_tile_frame == 3
    assert info.primary_tile_label == "ssnow1.obj (Frame 3)"


def test_inspect_cell_empty():
    """Validates inspection on completely empty cell."""
    comp = CellComponent(ComponentType.FLOOR, False, 0, 0, 0)
    cell = MapCell(
        x=0,
        y=0,
        z=0,
        floor=comp,
        left_wall=CellComponent(ComponentType.LEFT_WALL, False, 0, 0, 0),
        right_wall=CellComponent(ComponentType.RIGHT_WALL, False, 0, 0, 0),
        clutter=CellComponent(ComponentType.CLUTTER, False, 0, 0, 0),
        elevation_attr=0,
        flags=0,
    )

    info = CellInspector.inspect_cell(cell)
    assert info.primary_tile_name is None
    assert info.primary_tile_frame is None
    assert info.primary_tile_label == "Empty Cell"
    for c in info.components:
        assert c.is_present is False
        assert c.status_label == "EMPTY"
        assert c.asset_name is None


def test_selection_polygon_isometric():
    """Validates 4-vertex diamond polygon generation in isometric mode."""
    inspector = CellInspector()
    pts = inspector.get_selection_polygon((20, 18, 0), ViewPerspective.ISOMETRIC)
    assert len(pts) == 4
    # world_to_screen(20, 18, 0) = (128.0, 1216.0)
    top, right, bottom, left = pts
    assert top == (128.0, 1216.0)
    assert right == (192.0, 1248.0)
    assert bottom == (128.0, 1280.0)
    assert left == (64.0, 1248.0)


def test_selection_polygon_top_down():
    """Validates 4-vertex square polygon generation in top-down mode."""
    inspector = CellInspector()
    pts = inspector.get_selection_polygon((10, 5, 0), ViewPerspective.TOP_DOWN)
    assert len(pts) == 4
    # cell_size = 32.0 -> (320.0, 160.0)
    assert pts == [
        (320.0, 160.0),
        (352.0, 160.0),
        (352.0, 192.0),
        (320.0, 192.0),
    ]
