"""Hovered cell detection and picking calculations using inverse projections.

Computes exact logical map cell (X, Y, Z) under the mouse cursor at arbitrary
camera pan offsets, zoom levels, and elevation planes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from saw_map.geometry.transform import IsometricTransform, TopDownTransform
from saw_map.maps.model import ComponentType, MapCell, MapDocument, TilesetDefinition
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
    is_mask: bool
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
                if 0 <= gx < map_doc.width and 0 <= gy < map_doc.height:
                    cell = map_doc.get_cell(gx, gy, z)
                    if cell and cell.has_visual_content():
                        return (gx, gy, z)

            # Fallback to ground base layer (0) or lowest visible layer
            fallback_z = z_layers[-1] if z_layers else 0
            gx0, gy0 = self.iso_transform.screen_to_world(world_sx, world_sy, float(fallback_z))
            if 0 <= gx0 < map_doc.width and 0 <= gy0 < map_doc.height:
                return (gx0, gy0, fallback_z)
            return None
        else:
            # Orthogonal top-down projection
            gx, gy = self.top_transform.screen_to_world(world_sx, world_sy, 0.0)
            if 0 <= gx < map_doc.width and 0 <= gy < map_doc.height:
                for z in z_layers:
                    cell = map_doc.get_cell(gx, gy, z)
                    if cell and cell.has_visual_content():
                        return (gx, gy, z)
                fallback_z = z_layers[-1] if z_layers else 0
                return (gx, gy, fallback_z)
            return None

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

    @classmethod
    def inspect_cell(
        cls,
        cell: MapCell,
        tileset: Optional[TilesetDefinition] = None,
    ) -> CellInspectionInfo:
        """Inspects and formats all 4 component words and attributes of a MapCell.

        Accurately decomposes:
          - Slot 0 (Word 0, +0): Roof / Ceiling / Upper Cut-away Mask
          - Slot 1 (Word 1, +2): Left Wall structure
          - Slot 2 (Word 2, +4): Right Wall structure
          - Slot 3 (Word 3, +6): Procedural Ground Surface / Clutter Item
        """
        components: List[ComponentInspectionInfo] = []

        # Slot 0: Word 0 (Roof / Ceiling)
        comp0 = cell.floor
        is_mask0 = comp0.is_present and comp0.sprite_frame_index >= 200
        if comp0.is_present:
            status0 = "PRESENT"
            if is_mask0:
                role0 = f"Height Mask (Frm {comp0.sprite_frame_index})"
                asset0 = None
                det0 = f"Mask: Frame {comp0.sprite_frame_index}"
            else:
                asset0 = tileset.resolve_flat_asset(comp0.tileset_group_index) if tileset else None
                role0 = "Roof Sprite"
                obj0 = f"{asset0}.obj" if asset0 and not asset0.lower().endswith(".obj") else asset0
                det0 = f"Tile Name: {obj0 or 'Unresolved'} (Frame {comp0.sprite_frame_index})"
        else:
            status0 = "EMPTY"
            role0 = "Empty"
            asset0 = None
            det0 = "None"

        components.append(
            ComponentInspectionInfo(
                slot_index=0,
                slot_name="Roof / Ceiling",
                is_present=comp0.is_present,
                raw_word=comp0.raw_word,
                tileset_group_index=comp0.tileset_group_index,
                sprite_frame_index=comp0.sprite_frame_index,
                is_mask=is_mask0,
                asset_name=asset0,
                semantic_role=role0,
                status_label=status0,
                details_line=det0,
            )
        )

        # Slot 1: Word 1 (Left Wall)
        comp1 = cell.left_wall
        is_mask1 = comp1.is_present and comp1.sprite_frame_index >= 200
        if comp1.is_present:
            status1 = "PRESENT"
            asset1 = (
                tileset.resolve_asset(ComponentType.LEFT_WALL, comp1.tileset_group_index)
                if tileset
                else None
            )
            if not asset1 and tileset:
                asset1 = tileset.resolve_flat_asset(comp1.tileset_group_index)
            role1 = "Left Wall"
            obj1 = f"{asset1}.obj" if asset1 and not asset1.lower().endswith(".obj") else asset1
            det1 = f"Tile Name: {obj1 or 'Unresolved'} (Frame {comp1.sprite_frame_index})"
        else:
            status1 = "EMPTY"
            role1 = "Empty"
            asset1 = None
            det1 = "None"

        components.append(
            ComponentInspectionInfo(
                slot_index=1,
                slot_name="Left Wall",
                is_present=comp1.is_present,
                raw_word=comp1.raw_word,
                tileset_group_index=comp1.tileset_group_index,
                sprite_frame_index=comp1.sprite_frame_index,
                is_mask=is_mask1,
                asset_name=asset1,
                semantic_role=role1,
                status_label=status1,
                details_line=det1,
            )
        )

        # Slot 2: Word 2 (Right Wall)
        comp2 = cell.right_wall
        is_mask2 = comp2.is_present and comp2.sprite_frame_index >= 200
        if comp2.is_present:
            status2 = "PRESENT"
            asset2 = (
                tileset.resolve_asset(ComponentType.RIGHT_WALL, comp2.tileset_group_index)
                if tileset
                else None
            )
            if not asset2 and tileset:
                asset2 = tileset.resolve_flat_asset(comp2.tileset_group_index)
            role2 = "Right Wall"
            obj2 = f"{asset2}.obj" if asset2 and not asset2.lower().endswith(".obj") else asset2
            det2 = f"Tile Name: {obj2 or 'Unresolved'} (Frame {comp2.sprite_frame_index})"
        else:
            status2 = "EMPTY"
            role2 = "Empty"
            asset2 = None
            det2 = "None"

        components.append(
            ComponentInspectionInfo(
                slot_index=2,
                slot_name="Right Wall",
                is_present=comp2.is_present,
                raw_word=comp2.raw_word,
                tileset_group_index=comp2.tileset_group_index,
                sprite_frame_index=comp2.sprite_frame_index,
                is_mask=is_mask2,
                asset_name=asset2,
                semantic_role=role2,
                status_label=status2,
                details_line=det2,
            )
        )

        # Slot 3: Word 3 (Surface / Clutter)
        comp3 = cell.clutter
        is_mask3 = comp3.is_present and comp3.sprite_frame_index >= 200
        if comp3.is_present:
            status3 = "PRESENT"
            asset3 = tileset.resolve_flat_asset(comp3.tileset_group_index) if tileset else None
            is_surface = bool(tileset and comp3.tileset_group_index < len(tileset.surfaces))
            role3 = "Ground Surface" if is_surface else "Clutter Item"
            obj3 = f"{asset3}.obj" if asset3 and not asset3.lower().endswith(".obj") else asset3
            det3 = f"Tile Name: {obj3 or 'Unresolved'} (Frame {comp3.sprite_frame_index})"
        else:
            status3 = "EMPTY"
            role3 = "Empty"
            asset3 = None
            det3 = "None"

        components.append(
            ComponentInspectionInfo(
                slot_index=3,
                slot_name="Surface / Clutter",
                is_present=comp3.is_present,
                raw_word=comp3.raw_word,
                tileset_group_index=comp3.tileset_group_index,
                sprite_frame_index=comp3.sprite_frame_index,
                is_mask=is_mask3,
                asset_name=asset3,
                semantic_role=role3,
                status_label=status3,
                details_line=det3,
            )
        )

        # Determine primary tile name and frame for the cell
        primary_tile_name: Optional[str] = None
        primary_tile_frame: Optional[int] = None
        primary_tile_label: str = "None"

        # Check ground surface (Slot 3) first
        if comp3.is_present and comp3.sprite_frame_index < 200 and asset3:
            primary_tile_name = asset3 if asset3.lower().endswith(".obj") else f"{asset3}.obj"
            primary_tile_frame = comp3.sprite_frame_index
            primary_tile_label = f"{primary_tile_name} (Frame {primary_tile_frame})"
        # Check roof tile (Slot 0)
        elif comp0.is_present and comp0.sprite_frame_index < 200 and asset0:
            primary_tile_name = asset0 if asset0.lower().endswith(".obj") else f"{asset0}.obj"
            primary_tile_frame = comp0.sprite_frame_index
            primary_tile_label = f"{primary_tile_name} (Frame {primary_tile_frame})"
        # Check walls (Slot 1, then Slot 2)
        elif comp1.is_present and comp1.sprite_frame_index < 200 and asset1:
            primary_tile_name = asset1 if asset1.lower().endswith(".obj") else f"{asset1}.obj"
            primary_tile_frame = comp1.sprite_frame_index
            primary_tile_label = f"{primary_tile_name} (Frame {primary_tile_frame})"
        elif comp2.is_present and comp2.sprite_frame_index < 200 and asset2:
            primary_tile_name = asset2 if asset2.lower().endswith(".obj") else f"{asset2}.obj"
            primary_tile_frame = comp2.sprite_frame_index
            primary_tile_label = f"{primary_tile_name} (Frame {primary_tile_frame})"
        elif comp0.is_present and comp0.sprite_frame_index >= 200:
            primary_tile_label = f"Mask (Frame {comp0.sprite_frame_index})"
        elif cell.is_empty():
            primary_tile_label = "Empty Cell"
        else:
            primary_tile_label = "Unresolved Tile"

        return CellInspectionInfo(
            coord=(cell.x, cell.y, cell.z),
            elevation_attr=cell.elevation_attr,
            flags=cell.flags,
            components=components,
            primary_tile_name=primary_tile_name,
            primary_tile_frame=primary_tile_frame,
            primary_tile_label=primary_tile_label,
        )


