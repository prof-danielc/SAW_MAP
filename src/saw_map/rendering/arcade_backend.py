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
from saw_map.viewer.inspector import CellInspector
from saw_map.viewer.minimap import MinimapCalculator, generate_minimap_image

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
        arcade.set_background_color((20, 24, 30))
        self.mouse_screen_x: float = 0.0
        self.mouse_screen_y: float = 0.0

    def on_resize(self, width: int, height: int) -> None:
        """Updates camera viewport when window is resized."""
        super().on_resize(width, height)
        if self.renderer.world_camera:
            self.renderer.world_camera.match_window()
        if self.renderer.gui_camera:
            self.renderer.gui_camera.match_window()
            self.renderer.gui_camera.position = (width / 2.0, height / 2.0)

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
            self.renderer.camera.pan(dx / zoom, -dy / zoom)

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
            cam.pan(0, step)
        elif symbol in (arcade.key.DOWN, arcade.key.S):
            cam.pan(0, -step)

        # Zooming
        elif symbol in (arcade.key.EQUAL, arcade.key.PLUS):
            cam.zoom_in()
        elif symbol in (arcade.key.MINUS, arcade.key.UNDERSCORE):
            cam.zoom_out()
        elif symbol in (arcade.key.HOME, arcade.key.R):
            self.renderer._update_map_center()
            cam.zoom = 1.0
            self.renderer.update_hover(int(self.mouse_screen_x), int(self.mouse_screen_y), self.width, self.height)

        # Elevation Filtering (PageUp / PageDown / E / Q)
        elif symbol in (arcade.key.PAGEUP, arcade.key.E):
            cam.active_max_layer = min(6, cam.active_max_layer + 1)
            cam.isolated_layer = None
            self.renderer.rebuild_sprites()
            self.renderer.update_hover(int(self.mouse_screen_x), int(self.mouse_screen_y), self.width, self.height)
        elif symbol in (arcade.key.PAGEDOWN, arcade.key.Q):
            cam.active_max_layer = max(0, cam.active_max_layer - 1)
            cam.isolated_layer = None
            self.renderer.rebuild_sprites()
            self.renderer.update_hover(int(self.mouse_screen_x), int(self.mouse_screen_y), self.width, self.height)

        # Single layer isolation mode toggle
        elif symbol == arcade.key.L:
            if cam.isolated_layer is None:
                cam.isolated_layer = cam.active_max_layer
            else:
                cam.isolated_layer = None
            self.renderer.rebuild_sprites()
            self.renderer.update_hover(int(self.mouse_screen_x), int(self.mouse_screen_y), self.width, self.height)

        # Perspectives (Tab / T)
        elif symbol in (arcade.key.TAB, arcade.key.T):
            if cam.perspective == ViewPerspective.ISOMETRIC:
                cam.perspective = ViewPerspective.TOP_DOWN
            else:
                cam.perspective = ViewPerspective.ISOMETRIC
            self.renderer._update_map_center()
            self.renderer.rebuild_sprites()
            self.renderer.update_hover(int(self.mouse_screen_x), int(self.mouse_screen_y), self.width, self.height)

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

        # Fullscreen / Maximize toggle (F11 / F)
        elif symbol in (arcade.key.F11, arcade.key.F):
            self.set_fullscreen(not self.fullscreen)

        # Exit (Escape)
        elif symbol == arcade.key.ESCAPE:
            self.close()


