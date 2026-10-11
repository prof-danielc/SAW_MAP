"""Arcade 3.3.1 hardware-accelerated rendering engine for Soldiers at War visualizer.

Provides OpenGL batched sprite rendering (arcade.SpriteList), Camera2D transformations,
and 60 FPS viewport navigation.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import arcade
from PIL import Image

from saw_map.assets.loader import IAssetLoader
from saw_map.diagnostics.logger import get_logger
from saw_map.formats.palette_reader import Palette
from saw_map.geometry.transform import IsometricTransform, TopDownTransform
from saw_map.maps.model import ComponentType, MapCell, MapDocument, TilesetDefinition
from saw_map.rendering.backend_base import IRenderer
from saw_map.rendering.draw_order import DrawOrderStrategy, RenderItem
from saw_map.rendering.fallback import create_placeholder_sprite
from saw_map.viewer.camera import Camera, ViewPerspective

logger = get_logger("rendering.arcade")


class ArcadeWindow(arcade.Window):
    """Interactive OpenGL viewport window powered by Arcade 3.3.1."""

    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        renderer: ArcadeRenderer,
    ) -> None:
        super().__init__(width, height, title, resizable=True)
        self.renderer = renderer
        arcade.set_background_color(arcade.color.CHARCOAL)
        self.mouse_screen_x: float = 0.0
        self.mouse_screen_y: float = 0.0

    def on_draw(self) -> None:
        """Renders viewport frame."""
        self.clear()
        self.renderer.draw_viewport(self.width, self.height)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        """Tracks cursor motion for tile coordinate picking."""
        self.mouse_screen_x = float(x)
        self.mouse_screen_y = float(y)
        self.renderer.update_hover(x, y, self.width, self.height)

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int) -> None:
        """Pans camera on mouse drag."""
        self.mouse_screen_x = float(x)
        self.mouse_screen_y = float(y)
        if buttons & arcade.MOUSE_BUTTON_LEFT:
            zoom = self.renderer.camera.zoom
            self.renderer.camera.pan(dx / zoom, dy / zoom)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        """Zooms camera centered on view."""
        if scroll_y > 0:
            self.renderer.camera.zoom_in()
        elif scroll_y < 0:
            self.renderer.camera.zoom_out()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        """Handles keyboard navigation and diagnostic toggles."""
        cam = self.renderer.camera

        # Panning
        step = 40.0 / cam.zoom
        if symbol in (arcade.key.LEFT, arcade.key.A):
            cam.pan(step, 0)
        elif symbol in (arcade.key.RIGHT, arcade.key.D):
            cam.pan(-step, 0)
        elif symbol in (arcade.key.UP, arcade.key.W):
            cam.pan(0, -step)
        elif symbol in (arcade.key.DOWN, arcade.key.S):
            cam.pan(0, step)

        # Zooming
        elif symbol in (arcade.key.EQUAL, arcade.key.PLUS):
            cam.zoom_in()
        elif symbol in (arcade.key.MINUS, arcade.key.UNDERSCORE):
            cam.zoom_out()
        elif symbol in (arcade.key.HOME, arcade.key.R):
            cam.reset()

        # Elevation Filtering (PageUp / PageDown / E / Q)
        elif symbol in (arcade.key.PAGEUP, arcade.key.E):
            cam.active_max_layer = min(6, cam.active_max_layer + 1)
            cam.isolated_layer = None
            self.renderer.rebuild_sprites()
        elif symbol in (arcade.key.PAGEDOWN, arcade.key.Q):
            cam.active_max_layer = max(0, cam.active_max_layer - 1)
            cam.isolated_layer = None
            self.renderer.rebuild_sprites()

        # Single layer isolation mode toggle
        elif symbol == arcade.key.L:
            if cam.isolated_layer is None:
                cam.isolated_layer = cam.active_max_layer
            else:
                cam.isolated_layer = None
            self.renderer.rebuild_sprites()

        # Perspectives (Tab / T)
        elif symbol in (arcade.key.TAB, arcade.key.T):
            if cam.perspective == ViewPerspective.ISOMETRIC:
                cam.perspective = ViewPerspective.TOP_DOWN
            else:
                cam.perspective = ViewPerspective.ISOMETRIC
            self.renderer.rebuild_sprites()

        # Minimap (M)
        elif symbol == arcade.key.M:
            cam.show_minimap = not cam.show_minimap

        # Inspection Sidebar (I)
        elif symbol == arcade.key.I:
            cam.show_sidebar = not cam.show_sidebar

        # Component Toggles (1=Floors, 2=Left walls, 3=Right walls, 4=Clutter)
        elif symbol == arcade.key.KEY_1:
            cam.show_floors = not cam.show_floors
            self.renderer.rebuild_sprites()
        elif symbol == arcade.key.KEY_2:
            cam.show_left_walls = not cam.show_left_walls
            self.renderer.rebuild_sprites()
        elif symbol == arcade.key.KEY_3:
            cam.show_right_walls = not cam.show_right_walls
            self.renderer.rebuild_sprites()
        elif symbol == arcade.key.KEY_4:
            cam.show_clutter = not cam.show_clutter
            self.renderer.rebuild_sprites()

        # Palette Cycle (P)
        elif symbol == arcade.key.P:
            self.renderer.cycle_palette()

        # Exit (Escape)
        elif symbol == arcade.key.ESCAPE:
            self.close()


class ArcadeRenderer(IRenderer):
    """Arcade 3.3.1 hardware accelerated implementation of IRenderer."""

    def __init__(self) -> None:
        self.window: Optional[ArcadeWindow] = None
        self.camera = Camera()
        self.map_doc: Optional[MapDocument] = None
        self.asset_loader: Optional[IAssetLoader] = None
        self.tileset: Optional[TilesetDefinition] = None
        self.palette: Optional[Palette] = None
        self.available_palettes: List[str] = ["Win.pal", "Darkpal.col"]
        self.current_pal_idx: int = 0

        self.iso_transform = IsometricTransform()
        self.top_transform = TopDownTransform()

        self.sprite_list = arcade.SpriteList()
        self._texture_cache: Dict[Tuple[str, int, str], arcade.Texture] = {}
        self.hovered_cell: Optional[Tuple[int, int, int]] = None

    def initialize(self, width: int = 1280, height: int = 720, title: str = "SAW Map Visualizer") -> None:
        """Initializes Arcade window."""
        self.window = ArcadeWindow(width, height, title, self)

    def set_map(
        self,
        map_doc: MapDocument,
        asset_loader: IAssetLoader,
        tileset: Optional[TilesetDefinition] = None,
        palette: Optional[Palette] = None,
    ) -> None:
        """Binds map document and asset manager, and generates initial sprite lists."""
        self.map_doc = map_doc
        self.asset_loader = asset_loader
        self.tileset = tileset
        self.palette = palette
        self.rebuild_sprites()

    def rebuild_sprites(self) -> None:
        """Reconstructs batched sprite lists based on active filters and camera perspective."""
        if not self.map_doc or not self.asset_loader:
            return

        self.sprite_list.clear()

        # Select palette
        active_pal = self.palette
        if not active_pal:
            active_pal = self.asset_loader.load_palette("Win.pal")
            self.palette = active_pal

        # Depth-sort render items
        items = DrawOrderStrategy.generate_render_list(
            map_doc=self.map_doc,
            tileset=self.tileset,
            max_layer=self.camera.active_max_layer,
            isolated_layer=self.camera.isolated_layer,
            show_floors=self.camera.show_floors,
            show_left_walls=self.camera.show_left_walls,
            show_right_walls=self.camera.show_right_walls,
            show_clutter=self.camera.show_clutter,
        )

        is_iso = self.camera.perspective == ViewPerspective.ISOMETRIC

        for item in items:
            # Resolve texture
            tex = self._get_texture(item, active_pal)
            if not tex:
                continue

            # Calculate screen coordinates
            if is_iso:
                sx, sy = self.iso_transform.world_to_screen(item.grid_x, item.grid_y, item.grid_z)
            else:
                sx, sy = self.top_transform.world_to_screen(item.grid_x, item.grid_y, item.grid_z)

            # Invert sy for Arcade (bottom-left origin)
            arcade_x = sx
            arcade_y = -sy

            sprite = arcade.Sprite(tex)
            sprite.center_x = arcade_x
            sprite.center_y = arcade_y
            self.sprite_list.append(sprite)

    def _get_texture(self, item: RenderItem, palette: Palette) -> Optional[arcade.Texture]:
        """Loads and caches arcade.Texture from Pillow image."""
        if not self.asset_loader:
            return None

        asset_name = item.asset_name or "placeholder"
        key = (asset_name.lower(), item.sprite_frame_index, palette.name)

        if key in self._texture_cache:
            return self._texture_cache[key]

        if item.asset_name:
            pil_img = self.asset_loader.get_sprite_image(
                item.asset_name, item.sprite_frame_index, palette
            )
        else:
            pil_img = create_placeholder_sprite(item.component_type, 64, 32)

        try:
            tex = arcade.Texture(image=pil_img)
            self._texture_cache[key] = tex
            return tex
        except Exception as exc:
            logger.warning(f"Error creating texture for {key}: {exc}")
            return None

    def cycle_palette(self) -> None:
        """Cycles between daylight and ambient palettes."""
        if not self.asset_loader:
            return
        self.current_pal_idx = (self.current_pal_idx + 1) % len(self.available_palettes)
        pal_name = self.available_palettes[self.current_pal_idx]
        self.palette = self.asset_loader.load_palette(pal_name)
        self._texture_cache.clear()
        self.rebuild_sprites()

    def update_hover(self, mx: float, my: float, win_w: int, win_h: int) -> None:
        """Determines logical cell coordinates under cursor."""
        if not self.map_doc:
            return

        center_x = win_w / 2.0 + (self.camera.x * self.camera.zoom)
        center_y = win_h / 2.0 + (self.camera.y * self.camera.zoom)

        world_sx = (mx - center_x) / self.camera.zoom
        world_sy = -(my - center_y) / self.camera.zoom

        z_plane = float(
            self.camera.isolated_layer
            if self.camera.isolated_layer is not None
            else self.camera.active_max_layer
        )

        if self.camera.perspective == ViewPerspective.ISOMETRIC:
            gx, gy = self.iso_transform.screen_to_world(world_sx, world_sy, z_plane)
        else:
            gx, gy = self.top_transform.screen_to_world(world_sx, world_sy, z_plane)

        if 0 <= gx < self.map_doc.width and 0 <= gy < self.map_doc.height:
            self.hovered_cell = (gx, gy, int(z_plane))
        else:
            self.hovered_cell = None

    def draw_viewport(self, win_w: int, win_h: int) -> None:
        """Draws world sprites and diagnostic HUD overlays."""
        center_x = win_w / 2.0 + (self.camera.x * self.camera.zoom)
        center_y = win_h / 2.0 + (self.camera.y * self.camera.zoom)

        # Draw world sprites using view transform
        for sprite in self.sprite_list:
            sprite.scale = self.camera.zoom
            sprite.left = center_x + (sprite.center_x - sprite.width / 2.0) * self.camera.zoom
            # arcade sprites use center coordinates
        self.sprite_list.draw()

        # Draw overlays
        self._draw_status_bar(win_w, win_h)
        if self.camera.show_minimap:
            self._draw_minimap(win_w, win_h)
        if self.camera.show_sidebar:
            self._draw_sidebar(win_w, win_h)

    def _draw_status_bar(self, win_w: int, win_h: int) -> None:
        """Renders bottom HUD status bar with cell coordinates and metadata."""
        bar_h = 28
        arcade.draw_lrbt_rectangle_filled(0, win_w, 0, bar_h, (15, 18, 22, 230))
        arcade.draw_line(0, bar_h, win_w, bar_h, arcade.color.DARK_GRAY, 1)

        info_parts: List[str] = []
        if self.map_doc:
            info_parts.append(f"Map: {self.map_doc.title} ({self.map_doc.width}x{self.map_doc.height})")
            info_parts.append(f"View: {self.camera.perspective.value.upper()}")
            info_parts.append(f"Layer: Z={self.camera.active_max_layer}/6")
            info_parts.append(f"Zoom: {self.camera.zoom:.2f}x")

            if self.hovered_cell:
                hx, hy, hz = self.hovered_cell
                cell = self.map_doc.get_cell(hx, hy, hz)
                comp_info = "empty"
                if cell and not cell.is_empty():
                    parts = []
                    if cell.floor.is_present: parts.append(f"Flr:{cell.floor.tileset_group_index}:{cell.floor.sprite_frame_index}")
                    if cell.left_wall.is_present: parts.append(f"LWall:{cell.left_wall.tileset_group_index}:{cell.left_wall.sprite_frame_index}")
                    if cell.right_wall.is_present: parts.append(f"RWall:{cell.right_wall.tileset_group_index}:{cell.right_wall.sprite_frame_index}")
                    if cell.clutter.is_present: parts.append(f"Clut:{cell.clutter.tileset_group_index}:{cell.clutter.sprite_frame_index}")
                    comp_info = " ".join(parts)
                info_parts.append(f"Hover: ({hx}, {hy}, {hz}) [{comp_info}]")

        status_text = " | ".join(info_parts)
        arcade.draw_text(status_text, 12, 7, arcade.color.WHITE, 12)

    def _draw_minimap(self, win_w: int, win_h: int) -> None:
        """Renders 2D top-down minimap overview in top-right corner."""
        if not self.map_doc:
            return
        mw, mh = 140, 110
        margin = 12
        left = win_w - mw - margin
        bottom = win_h - mh - margin

        # Background box
        arcade.draw_lrbt_rectangle_filled(left, left + mw, bottom, bottom + mh, (10, 12, 16, 220))
        arcade.draw_lrbt_rectangle_outline(left, left + mw, bottom, bottom + mh, arcade.color.GOLD, 1)
        arcade.draw_text("MINIMAP (M)", left + 6, bottom + mh - 16, arcade.color.GOLD, 9)

        # Plot map boundary
        map_w = float(self.map_doc.width)
        map_h = float(self.map_doc.height)
        scale_x = (mw - 16) / max(1.0, map_w)
        scale_y = (mh - 26) / max(1.0, map_h)

        # Draw grid frame
        gx0 = left + 8
        gy0 = bottom + 6
        arcade.draw_lrbt_rectangle_outline(gx0, gx0 + map_w * scale_x, gy0, gy0 + map_h * scale_y, (80, 90, 100), 1)

    def _draw_sidebar(self, win_w: int, win_h: int) -> None:
        """Renders detailed cell inspection sidebar on right."""
        side_w = 260
        left = win_w - side_w
        arcade.draw_lrbt_rectangle_filled(left, win_w, 28, win_h, (20, 24, 30, 245))
        arcade.draw_line(left, 28, left, win_h, arcade.color.GOLD, 1)

        y = win_h - 24
        arcade.draw_text("CELL INSPECTION (I)", left + 14, y, arcade.color.GOLD, 13, bold=True)
        y -= 28

        if self.hovered_cell and self.map_doc:
            hx, hy, hz = self.hovered_cell
            cell = self.map_doc.get_cell(hx, hy, hz)
            arcade.draw_text(f"Coordinate: ({hx}, {hy}, {hz})", left + 14, y, arcade.color.WHITE, 11)
            y -= 22
            if cell:
                arcade.draw_text(f"Elevation Byte: {cell.elevation_attr}", left + 14, y, arcade.color.LIGHT_GRAY, 11)
                y -= 20
                arcade.draw_text(f"Cell Flags: 0x{cell.flags:08X}", left + 14, y, arcade.color.LIGHT_GRAY, 11)
                y -= 28

                for label, comp in (
                    ("Floor", cell.floor),
                    ("Left Wall", cell.left_wall),
                    ("Right Wall", cell.right_wall),
                    ("Clutter", cell.clutter),
                ):
                    status = "PRESENT" if comp.is_present else "EMPTY"
                    color = arcade.color.GREEN if comp.is_present else arcade.color.GRAY
                    arcade.draw_text(f"• {label}: {status}", left + 14, y, color, 11, bold=True)
                    y -= 18
                    if comp.is_present:
                        asset = self.tileset.resolve_asset(comp.component_type, comp.tileset_group_index) if self.tileset else None
                        arcade.draw_text(f"   Asset: {asset or 'Unresolved'}", left + 14, y, arcade.color.WHITE, 10)
                        y -= 16
                        arcade.draw_text(f"   Group: {comp.tileset_group_index} | Frame: {comp.sprite_frame_index}", left + 14, y, arcade.color.LIGHT_GRAY, 10)
                        y -= 20
        else:
            arcade.draw_text("Hover over a cell to inspect", left + 14, y, arcade.color.GRAY, 11)

    def render_frame(self, camera: Camera) -> None:
        """Forces single frame update (used in headless testing)."""
        self.camera = camera
        self.rebuild_sprites()

    def run_loop(self) -> None:
        """Starts Arcade event loop."""
        if self.window:
            arcade.run()

    def close(self) -> None:
        """Closes Arcade window cleanly."""
        if self.window:
            self.window.close()
