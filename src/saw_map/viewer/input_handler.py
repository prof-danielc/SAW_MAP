"""Unified input handling and key/mouse mapping for Soldiers at War visualizer.

Provides abstract event dispatching decoupled from backend graphics engines.
Backends translate their native key codes into InputAction values and delegate
all camera and filter state changes to InputHandler.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, FrozenSet, Optional, Set

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
    TOGGLE_METADATA = "TOGGLE_METADATA"
    TOGGLE_GRID = "TOGGLE_GRID"
    TOGGLE_FLOORS = "TOGGLE_FLOORS"
    TOGGLE_LEFT_WALLS = "TOGGLE_LEFT_WALLS"
    TOGGLE_RIGHT_WALLS = "TOGGLE_RIGHT_WALLS"
    TOGGLE_CLUTTER = "TOGGLE_CLUTTER"
    TOGGLE_ENTITIES = "TOGGLE_ENTITIES"
    TOGGLE_MARKERS = "TOGGLE_MARKERS"
    CYCLE_PALETTE = "CYCLE_PALETTE"
    TOGGLE_FULLSCREEN = "TOGGLE_FULLSCREEN"
    EXIT = "EXIT"


# Actions that pan continuously while their key is held
PAN_ACTIONS: FrozenSet[InputAction] = frozenset(
    {InputAction.PAN_LEFT, InputAction.PAN_RIGHT, InputAction.PAN_UP, InputAction.PAN_DOWN}
)


class InputHandler:
    """Manages viewport action dispatching and camera updates.

    Panning is continuous: backends report pan keys going down and up with
    set_pan_held() and call update() once per frame with the elapsed time.

    Args:
        camera: Camera state mutated by the actions.
        on_redraw_needed: Called after a change that invalidates the render list
            (layer, perspective, or component filters).
        on_recenter: Centers the camera on the map; called on view reset and
            perspective changes.
        on_cycle_palette: Switches to the next available palette.
        on_toggle_fullscreen: Toggles fullscreen display mode.
        on_exit: Closes the application.
    """

    ZOOM_IN_FACTOR = 1.25
    ZOOM_OUT_FACTOR = 0.8
    # Continuous pan speed in window pixels per second (independent of zoom)
    PAN_SPEED = 900.0
    # Longest frame time applied to one pan step, so a stalled frame does not jump the view
    MAX_PAN_FRAME_TIME = 0.1

    def __init__(
        self,
        camera: Camera,
        on_redraw_needed: Optional[Callable[[], None]] = None,
        on_recenter: Optional[Callable[[], None]] = None,
        on_cycle_palette: Optional[Callable[[], None]] = None,
        on_toggle_fullscreen: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ) -> None:
        self.camera = camera
        self.on_redraw_needed = on_redraw_needed
        self.on_recenter = on_recenter
        self.on_cycle_palette = on_cycle_palette
        self.on_toggle_fullscreen = on_toggle_fullscreen
        self.on_exit = on_exit
        self._held_pans: Set[InputAction] = set()

    def set_pan_held(self, action: InputAction, held: bool) -> None:
        """Records a pan key going down or up; other actions are ignored."""
        if action not in PAN_ACTIONS:
            return
        if held:
            self._held_pans.add(action)
        else:
            self._held_pans.discard(action)

    def release_all_pans(self) -> None:
        """Stops panning, e.g. when the window loses keyboard focus."""
        self._held_pans.clear()

    @property
    def is_panning(self) -> bool:
        """True while at least one pan key is held."""
        return bool(self._held_pans)

    def update(self, delta_time: float) -> bool:
        """Pans the camera for one frame according to the held pan keys.

        Opposite directions cancel. Returns True if the camera moved.
        """
        held = self._held_pans
        dir_x = (InputAction.PAN_LEFT in held) - (InputAction.PAN_RIGHT in held)
        dir_y = (InputAction.PAN_UP in held) - (InputAction.PAN_DOWN in held)
        if (dir_x == 0 and dir_y == 0) or delta_time <= 0.0:
            return False
        amount = self.PAN_SPEED * min(delta_time, self.MAX_PAN_FRAME_TIME) / self.camera.zoom
        self.camera.pan(dir_x * amount, dir_y * amount)
        return True

    def _redraw(self) -> None:
        if self.on_redraw_needed:
            self.on_redraw_needed()

    def handle_zoom_at_cursor(
        self, zoom_in: bool, cursor_x: float, cursor_y: float, win_w: float, win_h: float
    ) -> None:
        """Zooms one step keeping the world point under the cursor stationary.

        Cursor coordinates are window pixels with a top-left origin (Y down).
        """
        factor = self.ZOOM_IN_FACTOR if zoom_in else self.ZOOM_OUT_FACTOR
        self.camera.zoom_at_cursor(cursor_x, cursor_y, factor, win_w, win_h)

    def handle_action(self, action: InputAction, step: float = 40.0) -> None:
        """Executes semantic input action against camera state."""
        cam = self.camera
        pan_amount = step / cam.zoom

        if action == InputAction.PAN_LEFT:
            cam.pan(pan_amount, 0)
        elif action == InputAction.PAN_RIGHT:
            cam.pan(-pan_amount, 0)
        elif action == InputAction.PAN_UP:
            cam.pan(0, pan_amount)
        elif action == InputAction.PAN_DOWN:
            cam.pan(0, -pan_amount)

        elif action == InputAction.ZOOM_IN:
            cam.zoom_in(self.ZOOM_IN_FACTOR)
        elif action == InputAction.ZOOM_OUT:
            cam.zoom_out(self.ZOOM_OUT_FACTOR)
        elif action == InputAction.RESET_VIEW:
            cam.reset()
            if self.on_recenter:
                self.on_recenter()

        elif action == InputAction.ELEVATION_UP:
            cam.active_max_layer = min(6, cam.active_max_layer + 1)
            cam.isolated_layer = None
            self._redraw()

        elif action == InputAction.ELEVATION_DOWN:
            cam.active_max_layer = max(0, cam.active_max_layer - 1)
            cam.isolated_layer = None
            self._redraw()

        elif action == InputAction.TOGGLE_LAYER_ISOLATION:
            if cam.isolated_layer is None:
                cam.isolated_layer = cam.active_max_layer
            else:
                cam.isolated_layer = None
            self._redraw()

        elif action == InputAction.TOGGLE_PERSPECTIVE:
            if cam.perspective == ViewPerspective.ISOMETRIC:
                cam.perspective = ViewPerspective.TOP_DOWN
            else:
                cam.perspective = ViewPerspective.ISOMETRIC
            if self.on_recenter:
                self.on_recenter()
            self._redraw()

        elif action == InputAction.TOGGLE_MINIMAP:
            cam.show_minimap = not cam.show_minimap

        elif action == InputAction.TOGGLE_SIDEBAR:
            cam.show_sidebar = not cam.show_sidebar

        elif action == InputAction.TOGGLE_METADATA:
            cam.show_metadata = not cam.show_metadata

        elif action == InputAction.TOGGLE_GRID:
            cam.show_grid = not cam.show_grid
            self._redraw()

        elif action == InputAction.TOGGLE_FLOORS:
            cam.show_floors = not cam.show_floors
            self._redraw()

        elif action == InputAction.TOGGLE_LEFT_WALLS:
            cam.show_left_walls = not cam.show_left_walls
            self._redraw()

        elif action == InputAction.TOGGLE_RIGHT_WALLS:
            cam.show_right_walls = not cam.show_right_walls
            self._redraw()

        elif action == InputAction.TOGGLE_CLUTTER:
            cam.show_clutter = not cam.show_clutter
            self._redraw()

        elif action == InputAction.TOGGLE_ENTITIES:
            cam.show_entities = not cam.show_entities
            self._redraw()

        elif action == InputAction.TOGGLE_MARKERS:
            cam.show_markers = not cam.show_markers
            self._redraw()

        elif action == InputAction.CYCLE_PALETTE:
            if self.on_cycle_palette:
                self.on_cycle_palette()

        elif action == InputAction.TOGGLE_FULLSCREEN:
            if self.on_toggle_fullscreen:
                self.on_toggle_fullscreen()

        elif action == InputAction.EXIT:
            if self.on_exit:
                self.on_exit()
