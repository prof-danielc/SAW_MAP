"""Unit tests for camera navigation, zoom bounds, and coordinate resets."""

import pytest
from saw_map.viewer.camera import Camera, ViewPerspective


def test_camera_initial_state():
    """Validates camera default values."""
    cam = Camera()
    assert cam.x == 0.0
    assert cam.y == 0.0
    assert cam.zoom == 1.0
    assert cam.active_max_layer == 6
    assert cam.isolated_layer is None
    assert cam.perspective == ViewPerspective.ISOMETRIC
    assert cam.show_minimap is True
    assert cam.show_sidebar is False


def test_camera_panning():
    """Validates camera translation."""
    cam = Camera()
    cam.pan(25.0, -10.0)
    assert cam.x == 25.0
    assert cam.y == -10.0

    cam.pan(-5.0, 15.0)
    assert cam.x == 20.0
    assert cam.y == 5.0


def test_camera_zoom_clamping():
    """Validates zoom factor stays within [0.25, 4.0]."""
    cam = Camera()
    cam.set_zoom(0.1)
    assert cam.zoom == 0.25

    cam.set_zoom(10.0)
    assert cam.zoom == 4.0

    cam.set_zoom(2.0)
    assert cam.zoom == 2.0


def test_camera_zoom_step():
    """Validates zoom_in and zoom_out methods."""
    cam = Camera()
    cam.zoom_in(1.25)
    assert cam.zoom == 1.25

    cam.zoom_out(0.8)
    assert cam.zoom == pytest.approx(1.0)


def test_camera_reset():
    """Validates resetting camera back to origin and 1.0x zoom."""
    cam = Camera()
    cam.pan(150.0, -80.0)
    cam.set_zoom(3.0)
    assert cam.x == 150.0
    assert cam.zoom == 3.0

    cam.reset()
    assert cam.x == 0.0
    assert cam.y == 0.0
    assert cam.zoom == 1.0
