"""Unit and integration tests for map objects (planes, fences, trees, clutter) rendering."""

from pathlib import Path
import pytest

from saw_map.formats.map_reader import MapReader
from saw_map.formats.set_parser import TilesetParser
from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument, TilesetDefinition
from saw_map.rendering.draw_order import DrawOrderStrategy, RenderItem
from saw_map.viewer.inspector import CellInspector


@pytest.fixture
def airfield_tileset() -> TilesetDefinition:
    """Fixture matching Airfield.set partitions."""
    return TilesetDefinition(
        name="Airfield",
        surfaces=["sgrass", "shill", "ssnow1", "sdirt", "sstone1"],
        left_walls=["lwood1", "lmetal1", "lbarb"],
        right_walls=["rwood1", "rmetal1", "rbarb"],
        clutter=["snwtree1", "crock4", "cplane1", "cplane2"],
    )


def test_map_cell_clutter_object_properties():
    """Validates MapCell.has_clutter_object, clutter_object_group, and clutter_object_frame."""
    # flags with bit 31 set and group 58 (0x3A): 0xBA000000
    # floor word storing frame 14: 0xFF0E (w0 & 0x7F = 14)
    cell = MapCell(
        x=53,
        y=55,
        z=0,
        floor=CellComponent.from_raw_word(ComponentType.FLOOR, 0xFF0E),
        left_wall=CellComponent.from_raw_word(ComponentType.LEFT_WALL, 0),
        right_wall=CellComponent.from_raw_word(ComponentType.RIGHT_WALL, 0),
        clutter=CellComponent.from_raw_word(ComponentType.CLUTTER, 0),
        elevation_attr=1,
        flags=0xBA000000,
    )

    assert cell.has_clutter_object is True
    assert cell.clutter_object_group == 58
    assert cell.clutter_object_frame == 14
    assert cell.is_empty() is False
    assert cell.has_visual_content() is True


def test_map_cell_no_clutter_object_when_bit31_unset():
    """Footprint cell with group 58 but bit 31 unset should not be a visible clutter object."""
    cell = MapCell(
        x=46,
        y=43,
        z=0,
        floor=CellComponent.from_raw_word(ComponentType.FLOOR, 0xFF00),
        left_wall=CellComponent.from_raw_word(ComponentType.LEFT_WALL, 0),
        right_wall=CellComponent.from_raw_word(ComponentType.RIGHT_WALL, 0),
        clutter=CellComponent.from_raw_word(ComponentType.CLUTTER, 0),
        elevation_attr=1,
        flags=0x3A000000,  # bit 31 is 0
    )

    assert cell.has_clutter_object is False
    assert cell.clutter_object_group == 58


def test_draw_order_extracts_clutter_objects(airfield_tileset: TilesetDefinition):
    """Validates that DrawOrderStrategy emits RenderItem for clutter objects in cell.flags."""
    # Create map doc with 1 ground tile and 1 plane tile
    cell_plane = MapCell(
        x=50,
        y=50,
        z=0,
        floor=CellComponent.from_raw_word(ComponentType.FLOOR, 0xFF05),  # frame 5
        left_wall=CellComponent.from_raw_word(ComponentType.LEFT_WALL, 0),
        right_wall=CellComponent.from_raw_word(ComponentType.RIGHT_WALL, 0),
        clutter=CellComponent.from_raw_word(ComponentType.CLUTTER, 0x8182),  # ssnow1 ground
        elevation_attr=1,
        flags=0x80000000 | (13 << 24),  # group 13 in airfield_tileset is cplane1
    )

    map_doc = MapDocument(
        title="TestMap",
        version="20",
        width=60,
        height=60,
        cells={(50, 50, 0): cell_plane},
    )

    items = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset)

    # Should have ground floor (ssnow1) AND clutter object (cplane1)
    assert len(items) == 2
    types = [it.component_type for it in items]
    assert ComponentType.FLOOR in types
    assert ComponentType.CLUTTER in types

    clutter_item = next(it for it in items if it.component_type == ComponentType.CLUTTER)
    assert clutter_item.asset_name == "cplane1"
    assert clutter_item.sprite_frame_index == 5
    assert clutter_item.grid_x == 50
    assert clutter_item.grid_y == 50


