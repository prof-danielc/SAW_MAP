"""Overlay text formatters for the HUD status bar and the map metadata dialog.

Decoupled data providers used by both the Arcade and Pygame graphics backends.
"""

from __future__ import annotations

import textwrap
from typing import List, Optional, Tuple

from saw_map.maps.model import MapDocument, TilesetDefinition
from saw_map.viewer.camera import Camera
from saw_map.viewer.inspector import CellInspector


class OverlayModel:
    """Formats and prepares diagnostic information for display overlays."""

    @staticmethod
    def get_status_bar_text(
        map_doc: Optional[MapDocument],
        camera: Camera,
        hovered_cell: Optional[Tuple[int, int, int]],
        tileset: Optional[TilesetDefinition] = None,
    ) -> str:
        """Builds one-line formatted status bar string."""
        if not map_doc:
            return "No map loaded"

        parts: List[str] = [
            f"Map: {map_doc.name or map_doc.title} ({map_doc.width}x{map_doc.height})",
            f"View: {camera.perspective.value.upper()}",
            f"Layer: Z={camera.active_max_layer}/6",
            f"Zoom: {camera.zoom:.2f}x",
        ]

        if hovered_cell:
            hx, hy, hz = hovered_cell
            cell = map_doc.get_cell(hx, hy, hz)
            tile_info = ""
            if cell:
                info = CellInspector.inspect_cell(cell, tileset)
                if info.primary_tile_name:
                    tile_info = f" [{info.primary_tile_name}:{info.primary_tile_frame}]"
            parts.append(f"Hover: ({hx}, {hy}, {hz}){tile_info}")

        return " | ".join(parts)

    @staticmethod
    def get_map_metadata_lines(
        map_doc: Optional[MapDocument],
        tileset: Optional[TilesetDefinition],
        wrap_width: int = 76,
    ) -> List[str]:
        """Builds the lines of the map metadata dialog (map, tileset, mission briefing).

        Args:
            map_doc: Loaded map document, or None.
            tileset: Companion tileset definition, or None if unresolved.
            wrap_width: Maximum characters per line for the mission briefing.

        Returns:
            Display lines, top to bottom; empty strings are blank spacer lines.
        """
        if not map_doc:
            return ["No map document loaded."]

        lines = [
            f"MAP: {map_doc.name or map_doc.title}",
            f"Version: {map_doc.version}",
            f"Dimensions: {map_doc.width} x {map_doc.height} x {map_doc.layer_count}",
            f"Tileset: {', '.join(map_doc.tileset_names)}",
        ]

        if tileset:
            lines.extend([
                "",
                f"TILESET DEFINITION: {tileset.name}",
                f"Surfaces: {len(tileset.surfaces)}   Left Walls: {len(tileset.left_walls)}   "
                f"Right Walls: {len(tileset.right_walls)}   Clutter: {len(tileset.clutter)}",
            ])

        if map_doc.mission_text:
            lines.extend(["", "MISSION BRIEFING"])
            for paragraph in map_doc.mission_text.splitlines():
                lines.extend(textwrap.wrap(paragraph, wrap_width) or [""])

        return lines
