"""Binary parser for Soldiers at War map documents (.map).

Supports gzip and uncompressed containers, version 20 and 21 AMB_MAP headers,
and 3D cell array extraction across 7 vertical elevation layers.
"""

from __future__ import annotations

import gzip
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from saw_map.diagnostics.logger import get_logger
from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument

logger = get_logger("formats.map_reader")

GZIP_MAGIC = b"\x1f\x8b"
AMB_SIGNATURE = b"AMB_MAP"
EXPECTED_LAYERS = 7
GRID_MAX_WIDTH = 130
GRID_MAX_HEIGHT = 100
CELL_BYTE_SIZE = 13
HEADER_ARRAY_OFFSET = 187


class MapReader:
    """Parses Soldiers at War binary map files into MapDocument domain objects."""

    @classmethod
    def can_parse(cls, file_path: Union[str, Path]) -> bool:
        """Inspects file signature to verify AMB_MAP format support."""
        path = Path(file_path)
        if not path.is_file():
            return False

        try:
            head = path.read_bytes()[:16]
            if len(head) < 2:
                return False

            if head[:2] == GZIP_MAGIC:
                with gzip.open(path, "rb") as gz:
                    decomp = gz.read(16)
                    if len(decomp) >= 10:
                        ver = struct.unpack("<H", decomp[:2])[0]
                        sig = decomp[2:9]
                        return ver in (20, 21) and sig == AMB_SIGNATURE
                return False
            else:
                if len(head) >= 10:
                    ver = struct.unpack("<H", head[:2])[0]
                    sig = head[2:9]
                    return ver in (20, 21) and sig == AMB_SIGNATURE
        except Exception:
            return False

        return False

    @classmethod
    def parse_map(
        cls,
        file_path: Union[str, Path],
        override_width: Optional[int] = None,
        override_height: Optional[int] = None,
    ) -> MapDocument:
        """Parses a Soldiers at War .map file into a MapDocument.

        Args:
            file_path: Path to the .map file.
            override_width: Optional active width override.
            override_height: Optional active height override.

        Returns:
            Populated MapDocument instance.

        Raises:
            FileNotFoundError: If the map file is not found.
            ValueError: If decompression or header validation fails.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Map file not found: {path}")

        raw_bytes = path.read_bytes()
        logger.debug(f"Read {len(raw_bytes)} bytes from {path.name}")

        # Auto-detect Gzip compression
        if raw_bytes[:2] == GZIP_MAGIC:
            logger.debug("Detected Gzip header (1F 8B); decompressing in-memory")
            try:
                data = gzip.decompress(raw_bytes)
            except Exception as exc:
                raise ValueError(f"Failed to decompress gzip map stream: {exc}") from exc
        else:
            logger.debug("Treating as uncompressed raw map stream")
            data = raw_bytes

        logger.debug(f"Decompressed stream size: {len(data):,} bytes")
        if len(data) < HEADER_ARRAY_OFFSET:
            raise ValueError(f"Stream size {len(data)} too small for valid map header")

        # Parse header
        version_num = struct.unpack("<H", data[:2])[0]
        version_str = str(version_num)
        signature = data[2:9]
        if signature != AMB_SIGNATURE:
            raise ValueError(
                f"Invalid map signature: {signature!r}. Expected {AMB_SIGNATURE!r}"
            )
        if version_str not in ("20", "21"):
            raise ValueError(
                f"Unsupported map version: {version_str}. Expected 20 or 21."
            )

        title_raw = data[10:138]
        title = title_raw.split(b"\x00")[0].decode("latin-1", errors="replace").strip()
        if not title:
            title = path.stem
        logger.debug(f"Map header verified: version={version_str}, title='{title}'")

        # Discover active dimensions (check companion .txt first if available)
        width, height = cls._discover_dimensions(path, override_width, override_height)
        logger.info(f"Loaded map '{title}': active dimensions {width}x{height} (max 130x100x7)")

        # Parse 3D cell array
        # Array dimensions: 7 layers x 100 rows x 130 columns x 13 bytes
        cells: Dict[Tuple[int, int, int], MapCell] = {}
        tile_start = HEADER_ARRAY_OFFSET
        total_cells = EXPECTED_LAYERS * GRID_MAX_HEIGHT * GRID_MAX_WIDTH
        required_bytes = total_cells * CELL_BYTE_SIZE

        if len(data) < tile_start + required_bytes:
            raise ValueError(
                f"Map stream truncated: expected at least {tile_start + required_bytes:,} bytes, "
                f"got {len(data):,} bytes"
            )

        # Unpack cells into coordinate dictionary
        for z in range(EXPECTED_LAYERS):
            for y in range(height):
                for x in range(width):
                    idx = (z * GRID_MAX_HEIGHT * GRID_MAX_WIDTH) + (y * GRID_MAX_WIDTH) + x
                    cell_offset = tile_start + (idx * CELL_BYTE_SIZE)
                    chunk = data[cell_offset : cell_offset + CELL_BYTE_SIZE]

                    w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", chunk)

                    floor = CellComponent.from_raw_word(ComponentType.FLOOR, w0)
                    left_wall = CellComponent.from_raw_word(ComponentType.LEFT_WALL, w1)
                    right_wall = CellComponent.from_raw_word(ComponentType.RIGHT_WALL, w2)
                    clutter = CellComponent.from_raw_word(ComponentType.CLUTTER, w3)

                    cell = MapCell(
                        x=x,
                        y=y,
                        z=z,
                        floor=floor,
                        left_wall=left_wall,
                        right_wall=right_wall,
                        clutter=clutter,
                        elevation_attr=b4,
                        flags=dw5,
                    )
                    cells[(x, y, z)] = cell

        tileset_names = [title] if title else [path.stem]

        return MapDocument(
            title=title,
            version=version_str,
            width=width,
            height=height,
            layer_count=EXPECTED_LAYERS,
            tileset_names=tileset_names,
            cells=cells,
        )

    @staticmethod
    def _discover_dimensions(
        map_path: Path,
        override_w: Optional[int],
        override_h: Optional[int],
    ) -> Tuple[int, int]:
        """Discovers active grid dimensions from parameters or companion mission .txt file."""
        if override_w is not None and override_h is not None:
            if 20 <= override_w <= GRID_MAX_WIDTH and 20 <= override_h <= GRID_MAX_HEIGHT:
                return (override_w, override_h)

        # Check for companion .txt in same directory
        companion_txt = map_path.with_suffix(".txt")
        if not companion_txt.is_file():
            # Check case-insensitive
            parent = map_path.parent
            for f in parent.glob("*.txt"):
                if f.stem.lower() == map_path.stem.lower():
                    companion_txt = f
                    break

        if companion_txt.is_file():
            try:
                lines = [l.strip() for l in companion_txt.read_text(encoding="latin-1").splitlines() if l.strip()]
                # Typically the 2nd and 3rd lines from the end are width and height
                if len(lines) >= 3:
                    cand_w = int(lines[-3])
                    cand_h = int(lines[-2])
                    if 20 <= cand_w <= GRID_MAX_WIDTH and 20 <= cand_h <= GRID_MAX_HEIGHT:
                        return (cand_w, cand_h)
            except Exception:
                pass

        # Default standard map size
        return (GRID_MAX_WIDTH, GRID_MAX_HEIGHT)
