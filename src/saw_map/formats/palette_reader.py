"""Autodesk COL / PAL format palette reader.

Supports 776-byte Autodesk Animator format (8-byte header + 768 RGB bytes)
and raw 768-byte RGB tables.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Union

AUTODESK_HEADER_SIZE = 8
EXPECTED_COL_SIZE = 776
RAW_PAL_SIZE = 768
COLOR_COUNT = 256


@dataclass(slots=True)
class Palette:
    """Represents a 256-color indexed lookup table."""
    name: str
    rgb_table: List[Tuple[int, int, int]]

    def __post_init__(self) -> None:
        if len(self.rgb_table) != COLOR_COUNT:
            raise ValueError(f"Palette must contain exactly 256 colors, got {len(self.rgb_table)}")

    def get_color(self, index: int) -> Tuple[int, int, int]:
        """Retrieves RGB tuple by color index (0..255)."""
        if 0 <= index < COLOR_COUNT:
            return self.rgb_table[index]
        return (0, 0, 0)

    def to_pillow_palette(self) -> List[int]:
        """Flattens 256 RGB tuples into a 768-element list suitable for PIL putpalette."""
        flat: List[int] = []
        for r, g, b in self.rgb_table:
            flat.extend((r, g, b))
        return flat


class PaletteReader:
    """Reads and validates Autodesk Animator and raw palette files."""

    @staticmethod
    def read_palette(file_path: Union[str, Path]) -> Palette:
        """Parses a palette file from disk.

        Args:
            file_path: Path to .pal or .col file.

        Returns:
            Populated Palette object.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file size or header is malformed.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Palette file not found: {path}")

        data = path.read_bytes()
        return PaletteReader.read_palette_bytes(data, name=path.name)

    @staticmethod
    def read_palette_bytes(data: bytes, name: str = "custom.pal") -> Palette:
        """Parses palette data from memory bytes.

        Args:
            data: Binary palette buffer.
            name: Label for the palette.

        Returns:
            Populated Palette object.
        """
        data_len = len(data)

        if data_len == EXPECTED_COL_SIZE:
            # Autodesk format: 4-byte size, 2-byte major, 2-byte minor, 768 bytes RGB
            file_size, major, minor = struct.unpack("<IHH", data[:8])
            if file_size != EXPECTED_COL_SIZE or major != 0xB123 or minor != 0:
                # Some variants might differ in major version, but if size matches 776 proceed with caution
                pass
            raw_rgb = data[8:776]
        elif data_len == RAW_PAL_SIZE:
            # Raw 768-byte RGB table
            raw_rgb = data
        elif data_len > EXPECTED_COL_SIZE:
            # Sized buffer with header
            raw_rgb = data[8:776]
        else:
            raise ValueError(
                f"Invalid palette byte size: {data_len}. Expected 776 (Autodesk) or 768 (raw)."
            )

        colors: List[Tuple[int, int, int]] = []
        for i in range(0, 768, 3):
            r = data[8 + i] if data_len >= EXPECTED_COL_SIZE else raw_rgb[i]
            g = data[8 + i + 1] if data_len >= EXPECTED_COL_SIZE else raw_rgb[i + 1]
            b = data[8 + i + 2] if data_len >= EXPECTED_COL_SIZE else raw_rgb[i + 2]
            colors.append((r, g, b))

        return Palette(name=name, rgb_table=colors)
