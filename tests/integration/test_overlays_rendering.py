"""Integration tests for rendering overlays (minimap, sidebar, metadata dialog) across backends."""

import os
import pygame
import pytest
from saw_map.assets.loader import AssetLoader
from saw_map.formats.map_reader import MapReader
from saw_map.formats.set_parser import TilesetParser
from saw_map.rendering.pygame_backend import PygameRenderer
from saw_map.viewer.camera import Camera
from saw_map.viewer.input_handler import InputHandler
from saw_map.viewer.minimap import get_minimap_markers


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
    # The inspected cell is highlighted on its floor sprite (tinted variant)
    assert any("#hover" in key[0] for key in renderer._surface_cache)

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

    # 4. Pan keys are held, not stepped: the camera moves on frame updates until release
    start_x = cam.x
    renderer._handle_keydown(pygame.K_LEFT)
    assert cam.x == start_x
    assert renderer.input.update(0.1) is True
    assert cam.x == start_x + InputHandler.PAN_SPEED * 0.1
    renderer._handle_keyup(pygame.K_LEFT)
    assert renderer.input.update(0.1) is False

    # 5. The cell grid (painted on floor sprite borders) and the minimap soldier dots render
    renderer._handle_keydown(pygame.K_g)
    assert cam.show_grid is True
    assert len(get_minimap_markers(doc, cam.active_max_layer)) > 0
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
    # The inspected cell is highlighted on its floor sprite: same sprite, tinted texture
    assert renderer._highlighted_cell == (20, 18, 0)
    floor_sprite, floor_item = renderer._floor_sprites[(20, 18, 0)]
    assert floor_sprite.texture is renderer._get_texture_data(floor_item, renderer.palette, highlight=True)[0]
    # The minimap shares the sprite atlas: drawing it must not switch the atlas to linear filtering,
    # which blurs the map sprites and shows seams between floor tiles
    nearest = renderer.window.ctx.NEAREST
    assert renderer.sprite_list.atlas.texture.filter == (nearest, nearest)

    # 2. Render frame with no hovered cell: the floor gets its plain texture back
    renderer.hovered_cell = None
    renderer._apply_highlight()
    assert renderer._highlighted_cell is None
    assert floor_sprite.texture is renderer._get_texture_data(floor_item, renderer.palette)[0]
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

    # 4. Pan keys are held, not stepped: the camera moves on frame updates until release
    start_y = cam.y
    renderer.window.on_key_press(arcade.key.W, 0)
    assert cam.y == start_y
    renderer.window.on_update(0.1)
    assert cam.y == start_y + InputHandler.PAN_SPEED * 0.1 / cam.zoom
    renderer.window.on_key_release(arcade.key.W, 0)
    renderer.window.on_update(0.1)
    assert cam.y == start_y + InputHandler.PAN_SPEED * 0.1 / cam.zoom

    # 5. The cell grid swaps the floor sprites for variants with a painted border
    plain_keys = set(renderer._texture_cache)
    assert not any("#grid" in key[0] for key in plain_keys)
    sprite_count = len(renderer.sprite_list)
    renderer.window.on_key_press(arcade.key.G, 0)
    assert cam.show_grid is True
    assert any("#grid" in key[0] for key in renderer._texture_cache)
    assert len(renderer.sprite_list) == sprite_count
    renderer.render_frame(cam)
    assert renderer._metadata_texts

    renderer.close()

