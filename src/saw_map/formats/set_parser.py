"""Parser for Soldiers at War companion tileset definition files (.set).

Partitions tileset asset names into surfaces (floors), left walls, right walls,
and clutter based on the header line count definitions.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Union

from saw_map.maps.model import TilesetDefinition


class TilesetParser:
    """Parses companion .set files into structured TilesetDefinition instances."""

    @classmethod
    def parse_file(cls, file_path: Union[str, Path]) -> TilesetDefinition:
        """Parses a .set file from disk.

        Args:
            file_path: Path to .set file.

        Returns:
            TilesetDefinition populated with partitioned asset names.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If header counts cannot be found or data is malformed.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Tileset file not found: {path}")

        content = path.read_text(encoding="latin-1", errors="replace")
        return cls.parse_text(content, name=path.stem)

    @classmethod
    def parse_text(cls, content: str, name: str = "custom") -> TilesetDefinition:
        """Parses .set content from a text string.

        Args:
            content: Raw text content of the .set file.
            name: Identifier for the tileset (usually filename stem).

        Returns:
            TilesetDefinition populated with partitioned asset names.
        """
        raw_lines = [line.strip() for line in content.splitlines()]

        # Filter out empty lines and comment lines
        lines: List[str] = []
        for line in raw_lines:
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            lines.append(line)

        # Locate the line with 4 integers
        count_idx = -1
        counts: List[int] = []
        for i, line in enumerate(lines):
            tokens = line.split()
            if len(tokens) == 4 and all(t.isdigit() for t in tokens):
                count_idx = i
                counts = [int(t) for t in tokens]
                break

        if count_idx == -1:
            raise ValueError(f"Could not find 4-integer count header in tileset definition '{name}'")

        n_surfaces, n_left_walls, n_right_walls, n_clutter = counts
        asset_lines = lines[count_idx + 1 :]

        surfaces: List[str] = []
        left_walls: List[str] = []
        right_walls: List[str] = []
        clutter: List[str] = []

        curr = 0
        surfaces = asset_lines[curr : curr + n_surfaces]
        curr += n_surfaces

        left_walls = asset_lines[curr : curr + n_left_walls]
        curr += n_left_walls

        right_walls = asset_lines[curr : curr + n_right_walls]
        curr += n_right_walls

        clutter = asset_lines[curr : curr + n_clutter]

        return TilesetDefinition(
            name=name,
            surfaces=surfaces,
            left_walls=left_walls,
            right_walls=right_walls,
            clutter=clutter,
        )
