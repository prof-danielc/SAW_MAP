"""Integration tests verifying loading, parsing, and cell consistency across multiple maps."""

from pathlib import Path
import pytest
from saw_map.formats.map_reader import MapReader
from saw_map.maps.model import MapDocument


@pytest.mark.parametrize("map_rel_path, expected_title, expected_dim", [
    ("Research/SSI/Soldiers at War/Single_g/Cassino.map", "Cassino", (52, 40)),
    ("Research/SSI/Soldiers at War/Single_g/Normandy.map", "Normandy", (78, 60)),
    ("Research/SSI/Soldiers at War/Single_g/Mansion.map", "Mansion", (104, 80)),
])
def test_load_multiple_original_maps(map_rel_path: str, expected_title: str, expected_dim: tuple[int, int]):
    """Validates decompression and parsing for several original campaign maps."""
    map_path = Path(map_rel_path)
    if not map_path.is_file():
        pytest.skip(f"Map file {map_rel_path} not found in research folder")

    assert MapReader.can_parse(map_path) is True
    doc: MapDocument = MapReader.parse_map(map_path)

    assert doc.title.lower() == expected_title.lower()
    assert doc.version in ("20", "21")
    assert doc.layer_count == 7
    exp_w, exp_h = expected_dim
    assert doc.width == exp_w
    assert doc.height == exp_h
    assert len(doc.cells) == exp_w * exp_h * 7

    # Verify at least some non-empty terrain exists
    non_empty = [c for c in doc.cells.values() if not c.is_empty()]
    assert len(non_empty) > 100
