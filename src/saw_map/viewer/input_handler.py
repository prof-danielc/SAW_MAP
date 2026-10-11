"""Unified input handling and key/mouse mapping for Soldiers at War visualizer.

Provides abstract event dispatching decoupled from backend graphics engines.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, Dict, Optional

from saw_map.maps.model import ComponentType
from saw_map.viewer.camera import Camera, ViewPerspective


class InputAction(str, Enum):
    """Semantic user interaction actions."""
    PAN_LEFT = "PAN_LEFT"
    PAN_RIGHT = "PAN_RIGHT"
    PAN_UP = "PAN_UP"
    PAN_DOWN = "PAN_DOWN"
    ZOOM_IN = "ZOOM_IN"
    ZOOM_OUT = "ZOOM_OUT"
    RESET_VIEW = "RESET_VIEW"
    ELEVATION_UP = "ELEVATION_UP"
    ELEVATION_DOWN = "ELEVATION_DOWN"
    TOGGLE_LAYER_ISOLATION = "TOGGLE_LAYER_ISOLATION"
    TOGGLE_PERSPECTIVE = "TOGGLE_PERSPECTIVE"
    TOGGLE_MINIMAP = "TOGGLE_MINIMAP"
    TOGGLE_SIDEBAR = "TOGGLE_SIDEBAR"
    TOGGLE_FLOORS = "TOGGLE_FLOORS"
    TOGGLE_LEFT_WALLS = "TOGGLE_LEFT_WALLS"
    TOGGLE_RIGHT_WALLS = "TOGGLE_RIGHT_WALLS"
    TOGGLE_CLUTTER = "TOGGLE_CLUTTER"
    CYCLE_PALETTE = "CYCLE_PALETTE"
    EXIT = "EXIT"


class InputHandler:
    """Manages viewport action dispatching and camera updates."""

    def __init__(self, camera: Camera, on_redraw_needed: Optional[Callable[[], None]] = None) -> None:
        self.camera = camera
        self.on_redraw_needed = on_redraw_needed

    def handle_action(self, action: InputAction, step: float = 40.0) -> None:
        """Executes semantic input action against camera state."""
        cam = self.camera
        pan_amount = step / cam.zoom

        if action == InputAction.PAN_LEFT:
            cam.pan(pan_amount, 0)
        elif action == InputAction.PAN_RIGHT:
            cam.pan(-pan_amount, 0)
        elif action == InputAction.PAN_UP:
            cam.pan(0, -pan_amount)
        elif action == InputAction.PAN_DOWN:
            cam.pan(0, pan_amount)

        elif action == InputAction.ZOOM_IN:
            cam.zoom_in()
        elif action == InputAction.ZOOM_OUT:
            cam.zoom_out()
        elif action == InputAction.RESET_VIEW:
            cam.reset()

        elif action == InputAction.ELEVATION_UP:
            cam.active_max_layer = min(6, cam.active_max_layer + 1)
            cam.isolated_layer = None
            if self.on_redraw_needed: self.on_redraw_needed()

        elif action == InputAction.ELEVATION_DOWN:
            cam.active_max_layer = max(0, cam.active_max_layer - 1)
            cam.isolated_layer = None
            if self.on_redraw_needed: self.on_redraw_needed()

        elif action == InputAction.TOGGLE_LAYER_ISOLATION:
            if cam.isolated_layer is None:
                cam.isolated_layer = cam.active_max_layer
            else:
                cam.isolated_layer = None
            if self.on_redraw_needed: self.on_redraw_needed()

        elif action == InputAction.TOGGLE_PERSPECTIVE:
            if cam.perspective == ViewPerspective.ISOMETRIC:
                cam.perspective = ViewPerspective.TOP_DOWN
            else:
                cam.perspective = ViewPerspective.ISOMETRIC
            if self.on_redraw_needed: self.on_redraw_needed()

        elif action == InputAction.TOGGLE_MINIMAP:
            cam.show_minimap = not cam.show_minimap

        elif action == InputAction.TOGGLE_SIDEBAR:
            cam.show_sidebar = not cam.show_sidebar

        elif action == InputAction.TOGGLE_FLOORS:
            cam.show_floors = not cam.show_floors
            if self.on_redraw_needed: self.on_redraw_needed()

        elif action == InputAction.TOGGLE_LEFT_WALLS:
            cam.show_left_walls = not cam.show_left_walls
            if self.on_redraw_needed: self.on_redraw_needed()

        elif action == InputAction.TOGGLE_RIGHT_WALLS:
            cam.show_right_walls = not cam.show_right_walls
            if self.on_redraw_needed: self.on_redraw_needed()

        elif action == InputAction.TOGGLE_CLUTTER:
            cam.show_clutter = not cam.show_clutter
            if self.on_redraw_needed: self.on_redraw_needed()
