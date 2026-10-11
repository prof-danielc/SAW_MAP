"""Integration tests for rendering overlays (minimap, sidebar, metadata dialog) across backends."""

import os
import pygame
import pytest
from saw_map.assets.loader import AssetLoader
from saw_map.formats.map_reader import MapReader
from saw_map.formats.set_parser import TilesetParser
from saw_map.rendering.pygame_backend import PygameRenderer
from saw_map.viewer.camera import Camera


AIRFIELD_MAP = "Research/SSI/Soldiers at War/Single_g/Airfield.map"
AIRFIELD_SET = "Research/SSI/Soldiers at War/Sets/Airfield.set"


@pytest.mark.skipif(not os.path.exists(AIRFIELD_MAP), reason="Game assets not found")
def test_pygame_minimap_and_sidebar_rendering():
    """Validates Pygame rendering frames with minimap and sidebar enabled."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    doc = MapReader.parse_map(AIRFIELD_MAP)
    tileset = TilesetParser.parse_file(AIRFIELD_SET) if os.path.exists(AIRFIELD_SET) else None
    loader = AssetLoader("Research/SSI/Soldiers at War")

    renderer = PygameRenderer()
    renderer.initialize(width=1024, height=768, title="Test Viewport")
    renderer.set_map(doc, loader, tileset=tileset)

    # 1. Render frame with minimap and sidebar when hovering tile (20, 18, 0)
    cam = Camera(show_minimap=True, show_sidebar=True)
    renderer.hovered_cell = (20, 18, 0)
    renderer.render_frame(cam)

    assert renderer._minimap_surface is not None
    assert renderer._minimap_surface.get_size() == (doc.width, doc.height)

    # 2. Render frame with no hovered cell
    renderer.hovered_cell = None
    renderer.render_frame(cam)

    # 3. Key presses route through the shared InputHandler; metadata dialog renders
    renderer._handle_keydown(pygame.K_F1)
    assert cam.show_metadata is True
    renderer._handle_keydown(pygame.K_6)
    assert cam.show_markers is True
    renderer.hovered_cell = (44, 41, 0)  # cell holding a soldier
    renderer._handle_keydown(pygame.K_PAGEDOWN)
    assert cam.active_max_layer == 5
    renderer._handle_keydown(pygame.K_HOME)
    mid_x, mid_y = doc.center
    assert (cam.x, cam.y) == tuple(-v for v in renderer.iso_transform.world_to_screen(mid_x, mid_y, 0))
    renderer.render_frame(cam)

    renderer.close()


@pytest.mark.skipif(not os.path.exists(AIRFIELD_MAP), reason="Game assets not found")
def test_arcade_minimap_and_sidebar_rendering():
    """Validates Arcade rendering frames with minimap and sidebar enabled."""
    import arcade
    from saw_map.rendering.arcade_backend import ArcadeRenderer

    doc = MapReader.parse_map(AIRFIELD_MAP)
    tileset = TilesetParser.parse_file(AIRFIELD_SET) if os.path.exists(AIRFIELD_SET) else None
    loader = AssetLoader("Research/SSI/Soldiers at War")

    renderer = ArcadeRenderer()
    renderer.initialize(width=640, height=480, title="Headless Arcade Test")
    renderer.set_map(doc, loader, tileset=tileset)

    # 1. Render frame with minimap and sidebar when hovering tile (20, 18, 0)
    cam = Camera(show_minimap=True, show_sidebar=True)
    renderer.hovered_cell = (20, 18, 0)
    renderer.render_frame(cam)

    assert renderer._minimap_texture is not None

    # 2. Render frame with no hovered cell
    renderer.hovered_cell = None
    renderer.render_frame(cam)

    # 3. Key presses route through the shared InputHandler; metadata dialog renders
    renderer.window.on_key_press(arcade.key.H, 0)
    assert cam.show_metadata is True
    entity_sprites = len(renderer.sprite_list)
    renderer.window.on_key_press(arcade.key.KEY_5, 0)
    assert cam.show_entities is False
    assert len(renderer.sprite_list) < entity_sprites
    renderer.window.on_key_press(arcade.key.KEY_5, 0)
    assert len(renderer.sprite_list) == entity_sprites
    renderer.hovered_cell = (44, 41, 0)  # cell holding a soldier
    renderer.window.on_key_press(arcade.key.Q, 0)
    assert cam.active_max_layer == 5
    renderer.window.on_mouse_scroll(320, 240, 0, 1)
    assert cam.zoom == 1.25
    renderer.render_frame(cam)
    assert renderer._metadata_texts

    renderer.close()

