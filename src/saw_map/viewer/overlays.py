"""Overlay definitions and text formatters for HUD status bar, sidebar, and metadata dialog.

Decoupled data providers usable by both Arcade and Pygame graphics backends.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from saw_map.maps.model import ComponentType, MapCell, MapDocument, TilesetDefinition
from saw_map.viewer.camera import Camera


class OverlayModel:
    """Formats and prepares diagnostic information for display overlays."""

    @staticmethod
    def get_status_bar_text(
        map_doc: Optional[MapDocument],
        camera: Camera,
        hovered_cell: Optional[Tuple[int, int, int]],
    ) -> str:
        """Builds one-line formatted status bar string."""
        if not map_doc:
            return "No map loaded"

        parts: List[str] = [
            f"Map: {map_doc.title} ({map_doc.width}x{map_doc.height})",
            f"View: {camera.perspective.value.upper()}",
            f"Layer: Z={camera.active_max_layer}/6",
            f"Zoom: {camera.zoom:.2f}x",
        ]

        if hovered_cell:
            hx, hy, hz = hovered_cell
            cell = map_doc.get_cell(hx, hy, hz)
            comp_desc = "empty"
            if cell and not cell.is_empty():
                c_parts = []
                if cell.floor.is_present:
                    c_parts.append(f"Flr:{cell.floor.tileset_group_index}:{cell.floor.sprite_frame_index}")
                if cell.left_wall.is_present:
                    c_parts.append(f"LWall:{cell.left_wall.tileset_group_index}:{cell.left_wall.sprite_frame_index}")
                if cell.right_wall.is_present:
                    c_parts.append(f"RWall:{cell.right_wall.tileset_group_index}:{cell.right_wall.sprite_frame_index}")
                if cell.clutter.is_present:
                    c_parts.append(f"Clut:{cell.clutter.tileset_group_index}:{cell.clutter.sprite_frame_index}")
                comp_desc = " ".join(c_parts)
            parts.append(f"Hover: ({hx}, {hy}, {hz}) [{comp_desc}]")

        return " | ".join(parts)

    @staticmethod
    def get_sidebar_info(
        map_doc: Optional[MapDocument],
        tileset: Optional[TilesetDefinition],
        hovered_cell: Optional[Tuple[int, int, int]],
    ) -> Dict[str, str]:
        """Builds structured key-value pairs for the detailed inspection panel."""
        info: Dict[str, str] = {}
        if not map_doc or not hovered_cell:
            return info

        hx, hy, hz = hovered_cell
        info["Coordinate"] = f"({hx}, {hy}, {hz})"

        cell = map_doc.get_cell(hx, hy, hz)
        if not cell:
            info["Status"] = "Unpopulated / Out of Bounds"
            return info

        info["Elevation Byte"] = str(cell.elevation_attr)
        info["Flags"] = f"0x{cell.flags:08X}"

        for comp_name, comp_type, comp in (
            ("Floor", ComponentType.FLOOR, cell.floor),
            ("Left Wall", ComponentType.LEFT_WALL, cell.left_wall),
            ("Right Wall", ComponentType.RIGHT_WALL, cell.right_wall),
            ("Clutter", ComponentType.CLUTTER, cell.clutter),
        ):
            if comp.is_present:
                asset = tileset.resolve_asset(comp_type, comp.tileset_group_index) if tileset else None
                info[comp_name] = (
                    f"Asset: {asset or 'Unknown'} | Group: {comp.tileset_group_index} | "
                    f"Frame: {comp.sprite_frame_index}"
                )
            else:
                info[comp_name] = "None"

        return info

    @staticmethod
    def get_map_metadata_dialog_text(
        map_doc: Optional[MapDocument],
        tileset: Optional[TilesetDefinition],
        mission_text: Optional[str] = None,
    ) -> str:
        """Builds formatted help & mission summary dialog text."""
        if not map_doc:
            return "No map document loaded."

        lines = [
            f"=== MAP METADATA: {map_doc.title} ===",
            f"Version: {map_doc.version}",
            f"Dimensions: {map_doc.width} x {map_doc.height} x {map_doc.layer_count}",
            f"Total Loaded Cells: {len(map_doc.cells):,}",
            f"Tilesets Referenced: {', '.join(map_doc.tileset_names)}",
        ]

        if tileset:
            lines.extend([
                f"\n=== TILESET DEFINITION: {tileset.name} ===",
                f"Surfaces: {len(tileset.surfaces)}",
                f"Left Walls: {len(tileset.left_walls)}",
                f"Right Walls: {len(tileset.right_walls)}",
                f"Clutter: {len(tileset.clutter)}",
            ])

        if mission_text:
            lines.extend([
                "\n=== MISSION BRIEFING ===",
                mission_text.strip(),
            ])

        return "\n".join(lines)
