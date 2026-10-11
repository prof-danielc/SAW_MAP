"""Unit tests for companion .set file parser."""

from pathlib import Path
import pytest
from saw_map.formats.set_parser import TilesetParser


def test_synthetic_set_partitioning():
    """Validates partitioning into surfaces, left walls, right walls, and clutter."""
    synthetic_content = """Small test set
Defs
2 1 2 3
sgrass
sdirt
lwood
rwood1
rwood2
ctree
cstone
cbox
# Optional trailing comment
"""
    ts = TilesetParser.parse_text(synthetic_content, name="TestSet")
    assert ts.name == "TestSet"
    assert ts.surfaces == ["sgrass", "sdirt"]
    assert ts.left_walls == ["lwood"]
    assert ts.right_walls == ["rwood1", "rwood2"]
    assert ts.clutter == ["ctree", "cstone", "cbox"]


def test_missing_counts_raises_error():
    """Validates exception when count header line is absent."""
    invalid_content = """Some set
No numbers here
sgrass
lwood
"""
    with pytest.raises(ValueError, match="Could not find 4-integer count header"):
        TilesetParser.parse_text(invalid_content, name="BadSet")


def test_real_airfield_set_if_available():
    """Validates parsing real Airfield.set from Research directory."""
    path = Path("Research/SSI/Soldiers at War/Sets/Airfield.set")
    if not path.is_file():
        pytest.skip("Airfield.set not found in test environment")

    ts = TilesetParser.parse_file(path)
    assert ts.name == "Airfield"
    assert len(ts.surfaces) == 13
    assert len(ts.left_walls) == 12
    assert len(ts.right_walls) == 12
    assert len(ts.clutter) == 28
    assert "sgrass" in ts.surfaces
    assert "snwtree1" in ts.clutter


def test_set_parser_inline_comment_on_count_line():
    """Validates trailing '# ...' comments, as on the count line of Messina.set."""
    content = "\n".join([
        "Village near Messina, Italy.", "", "Defs", "", "1 1 1 2 # s l r c", "",
        "sgrass", "lwood1", "rwood1", "tree1 # oak", "crat1",
    ])
    ts = TilesetParser.parse_text(content, name="Messina")
    assert ts.surfaces == ["sgrass"]
    assert ts.left_walls == ["lwood1"]
    assert ts.right_walls == ["rwood1"]
    assert ts.clutter == ["tree1", "crat1"]
