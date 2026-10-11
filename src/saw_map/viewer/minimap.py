"""2D top-down minimap overlay calculations and viewport projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from saw_map.maps.model import MapDocument
from saw_map.viewer.camera import Camera


@dataclass(slots=True)
class MinimapBounds:
    """Screen-space rectangle coordinates for the minimap."""
    left: float
    top: float
    width: float
    height: float


@dataclass(slots=True)
class CameraFrustumBounds:
    """Position and size of camera viewport rectangle projected on minimap."""
    x: float
    y: float
    width: float
    height: float


class MinimapCalculator:
    """Computes coordinates and viewport projection for the 2D corner minimap."""

    def __init__(
        self,
        box_width: float = 140.0,
        box_height: float = 110.0,
        margin: float = 12.0,
    ) -> None:
        self.box_width = box_width
        self.box_height = box_height
        self.margin = margin

    def get_minimap_bounds(self, screen_w: float, screen_h: float) -> MinimapBounds:
        """Calculates top-right corner placement bounds."""
        left = screen_w - self.box_width - self.margin
        top = self.margin
        return MinimapBounds(
            left=left,
            top=top,
            width=self.box_width,
            height=self.box_height,
        )

    def calculate_camera_frustum(
        self,
        map_doc: MapDocument,
        camera: Camera,
        screen_w: float,
        screen_h: float,
    ) -> CameraFrustumBounds:
        """Calculates camera viewport indicator box on the minimap."""
        inner_w = self.box_width - 16.0
        inner_h = self.box_height - 28.0

        map_w = max(1.0, float(map_doc.width))
        map_h = max(1.0, float(map_doc.height))

        scale_x = inner_w / map_w
        scale_y = inner_h / map_h

        # Visible world width in grid units (approximate)
        visible_world_w = (screen_w / camera.zoom) / 64.0
        visible_world_h = (screen_h / camera.zoom) / 32.0

        frustum_w = max(4.0, visible_world_w * scale_x)
        frustum_h = max(4.0, visible_world_h * scale_y)

        # Center indicator based on camera pan
        center_grid_x = (-camera.x / 64.0) + (map_w / 2.0)
        center_grid_y = (-camera.y / 32.0) + (map_h / 2.0)

        fx = center_grid_x * scale_x - (frustum_w / 2.0)
        fy = center_grid_y * scale_y - (frustum_h / 2.0)

        # Clamp inside minimap box
        fx = max(0.0, min(inner_w - frustum_w, fx))
        fy = max(0.0, min(inner_h - frustum_h, fy))

        return CameraFrustumBounds(x=fx, y=fy, width=frustum_w, height=frustum_h)
