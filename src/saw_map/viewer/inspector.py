"""Hovered cell detection and picking calculations using inverse projections.

Computes exact logical map cell (X, Y, Z) under the mouse cursor at arbitrary
camera pan offsets, zoom levels, and elevation planes.
"""

from __future__ import annotations

from typing import Optional, Tuple

from saw_map.geometry.transform import IsometricTransform, TopDownTransform
from saw_map.maps.model import MapCell, MapDocument
from saw_map.viewer.camera import Camera, ViewPerspective


class CellInspector:
    """Calculates mouse cursor picking and inspects cell components."""

    def __init__(
        self,
        iso_transform: Optional[IsometricTransform] = None,
        top_transform: Optional[TopDownTransform] = None,
    ) -> None:
        self.iso_transform = iso_transform or IsometricTransform()
        self.top_transform = top_transform or TopDownTransform()

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

        z_plane = float(
            camera.isolated_layer
            if camera.isolated_layer is not None
            else camera.active_max_layer
        )

        if camera.perspective == ViewPerspective.ISOMETRIC:
            gx, gy = self.iso_transform.screen_to_world(world_sx, world_sy, z_plane)
        else:
            gx, gy = self.top_transform.screen_to_world(world_sx, world_sy, z_plane)

        if 0 <= gx < map_doc.width and 0 <= gy < map_doc.height:
            return (gx, gy, int(z_plane))
        return None

    @staticmethod
    def get_cell_details(map_doc: MapDocument, cell_coord: Tuple[int, int, int]) -> Optional[MapCell]:
        """Retrieves MapCell object for given coordinate."""
        x, y, z = cell_coord
        return map_doc.get_cell(x, y, z)
