"""Depth-sorting and draw-order calculation strategy for dimetric isometric rendering.

Ensures strict back-to-front rendering by elevation layer, isometric grid distance (X + Y),
sub-component priority (Floor -> Left Wall -> Right Wall -> Clutter), and row Y.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Optional

from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument, TilesetDefinition


@dataclass(slots=True)
class RenderItem:
    """An individual visual component scheduled for drawing."""
    grid_x: int
    grid_y: int
    grid_z: int
    component_type: ComponentType
    component: CellComponent
    asset_name: Optional[str]
    sprite_frame_index: int
    sort_key: tuple[int, int, int, int]


class DrawOrderStrategy:
    """Calculates draw orders and filters visible components."""

    @staticmethod
    def get_sort_key(z: int, x: int, y: int, comp_type: ComponentType) -> tuple[int, int, int, int]:
        """Calculates 4-element sort key: (layer_z, x + y, component_priority, y)."""
        return (z, x + y, int(comp_type), y)

    @classmethod
    def generate_render_list(
        cls,
        map_doc: MapDocument,
        tileset: Optional[TilesetDefinition] = None,
        max_layer: int = 6,
        isolated_layer: Optional[int] = None,
        show_floors: bool = True,
        show_left_walls: bool = True,
        show_right_walls: bool = True,
        show_clutter: bool = True,
    ) -> List[RenderItem]:
        """Collects, filters, and depth-sorts all visible components in the map document.

        Args:
            map_doc: The map document containing cells.
            tileset: Companion tileset definition for resolving asset names.
            max_layer: Maximum visible elevation layer (0..6).
            isolated_layer: If provided, only this specific layer is rendered.
            show_floors: Ground floor visibility toggle.
            show_left_walls: Left wall visibility toggle.
            show_right_walls: Right wall visibility toggle.
            show_clutter: Objects and clutter visibility toggle.

        Returns:
            Sorted list of RenderItem instances ready for drawing back-to-front.
        """
        items: List[RenderItem] = []

        type_visibility = {
            ComponentType.FLOOR: show_floors,
            ComponentType.LEFT_WALL: show_left_walls,
            ComponentType.RIGHT_WALL: show_right_walls,
            ComponentType.CLUTTER: show_clutter,
        }

        for (x, y, z), cell in map_doc.cells.items():
            # Check elevation filtering
            if isolated_layer is not None:
                if z != isolated_layer:
                    continue
            else:
                if z > max_layer:
                    continue

            if cell.is_empty():
                continue

            for declared_type, comp in (
                (ComponentType.FLOOR, cell.floor),
                (ComponentType.LEFT_WALL, cell.left_wall),
                (ComponentType.RIGHT_WALL, cell.right_wall),
                (ComponentType.CLUTTER, cell.clutter),
            ):
                if not comp.is_present:
                    continue

                # Filter out boundary / roof mask frames (>= 200)
                if comp.sprite_frame_index >= 200:
                    continue

                # Determine effective component type based on tileset registry if available
                effective_type = (
                    tileset.get_component_type_for_group(comp.tileset_group_index)
                    if tileset
                    else declared_type
                )

                if not type_visibility[effective_type]:
                    continue

                asset_name: Optional[str] = None
                if tileset:
                    asset_name = tileset.resolve_asset(effective_type, comp.tileset_group_index)
                    if asset_name is None:
                        continue

                sort_key = cls.get_sort_key(z, x, y, effective_type)
                items.append(
                    RenderItem(
                        grid_x=x,
                        grid_y=y,
                        grid_z=z,
                        component_type=effective_type,
                        component=comp,
                        asset_name=asset_name,
                        sprite_frame_index=comp.sprite_frame_index,
                        sort_key=sort_key,
                    )
                )

        # In-place sort by 4-tuple key
        items.sort(key=lambda item: item.sort_key)
        return items
