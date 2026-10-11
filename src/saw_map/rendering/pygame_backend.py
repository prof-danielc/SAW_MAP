"""Fallback Pygame 2.6.1 software surface rendering engine for Soldiers at War visualizer.

Provides CPU-based surface blitting, camera navigation, and diagnostic overlays
as an immediate drop-in replacement if OpenGL hardware initialization fails.
"""

from __future__ import annotations

import sys
from typing import Dict, List, Optional, Tuple

import pygame
from PIL import Image

from saw_map.assets.loader import IAssetLoader
from saw_map.diagnostics.logger import get_logger
from saw_map.formats.palette_reader import Palette
from saw_map.geometry.transform import IsometricTransform, TopDownTransform
from saw_map.maps.model import ComponentType, MapDocument, TilesetDefinition
from saw_map.rendering.backend_base import IRenderer
from saw_map.rendering.draw_order import DrawOrderStrategy, RenderItem
from saw_map.rendering.fallback import create_placeholder_sprite
from saw_map.viewer.camera import Camera, ViewPerspective
from saw_map.viewer.inspector import CellInspector
from saw_map.viewer.minimap import MinimapCalculator, generate_minimap_image

logger = get_logger("rendering.pygame")


class PygameRenderer(IRenderer):
    """Fallback Pygame software surface renderer implementing IRenderer."""

    def __init__(self) -> None:
        self.screen: Optional[pygame.Surface] = None
        self.clock = pygame.time.Clock()
        self.running: bool = False
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

        self._surface_cache: Dict[Tuple[str, int, str], Tuple[pygame.Surface, int, int]] = {}
        self._minimap_calc = MinimapCalculator(box_width=160.0, box_height=120.0, margin=12.0)
        self._minimap_surface: Optional[pygame.Surface] = None
        self._minimap_cache_layer: Optional[int] = None
        self.hovered_cell: Optional[Tuple[int, int, int]] = None
        self.width: int = 1280
        self.height: int = 720
        self.dragging: bool = False
        self.drag_start_mouse: Tuple[int, int] = (0, 0)
        self.drag_start_cam: Tuple[float, float] = (0.0, 0.0)

    def initialize(
        self,
        width: int = 1280,
        height: int = 720,
        title: str = "SAW Map Visualizer (Pygame)",
        maximized: bool = False,
    ) -> None:
        """Initializes Pygame display and window context."""
        pygame.init()
        pygame.font.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        pygame.display.set_caption(title)
        self.font = pygame.font.SysFont("Consolas", 14)
        self.font_bold = pygame.font.SysFont("Consolas", 14, bold=True)
        self.font_title = pygame.font.SysFont("Consolas", 16, bold=True)

    def set_map(
        self,
        map_doc: MapDocument,
        asset_loader: IAssetLoader,
        tileset: Optional[TilesetDefinition] = None,
        palette: Optional[Palette] = None,
    ) -> None:
        """Binds map document and asset dependencies."""
        self.map_doc = map_doc
        self.asset_loader = asset_loader
        self.tileset = tileset
        self.palette = palette or asset_loader.load_palette("Win.pal")
        # Center camera on map mid-point
        mid_x = map_doc.width / 2.0
        mid_y = map_doc.height / 2.0
        if self.camera.perspective == ViewPerspective.ISOMETRIC:
            sx, sy = self.iso_transform.world_to_screen(mid_x, mid_y, 0)
        else:
            sx, sy = self.top_transform.world_to_screen(mid_x, mid_y, 0)
        self.camera.x = -sx
        self.camera.y = -sy

    def _get_surface_data(self, item: RenderItem, palette: Palette) -> Optional[Tuple[pygame.Surface, int, int]]:
        """Loads and caches (pygame.Surface, offset_x, offset_y) from PIL Image."""
        if not self.asset_loader:
            return None

        asset_name = item.asset_name or "placeholder"
        key = (asset_name.lower(), item.sprite_frame_index, palette.name)

        if key in self._surface_cache:
            return self._surface_cache[key]

        if item.asset_name:
            pil_img, ox, oy = self.asset_loader.get_sprite_image_and_offset(
                item.asset_name, item.sprite_frame_index, palette
            )
        else:
            pil_img = create_placeholder_sprite(item.component_type, 128, 64)
            ox, oy = 209, 322

        raw_bytes = pil_img.tobytes()
        surf = pygame.image.fromstring(raw_bytes, pil_img.size, "RGBA")
        if pygame.display.get_init():
            try:
                surf = surf.convert_alpha()
            except pygame.error:
                pass
        res = (surf, ox, oy)
        self._surface_cache[key] = res
        return res

    def _get_surface(self, item: RenderItem, palette: Palette) -> Optional[pygame.Surface]:
        """Loads and caches Pygame Surface from PIL Image."""
        val = self._get_surface_data(item, palette)
        return val[0] if val else None

    def cycle_palette(self) -> None:
        """Cycles between daylight and ambient palettes."""
        if not self.asset_loader:
            return
        self.current_pal_idx = (self.current_pal_idx + 1) % len(self.available_palettes)
        pal_name = self.available_palettes[self.current_pal_idx]
        self.palette = self.asset_loader.load_palette(pal_name)
        self._surface_cache.clear()

    def update_hover(self, mx: int, my: int) -> None:
        """Calculates grid cell under cursor using top-down raycast picking."""
        if not self.map_doc:
            return

        center_x = self.width / 2.0 + (self.camera.x * self.camera.zoom)
        center_y = self.height / 2.0 + (self.camera.y * self.camera.zoom)

        world_sx = (mx - center_x) / self.camera.zoom
        world_sy = (my - center_y) / self.camera.zoom

        self.hovered_cell = self._inspector.pick_cell_from_world_coords(
            world_sx, world_sy, self.camera, self.map_doc
        )

    def render_frame(self, camera: Camera) -> None:
        """Renders complete frame to display surface."""
        if not self.screen or not self.map_doc or not self.asset_loader or not self.palette:
            return

        self.camera = camera
        self.screen.fill((20, 24, 30))

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

        center_x = self.width / 2.0 + (self.camera.x * self.camera.zoom)
        center_y = self.height / 2.0 + (self.camera.y * self.camera.zoom)
        is_iso = self.camera.perspective == ViewPerspective.ISOMETRIC
        zoom = self.camera.zoom

        for item in items:
            surf_data = self._get_surface_data(item, self.palette)
            if not surf_data:
                continue

            surf, ox, oy = surf_data

            if is_iso:
                sx, sy = self.iso_transform.world_to_screen(item.grid_x, item.grid_y, item.grid_z)
                # Apply Soldiers at War frame anchor offset relative to reference floor tile (209, 322)
                rel_ox = ox - 209
                rel_oy = oy - 322
                unscaled_x = sx - 64.0 + rel_ox
                unscaled_y = sy + rel_oy
            else:
                sx, sy = self.top_transform.world_to_screen(item.grid_x, item.grid_y, item.grid_z)
                unscaled_x = sx
                unscaled_y = sy

            # Scale if zoom != 1.0
            sw, sh = surf.get_size()
            if abs(zoom - 1.0) > 0.01:
                scaled_w = max(1, int(sw * zoom))
                scaled_h = max(1, int(sh * zoom))
                draw_surf = pygame.transform.scale(surf, (scaled_w, scaled_h))
            else:
                draw_surf = surf
                scaled_w, scaled_h = sw, sh

            draw_x = int(center_x + (unscaled_x * zoom))
            draw_y = int(center_y + (unscaled_y * zoom))

            # Viewport culling
            if draw_x + scaled_w < 0 or draw_x > self.width or draw_y + scaled_h < 0 or draw_y > self.height:
                continue

            self.screen.blit(draw_surf, (draw_x, draw_y))

        # Selection box for currently inspected cell
        if self.hovered_cell:
            self._draw_selection_box()

        # Overlays
        self._draw_status_bar()
        if self.camera.show_minimap:
            self._draw_minimap()
        if self.camera.show_sidebar:
            self._draw_sidebar()

        pygame.display.flip()

    def _draw_selection_box(self) -> None:
        """Renders highlighted selection diamond/square over the currently inspected cell."""
        if not self.hovered_cell or not self.map_doc or not self.screen:
            return

        hx, hy, hz = self.hovered_cell
        is_iso = self.camera.perspective == ViewPerspective.ISOMETRIC
        zoom = self.camera.zoom
        center_x = self.width / 2.0 + (self.camera.x * zoom)
        center_y = self.height / 2.0 + (self.camera.y * zoom)

        if is_iso:
            sx, sy = self.iso_transform.world_to_screen(hx, hy, hz)
            world_pts = [
                (sx, sy),
                (sx + 64.0, sy + 32.0),
                (sx, sy + 64.0),
                (sx - 64.0, sy + 32.0),
            ]
        else:
            sx, sy = self.top_transform.world_to_screen(hx, hy, hz)
            cw = self.top_transform.cell_size
            world_pts = [
                (sx, sy),
                (sx + cw, sy),
                (sx + cw, sy + cw),
                (sx, sy + cw),
            ]

        screen_pts = [
            (int(center_x + (px * zoom)), int(center_y + (py * zoom)))
            for px, py in world_pts
        ]

        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.polygon(overlay, (0, 230, 255, 45), screen_pts)
        pygame.draw.polygon(overlay, (0, 230, 255, 240), screen_pts, width=2)
        self.screen.blit(overlay, (0, 0))

    def _draw_status_bar(self) -> None:
        """Renders HUD status bar at bottom."""
        bar_h = 28
        bar_rect = pygame.Rect(0, self.height - bar_h, self.width, bar_h)
        pygame.draw.rect(self.screen, (15, 18, 22), bar_rect)
        pygame.draw.line(self.screen, (60, 65, 75), (0, self.height - bar_h), (self.width, self.height - bar_h))

        if not self.map_doc:
            return

        parts = [
            f"Map: {self.map_doc.title} ({self.map_doc.width}x{self.map_doc.height})",
            f"View: {self.camera.perspective.value.upper()}",
            f"Layer: Z={self.camera.active_max_layer}/6",
            f"Zoom: {self.camera.zoom:.2f}x",
        ]
        if self.hovered_cell:
            hx, hy, hz = self.hovered_cell
            cell = self.map_doc.get_cell(hx, hy, hz)
            tile_info = ""
            if cell:
                c_info = CellInspector.inspect_cell(cell, self.tileset)
                if c_info.primary_tile_name:
                    tile_info = f" [{c_info.primary_tile_name}:{c_info.primary_tile_frame}]"
            parts.append(f"Hover: ({hx}, {hy}, {hz}){tile_info}")

        status_text = " | ".join(parts)
        text_surf = self.font.render(status_text, True, (220, 225, 230))
        max_w = self.width - (280 if self.camera.show_sidebar else 24)
        if text_surf.get_width() > max_w and len(status_text) > 20:
            while len(status_text) > 10 and text_surf.get_width() > max_w:
                status_text = status_text[:-5]
                text_surf = self.font.render(status_text + "...", True, (220, 225, 230))

        self.screen.blit(text_surf, (12, self.height - bar_h + 6))

    def _update_minimap_cache(self) -> None:
        """Generates and caches 2D top-down terrain surface from map cell data."""
        if not self.map_doc:
            self._minimap_surface = None
            return

        active_z = (
            self.camera.isolated_layer
            if self.camera.isolated_layer is not None
            else self.camera.active_max_layer
        )
        if self._minimap_surface is not None and self._minimap_cache_layer == active_z:
            return

        pil_img = generate_minimap_image(self.map_doc, self.tileset, active_z)
        raw_bytes = pil_img.tobytes()
        surf = pygame.image.fromstring(raw_bytes, pil_img.size, "RGBA")
        if pygame.display.get_init():
            try:
                surf = surf.convert_alpha()
            except pygame.error:
                pass
        self._minimap_surface = surf
        self._minimap_cache_layer = active_z

    def _draw_minimap(self) -> None:
        """Renders 2D top-down minimap with terrain visualization and camera frustum."""
        if not self.map_doc:
            return

        self._update_minimap_cache()
        if not self._minimap_surface:
            return

        offset_r = 260.0 if self.camera.show_sidebar else 0.0
        bounds = self._minimap_calc.get_minimap_bounds(self.width, self.height, offset_right=offset_r)

        # Background box and gold border
        pygame.draw.rect(self.screen, (10, 12, 16), (int(bounds.left), int(bounds.top), int(bounds.width), int(bounds.height)))
        pygame.draw.rect(self.screen, (218, 165, 32), (int(bounds.left), int(bounds.top), int(bounds.width), int(bounds.height)), 1)

        title = self.font.render("MINIMAP (M)", True, (218, 165, 32))
        self.screen.blit(title, (int(bounds.left) + 8, int(bounds.top) + 4))

        # Terrain frame bounds inside box
        inner_w = bounds.width - 16.0
        inner_h = bounds.height - 26.0
        scale = min(
            inner_w / max(1.0, float(self.map_doc.width)),
            inner_h / max(1.0, float(self.map_doc.height)),
        )
        disp_w = max(1, int(self.map_doc.width * scale))
        disp_h = max(1, int(self.map_doc.height * scale))

        fx = bounds.left + 8.0 + (inner_w - disp_w) / 2.0
        fy = bounds.top + 20.0 + (inner_h - disp_h) / 2.0

        # Scale and blit terrain surface
        scaled_terrain = pygame.transform.scale(self._minimap_surface, (disp_w, disp_h))
        self.screen.blit(scaled_terrain, (int(fx), int(fy)))
        pygame.draw.rect(self.screen, (80, 90, 100), (int(fx), int(fy), disp_w, disp_h), 1)

        # Camera viewport indicator polygon (diamond in isometric, rectangle in top-down)
        poly = self._minimap_calc.calculate_viewport_polygon(
            self.map_doc, self.camera, self.width, self.height, fx, fy, disp_w, disp_h, invert_y=False
        )
        if len(poly) >= 3:
            clamped = [
                (max(fx, min(fx + disp_w, px)), max(fy, min(fy + disp_h, py)))
                for px, py in poly
            ]
            pygame.draw.polygon(self.screen, (255, 255, 255), clamped, 1)

    def _draw_sidebar(self) -> None:
        """Renders detailed cell inspection panel on right."""
        side_w = 260
        left = self.width - side_w
        pygame.draw.rect(self.screen, (20, 24, 30), (left, 0, side_w, self.height - 28))
        pygame.draw.line(self.screen, (218, 165, 32), (left, 0), (left, self.height - 28))

        title = self.font_title.render("CELL INSPECTION (I)", True, (218, 165, 32))
        self.screen.blit(title, (left + 14, 14))

        if self.hovered_cell and self.map_doc:
            hx, hy, hz = self.hovered_cell
            cell = self.map_doc.get_cell(hx, hy, hz)
            y = 42
            coord_txt = self.font_bold.render(f"Coordinate: ({hx}, {hy}, {hz})", True, (255, 255, 255))
            self.screen.blit(coord_txt, (left + 14, y))
            y += 20
            if cell:
                info = CellInspector.inspect_cell(cell, self.tileset)
                tile_txt = self.font_bold.render(f"Tile Name: {info.primary_tile_label}", True, (0, 220, 220))
                self.screen.blit(tile_txt, (left + 14, y))
                y += 18
                elev_txt = self.font.render(
                    f"Elevation: 0x{cell.elevation_attr:02X} ({cell.elevation_attr})", True, (180, 185, 190)
                )
                self.screen.blit(elev_txt, (left + 14, y))
                y += 16
                flags_txt = self.font.render(f"Flags: 0x{cell.flags:08X}", True, (180, 185, 190))
                self.screen.blit(flags_txt, (left + 14, y))
                y += 18

                pygame.draw.line(self.screen, (60, 65, 75), (left + 14, y), (left + side_w - 14, y))
                y += 8

                for comp in info.components:
                    color = (50, 205, 50) if comp.is_present else (120, 120, 120)
                    slot_header = f"• {comp.slot_name}: {comp.status_label}"
                    lbl_txt = self.font_bold.render(slot_header, True, color)
                    self.screen.blit(lbl_txt, (left + 14, y))
                    y += 16

                    if comp.is_present:
                        raw_txt = self.font.render(
                            f"   Raw: 0x{comp.raw_word:04X} (G:{comp.tileset_group_index} F:{comp.sprite_frame_index})",
                            True,
                            (170, 175, 185),
                        )
                        self.screen.blit(raw_txt, (left + 14, y))
                        y += 15
                        det_txt = self.font.render(f"   {comp.details_line}", True, (220, 225, 230))
                        self.screen.blit(det_txt, (left + 14, y))
                        y += 18
                    else:
                        raw_txt = self.font.render(f"   Raw: 0x{comp.raw_word:04X}", True, (110, 115, 120))
                        self.screen.blit(raw_txt, (left + 14, y))
                        y += 16
        else:
            y = 48
            no_sel = self.font_bold.render("No cell hovered", True, (180, 185, 190))
            self.screen.blit(no_sel, (left + 14, y))
            y += 24
            tips = [
                "Move mouse over map",
                "to inspect components,",
                "attributes, and flags.",
                "",
                "Shortcuts:",
                "  [I] Toggle Sidebar",
                "  [M] Toggle Minimap",
                "  [PgUp/PgDn] Change Layer",
                "  [Tab] Toggle Iso/TopDown",
                "  [1-4] Toggle Layers",
                "  [P] Cycle Palette",
            ]
            for tip in tips:
                if tip:
                    col = (218, 165, 32) if tip.startswith("Shortcuts:") else (150, 155, 165)
                    fnt = self.font_bold if tip.startswith("Shortcuts:") else self.font
                    txt = fnt.render(tip, True, col)
                    self.screen.blit(txt, (left + 14, y))
                y += 18


    def run_loop(self) -> None:
        """Starts Pygame event loop."""
        self.running = True
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.width = event.w
                    self.height = event.h
                    self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                elif event.type == pygame.MOUSEMOTION:
                    self.update_hover(event.pos[0], event.pos[1])
                    if self.dragging:
                        dx = (event.pos[0] - self.drag_start_mouse[0]) / self.camera.zoom
                        dy = (event.pos[1] - self.drag_start_mouse[1]) / self.camera.zoom
                        self.camera.x = self.drag_start_cam[0] + dx
                        self.camera.y = self.drag_start_cam[1] + dy
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.dragging = True
                        self.drag_start_mouse = event.pos
                        self.drag_start_cam = (self.camera.x, self.camera.y)
                    elif event.button == 4:
                        self.camera.zoom_in()
                    elif event.button == 5:
                        self.camera.zoom_out()
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.dragging = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event.key)

            self.render_frame(self.camera)
            self.clock.tick(60)

        pygame.quit()

    def _handle_keydown(self, key: int) -> None:
        """Processes keyboard input."""
        cam = self.camera
        step = 40.0 / cam.zoom

        if key in (pygame.K_LEFT, pygame.K_a): cam.pan(step, 0)
        elif key in (pygame.K_RIGHT, pygame.K_d): cam.pan(-step, 0)
        elif key in (pygame.K_UP, pygame.K_w): cam.pan(0, step)
        elif key in (pygame.K_DOWN, pygame.K_s): cam.pan(0, -step)
        elif key in (pygame.K_PLUS, pygame.K_EQUALS): cam.zoom_in()
        elif key in (pygame.K_MINUS, pygame.K_UNDERSCORE): cam.zoom_out()
        elif key in (pygame.K_HOME, pygame.K_r): cam.reset()
        elif key in (pygame.K_PAGEUP, pygame.K_e):
            cam.active_max_layer = min(6, cam.active_max_layer + 1)
            cam.isolated_layer = None
            self.update_hover(*pygame.mouse.get_pos())
        elif key in (pygame.K_PAGEDOWN, pygame.K_q):
            cam.active_max_layer = max(0, cam.active_max_layer - 1)
            cam.isolated_layer = None
            self.update_hover(*pygame.mouse.get_pos())
        elif key == pygame.K_l:
            cam.isolated_layer = cam.active_max_layer if cam.isolated_layer is None else None
            self.update_hover(*pygame.mouse.get_pos())
        elif key in (pygame.K_TAB, pygame.K_t):
            cam.perspective = ViewPerspective.TOP_DOWN if cam.perspective == ViewPerspective.ISOMETRIC else ViewPerspective.ISOMETRIC
            self.update_hover(*pygame.mouse.get_pos())
        elif key == pygame.K_m: cam.show_minimap = not cam.show_minimap
        elif key == pygame.K_i: cam.show_sidebar = not cam.show_sidebar
        elif key == pygame.K_1: cam.show_floors = not cam.show_floors
        elif key == pygame.K_2: cam.show_left_walls = not cam.show_left_walls
        elif key == pygame.K_3: cam.show_right_walls = not cam.show_right_walls
        elif key == pygame.K_4: cam.show_clutter = not cam.show_clutter
        elif key == pygame.K_p: self.cycle_palette()
        elif key in (pygame.K_F11, pygame.K_f):
            try:
                pygame.display.toggle_fullscreen()
            except Exception:
                pass
        elif key == pygame.K_ESCAPE: self.running = False

    def close(self) -> None:
        """Closes Pygame."""
        self.running = False
        pygame.quit()