class ArcadeRenderer(IRenderer):
    """Arcade 3.3.1 hardware accelerated implementation of IRenderer."""

    def __init__(self) -> None:
        self.window: Optional[ArcadeWindow] = None
        self.world_camera: Optional[arcade.camera.Camera2D] = None
        self.gui_camera: Optional[arcade.camera.Camera2D] = None
        self.camera = Camera()
        self.map_doc: Optional[MapDocument] = None
        self.asset_loader: Optional[IAssetLoader] = None
        self.tileset: Optional[TilesetDefinition] = None
        self.palette: Optional[Palette] = None
        self.available_palettes: List[str] = ["Win.pal", "Darkpal.col"]
        self.current_pal_idx: int = 0

        self.iso_transform = IsometricTransform()
        self.top_transform = TopDownTransform()
        self._inspector = CellInspector(self.iso_transform, self.top_transform)

        self.sprite_list = arcade.SpriteList()
        self._texture_cache: Dict[Tuple[str, int, str], Tuple[arcade.Texture, int, int]] = {}
        self.hovered_cell: Optional[Tuple[int, int, int]] = None
        self.map_center_x: float = 0.0
        self.map_center_y: float = 0.0

        # Cached Text object for status bar
        self._status_text_obj: Optional[arcade.Text] = None
        self._last_status_text: str = ""

        # Minimap calculations and cached texture
        self._minimap_calc = MinimapCalculator(box_width=160.0, box_height=120.0, margin=12.0)
        self._minimap_texture: Optional[arcade.Texture] = None
        self._minimap_cache_layer: Optional[int] = None
        self._minimap_title_obj: Optional[arcade.Text] = None
        self._minimap_title_pos: Optional[Tuple[float, float]] = None

        # Sidebar cached Text objects
        self._sidebar_texts: List[arcade.Text] = []
        self._last_sidebar_key: Optional[Tuple] = None
        self._sidebar_title_obj: Optional[arcade.Text] = None
        self._sidebar_title_pos: Optional[Tuple[float, float]] = None

    def initialize(
        self,
        width: int = 1280,
        height: int = 720,
        title: str = "SAW Map Visualizer",
        maximized: bool = False,
    ) -> None:
        """Initializes Arcade window and Camera2D viewports."""
        self.window = ArcadeWindow(width, height, title, self)
        self.world_camera = arcade.camera.Camera2D(window=self.window)
        self.gui_camera = arcade.camera.Camera2D(window=self.window)
        if maximized:
            try:
                self.window.maximize()
            except Exception:
                pass

    def _update_map_center(self) -> None:
        """Computes center of the active map in world coordinates and centers camera."""
        if not self.map_doc:
            self.map_center_x = 0.0
            self.map_center_y = 0.0
            return
        mid_x = self.map_doc.width / 2.0
        mid_y = self.map_doc.height / 2.0
        if self.camera.perspective == ViewPerspective.ISOMETRIC:
            sx, sy = self.iso_transform.world_to_screen(mid_x, mid_y, 0)
        else:
            sx, sy = self.top_transform.world_to_screen(mid_x, mid_y, 0)
        self.map_center_x = sx
        self.map_center_y = -sy
        self.camera.x = -sx
        self.camera.y = -sy

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
        self._update_map_center()
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
            tex_data = self._get_texture_data(item, active_pal)
            if not tex_data:
                continue

            tex, ox, oy = tex_data

            # Calculate screen coordinates
            if is_iso:
                sx, sy = self.iso_transform.world_to_screen(item.grid_x, item.grid_y, item.grid_z)
                # Apply Soldiers at War frame anchor offset relative to reference floor tile (209, 322)
                rel_ox = ox - 209
                rel_oy = oy - 322
                arcade_center_x = sx - 64.0 + rel_ox + (tex.width / 2.0)
                arcade_center_y = -(sy + rel_oy + (tex.height / 2.0))
            else:
                sx, sy = self.top_transform.world_to_screen(item.grid_x, item.grid_y, item.grid_z)
                arcade_center_x = sx + (tex.width / 2.0)
                arcade_center_y = -(sy + (tex.height / 2.0))

            sprite = arcade.Sprite(tex)
            sprite.center_x = arcade_center_x
            sprite.center_y = arcade_center_y
            self.sprite_list.append(sprite)

    def _get_texture_data(self, item: RenderItem, palette: Palette) -> Optional[Tuple[arcade.Texture, int, int]]:
        """Loads and caches (arcade.Texture, offset_x, offset_y) from Pillow image."""
        if not self.asset_loader:
            return None

        asset_name = item.asset_name or "placeholder"
        key = (asset_name.lower(), item.sprite_frame_index, palette.name)

        if key in self._texture_cache:
            return self._texture_cache[key]

        if item.asset_name:
            pil_img, ox, oy = self.asset_loader.get_sprite_image_and_offset(
                item.asset_name, item.sprite_frame_index, palette
            )
        else:
            pil_img = create_placeholder_sprite(item.component_type, 128, 64)
            ox, oy = 209, 322

        try:
            tex = arcade.Texture(image=pil_img)
            val = (tex, ox, oy)
            self._texture_cache[key] = val
            return val
        except Exception as exc:
            logger.warning(f"Error creating texture for {key}: {exc}")
            return None

    def _get_texture(self, item: RenderItem, palette: Palette) -> Optional[arcade.Texture]:
        """Loads and caches arcade.Texture from Pillow image."""
        val = self._get_texture_data(item, palette)
        return val[0] if val else None

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
        """Determines logical cell coordinates under cursor using top-down raycast picking."""
        if not self.map_doc or not self.world_camera:
            return

        world_pt = self.world_camera.unproject((mx, my))
        world_sx = world_pt.x
        world_sy = -world_pt.y

        self.hovered_cell = self._inspector.pick_cell_from_world_coords(
            world_sx, world_sy, self.camera, self.map_doc
        )

    def draw_viewport(self, win_w: int, win_h: int) -> None:
        """Draws world sprites, selection box, and diagnostic HUD overlays."""
        if not self.world_camera:
            return

        # 1. Activate world camera (GPU matrix transform)
        self.world_camera.position = (-self.camera.x, self.camera.y)
        self.world_camera.zoom = self.camera.zoom
        self.world_camera.use()

        # 2. Draw world sprites hardware accelerated
        self.sprite_list.draw()

        # 2b. Draw selection box for currently inspected cell
        self._draw_selection_box()

        # 3. Activate GUI camera for HUD & overlays (1:1 pixel coords)
        if self.gui_camera:
            self.gui_camera.position = (win_w / 2.0, win_h / 2.0)
            self.gui_camera.use()
        elif self.window:
            self.window.default_camera.use()

        self._draw_status_bar(win_w, win_h)
        if self.camera.show_minimap:
            self._draw_minimap(win_w, win_h)
        if self.camera.show_sidebar:
            self._draw_sidebar(win_w, win_h)

    def _draw_selection_box(self) -> None:
        """Renders highlighted selection diamond/square over the currently inspected cell."""
        if not self.hovered_cell or not self.map_doc:
            return

        hx, hy, hz = self.hovered_cell
        is_iso = self.camera.perspective == ViewPerspective.ISOMETRIC

        if is_iso:
            sx, sy = self.iso_transform.world_to_screen(hx, hy, hz)
            # In Arcade world coordinates, Y is inverted: arcade_y = -sy
            p_top = (sx, -sy)
            p_right = (sx + 64.0, -(sy + 32.0))
            p_bottom = (sx, -(sy + 64.0))
            p_left = (sx - 64.0, -(sy + 32.0))
            points = [p_top, p_right, p_bottom, p_left]
        else:
            sx, sy = self.top_transform.world_to_screen(hx, hy, hz)
            cw = self.top_transform.cell_size
            points = [(sx, -sy), (sx + cw, -sy), (sx + cw, -(sy + cw)), (sx, -(sy + cw))]

        arcade.draw_polygon_filled(points, (0, 230, 255, 45))
        arcade.draw_polygon_outline(points, (0, 230, 255, 240), line_width=2.0)

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
                tile_info = ""
                if cell:
                    c_info = CellInspector.inspect_cell(cell, self.tileset)
                    if c_info.primary_tile_name:
                        tile_info = f" [{c_info.primary_tile_name}:{c_info.primary_tile_frame}]"
                info_parts.append(f"Hover: ({hx}, {hy}, {hz}){tile_info}")

        status_text = " | ".join(info_parts)
        if self._status_text_obj is None:
            self._status_text_obj = arcade.Text(status_text, 12, 7, arcade.color.WHITE, 12)
            self._last_status_text = status_text
        elif self._last_status_text != status_text:
            self._status_text_obj.text = status_text
            self._last_status_text = status_text

        # Ensure text does not overflow screen width in compact or resized windows
        available_w = max(50.0, float(win_w - (280 if self.camera.show_sidebar else 24)))
        if self._status_text_obj.content_width > available_w and len(status_text) > 20:
            shortened = status_text
            while len(shortened) > 10 and self._status_text_obj.content_width > available_w:
                shortened = shortened[:-5]
                self._status_text_obj.text = shortened + "..."
            self._last_status_text = ""

        self._status_text_obj.draw()

    def _update_minimap_cache(self) -> None:
        """Generates and caches 2D top-down terrain texture from map cell data."""
        if not self.map_doc:
            self._minimap_texture = None
            return

        active_z = (
            self.camera.isolated_layer
            if self.camera.isolated_layer is not None
            else self.camera.active_max_layer
        )
        if self._minimap_texture is not None and self._minimap_cache_layer == active_z:
            return

        pil_img = generate_minimap_image(self.map_doc, self.tileset, active_z)
        try:
            self._minimap_texture = arcade.Texture(image=pil_img)
            self._minimap_cache_layer = active_z
        except Exception as exc:
            logger.warning(f"Error creating minimap texture: {exc}")
            self._minimap_texture = None

    def _draw_minimap(self, win_w: int, win_h: int) -> None:
        """Renders 2D top-down minimap with terrain visualization and camera frustum."""
        if not self.map_doc:
            return

        self._update_minimap_cache()
        if not self._minimap_texture:
            return

        offset_r = 260.0 if self.camera.show_sidebar else 0.0
        bounds = self._minimap_calc.get_minimap_bounds(win_w, win_h, offset_right=offset_r)

        mw = bounds.width
        mh = bounds.height
        left = bounds.left
        top = float(win_h) - bounds.top
        bottom = top - mh

        # Background box and gold border
        arcade.draw_lrbt_rectangle_filled(left, left + mw, bottom, top, (10, 12, 16, 230))
        arcade.draw_lrbt_rectangle_outline(left, left + mw, bottom, top, arcade.color.GOLD, 1)

        # Title text
        if self._minimap_title_obj is None or self._minimap_title_pos != (left + 8, top - 18):
            self._minimap_title_obj = arcade.Text("MINIMAP (M)", left + 8, top - 18, arcade.color.GOLD, 10, bold=True)
            self._minimap_title_pos = (left + 8, top - 18)
        self._minimap_title_obj.draw()

        # Inner terrain display area
        inner_w = mw - 16.0
        inner_h = mh - 26.0
        scale = min(
            inner_w / max(1.0, float(self.map_doc.width)),
            inner_h / max(1.0, float(self.map_doc.height)),
        )
        disp_w = max(1.0, float(self.map_doc.width) * scale)
        disp_h = max(1.0, float(self.map_doc.height) * scale)

        gx0 = left + 8.0 + (inner_w - disp_w) / 2.0
        gy0 = bottom + 6.0 + (inner_h - disp_h) / 2.0

        # Draw terrain texture
        rect = arcade.LRBT(gx0, gx0 + disp_w, gy0, gy0 + disp_h)
        arcade.draw_texture_rect(self._minimap_texture, rect)
        arcade.draw_lrbt_rectangle_outline(gx0, gx0 + disp_w, gy0, gy0 + disp_h, (80, 90, 100), 1)

        # Viewport polygon (diamond frustum in isometric)
        poly = self._minimap_calc.calculate_viewport_polygon(
            self.map_doc, self.camera, win_w, win_h, gx0, gy0, disp_w, disp_h, invert_y=True
        )
        if len(poly) >= 3:
            clamped = [
                (max(gx0, min(gx0 + disp_w, px)), max(gy0, min(gy0 + disp_h, py)))
                for px, py in poly
            ]
            arcade.draw_polygon_outline(clamped, arcade.color.WHITE, 1)

    def _draw_sidebar(self, win_w: int, win_h: int) -> None:
        """Renders detailed cell inspection sidebar on right."""
        side_w = 260.0
        left = float(win_w) - side_w
        arcade.draw_lrbt_rectangle_filled(left, float(win_w), 28.0, float(win_h), (20, 24, 30, 245))
        arcade.draw_line(left, 28.0, left, float(win_h), arcade.color.GOLD, 1)

        # Title
        if self._sidebar_title_obj is None or self._sidebar_title_pos != (left + 14, float(win_h) - 22):
            self._sidebar_title_obj = arcade.Text(
                "CELL INSPECTION (I)", left + 14, float(win_h) - 22, arcade.color.GOLD, 11, bold=True
            )
            self._sidebar_title_pos = (left + 14, float(win_h) - 22)
        self._sidebar_title_obj.draw()

        # Cache check
        active_z = (
            self.camera.isolated_layer
            if self.camera.isolated_layer is not None
            else self.camera.active_max_layer
        )
        key = (self.hovered_cell, win_w, win_h, active_z)

        if key != self._last_sidebar_key:
            self._sidebar_texts = []
            if self.hovered_cell and self.map_doc:
                hx, hy, hz = self.hovered_cell
                cell = self.map_doc.get_cell(hx, hy, hz)
                y = float(win_h) - 44
                self._sidebar_texts.append(
                    arcade.Text(f"Coordinate: ({hx}, {hy}, {hz})", left + 14, y, arcade.color.WHITE, 10, bold=True)
                )
                y -= 20
                if cell:
                    info = CellInspector.inspect_cell(cell, self.tileset)
                    self._sidebar_texts.append(
                        arcade.Text(f"Tile Name: {info.primary_tile_label}", left + 14, y, arcade.color.CYAN, 9, bold=True)
                    )
                    y -= 18
                    self._sidebar_texts.append(
                        arcade.Text(f"Elevation: 0x{cell.elevation_attr:02X} ({cell.elevation_attr})", left + 14, y, (180, 185, 190), 9)
                    )
                    y -= 16
                    self._sidebar_texts.append(
                        arcade.Text(f"Flags: 0x{cell.flags:08X}", left + 14, y, (180, 185, 190), 9)
                    )
                    y -= 19

                    for comp in info.components:
                        col = (50, 205, 50) if comp.is_present else (120, 120, 120)
                        self._sidebar_texts.append(
                            arcade.Text(f"• {comp.slot_name}: {comp.status_label}", left + 14, y, col, 9, bold=True)
                        )
                        y -= 14
                        if comp.is_present:
                            self._sidebar_texts.append(
                                arcade.Text(
                                    f"   Raw: 0x{comp.raw_word:04X} (G:{comp.tileset_group_index} F:{comp.sprite_frame_index})",
                                    left + 14,
                                    y,
                                    (170, 175, 185),
                                    8,
                                )
                            )
                            y -= 13
                            self._sidebar_texts.append(
                                arcade.Text(f"   {comp.details_line}", left + 14, y, (220, 225, 230), 8)
                            )
                            y -= 16
                        else:
                            self._sidebar_texts.append(
                                arcade.Text(f"   Raw: 0x{comp.raw_word:04X}", left + 14, y, (110, 115, 120), 8)
                            )
                            y -= 14

            else:
                y = float(win_h) - 46
                self._sidebar_texts.append(
                    arcade.Text("No cell hovered", left + 14, y, (180, 185, 190), 10, bold=True)
                )
                y -= 22
                tips = [
                    ("Move mouse over map", (150, 155, 165), False),
                    ("to inspect components,", (150, 155, 165), False),
                    ("attributes, and flags.", (150, 155, 165), False),
                    ("", (150, 155, 165), False),
                    ("Shortcuts:", arcade.color.GOLD, True),
                    ("  [I] Toggle Sidebar", (150, 155, 165), False),
                    ("  [M] Toggle Minimap", (150, 155, 165), False),
                    ("  [PgUp/PgDn] Change Layer", (150, 155, 165), False),
                    ("  [Tab] Toggle Iso/TopDown", (150, 155, 165), False),
                    ("  [1-4] Toggle Layers", (150, 155, 165), False),
                    ("  [P] Cycle Palette", (150, 155, 165), False),
                ]
                for text_val, col_val, is_b in tips:
                    if text_val:
                        self._sidebar_texts.append(
                            arcade.Text(text_val, left + 14, y, col_val, 9, bold=is_b)
                        )
                    y -= 16

            self._last_sidebar_key = key

        # Draw divider line when hovering a cell
        if self.hovered_cell and self.map_doc:
            arcade.draw_line(left + 14, float(win_h) - 96, float(win_w) - 14, float(win_h) - 96, (60, 65, 75), 1)

        for text_item in self._sidebar_texts:
            text_item.draw()


    def render_frame(self, camera: Camera) -> None:
        """Forces single frame update (used in headless testing)."""
        self.camera = camera
        self.rebuild_sprites()
        if self.window:
            self.draw_viewport(self.window.width, self.window.height)

    def run_loop(self) -> None:
        """Starts Arcade event loop."""
        if self.window:
            arcade.run()

    def close(self) -> None:
        """Closes Arcade window cleanly."""
        if self.window:
            self.window.close()
