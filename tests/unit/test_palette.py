"""Unit tests for palette reader."""

import os
import struct
from pathlib import Path
import pytest
from saw_map.formats.palette_reader import Palette, PaletteReader


def test_synthetic_autodesk_palette():
    """Validates Autodesk 776-byte structure parsing."""
    header = struct.pack("<IHH", 776, 0xB123, 0)
    rgb_data = bytearray()
    for i in range(256):
        rgb_data.extend([i, (i * 2) % 256, (i * 3) % 256])

    raw = header + bytes(rgb_data)
    pal = PaletteReader.read_palette_bytes(raw, name="synthetic.col")

    assert len(pal.rgb_table) == 256
    assert pal.get_color(0) == (0, 0, 0)
    assert pal.get_color(1) == (1, 2, 3)
    assert pal.get_color(10) == (10, 20, 30)


def test_synthetic_raw_palette():
    """Validates raw 768-byte palette parsing without 8-byte header."""
    rgb_data = bytearray()
    for i in range(256):
        rgb_data.extend([255 - i, i, 128])

    pal = PaletteReader.read_palette_bytes(bytes(rgb_data), name="raw.pal")
    assert len(pal.rgb_table) == 256
    assert pal.get_color(0) == (255, 0, 128)
    assert pal.get_color(255) == (0, 255, 128)


def test_invalid_palette_size():
    """Validates rejection of malformed buffer sizes."""
    with pytest.raises(ValueError, match="Invalid palette byte size"):
        PaletteReader.read_palette_bytes(b"\x00" * 500)


def test_load_real_win_pal():
    """Validates reading real Research/SSI/Soldiers at War/Misc/Win.pal if it exists."""
    path = Path("Research/SSI/Soldiers at War/Misc/Win.pal")
    if not path.is_file():
        pytest.skip("Original Win.pal not available in test environment")

    pal = PaletteReader.read_palette(path)
    assert len(pal.rgb_table) == 256
    # Verify that not all colors are pure black
    distinct_colors = set(pal.rgb_table)
    assert len(distinct_colors) > 10
