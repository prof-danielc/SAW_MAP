"""Unit tests for isometric and orthogonal coordinate transformations."""

import pytest
from saw_map.geometry.transform import IsometricTransform, TopDownTransform


def test_isometric_origin():
    """Origin (0, 0, 0) transforms to (0.0, 0.0)."""
    iso = IsometricTransform(tile_width=64.0, tile_height=32.0, elevation_step=16.0)
    sx, sy = iso.world_to_screen(0.0, 0.0, 0.0)
    assert sx == 0.0
    assert sy == 0.0

    gx, gy = iso.screen_to_world_float(0.0, 0.0, 0.0)
    assert gx == pytest.approx(0.0)
    assert gy == pytest.approx(0.0)


def test_isometric_forward_calculation():
    """Tests forward projection for known grid points."""
    iso = IsometricTransform(tile_width=64.0, tile_height=32.0, elevation_step=16.0)

    # (1, 0, 0): screen_x = (1 - 0) * 32 = 32, screen_y = (1 + 0) * 16 = 16
    sx, sy = iso.world_to_screen(1.0, 0.0, 0.0)
    assert sx == pytest.approx(32.0)
    assert sy == pytest.approx(16.0)

    # (0, 1, 0): screen_x = (0 - 1) * 32 = -32, screen_y = (0 + 1) * 16 = 16
    sx, sy = iso.world_to_screen(0.0, 1.0, 0.0)
    assert sx == pytest.approx(-32.0)
    assert sy == pytest.approx(16.0)

    # (1, 1, 0): screen_x = 0, screen_y = (1 + 1) * 16 = 32
    sx, sy = iso.world_to_screen(1.0, 1.0, 0.0)
    assert sx == pytest.approx(0.0)
    assert sy == pytest.approx(32.0)


def test_isometric_elevation_displacement():
    """Tests vertical elevation displacement per Z layer."""
    iso = IsometricTransform(tile_width=64.0, tile_height=32.0, elevation_step=16.0)

    # At Z=1, screen_y is offset by -16
    sx, sy = iso.world_to_screen(0.0, 0.0, 1.0)
    assert sx == pytest.approx(0.0)
    assert sy == pytest.approx(-16.0)

    # At Z=3, screen_y is offset by -48
    sx, sy = iso.world_to_screen(0.0, 0.0, 3.0)
    assert sx == pytest.approx(0.0)
    assert sy == pytest.approx(-48.0)


def test_isometric_roundtrip_precision():
    """Tests that screen_to_world_float(world_to_screen(x, y, z)) returns original (x, y)."""
    iso = IsometricTransform(tile_width=64.0, tile_height=32.0, elevation_step=16.0)

    for gx in [0.0, 5.0, 23.5, 99.0]:
        for gy in [0.0, 8.0, 42.25, 75.0]:
            for gz in [0.0, 1.0, 4.0, 6.0]:
                sx, sy = iso.world_to_screen(gx, gy, gz)
                rx, ry = iso.screen_to_world_float(sx, sy, gz)
                assert rx == pytest.approx(gx, abs=1e-6)
                assert ry == pytest.approx(gy, abs=1e-6)


def test_isometric_integer_picking():
    """Tests screen_to_world integer grid snapping."""
    iso = IsometricTransform(tile_width=64.0, tile_height=32.0, elevation_step=16.0)

    # Center of tile (10, 20) at z=2: gx = 10.5, gy = 20.5
    sx, sy = iso.world_to_screen(10.5, 20.5, 2.0)
    ix, iy = iso.screen_to_world(sx, sy, 2.0)
    assert ix == 10
    assert iy == 20


def test_top_down_transform():
    """Tests orthogonal top down transform."""
    td = TopDownTransform(cell_size=32.0)
    sx, sy = td.world_to_screen(5.0, 10.0)
    assert sx == 160.0
    assert sy == 320.0

    ix, iy = td.screen_to_world(165.0, 335.0)
    assert ix == 5
    assert iy == 10
