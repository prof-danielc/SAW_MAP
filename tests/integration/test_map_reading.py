"""Integration test verifying full map loading, decompression, and cell validation on Airfield.map."""

from pathlib import Path
import pytest
from saw_map.assets.loader import AssetLoader
from saw_map.formats.map_reader import MapReader
from saw_map.maps.model import ComponentType, MapDocument


def test_airfield_map_integration():
    """Validates loading Research/SSI/Soldiers at War/Single_g/Airfield.map."""
    map_path = Path("Research/SSI/Soldiers at War/Single_g/Airfield.map")
    if not map_path.is_file():
        pytest.skip("Airfield.map not present in research directory")

    assert MapReader.can_parse(map_path) is True

    doc: MapDocument = MapReader.parse_map(map_path)
    assert doc.title.lower() == "airfield"
    assert doc.version == "21"
    assert doc.layer_count == 7
    # Airfield has companion Airfield.txt specifying 104x80
    assert doc.width == 104
    assert doc.height == 80
    assert len(doc.cells) == 104 * 80 * 7
    # The playable window is centered inside the fixed 130x100 grid
    assert (doc.origin_x, doc.origin_y) == (13, 10)
    assert doc.contains(13, 10) and doc.contains(116, 89)
    assert not doc.contains(12, 10) and not doc.contains(117, 89)

    # Verify presence of terrain on layer 0
    ground_cells_with_floor = [
        cell for (x, y, z), cell in doc.cells.items()
        if z == 0 and cell.floor.is_present
    ]
    assert len(ground_cells_with_floor) > 1000

    # Verify cell accessor
    c0 = doc.get_cell(30, 30, 0)
    assert c0 is not None
    assert c0.x == 30 and c0.y == 30 and c0.z == 0
    assert doc.get_cell(5, 5, 0) is None

    # Tile (20, 18, 0): ssnow1 frame 3 ground surface, matching the Scenario Builder
    # screenshot Research/EditorScreenshots/airfield_tile_20_18_0_level_0_tile.png
    c = doc.get_cell(20, 18, 0)
    assert c is not None
    assert c.floor.raw_word == 0x8182
    assert c.left_wall.is_present is False
    assert c.right_wall.is_present is False
    assert c.flags == 0x001F0000

    # The header string names the companion tileset; the file stem names the map
    assert doc.tileset_names == ["Airfield"]
    assert doc.name == "Airfield"
    assert "German airfield" in doc.mission_text
    assert "104" not in doc.mission_text.splitlines()


def test_all_maps_reference_valid_registry_slots():
    """Every present word of every shipped map stays inside its tileset partition range."""
    game_dir = Path("Research/SSI/Soldiers at War")
    if not (game_dir / "Sets").is_dir():
        pytest.skip("Game directory not present in research directory")

    loader = AssetLoader(game_dir)
    map_paths = sorted(p for p in game_dir.rglob("*") if p.suffix.lower() == ".map")
    assert map_paths

    for map_path in map_paths:
        doc = MapReader.parse_map(map_path)
        tileset = loader.load_tileset(doc.tileset_names[0])
        assert tileset.surfaces, f"{map_path.name}: tileset '{doc.title}' not resolved"
        n_surf = len(tileset.surfaces)
        n_left = n_surf + len(tileset.left_walls)
        n_right = n_left + len(tileset.right_walls)
        n_set = n_right + len(tileset.clutter)

        for cell in doc.cells.values():
            if cell.floor.is_present:
                assert cell.floor.tileset_group_index < n_surf, map_path.name
            if cell.left_wall.is_present:
                assert n_surf <= cell.left_wall.tileset_group_index < n_left, map_path.name
            if cell.right_wall.is_present:
                assert n_left <= cell.right_wall.tileset_group_index < n_right, map_path.name
            if cell.clutter.is_present:
                assert cell.clutter.tileset_group_index < n_set, map_path.name
