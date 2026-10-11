"""Overlay text formatters for the HUD status bar and the map metadata dialog.

Decoupled data providers used by both the Arcade and Pygame graphics backends.
"""

from __future__ import annotations

import textwrap
from collections import Counter
from typing import List, Optional, Sequence, Tuple

from saw_map.maps.model import MapDocument, TilesetDefinition
from saw_map.maps.records import EntityCategory, PlacedEntity
from saw_map.viewer.camera import Camera
from saw_map.viewer.inspector import CellInspector


# Entity attributes already conveyed by the heading or of no interest in the sidebar
_HIDDEN_ATTRIBUTES = frozenset({"nationality", "group", "part", "soldier", "message", "item_class", "item_kind"})

# Popup messages are abbreviated to this many characters in the sidebar
_MESSAGE_PREVIEW = 44


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
            placed = [e for e in map_doc.entities_at(hx, hy, hz) if e.category != EntityCategory.MARKER]
            if placed:
                tile_info += f" <{placed[0].label}>"
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

        lines.extend(["", "MISSION CONTENT"])
        lines.extend(OverlayModel.get_entity_summary_lines(map_doc))

        if map_doc.mission_text:
            lines.extend(["", "MISSION BRIEFING"])
            for paragraph in map_doc.mission_text.splitlines():
                lines.extend(textwrap.wrap(paragraph, wrap_width) or [""])

        return lines

    @staticmethod
    def get_entity_summary_lines(map_doc: MapDocument) -> List[str]:
        """Summarises the decoded mission content: entity counts per category."""
        post_tile = map_doc.post_tile
        if post_tile is None:
            return ["No post-tile data loaded."]
        if not post_tile.is_decoded:
            return [f"Records not decoded: {post_tile.status_detail}"]

        counts = Counter(e.category for e in map_doc.entities)
        parts = [
            f"{label}: {counts[category]}"
            for category, label in (
                (EntityCategory.SOLDIER, "Soldiers"),
                (EntityCategory.RELOCATION, "Alternate Positions"),
                (EntityCategory.TOKEN, "Reinforcement Tokens"),
                (EntityCategory.INFO, "Information Tokens"),
                (EntityCategory.CANISTER, "Items / Canisters"),
                (EntityCategory.TURRET, "Turret Parts"),
                (EntityCategory.ITEM, "Items in Canisters"),
            )
        ]
        anomalies = sum(1 for e in map_doc.entities if e.anomalies)
        return [
            "   ".join(parts[:3]),
            "   ".join(parts[3:5]),
            "   ".join(parts[5:]),
            f"Editor Markers: {counts[EntityCategory.MARKER]}   Anomalies: {anomalies}",
        ]

    @staticmethod
    def get_entity_lines(entities: Sequence[PlacedEntity]) -> List[Tuple[str, str]]:
        """Formats the placed entities of a cell as (heading, detail) line pairs for the sidebar."""
        lines: List[Tuple[str, str]] = []
        for entity in entities:
            if entity.sprite_archive is not None:
                sprite = f"{entity.sprite_archive}.obj:{entity.sprite_frame}"
            else:
                sprite = "no sprite"
            source = entity.source if entity.slot_index < 0 else f"{entity.source}[{entity.slot_index}]"
            detail = f"{sprite} | {source}"
            shown = [f"{key}={value}" for key, value in entity.attributes.items() if key not in _HIDDEN_ATTRIBUTES]
            if shown:
                detail += " | " + " ".join(shown)
            message = entity.attributes.get("message")
            if message:
                preview = message if len(message) <= _MESSAGE_PREVIEW else message[:_MESSAGE_PREVIEW] + "..."
                detail += f' | "{preview}"'
            if entity.anomalies:
                detail += f" | ! {', '.join(entity.anomalies)}"
            lines.append((f"{entity.category.value}: {entity.label}", detail))
        return lines
