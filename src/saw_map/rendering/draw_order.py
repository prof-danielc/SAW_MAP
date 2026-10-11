"""Depth-sorting and draw-order calculation strategy for dimetric isometric rendering.

Ensures strict back-to-front rendering by elevation layer, isometric grid distance (X + Y),
sub-component priority (Floor -> Left Wall -> Right Wall -> Clutter -> Entity), and row Y.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from saw_map.maps.model import CellComponent, ComponentType, MapDocument, TilesetDefinition
from saw_map.maps.records import EntityCategory, PlacedEntity


@dataclass(slots=True)
class RenderItem:
    """An individual visual component or placed entity scheduled for drawing.

    Exactly one of `component` (a cell word) and `entity` (a placed entity) is set.
    """
    grid_x: int
    grid_y: int
    grid_z: int
    component_type: ComponentType
    component: Optional[CellComponent]
    asset_name: Optional[str]
    sprite_frame_index: int
    sort_key: tuple[int, int, int, int]
    entity: Optional[PlacedEntity] = None


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
        show_entities: bool = True,
        show_markers: bool = False,
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
            show_entities: Placed entities (soldiers, tokens, info items, ...) visibility toggle.
            show_markers: Editor markers derived from cell flags visibility toggle.

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
            elif z > max_layer:
                continue

            if cell.is_empty():
                continue

            # Word 0..3 map one-to-one onto floor, left wall, right wall, and clutter;
            # each word indexes the flat tileset registry (SAW_TD sub_4508F9 / sub_451610).
            for comp in (cell.floor, cell.left_wall, cell.right_wall, cell.clutter):
                if not comp.is_present or not type_visibility[comp.component_type]:
                    continue

                # The engine skips a floor once the view level reaches its cover level
                # (flags bits 18..20), because a higher floor then hides it.
                if (
                    comp.component_type == ComponentType.FLOOR
                    and isolated_layer is None
                    and z < cell.roof_cutoff_layer <= max_layer
                ):
                    continue

                asset_name = tileset.resolve_flat_asset(comp.tileset_group_index) if tileset else None
                items.append(
                    RenderItem(
                        grid_x=x,
                        grid_y=y,
                        grid_z=z,
                        component_type=comp.component_type,
                        component=comp,
                        asset_name=asset_name,
                        sprite_frame_index=comp.sprite_frame_index,
                        sort_key=cls.get_sort_key(z, x, y, comp.component_type),
                    )
                )

        # Placed entities are drawn after the clutter of their own cell. Soldiers the
        # engine does not draw (hidden flag) stay listed in the inspector only.
        for entity in map_doc.entities:
            if entity.category == EntityCategory.MARKER:
                if not show_markers:
                    continue
            elif not show_entities or entity.attributes.get("hidden"):
                continue

            if isolated_layer is not None:
                if entity.z != isolated_layer:
                    continue
            elif entity.z > max_layer:
                continue

            items.append(
                RenderItem(
                    grid_x=entity.x,
                    grid_y=entity.y,
                    grid_z=entity.z,
                    component_type=ComponentType.ENTITY,
                    component=None,
                    asset_name=entity.sprite_archive,
                    sprite_frame_index=entity.sprite_frame or 0,
                    sort_key=cls.get_sort_key(entity.z, entity.x, entity.y, ComponentType.ENTITY),
                    entity=entity,
                )
            )

        # In-place sort by 4-tuple key
        items.sort(key=lambda item: item.sort_key)
        return items
