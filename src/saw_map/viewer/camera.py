"""Camera and viewport viewing state manager for Soldiers at War visualizer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class ViewPerspective(str, Enum):
    """Rendering projection mode."""
    ISOMETRIC = "isometric"
    TOP_DOWN = "top-down"


@dataclass
class Camera:
    """Manages viewport offsets, zoom level, layer filters, and component toggles."""
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    active_max_layer: int = 6
    isolated_layer: Optional[int] = None
    show_floors: bool = True
    show_left_walls: bool = True
    show_right_walls: bool = True
    show_clutter: bool = True
    show_entities: bool = True
    show_markers: bool = False
    show_effects: bool = True
    perspective: ViewPerspective = ViewPerspective.ISOMETRIC
    show_minimap: bool = True
    show_sidebar: bool = False
    show_metadata: bool = False
    show_grid: bool = False

    MIN_ZOOM: float = 0.25
    MAX_ZOOM: float = 4.0

    def pan(self, dx: float, dy: float) -> None:
        """Translates camera center by delta in screen space."""
        self.x += dx
        self.y += dy

    def set_zoom(self, new_zoom: float) -> None:
        """Updates zoom clamped to valid range [0.25, 4.0]."""
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, float(new_zoom)))

    def zoom_in(self, factor: float = 1.25) -> None:
        """Multiplies zoom scale."""
        self.set_zoom(self.zoom * factor)

    def zoom_out(self, factor: float = 0.8) -> None:
        """Divides zoom scale."""
        self.set_zoom(self.zoom * factor)

    def zoom_at_cursor(self, cursor_x: float, cursor_y: float, factor: float, win_w: float, win_h: float) -> None:
        """Zooms centered at cursor position.

        Adjusts (x, y) pan offsets so the world point beneath the cursor
        remains stationary on screen before and after scaling.
        """
        old_zoom = self.zoom
        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, old_zoom * factor))
        if abs(new_zoom - old_zoom) < 1e-5:
            return

        # World point relative to center before zoom
        center_x = win_w / 2.0
        center_y = win_h / 2.0

        world_x = (cursor_x - center_x - self.x * old_zoom) / old_zoom
        world_y = (cursor_y - center_y - self.y * old_zoom) / old_zoom

        self.zoom = new_zoom
        self.x = (cursor_x - center_x - world_x * new_zoom) / new_zoom
        self.y = (cursor_y - center_y - world_y * new_zoom) / new_zoom

    def reset(self) -> None:
        """Resets camera position and zoom to defaults."""
        self.x = 0.0
        self.y = 0.0
        self.zoom = 1.0
