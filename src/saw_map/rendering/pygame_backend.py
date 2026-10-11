"""Fallback Pygame 2.6.1 software surface rendering engine for Soldiers at War visualizer.

Provides CPU-based surface blitting, camera navigation, and diagnostic overlays
as an immediate drop-in replacement if OpenGL hardware initialization fails.
"""

from __future__ import annotations

import math
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
from saw_map.rendering.fallback import (
    EDGE_BLEED,
    create_placeholder_sprite,
    expand_opaque_edges,
    highlight_opaque_area,
    outline_opaque_edges,
)
from saw_map.viewer.camera import Camera, ViewPerspective
from saw_map.viewer.input_handler import PAN_ACTIONS, InputAction, InputHandler
from saw_map.viewer.inspector import CellInspector
from saw_map.viewer.minimap import MinimapCalculator, generate_minimap_image, get_minimap_markers
from saw_map.viewer.overlays import OverlayModel

logger = get_logger("rendering.pygame")

# Pygame key code -> semantic input action
_KEY_ACTIONS: Dict[int, InputAction] = {
    pygame.K_LEFT: InputAction.PAN_LEFT,
    pygame.K_a: InputAction.PAN_LEFT,
    pygame.K_RIGHT: InputAction.PAN_RIGHT,
    pygame.K_d: InputAction.PAN_RIGHT,
    pygame.K_UP: InputAction.PAN_UP,
    pygame.K_w: InputAction.PAN_UP,
    pygame.K_DOWN: InputAction.PAN_DOWN,
    pygame.K_s: InputAction.PAN_DOWN,
    pygame.K_PLUS: InputAction.ZOOM_IN,
    pygame.K_EQUALS: InputAction.ZOOM_IN,
    pygame.K_KP_PLUS: InputAction.ZOOM_IN,
    pygame.K_MINUS: InputAction.ZOOM_OUT,
    pygame.K_UNDERSCORE: InputAction.ZOOM_OUT,
    pygame.K_KP_MINUS: InputAction.ZOOM_OUT,
    pygame.K_HOME: InputAction.RESET_VIEW,
    pygame.K_r: InputAction.RESET_VIEW,
    pygame.K_PAGEUP: InputAction.ELEVATION_UP,
    pygame.K_e: InputAction.ELEVATION_UP,
    pygame.K_PAGEDOWN: InputAction.ELEVATION_DOWN,
    pygame.K_q: InputAction.ELEVATION_DOWN,
    pygame.K_l: InputAction.TOGGLE_LAYER_ISOLATION,
    pygame.K_TAB: InputAction.TOGGLE_PERSPECTIVE,
    pygame.K_t: InputAction.TOGGLE_PERSPECTIVE,
    pygame.K_m: InputAction.TOGGLE_MINIMAP,
    pygame.K_i: InputAction.TOGGLE_SIDEBAR,
    pygame.K_F1: InputAction.TOGGLE_METADATA,
    pygame.K_h: InputAction.TOGGLE_METADATA,
    pygame.K_g: InputAction.TOGGLE_GRID,
    pygame.K_1: InputAction.TOGGLE_FLOORS,
    pygame.K_2: InputAction.TOGGLE_LEFT_WALLS,
    pygame.K_3: InputAction.TOGGLE_RIGHT_WALLS,
    pygame.K_4: InputAction.TOGGLE_CLUTTER,
    pygame.K_5: InputAction.TOGGLE_ENTITIES,
    pygame.K_6: InputAction.TOGGLE_MARKERS,
    pygame.K_7: InputAction.TOGGLE_EFFECTS,
    pygame.K_p: InputAction.CYCLE_PALETTE,
    pygame.K_F11: InputAction.TOGGLE_FULLSCREEN,
    pygame.K_f: InputAction.TOGGLE_FULLSCREEN,
    pygame.K_ESCAPE: InputAction.EXIT,
}


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

        self.input = InputHandler(
            self.camera,
            on_recenter=self._update_map_center,
            on_cycle_palette=self.cycle_palette,
            on_toggle_fullscreen=self._toggle_fullscreen,
            on_exit=self._stop,
        )

    def _toggle_fullscreen(self) -> None:
        """Toggles the display between fullscreen and windowed mode."""
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error as exc:
            logger.warning(f"Fullscreen toggle not supported: {exc}")

    def _update_map_center(self) -> None:
        """Centers the camera on the mid-point of the active map."""
        if not self.map_doc:
            return
        mid_x, mid_y = self.map_doc.center
        if self.camera.perspective == ViewPerspective.ISOMETRIC:
            sx, sy = self.iso_transform.world_to_screen(mid_x, mid_y, 0)
        else:
            sx, sy = self.top_transform.world_to_screen(mid_x, mid_y, 0)
        self.camera.x = -sx
        self.camera.y = -sy

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
        self._minimap_surface = None
        self._update_map_center()

    def _get_surface_data(
        self, item: RenderItem, palette: Palette, highlight: bool = False
    ) -> Optional[Tuple[pygame.Surface, int, int]]:
        """Loads and caches (pygame.Surface, offset_x, offset_y) from PIL Image.

        highlight selects the tinted variant used for the floor of the inspected cell.
        """
        if not self.asset_loader:
            return None

        asset_name = item.asset_name or f"placeholder:{int(item.component_type)}"
        # With the cell grid on, floors use a variant with their border painted
        is_floor = item.component_type == ComponentType.FLOOR
        with_grid = is_floor and self.camera.show_grid
        variant = ("#grid" if with_grid else "") + ("#hover" if highlight and is_floor else "")
        key = (asset_name.lower() + variant, item.sprite_frame_index, palette.name)

        if key in self._surface_cache:
            return self._surface_cache[key]

        if item.asset_name:
            pil_img, ox, oy = self.asset_loader.get_sprite_image_and_offset(
                item.asset_name, item.sprite_frame_index, palette
            )
        else:
            pil_img = create_placeholder_sprite(item.component_type, 128, 64)
            ox, oy = 209, 322

        # Floors overlap their neighbours by one pixel so no seams show between tiles.
        # The grid border is painted on that overlap, so a shared edge shows a single line.
        if is_floor:
            pil_img = expand_opaque_edges(pil_img)
            ox -= EDGE_BLEED
            oy -= EDGE_BLEED
            if with_grid:
                pil_img = outline_opaque_edges(pil_img)
            if highlight:
                pil_img = highlight_opaque_area(pil_img)

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
        self.input.camera = camera
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
            show_entities=self.camera.show_entities,
            show_markers=self.camera.show_markers,
            show_effects=self.camera.show_effects,
        )

        center_x = self.width / 2.0 + (self.camera.x * self.camera.zoom)
        center_y = self.height / 2.0 + (self.camera.y * self.camera.zoom)
        is_iso = self.camera.perspective == ViewPerspective.ISOMETRIC
        zoom = self.camera.zoom

        # The floor of the inspected cell is drawn with a tinted, outlined variant of its sprite,
        # so the highlight has the sprite's shape and is covered by whatever stands in front
        floor_highlighted = False
        for item in items:
            highlight = (
                item.component_type == ComponentType.FLOOR
                and (item.grid_x, item.grid_y, item.grid_z) == self.hovered_cell
            )
            surf_data = self._get_surface_data(item, self.palette, highlight=highlight)
            if not surf_data:
                continue
            floor_highlighted = floor_highlighted or highlight

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

            # Screen rectangle: both edges are rounded outwards from the scaled world position,
            # so neighbouring tiles overlap instead of leaving gaps at fractional zoom
            sw, sh = surf.get_size()
            draw_x = math.floor(center_x + (unscaled_x * zoom))
            draw_y = math.floor(center_y + (unscaled_y * zoom))
            if abs(zoom - 1.0) > 0.01:
                scaled_w = max(1, math.ceil(center_x + ((unscaled_x + sw) * zoom)) - draw_x)
                scaled_h = max(1, math.ceil(center_y + ((unscaled_y + sh) * zoom)) - draw_y)
            else:
                scaled_w, scaled_h = sw, sh

            # Viewport culling
            if draw_x + scaled_w < 0 or draw_x > self.width or draw_y + scaled_h < 0 or draw_y > self.height:
                continue

            if (scaled_w, scaled_h) != (sw, sh):
                draw_surf = pygame.transform.scale(surf, (scaled_w, scaled_h))
            else:
                draw_surf = surf

            self.screen.blit(draw_surf, (draw_x, draw_y))

        # Selection box, only for an inspected cell without a drawn floor
        if self.hovered_cell and not floor_highlighted:
            self._draw_selection_box()

        # Overlays
        self._draw_status_bar()
        if self.camera.show_minimap:
            self._draw_minimap()
        if self.camera.show_sidebar:
            self._draw_sidebar()
        if self.camera.show_metadata:
            self._draw_metadata_dialog()

        pygame.display.flip()

    def _draw_selection_box(self) -> None:
        """Renders a selection diamond/square over the inspected cell when it has no drawn floor."""
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

        status_text = OverlayModel.get_status_bar_text(
            self.map_doc, self.camera, self.hovered_cell, self.tileset
        )
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

        # Soldier dots: allied green, enemy red, civilian blue
        dot = max(3, int(round(scale)) + 1)
        for marker in get_minimap_markers(
            self.map_doc, self.camera.active_max_layer, self.camera.isolated_layer
        ):
            cx = fx + (marker.x + 0.5) * scale
            cy = fy + (marker.y + 0.5) * scale
            pygame.draw.rect(self.screen, marker.color, (int(cx - dot / 2.0), int(cy - dot / 2.0), dot, dot))

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
                info = CellInspector.inspect_cell(cell, self.tileset, self.map_doc.entities_at(hx, hy, hz))
                tile_txt = self.font_bold.render(f"Tile Name: {info.primary_tile_label}", True, (0, 220, 220))
                self.screen.blit(tile_txt, (left + 14, y))
                y += 18
                elev_txt = self.font.render(
                    f"Black-out mask: 0x{cell.elevation_attr:02X}", True, (180, 185, 190)
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

                for heading, detail in OverlayModel.get_entity_lines(info.entities):
                    head_txt = self.font_bold.render(f"◆ {heading}", True, (218, 165, 32))
                    self.screen.blit(head_txt, (left + 14, y))
                    y += 15
                    det_txt = self.font.render(f"   {detail}", True, (220, 225, 230))
                    self.screen.blit(det_txt, (left + 14, y))
                    y += 18
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
                "  [5] Toggle Entities",
                "  [6] Toggle Editor Markers",
                "  [7] Toggle Fog / Smoke / Fire",
                "  [G] Toggle Cell Grid",
                "  [P] Cycle Palette",
            ]
            for tip in tips:
                if tip:
                    col = (218, 165, 32) if tip.startswith("Shortcuts:") else (150, 155, 165)
                    fnt = self.font_bold if tip.startswith("Shortcuts:") else self.font
                    txt = fnt.render(tip, True, col)
                    self.screen.blit(txt, (left + 14, y))
                y += 18

    def _draw_metadata_dialog(self) -> None:
        """Renders centered map metadata dialog (map, tileset, mission briefing)."""
        panel_w = min(640, self.width - 40)
        panel_h = min(460, self.height - 80)
        if panel_w < 200 or panel_h < 100:
            return
        left = (self.width - panel_w) // 2
        top = (self.height - panel_h) // 2
        pygame.draw.rect(self.screen, (15, 18, 22), (left, top, panel_w, panel_h))
        pygame.draw.rect(self.screen, (218, 165, 32), (left, top, panel_w, panel_h), 1)

        title = self.font_title.render("MAP METADATA (F1 / H)", True, (218, 165, 32))
        self.screen.blit(title, (left + 16, top + 12))

        line_h = 18
        max_lines = (panel_h - 52) // line_h
        lines = OverlayModel.get_map_metadata_lines(self.map_doc, self.tileset, wrap_width=72)
        if len(lines) > max_lines:
            lines = lines[: max_lines - 1] + ["..."]

        y = top + 42
        for line in lines:
            if line:
                is_heading = line.isupper() or line.startswith(("MAP:", "TILESET DEFINITION:"))
                font = self.font_bold if is_heading else self.font
                color = (0, 220, 220) if is_heading else (220, 225, 230)
                self.screen.blit(font.render(line, True, color), (left + 16, y))
            y += line_h

    def run_loop(self) -> None:
        """Starts Pygame event loop."""
        self.running = True
        delta_time = 0.0
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.width = event.w
                    self.height = event.h
                    self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                elif event.type == pygame.MOUSEMOTION:
                    if self.dragging:
                        dx = (event.pos[0] - self.drag_start_mouse[0]) / self.camera.zoom
                        dy = (event.pos[1] - self.drag_start_mouse[1]) / self.camera.zoom
                        self.camera.x = self.drag_start_cam[0] + dx
                        self.camera.y = self.drag_start_cam[1] + dy
                    self.update_hover(event.pos[0], event.pos[1])
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.dragging = True
                        self.drag_start_mouse = event.pos
                        self.drag_start_cam = (self.camera.x, self.camera.y)
                    elif event.button in (4, 5):
                        self.input.handle_zoom_at_cursor(
                            event.button == 4,
                            float(event.pos[0]),
                            float(event.pos[1]),
                            float(self.width),
                            float(self.height),
                        )
                        self.update_hover(event.pos[0], event.pos[1])
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.dragging = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event.key)
                elif event.type == pygame.KEYUP:
                    self._handle_keyup(event.key)
                elif event.type == pygame.WINDOWFOCUSLOST:
                    self.input.release_all_pans()

            if self.running:
                # Held pan keys move the camera every frame
                if self.input.update(delta_time):
                    self.update_hover(*pygame.mouse.get_pos())
                self.render_frame(self.camera)
                delta_time = self.clock.tick(60) / 1000.0

        pygame.quit()

    def _handle_keydown(self, key: int) -> None:
        """Translates a key press into an InputAction handled by the shared InputHandler."""
        action = _KEY_ACTIONS.get(key)
        if action is None:
            return
        if action in PAN_ACTIONS:
            self.input.set_pan_held(action, True)
            return
        self.input.handle_action(action)
        if action != InputAction.EXIT:
            self.update_hover(*pygame.mouse.get_pos())

    def _handle_keyup(self, key: int) -> None:
        """Stops the continuous pan of a released pan key."""
        action = _KEY_ACTIONS.get(key)
        if action is not None:
            self.input.set_pan_held(action, False)

    def _stop(self) -> None:
        """Requests termination of the event loop."""
        self.running = False

    def close(self) -> None:
        """Closes Pygame."""
        self.running = False
        pygame.quit()
