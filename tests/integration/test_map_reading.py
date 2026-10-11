"""Integration test verifying full map loading, decompression, and cell validation on Airfield.map."""

from pathlib import Path
import pytest
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

    # Verify presence of terrain on layer 0
    ground_cells_with_floor = [
        cell for (x, y, z), cell in doc.cells.items()
        if z == 0 and cell.floor.is_present
    ]
    assert len(ground_cells_with_floor) > 1000

    # Verify cell accessor
    c0 = doc.get_cell(10, 10, 0)
    assert c0 is not None
    assert c0.x == 10 and c0.y == 10 and c0.z == 0
