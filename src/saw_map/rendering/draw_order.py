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
                cutoff_limit = isolated_layer
            else:
                if z > max_layer:
                    continue
                cutoff_limit = max_layer

            if cell.is_empty():
                continue

            # 1. Roof / Ceiling geometry from cell.floor (Word 0)
            # In the Soldiers at War engine (sub_4508F9 / sub_43948B), Word 0 is rendered ONLY if
            # ((cell.flags >> 18) & 7) > cutoff_limit, and not storing a clutter object frame.
            # When tileset is None (synthetic unit tests), render if present.
            if cell.floor.is_present and not cell.has_clutter_object:
                if tileset is None or cell.roof_cutoff_layer > cutoff_limit:
                    if cell.floor.sprite_frame_index < 200:
                        eff_type = (
                            tileset.get_component_type_for_group(cell.floor.tileset_group_index)
                            if tileset
                            else ComponentType.FLOOR
                        )
                        if type_visibility[eff_type]:
                            asset_name = (
                                tileset.resolve_asset(eff_type, cell.floor.tileset_group_index)
                                if tileset
                                else None
                            )
                            if asset_name is not None or tileset is None:
                                sort_key = cls.get_sort_key(z, x, y, eff_type)
                                items.append(
                                    RenderItem(
                                        grid_x=x,
                                        grid_y=y,
                                        grid_z=z,
                                        component_type=eff_type,
                                        component=cell.floor,
                                        asset_name=asset_name,
                                        sprite_frame_index=cell.floor.sprite_frame_index,
                                        sort_key=sort_key,
                                    )
                                )

            # 2. Structural Left Wall (Word 1)
            if cell.left_wall.is_present:
                eff_type = ComponentType.LEFT_WALL
                if type_visibility[eff_type]:
                    eff_frame = (
                        0 if cell.left_wall.sprite_frame_index >= 200 else cell.left_wall.sprite_frame_index
                    )
                    asset_name = (
                        tileset.resolve_asset(eff_type, cell.left_wall.tileset_group_index)
                        if tileset
                        else None
                    )
                    if asset_name is not None or tileset is None:
                        sort_key = cls.get_sort_key(z, x, y, eff_type)
                        items.append(
                            RenderItem(
                                grid_x=x,
                                grid_y=y,
                                grid_z=z,
                                component_type=eff_type,
                                component=cell.left_wall,
                                asset_name=asset_name,
                                sprite_frame_index=eff_frame,
                                sort_key=sort_key,
                            )
                        )

            # 3. Structural Right Wall (Word 2)
            if cell.right_wall.is_present:
                eff_type = ComponentType.RIGHT_WALL
                if type_visibility[eff_type]:
                    eff_frame = (
                        0 if cell.right_wall.sprite_frame_index >= 200 else cell.right_wall.sprite_frame_index
                    )
                    asset_name = (
                        tileset.resolve_asset(eff_type, cell.right_wall.tileset_group_index)
                        if tileset
                        else None
                    )
                    if asset_name is not None or tileset is None:
                        sort_key = cls.get_sort_key(z, x, y, eff_type)
                        items.append(
                            RenderItem(
                                grid_x=x,
                                grid_y=y,
                                grid_z=z,
                                component_type=eff_type,
                                component=cell.right_wall,
                                asset_name=asset_name,
                                sprite_frame_index=eff_frame,
                                sort_key=sort_key,
                            )
                        )

            # 4. Ground Surface / Procedural Surface / Clutter (Word 3)
            # In Soldiers at War maps, Word 3 encodes ground surface tiles (e.g. ssnow1, sdirt,
            # sstone1) as well as elevated floors/platforms.
            if cell.clutter.is_present and cell.clutter.sprite_frame_index < 200:
                eff_type = (
                    tileset.get_component_type_for_group(cell.clutter.tileset_group_index)
                    if tileset
                    else ComponentType.CLUTTER
                )
                if type_visibility[eff_type]:
                    asset_name = (
                        tileset.resolve_asset(eff_type, cell.clutter.tileset_group_index)
                        if tileset
                        else None
                    )
                    if asset_name is not None or tileset is None:
                        sort_key = cls.get_sort_key(z, x, y, eff_type)
                        items.append(
                            RenderItem(
                                grid_x=x,
                                grid_y=y,
                                grid_z=z,
                                component_type=eff_type,
                                component=cell.clutter,
                                asset_name=asset_name,
                                sprite_frame_index=cell.clutter.sprite_frame_index,
                                sort_key=sort_key,
                            )
                        )

            # 5. Clutter object from flags (planes, trees, vehicles, guns, warehouses, crates)
            if cell.has_clutter_object and type_visibility[ComponentType.CLUTTER]:
                clutter_group = cell.clutter_object_group
                clutter_frame = cell.clutter_object_frame
                clutter_asset = tileset.resolve_flat_asset(clutter_group) if tileset else None
                if clutter_asset or not tileset:
                    sort_key = cls.get_sort_key(z, x, y, ComponentType.CLUTTER)
                    items.append(
                        RenderItem(
                            grid_x=x,
                            grid_y=y,
                            grid_z=z,
                            component_type=ComponentType.CLUTTER,
                            component=cell.clutter,
                            asset_name=clutter_asset,
                            sprite_frame_index=clutter_frame,
                            sort_key=sort_key,
                        )
                    )

        # In-place sort by 4-tuple key
        items.sort(key=lambda item: item.sort_key)
        return items
