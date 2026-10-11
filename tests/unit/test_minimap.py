"""Unit tests for 2D minimap terrain generation and viewport frustum projection."""

import pytest
from PIL import Image
from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument, TilesetDefinition
from saw_map.viewer.camera import Camera, ViewPerspective
from saw_map.viewer.minimap import MinimapCalculator, generate_minimap_image, get_surface_color


@pytest.fixture
def mock_tileset() -> TilesetDefinition:
    """Fixture providing a mock tileset definition."""
    return TilesetDefinition(
        name="Airfield",
        surfaces=["sgrass", "shill", "ssnow1", "sdirt", "sstone1", "strack2"],
        left_walls=["lwood1", "lmetal1"],
        right_walls=["rwood1", "rmetal1"],
        clutter=["snwtree1"],
    )


def test_surface_color_mapping(mock_tileset: TilesetDefinition):
    """Validates terrain asset name to RGB surface class coloring."""
    # Snow
    assert get_surface_color("ssnow1") == (210, 215, 220)
    assert get_surface_color("csnow1") == (210, 215, 220)

    # Stone / Hangar concrete
    assert get_surface_color("sstone1") == (90, 95, 100)
    assert get_surface_color("sstone3") == (90, 95, 100)

    # Dirt / mud
    assert get_surface_color("sdirt") == (130, 90, 50)

    # Railroad steel
    assert get_surface_color("strack2") == (55, 55, 60)

    # Grass
    assert get_surface_color("sgrass") == (70, 120, 60)

    # None / Empty
    assert get_surface_color(None) == (10, 12, 16)


def test_generate_minimap_image(mock_tileset: TilesetDefinition):
    """Validates top-down orthogonal image generation from map cells."""
    cells = {}
    # Create a 20x20 test map
    for y in range(20):
        for x in range(20):
            # Place snow on left, dirt on right
            grp = 2 if x < 10 else 3
            # Group 2 is ssnow1, Group 3 is sdirt
            raw_w = (1 << 15) | (0 << 7) | (grp & 0x7F)
            comp_surf = CellComponent.from_raw_word(ComponentType.FLOOR, raw_w)
            empty_comp = CellComponent(ComponentType.CLUTTER, False, 0, 0, 0)
            cells[(x, y, 0)] = MapCell(
                x=x,
                y=y,
                z=0,
                floor=comp_surf,
                left_wall=empty_comp,
                right_wall=empty_comp,
                clutter=empty_comp,
            )

    # A tree (flat group 10 = snwtree1) at (3, 3) and a left wall (group 6) at (12, 12)
    cells[(3, 3, 0)].clutter = CellComponent.from_raw_word(ComponentType.CLUTTER, (1 << 15) | 10)
    cells[(12, 12, 0)].left_wall = CellComponent.from_raw_word(ComponentType.LEFT_WALL, (1 << 15) | 6)

    doc = MapDocument(title="MinimapTest", version="21", width=20, height=20, cells=cells)
    img = generate_minimap_image(doc, mock_tileset, active_layer=0)

    assert isinstance(img, Image.Image)
    assert img.size == (20, 20)
    assert img.mode == "RGBA"

    # Pixel (5, 5) should be snow (light grey/white)
    r, g, b, a = img.getpixel((5, 5))
    assert (r, g, b) == (210, 215, 220)
    assert a == 255

    # Pixel (15, 15) should be dirt (brown)
    r, g, b, a = img.getpixel((15, 15))
    assert (r, g, b) == (130, 90, 50)
    assert a == 255

    # Objects and walls override the ground color
    assert img.getpixel((3, 3))[:3] == (35, 75, 30)
    assert img.getpixel((12, 12))[:3] == (45, 45, 50)


def test_minimap_calculator_bounds_offset():
    """Validates minimap positioning with and without sidebar open."""
    calc = MinimapCalculator(box_width=160.0, box_height=120.0, margin=12.0)

    # Normal bounds without sidebar
    bounds_no_sb = calc.get_minimap_bounds(1280.0, 720.0, offset_right=0.0)
    assert bounds_no_sb.left == 1280.0 - 160.0 - 12.0
    assert bounds_no_sb.top == 12.0
    assert bounds_no_sb.width == 160.0
    assert bounds_no_sb.height == 120.0

    # Bounds with sidebar offset (260 px)
    bounds_sb = calc.get_minimap_bounds(1280.0, 720.0, offset_right=260.0)
    assert bounds_sb.left == 1280.0 - 160.0 - 12.0 - 260.0
    assert bounds_sb.left < bounds_no_sb.left


def test_calculate_viewport_polygon_isometric():
    """Validates 4-vertex viewport diamond calculation in isometric view."""
    calc = MinimapCalculator()
    doc = MapDocument(title="FrustumTest", version="21", width=100, height=100, cells={})
    cam = Camera(x=0.0, y=0.0, zoom=1.0, perspective=ViewPerspective.ISOMETRIC)

    poly = calc.calculate_viewport_polygon(
        map_doc=doc,
        camera=cam,
        screen_w=1280.0,
        screen_h=720.0,
        frame_x=10.0,
        frame_y=10.0,
        frame_w=100.0,
        frame_h=100.0,
        invert_y=False,
    )

    assert len(poly) == 4
    # All vertices should be valid floats
    for px, py in poly:
        assert isinstance(px, float)
        assert isinstance(py, float)


def test_minimap_panning_forward_moves_frustum_upward_pygame():
    """Validates that walking forwards ('W' / +dy) moves frustum upwards towards North in Pygame."""
    calc = MinimapCalculator()
    doc = MapDocument(title="FrustumTest", version="21", width=100, height=100, cells={})
    cam = Camera(x=-1000.0, y=-1000.0, zoom=1.0, perspective=ViewPerspective.ISOMETRIC)

    poly_init = calc.calculate_viewport_polygon(
        doc, cam, 1280.0, 720.0, 0.0, 0.0, 100.0, 100.0, invert_y=False
    )
    center_y_init = sum(p[1] for p in poly_init) / 4.0

    # Pan forwards ('W' / +dy)
    cam.pan(0, 200.0)
    poly_panned = calc.calculate_viewport_polygon(
        doc, cam, 1280.0, 720.0, 0.0, 0.0, 100.0, 100.0, invert_y=False
    )
    center_y_panned = sum(p[1] for p in poly_panned) / 4.0

    # In Pygame (Y-down), moving forward towards top of map decreases py
    assert center_y_panned < center_y_init


def test_minimap_panning_forward_moves_frustum_upward_arcade():
    """Validates that walking forwards ('W' / +dy) moves frustum upwards towards North in Arcade."""
    calc = MinimapCalculator()
    doc = MapDocument(title="FrustumTest", version="21", width=100, height=100, cells={})
    cam = Camera(x=-1000.0, y=-1000.0, zoom=1.0, perspective=ViewPerspective.ISOMETRIC)

    poly_init = calc.calculate_viewport_polygon(
        doc, cam, 1280.0, 720.0, 0.0, 0.0, 100.0, 100.0, invert_y=True
    )
    center_y_init = sum(p[1] for p in poly_init) / 4.0

    # Pan forwards ('W' / +dy)
    cam.pan(0, 200.0)
    poly_panned = calc.calculate_viewport_polygon(
        doc, cam, 1280.0, 720.0, 0.0, 0.0, 100.0, 100.0, invert_y=True
    )
    center_y_panned = sum(p[1] for p in poly_panned) / 4.0

    # In Arcade (Y-up), moving forward towards top of map increases py
    assert center_y_panned > center_y_init

