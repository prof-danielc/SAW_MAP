"""Binary parser for Soldiers at War map documents (.map).

Supports gzip and uncompressed containers, version 19, 20 and 21 AMB_MAP headers,
and 3D cell array extraction across 7 vertical elevation layers.
"""

from __future__ import annotations

import gzip
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from saw_map.diagnostics.logger import get_logger
from saw_map.maps.model import (
    SUPPORTED_MAP_VERSIONS,
    CellComponent,
    ComponentType,
    MapCell,
    MapDocument,
)

logger = get_logger("formats.map_reader")

GZIP_MAGIC = b"\x1f\x8b"
AMB_SIGNATURE = b"AMB_MAP"
EXPECTED_LAYERS = 7
GRID_MAX_WIDTH = 130
GRID_MAX_HEIGHT = 100
CELL_BYTE_SIZE = 13
CELLS_PER_LAYER = GRID_MAX_WIDTH * GRID_MAX_HEIGHT
PRESENCE_BIT = 0x8000
GROUP_MASK = 0x7F
# version (2) + signature (8) + tileset name (128) + 55 bytes of editor/view state
HEADER_ARRAY_OFFSET = 193


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
                        return str(ver) in SUPPORTED_MAP_VERSIONS and sig == AMB_SIGNATURE
                return False
            else:
                if len(head) >= 10:
                    ver = struct.unpack("<H", head[:2])[0]
                    sig = head[2:9]
                    return str(ver) in SUPPORTED_MAP_VERSIONS and sig == AMB_SIGNATURE
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
        if version_str not in SUPPORTED_MAP_VERSIONS:
            raise ValueError(
                f"Unsupported map version: {version_str}. Expected 19, 20 or 21."
            )

        title_raw = data[10:138]
        title = title_raw.split(b"\x00")[0].decode("latin-1", errors="replace").strip()
        if not title:
            title = path.stem
        logger.debug(f"Map header verified: version={version_str}, title='{title}'")

        # Parse 3D cell array
        # Array dimensions: 7 layers x 100 rows x 130 columns x 13 bytes
        tile_start = HEADER_ARRAY_OFFSET
        required_bytes = CELLS_PER_LAYER * EXPECTED_LAYERS * CELL_BYTE_SIZE

        if len(data) < tile_start + required_bytes:
            raise ValueError(
                f"Map stream truncated: expected at least {tile_start + required_bytes:,} bytes, "
                f"got {len(data):,} bytes"
            )

        raw_cells = list(struct.iter_unpack("<HHHHBI", data[tile_start : tile_start + required_bytes]))

        # Discover the playable window (companion .txt dimensions and stored content)
        mission_lines = cls._read_mission_lines(path)
        origin_x, origin_y, width, height = cls._discover_active_window(
            raw_cells, mission_lines, override_width, override_height
        )
        logger.info(
            f"Loaded map '{path.stem}' (tileset '{title}'): active window {width}x{height} "
            f"at ({origin_x}, {origin_y}) (max 130x100x7)"
        )

        # Unpack cells of the playable window into coordinate dictionary
        cells: Dict[Tuple[int, int, int], MapCell] = {}
        for z in range(EXPECTED_LAYERS):
            for y in range(origin_y, origin_y + height):
                row_start = (z * CELLS_PER_LAYER) + (y * GRID_MAX_WIDTH)
                for x in range(origin_x, origin_x + width):
                    w0, w1, w2, w3, b4, dw5 = raw_cells[row_start + x]
                    cells[(x, y, z)] = MapCell(
                        x=x,
                        y=y,
                        z=z,
                        floor=CellComponent.from_raw_word(ComponentType.FLOOR, w0),
                        left_wall=CellComponent.from_raw_word(ComponentType.LEFT_WALL, w1),
                        right_wall=CellComponent.from_raw_word(ComponentType.RIGHT_WALL, w2),
                        clutter=CellComponent.from_raw_word(ComponentType.CLUTTER, w3),
                        elevation_attr=b4,
                        flags=dw5,
                    )

        # The header string names the companion tileset (Sets/<title>.set)
        tileset_names = [title]

        return MapDocument(
            title=title,
            version=version_str,
            width=width,
            height=height,
            layer_count=EXPECTED_LAYERS,
            tileset_names=tileset_names,
            cells=cells,
            name=path.stem,
            mission_text=cls._extract_mission_text(mission_lines),
            origin_x=origin_x,
            origin_y=origin_y,
        )

    @staticmethod
    def _read_mission_lines(map_path: Path) -> List[str]:
        """Reads the non-empty lines of the companion mission .txt file, if present."""
        companion_txt = map_path.with_suffix(".txt")
        if not companion_txt.is_file():
            # Check case-insensitive
            for f in map_path.parent.glob("*.txt"):
                if f.stem.lower() == map_path.stem.lower():
                    companion_txt = f
                    break

        if not companion_txt.is_file():
            return []
        try:
            text = companion_txt.read_text(encoding="latin-1")
        except OSError as exc:
            logger.warning(f"Could not read companion mission file {companion_txt.name}: {exc}")
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]

    @staticmethod
    def _extract_mission_text(mission_lines: List[str]) -> str:
        """Returns the briefing text preceding the '<index> : <status>' objective lines."""
        briefing: List[str] = []
        for line in mission_lines:
            head, sep, tail = line.partition(":")
            if sep and head.strip().isdigit() and tail.strip().isdigit():
                break
            briefing.append(line)
        else:
            # No objective block: drop the trailing width / height / seed integers
            while briefing and briefing[-1].isdigit():
                briefing.pop()
        return "\n".join(briefing)

    @staticmethod
    def _declared_dimensions(mission_lines: List[str]) -> Optional[Tuple[int, int]]:
        """Reads the playable width and height from the trailing integers of the mission file.

        The file ends with width, height, and a seed (version 21), or with width and
        height only (version 19 Demo map).
        """
        trailing: List[int] = []
        for line in reversed(mission_lines):
            if not line.isdigit():
                break
            trailing.insert(0, int(line))

        if len(trailing) >= 3:
            cand_w, cand_h = trailing[-3], trailing[-2]
        elif len(trailing) == 2:
            cand_w, cand_h = trailing
        else:
            return None
        if 20 <= cand_w <= GRID_MAX_WIDTH and 20 <= cand_h <= GRID_MAX_HEIGHT:
            return (cand_w, cand_h)
        return None

    @staticmethod
    def _content_bounds(raw_cells: List[Tuple[int, ...]]) -> Optional[Tuple[int, int, int, int]]:
        """Computes the (min_x, min_y, max_x, max_y) bounds of authored map content.

        Cells outside the playable window only hold the editor's default ground fill
        (a layer-0 floor of surface group 0), which is not counted as content.
        """
        min_x, min_y, max_x, max_y = GRID_MAX_WIDTH, GRID_MAX_HEIGHT, -1, -1
        for idx, (w0, w1, w2, w3, _, _) in enumerate(raw_cells):
            has_content = (w1 | w2 | w3) & PRESENCE_BIT or (
                w0 & PRESENCE_BIT and (w0 & GROUP_MASK or idx >= CELLS_PER_LAYER)
            )
            if not has_content:
                continue
            y, x = divmod(idx % CELLS_PER_LAYER, GRID_MAX_WIDTH)
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y

        if max_x < 0:
            return None
        return (min_x, min_y, max_x, max_y)

    @classmethod
    def _discover_active_window(
        cls,
        raw_cells: List[Tuple[int, ...]],
        mission_lines: List[str],
        override_w: Optional[int],
        override_h: Optional[int],
    ) -> Tuple[int, int, int, int]:
        """Determines the playable window as (origin_x, origin_y, width, height).

        The engine centers a W x H playable area inside the fixed 130x100 grid. W and H
        come from the explicit overrides or the companion mission .txt file. Content
        stored outside that window (leftovers of maps authored at a larger size, such
        as Mansion and Normandy) is not part of the playable map.

        Without declared dimensions, the bounds of the authored content are used
        instead (heuristic), falling back to the full grid.
        """
        dims: Optional[Tuple[int, int]] = None
        if (
            override_w is not None
            and override_h is not None
            and 20 <= override_w <= GRID_MAX_WIDTH
            and 20 <= override_h <= GRID_MAX_HEIGHT
        ):
            dims = (override_w, override_h)
        else:
            dims = cls._declared_dimensions(mission_lines)

        if dims is not None:
            width, height = dims
            return ((GRID_MAX_WIDTH - width) // 2, (GRID_MAX_HEIGHT - height) // 2, width, height)

        content = cls._content_bounds(raw_cells)
        if content is not None:
            min_x, min_y, max_x, max_y = content
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            if width >= 20 and height >= 20:
                logger.debug(
                    f"No declared map dimensions; using content bounds x {min_x}..{max_x}, y {min_y}..{max_y}"
                )
                return (min_x, min_y, width, height)

        return (0, 0, GRID_MAX_WIDTH, GRID_MAX_HEIGHT)