def test_draw_order_wall_frame_remapping(airfield_tileset: TilesetDefinition):
    """Validates that wall/fence items with frame 254 or 255 remap to frame 0."""
    # group 7 in airfield_tileset is lbarb (left_walls[2], 5 surfaces + 2 = index 7)
    # raw_word with frame 255 and group 7: (1 << 15) | (255 << 7) | 7 = 0xFF87
    cell_fence = MapCell(
        x=20,
        y=20,
        z=0,
        floor=CellComponent.from_raw_word(ComponentType.FLOOR, 0xFF87),
        left_wall=CellComponent.from_raw_word(ComponentType.LEFT_WALL, 0),
        right_wall=CellComponent.from_raw_word(ComponentType.RIGHT_WALL, 0),
        clutter=CellComponent.from_raw_word(ComponentType.CLUTTER, 0),
        elevation_attr=1,
        flags=0,
    )

    map_doc = MapDocument(
        title="TestMap",
        version="20",
        width=30,
        height=30,
        cells={(20, 20, 0): cell_fence},
    )

    items = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset)
    assert len(items) == 1
    item = items[0]
    assert item.component_type == ComponentType.LEFT_WALL
    assert item.asset_name == "lbarb"
    assert item.sprite_frame_index == 0


def test_draw_order_clutter_toggle(airfield_tileset: TilesetDefinition):
    """Validates that show_clutter=False filters out clutter objects."""
    cell = MapCell(
        x=10,
        y=10,
        z=0,
        floor=CellComponent.from_raw_word(ComponentType.FLOOR, 0),
        left_wall=CellComponent.from_raw_word(ComponentType.LEFT_WALL, 0),
        right_wall=CellComponent.from_raw_word(ComponentType.RIGHT_WALL, 0),
        clutter=CellComponent.from_raw_word(ComponentType.CLUTTER, 0x8182),
        elevation_attr=1,
        flags=0x80000000 | (11 << 24),  # group 11 = snwtree1
    )
    map_doc = MapDocument(title="Test", version="20", width=25, height=25, cells={(10, 10, 0): cell})

    # With clutter enabled
    items_all = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset, show_clutter=True)
    assert len(items_all) == 2  # ground + tree

    # With clutter disabled
    items_no_clutter = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset, show_clutter=False)
    assert len(items_no_clutter) == 1  # only ground


def test_cell_inspector_clutter_object_primary_tile(airfield_tileset: TilesetDefinition):
    """Validates that CellInspector identifies clutter object as primary tile when present."""
    cell = MapCell(
        x=50,
        y=50,
        z=1,
        floor=CellComponent.from_raw_word(ComponentType.FLOOR, 0xFF02),
        left_wall=CellComponent.from_raw_word(ComponentType.LEFT_WALL, 0),
        right_wall=CellComponent.from_raw_word(ComponentType.RIGHT_WALL, 0),
        clutter=CellComponent.from_raw_word(ComponentType.CLUTTER, 0),
        elevation_attr=1,
        flags=0x80000000 | (13 << 24),  # cplane1
    )
    info = CellInspector.inspect_cell(cell, airfield_tileset)
    assert info.primary_tile_name == "cplane1.obj"
    assert info.primary_tile_frame == 2
    assert "cplane1.obj (Frame 2)" in info.primary_tile_label


def test_airfield_real_map_objects():
    """Integration test verifying real Airfield map renders planes, fences, and trees."""
    map_path = Path("Research/SSI/Soldiers at War/Single_g/Airfield.map")
    set_path = Path("Research/SSI/Soldiers at War/Sets/Airfield.set")
    if not map_path.is_file() or not set_path.is_file():
        pytest.skip("Airfield scenario files not present")

    doc = MapReader.parse_map(map_path)
    tileset = TilesetParser.parse_file(set_path)
    items = DrawOrderStrategy.generate_render_list(doc, tileset, max_layer=6)

    # Check that planes, fences, and trees are present in the render list
    assets = {it.asset_name for it in items}
    assert "cplane1" in assets
    assert "cplane2" in assets
    assert "lbarb" in assets
    assert "snwtree1" in assets

    # Count clutter and wall items
    clutter_items = [it for it in items if it.component_type == ComponentType.CLUTTER]
    wall_items = [it for it in items if it.component_type in (ComponentType.LEFT_WALL, ComponentType.RIGHT_WALL)]

    assert len(clutter_items) >= 2000
    assert len(wall_items) >= 1000
