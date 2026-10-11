"""Hovered cell detection and picking calculations using inverse projections.

Computes exact logical map cell (X, Y, Z) under the mouse cursor at arbitrary
camera pan offsets, zoom levels, and elevation planes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from saw_map.geometry.transform import IsometricTransform, TopDownTransform
from saw_map.maps.model import MapCell, MapDocument, TilesetDefinition
from saw_map.maps.records import EntityCategory, PlacedEntity
from saw_map.viewer.camera import Camera, ViewPerspective



@dataclass(slots=True)
class ComponentInspectionInfo:
    """Detailed metadata for one of the 4 cell component words."""
    slot_index: int
    slot_name: str
    is_present: bool
    raw_word: int
    tileset_group_index: int
    sprite_frame_index: int
    asset_name: Optional[str]
    semantic_role: str
    status_label: str
    details_line: str


@dataclass(slots=True)
class CellInspectionInfo:
    """Complete inspection representation for a selected map cell."""
    coord: Tuple[int, int, int]
    elevation_attr: int
    flags: int
    components: List[ComponentInspectionInfo]
    primary_tile_name: Optional[str] = None
    primary_tile_frame: Optional[int] = None
    primary_tile_label: str = "None"
    entities: Tuple[PlacedEntity, ...] = ()


class CellInspector:
    """Calculates mouse cursor picking and inspects cell components."""

    def __init__(
        self,
        iso_transform: Optional[IsometricTransform] = None,
        top_transform: Optional[TopDownTransform] = None,
    ) -> None:
        self.iso_transform = iso_transform or IsometricTransform()
        self.top_transform = top_transform or TopDownTransform()

    def pick_cell_from_world_coords(
        self,
        world_sx: float,
        world_sy: float,
        camera: Camera,
        map_doc: MapDocument,
    ) -> Optional[Tuple[int, int, int]]:
        """Projects screen-world coordinates downwards through elevation layers to select the top visible cell.

        Args:
            world_sx: Camera-unprojected horizontal screen world coordinate.
            world_sy: Camera-unprojected vertical screen world coordinate (Y down).
            camera: Active camera viewing state.
            map_doc: Target map document.

        Returns:
            (x, y, z) tuple of first visible cell, or fallback base ground cell, or None if out of bounds.
        """
        if camera.isolated_layer is not None:
            z_layers = [camera.isolated_layer]
        else:
            z_layers = list(range(camera.active_max_layer, -1, -1))

        if camera.perspective == ViewPerspective.ISOMETRIC:
            # Raycast from top-most visible layer down to layer 0
            for z in z_layers:
                gx, gy = self.iso_transform.screen_to_world(world_sx, world_sy, float(z))
                if map_doc.contains(gx, gy) and self._is_pickable(map_doc, gx, gy, z):
                    return (gx, gy, z)

            # Fallback to ground base layer (0) or lowest visible layer
            fallback_z = z_layers[-1] if z_layers else 0
            gx0, gy0 = self.iso_transform.screen_to_world(world_sx, world_sy, float(fallback_z))
            if map_doc.contains(gx0, gy0):
                return (gx0, gy0, fallback_z)
            return None
        else:
            # Orthogonal top-down projection
            gx, gy = self.top_transform.screen_to_world(world_sx, world_sy, 0.0)
            if map_doc.contains(gx, gy):
                for z in z_layers:
                    if self._is_pickable(map_doc, gx, gy, z):
                        return (gx, gy, z)
                fallback_z = z_layers[-1] if z_layers else 0
                return (gx, gy, fallback_z)
            return None

    @staticmethod
    def _is_pickable(map_doc: MapDocument, x: int, y: int, z: int) -> bool:
        """True if cell (x, y, z) shows a tile component or holds a placed entity."""
        cell = map_doc.get_cell(x, y, z)
        if cell and cell.has_visual_content():
            return True
        return any(e.category != EntityCategory.MARKER for e in map_doc.entities_at(x, y, z))

    def pick_cell(
        self,
        mouse_x: float,
        mouse_y: float,
        win_w: float,
        win_h: float,
        camera: Camera,
        map_doc: MapDocument,
    ) -> Optional[Tuple[int, int, int]]:
        """Inverse-projects screen mouse coordinates to discrete cell (X, Y, Z).

        Args:
            mouse_x: Screen X pixel coordinate.
            mouse_y: Screen Y pixel coordinate.
            win_w: Viewport window width.
            win_h: Viewport window height.
            camera: Active camera viewing state.
            map_doc: Target map document.

        Returns:
            (x, y, z) tuple if coordinates fall within map bounds, else None.
        """
        center_x = win_w / 2.0 + (camera.x * camera.zoom)
        center_y = win_h / 2.0 + (camera.y * camera.zoom)

        world_sx = (mouse_x - center_x) / camera.zoom
        world_sy = (mouse_y - center_y) / camera.zoom

        return self.pick_cell_from_world_coords(world_sx, world_sy, camera, map_doc)

    def get_selection_polygon(
        self,
        cell_coord: Tuple[int, int, int],
        perspective: ViewPerspective,
    ) -> List[Tuple[float, float]]:
        """Calculates 2D world-space polygon vertices (diamond or square) for selected cell.

        Args:
            cell_coord: Logical (x, y, z) coordinate.
            perspective: Active viewing perspective (ISOMETRIC or TOP_DOWN).

        Returns:
            List of 4 (x, y) vertex tuples in world coordinates (Y-down).
        """
        x, y, z = cell_coord
        if perspective == ViewPerspective.ISOMETRIC:
            sx, sy = self.iso_transform.world_to_screen(x, y, z)
            return [
                (sx, sy),
                (sx + 64.0, sy + 32.0),
                (sx, sy + 64.0),
                (sx - 64.0, sy + 32.0),
            ]
        else:
            sx, sy = self.top_transform.world_to_screen(x, y, z)
            cw = self.top_transform.cell_size
            return [
                (sx, sy),
                (sx + cw, sy),
                (sx + cw, sy + cw),
                (sx, sy + cw),
            ]

    @staticmethod
    def get_cell_details(map_doc: MapDocument, cell_coord: Tuple[int, int, int]) -> Optional[MapCell]:
        """Retrieves MapCell object for given coordinate."""
        x, y, z = cell_coord
        return map_doc.get_cell(x, y, z)

    # (slot name, semantic role) per component word, in stream order
    _SLOTS: Tuple[Tuple[str, str], ...] = (
        ("Floor / Surface", "Ground Surface"),
        ("Left Wall", "Left Wall"),
        ("Right Wall", "Right Wall"),
        ("Clutter / Object", "Clutter Item"),
    )

    @classmethod
    def inspect_cell(
        cls,
        cell: MapCell,
        tileset: Optional[TilesetDefinition] = None,
        entities: Sequence[PlacedEntity] = (),
    ) -> CellInspectionInfo:
        """Inspects and formats all 4 component words and attributes of a MapCell.

        Slots follow the stream order of the 13-byte cell:
          - Slot 0 (Word 0, +0): Floor / ground surface
          - Slot 1 (Word 1, +2): Left wall
          - Slot 2 (Word 2, +4): Right wall
          - Slot 3 (Word 3, +6): Clutter / object

        The primary tile is the first present component in the order
        floor, clutter, left wall, right wall. `entities` are the placed entities
        standing on the cell (MapDocument.entities_at) and are passed through.
        """
        components: List[ComponentInspectionInfo] = []
        slot_components = (cell.floor, cell.left_wall, cell.right_wall, cell.clutter)

        for slot_index, comp in enumerate(slot_components):
            slot_name, role = cls._SLOTS[slot_index]
            asset: Optional[str] = None
            if comp.is_present:
                asset = tileset.resolve_flat_asset(comp.tileset_group_index) if tileset else None
                status = "PRESENT"
                details = f"Tile Name: {cls._obj_name(asset) or 'Unresolved'} (Frame {comp.sprite_frame_index})"
            else:
                status = "EMPTY"
                role = "Empty"
                details = "None"

            components.append(
                ComponentInspectionInfo(
                    slot_index=slot_index,
                    slot_name=slot_name,
                    is_present=comp.is_present,
                    raw_word=comp.raw_word,
                    tileset_group_index=comp.tileset_group_index,
                    sprite_frame_index=comp.sprite_frame_index,
                    asset_name=asset,
                    semantic_role=role,
                    status_label=status,
                    details_line=details,
                )
            )

        primary_tile_name: Optional[str] = None
        primary_tile_frame: Optional[int] = None
        if cell.is_empty():
            primary_tile_label = "Empty Cell"
        else:
            primary_tile_label = "Unresolved Tile"
            for slot_index in (0, 3, 1, 2):
                info = components[slot_index]
                if info.is_present and info.asset_name:
                    primary_tile_name = cls._obj_name(info.asset_name)
                    primary_tile_frame = info.sprite_frame_index
                    primary_tile_label = f"{primary_tile_name} (Frame {primary_tile_frame})"
                    break

        return CellInspectionInfo(
            coord=(cell.x, cell.y, cell.z),
            elevation_attr=cell.elevation_attr,
            flags=cell.flags,
            components=components,
            primary_tile_name=primary_tile_name,
            primary_tile_frame=primary_tile_frame,
            primary_tile_label=primary_tile_label,
            entities=tuple(entities),
        )

    @staticmethod
    def _obj_name(asset: Optional[str]) -> Optional[str]:
        """Normalizes a registry asset name to its '<name>.obj' archive file name."""
        if not asset:
            return None
        return asset if asset.lower().endswith(".obj") else f"{asset}.obj"
