"""Unit tests for elevation layer filtering and component visibility toggles."""

import pytest
from saw_map.maps.model import CellComponent, ComponentType, MapCell, MapDocument
from saw_map.rendering.draw_order import DrawOrderStrategy


def make_test_map() -> MapDocument:
    """Creates a synthetic multi-layer map document."""
    cells = {}
    # Create 3 cells at z=0, z=1, z=2
    for z in range(3):
        # Cell with floor and clutter
        floor_comp = CellComponent.from_raw_word(ComponentType.FLOOR, (1 << 15) | (1 << 7) | 1)
        left_comp = CellComponent.from_raw_word(ComponentType.LEFT_WALL, (1 << 15) | (2 << 7) | 2)
        right_comp = CellComponent.from_raw_word(ComponentType.RIGHT_WALL, 0) # empty
        clutter_comp = CellComponent.from_raw_word(ComponentType.CLUTTER, (1 << 15) | (3 << 7) | 3)

        cell = MapCell(
            x=5, y=5, z=z,
            floor=floor_comp,
            left_wall=left_comp,
            right_wall=right_comp,
            clutter=clutter_comp,
        )
        cells[(5, 5, z)] = cell

    return MapDocument(title="FilterTest", version="21", width=20, height=20, cells=cells)


def test_elevation_max_layer_filtering():
    """Validates filtering by maximum visible layer."""
    doc = make_test_map()

    # Max layer 0: only items at z=0
    items_z0 = DrawOrderStrategy.generate_render_list(doc, max_layer=0)
    assert all(item.grid_z == 0 for item in items_z0)
    assert len(items_z0) == 3  # floor, left_wall, clutter

    # Max layer 1: items at z=0 and z=1
    items_z1 = DrawOrderStrategy.generate_render_list(doc, max_layer=1)
    assert len(items_z1) == 6
    assert all(item.grid_z in (0, 1) for item in items_z1)

    # Max layer 2: all items
    items_z2 = DrawOrderStrategy.generate_render_list(doc, max_layer=2)
    assert len(items_z2) == 9


def test_single_layer_isolation():
    """Validates isolated_layer parameter only includes that exact layer."""
    doc = make_test_map()

    items_iso1 = DrawOrderStrategy.generate_render_list(doc, isolated_layer=1)
    assert len(items_iso1) == 3
    assert all(item.grid_z == 1 for item in items_iso1)


def test_component_type_toggles():
    """Validates structural category filtering (floors, walls, clutter)."""
    doc = make_test_map()

    # Disable floors
    no_floors = DrawOrderStrategy.generate_render_list(doc, max_layer=0, show_floors=False)
    assert len(no_floors) == 2
    assert all(item.component_type != ComponentType.FLOOR for item in no_floors)

    # Disable clutter
    no_clutter = DrawOrderStrategy.generate_render_list(doc, max_layer=0, show_clutter=False)
    assert len(no_clutter) == 2
    assert all(item.component_type != ComponentType.CLUTTER for item in no_clutter)

    # Only left walls enabled
    only_walls = DrawOrderStrategy.generate_render_list(
        doc, max_layer=0, show_floors=False, show_left_walls=True, show_right_walls=False, show_clutter=False
    )
    assert len(only_walls) == 1
    assert only_walls[0].component_type == ComponentType.LEFT_WALL
