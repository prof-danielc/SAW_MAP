"""Unit and integration tests for map objects (planes, fences, trees, clutter) rendering."""

from pathlib import Path
import pytest

from saw_map.formats.map_reader import MapReader
from saw_map.formats.set_parser import TilesetParser
from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument, TilesetDefinition
from saw_map.rendering.draw_order import DrawOrderStrategy
from saw_map.viewer.inspector import CellInspector


@pytest.fixture
def airfield_tileset() -> TilesetDefinition:
    """Reduced fixture following the Airfield.set partition order.

    Flat registry: 0..4 surfaces, 5..7 left walls, 8..10 right walls, 11..14 clutter.
    """
    return TilesetDefinition(
        name="Airfield",
        surfaces=["sgrass", "shill", "ssnow1", "sdirt", "sstone1"],
        left_walls=["lwood1", "lmetal1", "lbarb"],
        right_walls=["rwood1", "rmetal1", "rbarb"],
        clutter=["snwtree1", "crock4", "cplane1", "cplane2"],
    )


def word(group: int, frame: int) -> int:
    """Packs a present component word."""
    return (1 << 15) | (frame << 7) | group


def make_cell(
    x: int, y: int, z: int, w0: int = 0, w1: int = 0, w2: int = 0, w3: int = 0, flags: int = 0x001F0000
) -> MapCell:
    """Builds a MapCell from 4 raw component words."""
    return MapCell(
        x=x,
        y=y,
        z=z,
        floor=CellComponent.from_raw_word(ComponentType.FLOOR, w0),
        left_wall=CellComponent.from_raw_word(ComponentType.LEFT_WALL, w1),
        right_wall=CellComponent.from_raw_word(ComponentType.RIGHT_WALL, w2),
        clutter=CellComponent.from_raw_word(ComponentType.CLUTTER, w3),
        elevation_attr=0xFF,
        flags=flags,
    )


def test_map_cell_visual_content():
    """Validates is_empty / has_visual_content for clutter-only and default cells."""
    # Upper-level plane piece: only word 3 present
    plane_cell = make_cell(48, 41, 1, w3=0x893B)
    assert plane_cell.is_empty() is False
    assert plane_cell.has_visual_content() is True

    # Default air cell: word 1 holds 0x0001 with the presence bit clear
    air_cell = make_cell(48, 41, 5, w1=0x0001)
    assert air_cell.is_empty() is True
    assert air_cell.has_visual_content() is False


def test_draw_order_emits_floor_and_clutter(airfield_tileset: TilesetDefinition):
    """Validates that word 0 yields the floor and word 3 the clutter object of a cell."""
    cell = make_cell(50, 50, 0, w0=word(3, 1), w3=word(13, 5))
    map_doc = MapDocument(title="TestMap", version="20", width=60, height=60, cells={(50, 50, 0): cell})

    items = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset)

    assert [it.component_type for it in items] == [ComponentType.FLOOR, ComponentType.CLUTTER]
    floor_item, clutter_item = items
    assert floor_item.asset_name == "sdirt"
    assert floor_item.sprite_frame_index == 1
    assert clutter_item.asset_name == "cplane1"
    assert clutter_item.sprite_frame_index == 5
    assert (clutter_item.grid_x, clutter_item.grid_y) == (50, 50)


def test_draw_order_walls_use_stored_frame(airfield_tileset: TilesetDefinition):
    """Validates that wall words resolve through the flat registry with their own frame index."""
    cell = make_cell(20, 20, 0, w1=word(7, 4), w2=word(10, 2))
    map_doc = MapDocument(title="TestMap", version="20", width=30, height=30, cells={(20, 20, 0): cell})

    items = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset)

    assert len(items) == 2
    left, right = items
    assert left.component_type == ComponentType.LEFT_WALL
    assert left.asset_name == "lbarb"
    assert left.sprite_frame_index == 4
    assert right.component_type == ComponentType.RIGHT_WALL
    assert right.asset_name == "rbarb"
    assert right.sprite_frame_index == 2


def test_draw_order_unresolved_group_keeps_placeholder_item(airfield_tileset: TilesetDefinition):
    """A group outside the registry is still emitted (asset_name None) so a placeholder is drawn."""
    cell = make_cell(10, 10, 0, w3=word(120, 0))
    map_doc = MapDocument(title="Test", version="20", width=25, height=25, cells={(10, 10, 0): cell})

    items = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset)
    assert len(items) == 1
    assert items[0].asset_name is None


def test_draw_order_clutter_toggle(airfield_tileset: TilesetDefinition):
    """Validates that show_clutter=False filters out word 3 objects only."""
    cell = make_cell(10, 10, 0, w0=word(2, 3), w3=word(11, 0))
    map_doc = MapDocument(title="Test", version="20", width=25, height=25, cells={(10, 10, 0): cell})

    items_all = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset, show_clutter=True)
    assert len(items_all) == 2  # ground + tree

    items_no_clutter = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset, show_clutter=False)
    assert [it.asset_name for it in items_no_clutter] == ["ssnow1"]


def test_draw_order_floor_cover_level(airfield_tileset: TilesetDefinition):
    """A floor is skipped once the view level reaches its cover level (flags bits 18..20)."""
    # Ground floor covered by a level-2 floor: flags bits 18..20 = 2 -> 0x000B0000
    covered = make_cell(10, 10, 0, w0=word(3, 0), flags=0x000B0000)
    roof = make_cell(10, 10, 2, w0=word(4, 0))
    map_doc = MapDocument(
        title="Test", version="20", width=25, height=25, cells={(10, 10, 0): covered, (10, 10, 2): roof}
    )

    # View level 6: the ground floor is hidden under the level-2 floor
    top = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset, max_layer=6)
    assert [(it.grid_z, it.asset_name) for it in top] == [(2, "sstone1")]

    # View level 1: the covering floor is sliced away, the ground floor is drawn
    sliced = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset, max_layer=1)
    assert [(it.grid_z, it.asset_name) for it in sliced] == [(0, "sdirt")]

    # Isolating layer 0 always shows its floor
    isolated = DrawOrderStrategy.generate_render_list(map_doc, airfield_tileset, isolated_layer=0)
    assert [(it.grid_z, it.asset_name) for it in isolated] == [(0, "sdirt")]


def test_cell_inspector_clutter_primary_tile_without_floor(airfield_tileset: TilesetDefinition):
    """Validates that the clutter object is the primary tile when the cell has no floor."""
    cell = make_cell(50, 50, 1, w3=word(13, 2))
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
    assert {"cplane1", "cplane2", "lbarb", "rbarb", "snwtree1", "ssnow1"} <= assets
    assert None not in assets

    # Every item's component type matches the registry partition of its group
    for it in items:
        if it.component_type != ComponentType.CLUTTER:
            assert tileset.get_component_type_for_group(it.component.tileset_group_index) == it.component_type

    clutter_items = [it for it in items if it.component_type == ComponentType.CLUTTER]
    wall_items = [it for it in items if it.component_type in (ComponentType.LEFT_WALL, ComponentType.RIGHT_WALL)]
    assert len(clutter_items) >= 2000
    assert len(wall_items) >= 1000

    # The Ju 52 fuselage at (49, 41, 0) is cplane2 frame 17 standing on dirt
    plane_cell = doc.get_cell(49, 41, 0)
    assert plane_cell is not None
    assert tileset.resolve_flat_asset(plane_cell.floor.tileset_group_index) == "sdirt"
    assert tileset.resolve_flat_asset(plane_cell.clutter.tileset_group_index) == "cplane2"
    assert plane_cell.clutter.sprite_frame_index == 17
