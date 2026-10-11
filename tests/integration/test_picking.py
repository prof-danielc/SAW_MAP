"""Integration tests for mouse-cursor grid cell picking at arbitrary camera zoom and pan offsets."""

import pytest
from saw_map.geometry.transform import IsometricTransform, TopDownTransform
from saw_map.maps.model import MapCell, MapDocument
from saw_map.viewer.camera import Camera, ViewPerspective
from saw_map.viewer.inspector import CellInspector


def make_dummy_document(width: int = 100, height: int = 80) -> MapDocument:
    """Creates a basic MapDocument for coordinate boundary tests."""
    return MapDocument(title="PickTest", version="21", width=width, height=height, cells={})


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


def test_picking_center_with_elevation_layer_6():
    """Validates that on layer 6 (offset -96 px), screen center maps to (3, 3, 6)."""
    inspector = CellInspector()
    cam = Camera(x=0.0, y=0.0, zoom=1.0, active_max_layer=6)
    doc = make_dummy_document()

    win_w = 1280.0
    win_h = 720.0
    picked = inspector.pick_cell(win_w / 2.0, win_h / 2.0, win_w, win_h, cam, doc)
    assert picked is not None
    assert picked == (3, 3, 6)


def test_picking_with_pan_offset():
    """Validates picking after camera panning into positive map territory."""
    inspector = CellInspector()
    cam = Camera(x=-64.0, y=-32.0, zoom=1.0, active_max_layer=0)
    doc = make_dummy_document()

    win_w = 1280.0
    win_h = 720.0
    picked = inspector.pick_cell(win_w / 2.0, win_h / 2.0, win_w, win_h, cam, doc)
    assert picked is not None
    assert picked == (2, 0, 0)


def test_picking_with_zoom():
    """Validates picking at 2.0x zoom on layer 0."""
    inspector = CellInspector()
    cam = Camera(x=0.0, y=0.0, zoom=2.0, active_max_layer=0)
    doc = make_dummy_document()

    win_w = 1280.0
    win_h = 720.0
    picked = inspector.pick_cell(win_w / 2.0, win_h / 2.0, win_w, win_h, cam, doc)
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
    """Validates orthogonal top-down picking."""
    inspector = CellInspector()
    cam = Camera(x=0.0, y=0.0, zoom=1.0, perspective=ViewPerspective.TOP_DOWN)
    doc = make_dummy_document(width=50, height=50)

    win_w = 1280.0
    win_h = 720.0
    # Point at center + 64 px X, center + 64 px Y (cell 2, 2 with 32px cells)
    picked = inspector.pick_cell(win_w / 2.0 + 64.0, win_h / 2.0 + 64.0, win_w, win_h, cam, doc)
    assert picked == (2, 2, 6)
