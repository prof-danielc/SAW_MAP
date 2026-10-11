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

        self._surface_cache: Dict[Tuple[str, int, str], pygame.Surface] = {}
        self.hovered_cell: Optional[Tuple[int, int, int]] = None
        self.width: int = 1280
        self.height: int = 720
        self.dragging: bool = False
        self.drag_start_mouse: Tuple[int, int] = (0, 0)
        self.drag_start_cam: Tuple[float, float] = (0.0, 0.0)

    def initialize(self, width: int = 1280, height: int = 720, title: str = "SAW Map Visualizer (Pygame)") -> None:
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

    def _get_surface(self, item: RenderItem, palette: Palette) -> Optional[pygame.Surface]:
        """Loads and caches Pygame Surface from PIL Image."""
        if not self.asset_loader:
            return None

        asset_name = item.asset_name or "placeholder"
        key = (asset_name.lower(), item.sprite_frame_index, palette.name)

        if key in self._surface_cache:
            return self._surface_cache[key]

        if item.asset_name:
            pil_img = self.asset_loader.get_sprite_image(
                item.asset_name, item.sprite_frame_index, palette
            )
        else:
            pil_img = create_placeholder_sprite(item.component_type, 64, 32)

        raw_bytes = pil_img.tobytes()
        surf = pygame.image.fromstring(raw_bytes, pil_img.size, "RGBA").convert_alpha()
        self._surface_cache[key] = surf
        return surf

    def cycle_palette(self) -> None:
        """Cycles between daylight and ambient palettes."""
        if not self.asset_loader:
            return
        self.current_pal_idx = (self.current_pal_idx + 1) % len(self.available_palettes)
        pal_name = self.available_palettes[self.current_pal_idx]
        self.palette = self.asset_loader.load_palette(pal_name)
        self._surface_cache.clear()

    def update_hover(self, mx: int, my: int) -> None:
        """Calculates grid cell under cursor."""
        if not self.map_doc:
            return

        center_x = self.width / 2.0 + (self.camera.x * self.camera.zoom)
        center_y = self.height / 2.0 + (self.camera.y * self.camera.zoom)

        world_sx = (mx - center_x) / self.camera.zoom
        world_sy = (my - center_y) / self.camera.zoom

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
            surf = self._get_surface(item, self.palette)
            if not surf:
                continue

            if is_iso:
                sx, sy = self.iso_transform.world_to_screen(item.grid_x, item.grid_y, item.grid_z)
            else:
                sx, sy = self.top_transform.world_to_screen(item.grid_x, item.grid_y, item.grid_z)

            # Scale if zoom != 1.0
            sw, sh = surf.get_size()
            if abs(zoom - 1.0) > 0.01:
                scaled_w = max(1, int(sw * zoom))
                scaled_h = max(1, int(sh * zoom))
                draw_surf = pygame.transform.scale(surf, (scaled_w, scaled_h))
            else:
                draw_surf = surf
                scaled_w, scaled_h = sw, sh

            draw_x = int(center_x + (sx * zoom) - (scaled_w // 2))
            draw_y = int(center_y + (sy * zoom) - (scaled_h // 2))

            # Viewport culling
            if draw_x + scaled_w < 0 or draw_x > self.width or draw_y + scaled_h < 0 or draw_y > self.height:
                continue

            self.screen.blit(draw_surf, (draw_x, draw_y))

        # Overlays
        self._draw_status_bar()
        if self.camera.show_minimap:
            self._draw_minimap()
        if self.camera.show_sidebar:
            self._draw_sidebar()

        pygame.display.flip()

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
            parts.append(f"Hover: ({hx}, {hy}, {hz})")

        text_surf = self.font.render(" | ".join(parts), True, (220, 225, 230))
        self.screen.blit(text_surf, (12, self.height - bar_h + 6))

    def _draw_minimap(self) -> None:
        """Renders 2D top-down minimap in top-right corner."""
        if not self.map_doc:
            return
        mw, mh = 140, 110
        left = self.width - mw - 12
        top = 12

        pygame.draw.rect(self.screen, (10, 12, 16), (left, top, mw, mh))
        pygame.draw.rect(self.screen, (218, 165, 32), (left, top, mw, mh), 1)

        title = self.font.render("MINIMAP (M)", True, (218, 165, 32))
        self.screen.blit(title, (left + 6, top + 4))

        scale_x = (mw - 16) / max(1.0, float(self.map_doc.width))
        scale_y = (mh - 28) / max(1.0, float(self.map_doc.height))
        frame_rect = pygame.Rect(left + 8, top + 22, int(self.map_doc.width * scale_x), int(self.map_doc.height * scale_y))
        pygame.draw.rect(self.screen, (80, 90, 100), frame_rect, 1)

    def _draw_sidebar(self) -> None:
        """Renders detailed inspection panel on right."""
        side_w = 260
        left = self.width - side_w
        pygame.draw.rect(self.screen, (20, 24, 30), (left, 0, side_w, self.height - 28))
        pygame.draw.line(self.screen, (218, 165, 32), (left, 0), (left, self.height - 28))

        title = self.font_title.render("CELL INSPECTION (I)", True, (218, 165, 32))
        self.screen.blit(title, (left + 14, 14))

        if self.hovered_cell and self.map_doc:
            hx, hy, hz = self.hovered_cell
            cell = self.map_doc.get_cell(hx, hy, hz)
            y = 45
            coord_txt = self.font.render(f"Coordinate: ({hx}, {hy}, {hz})", True, (255, 255, 255))
            self.screen.blit(coord_txt, (left + 14, y))
            y += 24
            if cell:
                elev_txt = self.font.render(f"Elevation Byte: {cell.elevation_attr}", True, (180, 185, 190))
                self.screen.blit(elev_txt, (left + 14, y))
                y += 20
                flags_txt = self.font.render(f"Cell Flags: 0x{cell.flags:08X}", True, (180, 185, 190))
                self.screen.blit(flags_txt, (left + 14, y))
                y += 28

                for label, comp in (
                    ("Floor", cell.floor),
                    ("Left Wall", cell.left_wall),
                    ("Right Wall", cell.right_wall),
                    ("Clutter", cell.clutter),
                ):
                    status = "PRESENT" if comp.is_present else "EMPTY"
                    color = (50, 205, 50) if comp.is_present else (120, 120, 120)
                    lbl_txt = self.font_bold.render(f"• {label}: {status}", True, color)
                    self.screen.blit(lbl_txt, (left + 14, y))
                    y += 18
                    if comp.is_present:
                        asset = self.tileset.resolve_asset(comp.component_type, comp.tileset_group_index) if self.tileset else None
                        as_txt = self.font.render(f"   Asset: {asset or 'Unresolved'}", True, (220, 220, 220))
                        self.screen.blit(as_txt, (left + 14, y))
                        y += 16
                        grp_txt = self.font.render(f"   Grp: {comp.tileset_group_index} | Frm: {comp.sprite_frame_index}", True, (160, 160, 160))
                        self.screen.blit(grp_txt, (left + 14, y))
                        y += 20

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
        elif key in (pygame.K_PAGEDOWN, pygame.K_q):
            cam.active_max_layer = max(0, cam.active_max_layer - 1)
            cam.isolated_layer = None
        elif key == pygame.K_l:
            cam.isolated_layer = cam.active_max_layer if cam.isolated_layer is None else None
        elif key in (pygame.K_TAB, pygame.K_t):
            cam.perspective = ViewPerspective.TOP_DOWN if cam.perspective == ViewPerspective.ISOMETRIC else ViewPerspective.ISOMETRIC
        elif key == pygame.K_m: cam.show_minimap = not cam.show_minimap
        elif key == pygame.K_i: cam.show_sidebar = not cam.show_sidebar
        elif key == pygame.K_1: cam.show_floors = not cam.show_floors
        elif key == pygame.K_2: cam.show_left_walls = not cam.show_left_walls
        elif key == pygame.K_3: cam.show_right_walls = not cam.show_right_walls
        elif key == pygame.K_4: cam.show_clutter = not cam.show_clutter
        elif key == pygame.K_p: self.cycle_palette()
        elif key == pygame.K_ESCAPE: self.running = False

    def close(self) -> None:
        """Closes Pygame."""
        self.running = False
        pygame.quit()
