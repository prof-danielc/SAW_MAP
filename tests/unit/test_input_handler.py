"""Unit tests for semantic input action dispatching and overlay text formatting."""

from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument, TilesetDefinition
from saw_map.viewer.camera import Camera, ViewPerspective
from saw_map.viewer.input_handler import InputAction, InputHandler
from saw_map.viewer.overlays import OverlayModel


def test_pan_actions_follow_camera_convention():
    """UP/LEFT pan with positive deltas, DOWN/RIGHT with negative deltas, scaled by zoom."""
    cam = Camera(zoom=2.0)
    handler = InputHandler(cam)

    handler.handle_action(InputAction.PAN_UP, step=40.0)
    assert (cam.x, cam.y) == (0.0, 20.0)
    handler.handle_action(InputAction.PAN_DOWN, step=40.0)
    assert (cam.x, cam.y) == (0.0, 0.0)
    handler.handle_action(InputAction.PAN_LEFT, step=40.0)
    assert (cam.x, cam.y) == (20.0, 0.0)
    handler.handle_action(InputAction.PAN_RIGHT, step=40.0)
    assert (cam.x, cam.y) == (0.0, 0.0)


def test_layer_and_filter_actions_request_redraw():
    """Layer, isolation, and component toggles mutate the camera and trigger a redraw."""
    cam = Camera()
    redraws = []
    handler = InputHandler(cam, on_redraw_needed=lambda: redraws.append(1))

    handler.handle_action(InputAction.ELEVATION_DOWN)
    assert cam.active_max_layer == 5
    handler.handle_action(InputAction.ELEVATION_UP)
    handler.handle_action(InputAction.ELEVATION_UP)
    assert cam.active_max_layer == 6

    handler.handle_action(InputAction.TOGGLE_LAYER_ISOLATION)
    assert cam.isolated_layer == 6
    handler.handle_action(InputAction.ELEVATION_DOWN)
    assert cam.isolated_layer is None

    handler.handle_action(InputAction.TOGGLE_FLOORS)
    handler.handle_action(InputAction.TOGGLE_CLUTTER)
    assert cam.show_floors is False and cam.show_clutter is False
    assert len(redraws) == 7

    # Overlay toggles do not invalidate the render list
    handler.handle_action(InputAction.TOGGLE_MINIMAP)
    handler.handle_action(InputAction.TOGGLE_SIDEBAR)
    handler.handle_action(InputAction.TOGGLE_METADATA)
    assert (cam.show_minimap, cam.show_sidebar, cam.show_metadata) == (False, True, True)
    assert len(redraws) == 7


def test_reset_perspective_and_callbacks():
    """Reset and perspective toggle recenter the camera; other actions reach their callbacks."""
    cam = Camera(x=50.0, y=60.0, zoom=2.0)
    calls = []
    handler = InputHandler(
        cam,
        on_redraw_needed=lambda: calls.append("redraw"),
        on_recenter=lambda: calls.append("recenter"),
        on_cycle_palette=lambda: calls.append("palette"),
        on_toggle_fullscreen=lambda: calls.append("fullscreen"),
        on_exit=lambda: calls.append("exit"),
    )

    handler.handle_action(InputAction.RESET_VIEW)
    assert cam.zoom == 1.0
    assert calls == ["recenter"]

    handler.handle_action(InputAction.TOGGLE_PERSPECTIVE)
    assert cam.perspective == ViewPerspective.TOP_DOWN
    assert calls == ["recenter", "recenter", "redraw"]

    handler.handle_action(InputAction.CYCLE_PALETTE)
    handler.handle_action(InputAction.TOGGLE_FULLSCREEN)
    handler.handle_action(InputAction.EXIT)
    assert calls[-3:] == ["palette", "fullscreen", "exit"]


def test_zoom_at_cursor_keeps_world_point_fixed():
    """The world point under the cursor stays at the same screen position after zooming."""
    cam = Camera(x=-300.0, y=-150.0, zoom=1.0)
    handler = InputHandler(cam)
    win_w, win_h, cx, cy = 1280.0, 720.0, 900.0, 200.0

    def world_under_cursor() -> tuple:
        return (
            (cx - win_w / 2.0) / cam.zoom - cam.x,
            (cy - win_h / 2.0) / cam.zoom - cam.y,
        )

    before = world_under_cursor()
    handler.handle_zoom_at_cursor(True, cx, cy, win_w, win_h)
    assert cam.zoom == 1.25
    after = world_under_cursor()
    assert abs(before[0] - after[0]) < 1e-6
    assert abs(before[1] - after[1]) < 1e-6


