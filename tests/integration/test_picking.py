"""Integration tests for mouse-cursor grid cell picking at arbitrary camera zoom and pan offsets."""

import pytest
from saw_map.geometry.transform import IsometricTransform, TopDownTransform
from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument
from saw_map.viewer.camera import Camera, ViewPerspective
from saw_map.viewer.inspector import CellInspector


def make_dummy_document(width: int = 100, height: int = 80) -> MapDocument:
    """Creates a basic MapDocument for coordinate boundary tests."""
    return MapDocument(title="PickTest", version="21", width=width, height=height, cells={})


def make_visual_cell(x: int, y: int, z: int) -> MapCell:
    """Creates a cell with active visual content."""
    empty_comp = CellComponent(ComponentType.FLOOR, False, 0, 0, 0)
    vis_comp = CellComponent(ComponentType.CLUTTER, True, 2, 3, 0x8182)
    return MapCell(
        x=x,
        y=y,
        z=z,
        floor=empty_comp,
        left_wall=empty_comp,
        right_wall=empty_comp,
        clutter=vis_comp,
    )


def test_picking_center_at_origin_layer_0():
    """Validates picking origin cell (0, 0, 0) at center of screen with default camera on ground layer."""
    inspector = CellInspector()
    cam = Camera(x=0.0, y=0.0, zoom=1.0, active_max_layer=0)
    doc = make_dummy_document()

    win_w = 1280.0
    win_h = 720.0
    # Screen center
    picked = inspector.pick_cell(win_w / 2.0, win_h / 2.0, win_w, win_h, cam, doc)
    assert picked is not None
    assert picked == (0, 0, 0)


def test_picking_center_with_elevation_layer_6_isolation():
    """Validates that with single-layer isolation on layer 6, screen center maps to (4, 4, 6)."""
    inspector = CellInspector()
    cam = Camera(x=0.0, y=0.0, zoom=1.0, isolated_layer=6)
    doc = make_dummy_document()

    win_w = 1280.0
    win_h = 720.0
    picked = inspector.pick_cell(win_w / 2.0, win_h / 2.0, win_w, win_h, cam, doc)
    assert picked is not None
    assert picked == (4, 4, 6)


def test_top_down_raycast_picks_ground_tile_from_layer_6():
    """Validates that hovering over tile (20, 18, 0) from layer 6 selects (20, 18, 0) and not (20, 18, 6)."""
    inspector = CellInspector()
    cam = Camera(x=0.0, y=0.0, zoom=1.0, active_max_layer=6)
    doc = make_dummy_document()

    # Ground tile with visual content at (20, 18, 0)
    doc.cells[(20, 18, 0)] = make_visual_cell(20, 18, 0)
    # Upper layer has empty air mask (sprite_frame_index >= 200)
    mask_comp = CellComponent(ComponentType.FLOOR, True, 0, 254, 0xFF00)
    empty_comp = CellComponent(ComponentType.LEFT_WALL, False, 0, 0, 0)
    doc.cells[(20, 18, 6)] = MapCell(
        x=20, y=18, z=6, floor=mask_comp, left_wall=empty_comp, right_wall=empty_comp, clutter=empty_comp
    )

    win_w = 1280.0
    win_h = 720.0

    # Calculate screen center for tile (20, 18, 0)
    sx, sy = inspector.iso_transform.world_to_screen(20, 18, 0.0)
    screen_x = win_w / 2.0 + sx
    screen_y = win_h / 2.0 + (sy + 32.0)  # Center of tile diamond

    picked = inspector.pick_cell(screen_x, screen_y, win_w, win_h, cam, doc)
    assert picked is not None
    # Must select (20, 18, 0) and NOT (20, 18, 6)!
    assert picked == (20, 18, 0)


def test_top_down_raycast_picks_elevated_structure():
    """Validates that an elevated roof tile at layer 2 is picked over ground layer 0."""
    inspector = CellInspector()
    cam = Camera(x=0.0, y=0.0, zoom=1.0, active_max_layer=6)
    doc = make_dummy_document()

    # Ground cell and elevated roof cell at layer 2
    doc.cells[(15, 12, 0)] = make_visual_cell(15, 12, 0)
    doc.cells[(15, 12, 2)] = make_visual_cell(15, 12, 2)

    win_w = 1280.0
    win_h = 720.0

    # Hover over the roof at layer 2
    sx, sy = inspector.iso_transform.world_to_screen(15, 12, 2.0)
    screen_x = win_w / 2.0 + sx
    screen_y = win_h / 2.0 + (sy + 32.0)

    picked = inspector.pick_cell(screen_x, screen_y, win_w, win_h, cam, doc)
    assert picked == (15, 12, 2)


def test_picking_with_pan_offset():
    """Validates picking after camera panning into positive map territory."""
    inspector = CellInspector()
    cam = Camera(x=-64.0, y=-32.0, zoom=1.0, active_max_layer=0)
    doc = make_dummy_document()

    win_w = 1280.0
    win_h = 720.0
    picked = inspector.pick_cell(win_w / 2.0, win_h / 2.0, win_w, win_h, cam, doc)
    assert picked is not None
    assert picked == (1, 0, 0)


def test_picking_with_zoom():
    """Validates picking at 2.0x zoom on layer 0."""
    inspector = CellInspector()
    cam = Camera(x=0.0, y=0.0, zoom=2.0, active_max_layer=0)
    doc = make_dummy_document()

    win_w = 1280.0
    win_h = 720.0
    picked = inspector.pick_cell(win_w / 2.0, win_h / 2.0, win_w, win_h, cam, doc)
    assert picked is not None
    assert picked == (0, 0, 0)


def test_picking_out_of_bounds():
    """Validates coordinates outside the map rectangle return None."""
    inspector = CellInspector()
    cam = Camera(x=0.0, y=0.0, zoom=1.0)
    doc = make_dummy_document(width=20, height=20)

    # Point far off in top-left
    picked = inspector.pick_cell(0.0, 0.0, 1280.0, 720.0, cam, doc)
    # Origin is at screen center, so (0, 0) is well outside a 20x20 board
    assert picked is None


def test_top_down_picking():
    """Validates orthogonal top-down picking selecting top visible layer."""
    inspector = CellInspector()
    cam = Camera(x=0.0, y=0.0, zoom=1.0, perspective=ViewPerspective.TOP_DOWN, active_max_layer=6)
    doc = make_dummy_document(width=50, height=50)
    doc.cells[(2, 2, 0)] = make_visual_cell(2, 2, 0)

    win_w = 1280.0
    win_h = 720.0
    # Point at center + 64 px X, center + 64 px Y (cell 2, 2 with 32px cells)
    picked = inspector.pick_cell(win_w / 2.0 + 64.0, win_h / 2.0 + 64.0, win_w, win_h, cam, doc)
    assert picked == (2, 2, 0)