def test_overlay_status_bar_and_metadata_lines():
    """Validates status bar text and metadata dialog lines built from the map document."""
    tileset = TilesetDefinition(
        name="Generic3", surfaces=["sgrass", "sdirt"], left_walls=["lwood1"], right_walls=["rwood1"], clutter=["tree1"]
    )
    empty = CellComponent.from_raw_word(ComponentType.LEFT_WALL, 0)
    cell = MapCell(
        x=30,
        y=25,
        z=0,
        floor=CellComponent.from_raw_word(ComponentType.FLOOR, (1 << 15) | (2 << 7) | 1),
        left_wall=empty,
        right_wall=empty,
        clutter=empty,
    )
    doc = MapDocument(
        title="Generic3",
        version="21",
        width=78,
        height=60,
        cells={(30, 25, 0): cell},
        tileset_names=["Generic3"],
        name="Bloody Farm",
        mission_text="Hold the farm.\n" + "word " * 40,
        origin_x=26,
        origin_y=20,
    )
    cam = Camera()

    status = OverlayModel.get_status_bar_text(doc, cam, (30, 25, 0), tileset)
    assert status.startswith("Map: Bloody Farm (78x60)")
    assert "Hover: (30, 25, 0) [sdirt.obj:2]" in status
    assert OverlayModel.get_status_bar_text(None, cam, None) == "No map loaded"

    lines = OverlayModel.get_map_metadata_lines(doc, tileset, wrap_width=40)
    assert lines[0] == "MAP: Bloody Farm"
    assert "Tileset: Generic3" in lines
    assert "MISSION BRIEFING" in lines
    assert "Hold the farm." in lines
    assert all(len(line) <= 40 for line in lines[lines.index("MISSION BRIEFING"):])
    assert OverlayModel.get_map_metadata_lines(None, None) == ["No map document loaded."]


def test_map_document_window_contains_and_center():
    """Validates playable window helpers for a centered 78x60 map."""
    doc = MapDocument(title="T", version="21", width=78, height=60, origin_x=26, origin_y=20)
    assert doc.contains(26, 20) and doc.contains(103, 79)
    assert not doc.contains(25, 20) and not doc.contains(104, 79) and not doc.contains(26, 80)
    assert doc.center == (65.0, 50.0)


def test_held_pan_keys_pan_continuously():
    """Held pan keys move the camera every frame, scaled by elapsed time and zoom."""
    cam = Camera(zoom=2.0)
    handler = InputHandler(cam)

    # Nothing held: no movement
    assert handler.update(0.1) is False and (cam.x, cam.y) == (0.0, 0.0)

    handler.set_pan_held(InputAction.PAN_UP, True)
    assert handler.is_panning
    assert handler.update(0.1) is True
    assert handler.update(0.1) is True
    # Two frames of 0.1 s at PAN_SPEED window pixels per second, divided by zoom
    step = InputHandler.PAN_SPEED * 0.1 / 2.0
    assert (cam.x, cam.y) == (0.0, 2 * step)

    # A second key combines into a diagonal; opposite keys cancel
    handler.set_pan_held(InputAction.PAN_RIGHT, True)
    handler.update(0.1)
    assert (cam.x, cam.y) == (-step, 3 * step)
    handler.set_pan_held(InputAction.PAN_DOWN, True)
    handler.update(0.1)
    assert (cam.x, cam.y) == (-2 * step, 3 * step)

    # Releasing stops the movement
    handler.release_all_pans()
    assert handler.is_panning is False
    assert handler.update(0.1) is False and (cam.x, cam.y) == (-2 * step, 3 * step)


def test_pan_update_ignores_other_actions_and_caps_long_frames():
    """Only pan actions can be held, and a stalled frame does not jump the view."""
    cam = Camera()
    handler = InputHandler(cam)

    handler.set_pan_held(InputAction.ZOOM_IN, True)
    assert handler.is_panning is False

    handler.set_pan_held(InputAction.PAN_LEFT, True)
    handler.update(5.0)
    assert cam.x == InputHandler.PAN_SPEED * InputHandler.MAX_PAN_FRAME_TIME
    handler.set_pan_held(InputAction.PAN_LEFT, False)
    assert handler.is_panning is False


def test_grid_toggle_requests_redraw():
    """The cell grid is painted on the floor sprites, so toggling it rebuilds them."""
    cam = Camera()
    redraws = []
    handler = InputHandler(cam, on_redraw_needed=lambda: redraws.append(1))

    assert cam.show_grid is False
    handler.handle_action(InputAction.TOGGLE_GRID)
    assert cam.show_grid is True
    handler.handle_action(InputAction.TOGGLE_GRID)
    assert cam.show_grid is False and len(redraws) == 2
