from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from PIL import Image

from saw_map.geometry.transform import IsometricTransform, TopDownTransform
from saw_map.maps.model import MapDocument, TilesetDefinition
from saw_map.viewer.camera import Camera, ViewPerspective


@dataclass(slots=True)
class MinimapBounds:
    """Screen-space rectangle coordinates for the minimap."""
    left: float
    top: float
    width: float
    height: float


@dataclass(slots=True)
class CameraFrustumBounds:
    """Position and size of camera viewport rectangle projected on minimap."""
    x: float
    y: float
    width: float
    height: float


def get_surface_color(
    asset_name: Optional[str],
    has_snow_context: bool = False,
) -> Tuple[int, int, int]:
    """Maps a surface asset name to RGB color based on Soldiers at War surface classes."""
    if not asset_name:
        return (10, 12, 16)
    name = asset_name.lower()

    # Snow surfaces (e.g. ssnow1, c_snow, etc.)
    if "snow" in name or "snw" in name:
        return (210, 215, 220)
    # Winter base maps default sgrass to snow color
    if has_snow_context and ("grass" in name or name == "sgrass"):
        return (210, 215, 220)

    # Water & rivers
    if any(k in name for k in ("water", "stream", "wtrfall", "deep")):
        return (50, 90, 150)
    # Sand & beaches
    if any(k in name for k in ("beach", "sand")):
        return (215, 195, 140)
    # Dirt roads, courtyards, paths
    if any(k in name for k in ("dirt", "path", "road")):
        return (130, 90, 50)
    # Railroad tracks & trains
    if any(k in name for k in ("track", "train", "rail")):
        return (55, 55, 60)
    # Stone, concrete, hangars, cobblestones
    if any(k in name for k in ("stone", "cobble", "swalk", "church", "mansn", "cat", "comp", "wrhouse", "gen")):
        return (90, 95, 100)
    # Wood decks, bridges, docks
    if any(k in name for k in ("wood", "dock", "bridge")):
        return (150, 110, 70)
    # Metal plates & roofs
    if any(k in name for k in ("metal", "tarrf")):
        return (115, 125, 135)
    # Hill, rocky terrain, caves, stairs
    if any(k in name for k in ("hill", "cave", "rock", "stairs")):
        return (140, 130, 110)
    # Grass & vegetation (summer maps)
    if any(k in name for k in ("grass", "vine", "tree")):
        return (70, 120, 60)

    return (120, 120, 125)


def generate_minimap_image(
    map_doc: MapDocument,
    tileset: Optional[TilesetDefinition] = None,
    active_layer: Optional[int] = None,
) -> Image.Image:
    """Generates a 2D top-down orthogonal RGB PIL image of the map terrain."""
    w = max(1, map_doc.width)
    h = max(1, map_doc.height)
    img = Image.new("RGBA", (w, h), (10, 12, 16, 255))

    has_snow = bool(tileset and any("snow" in s.lower() for s in tileset.surfaces))
    max_z = active_layer if active_layer is not None else (map_doc.layer_count - 1)

    for y in range(h):
        for x in range(w):
            color: Optional[Tuple[int, int, int]] = None
            cell0 = map_doc.get_cell(x, y, 0)
            if cell0:
                # w3 (clutter) stores procedural ground surface
                if cell0.clutter.is_present and cell0.clutter.sprite_frame_index < 200:
                    asset = tileset.resolve_flat_asset(cell0.clutter.tileset_group_index) if tileset else None
                    color = get_surface_color(asset, has_snow_context=has_snow)
                elif cell0.floor.is_present and cell0.floor.sprite_frame_index < 200:
                    asset = tileset.resolve_flat_asset(cell0.floor.tileset_group_index) if tileset else None
                    color = get_surface_color(asset, has_snow_context=has_snow)

            # Check if any layer up to active layer has walls or structures
            has_wall = False
            for z in range(max_z + 1):
                cell_z = map_doc.get_cell(x, y, z)
                if cell_z and (cell_z.left_wall.is_present or cell_z.right_wall.is_present):
                    has_wall = True
                    break

            if has_wall:
                color = (45, 45, 50)
            elif color is None:
                for z in range(1, max_z + 1):
                    cell_z = map_doc.get_cell(x, y, z)
                    if cell_z and cell_z.clutter.is_present and cell_z.clutter.sprite_frame_index < 200:
                        asset = tileset.resolve_flat_asset(cell_z.clutter.tileset_group_index) if tileset else None
                        color = get_surface_color(asset, has_snow_context=has_snow)
                        break

            if color is not None:
                img.putpixel((x, y), (*color, 255))
            else:
                img.putpixel((x, y), (10, 12, 16, 255))

    return img


class MinimapCalculator:
    """Computes coordinates and viewport projection for the 2D corner minimap."""

    def __init__(
        self,
        box_width: float = 160.0,
        box_height: float = 120.0,
        margin: float = 12.0,
    ) -> None:
        self.box_width = box_width
        self.box_height = box_height
        self.margin = margin
        self.iso_transform = IsometricTransform()
        self.top_transform = TopDownTransform()

    def get_minimap_bounds(
        self, screen_w: float, screen_h: float, offset_right: float = 0.0
    ) -> MinimapBounds:
        """Calculates top-right corner placement bounds, optional offset when sidebar is open."""
        left = screen_w - self.box_width - self.margin - offset_right
        top = self.margin
        return MinimapBounds(
            left=left,
            top=top,
            width=self.box_width,
            height=self.box_height,
        )

    def calculate_camera_frustum(
        self,
        map_doc: MapDocument,
        camera: Camera,
        screen_w: float,
        screen_h: float,
    ) -> CameraFrustumBounds:
        """Calculates camera viewport indicator box on the minimap."""
        inner_w = self.box_width - 16.0
        inner_h = self.box_height - 28.0

        map_w = max(1.0, float(map_doc.width))
        map_h = max(1.0, float(map_doc.height))

        scale_x = inner_w / map_w
        scale_y = inner_h / map_h

        visible_world_w = (screen_w / camera.zoom) / 64.0
        visible_world_h = (screen_h / camera.zoom) / 32.0

        frustum_w = max(4.0, visible_world_w * scale_x)
        frustum_h = max(4.0, visible_world_h * scale_y)

        center_grid_x = (-camera.x / 64.0) + (map_w / 2.0)
        center_grid_y = (-camera.y / 32.0) + (map_h / 2.0)

        fx = center_grid_x * scale_x - (frustum_w / 2.0)
        fy = center_grid_y * scale_y - (frustum_h / 2.0)

        fx = max(0.0, min(inner_w - frustum_w, fx))
        fy = max(0.0, min(inner_h - frustum_h, fy))

        return CameraFrustumBounds(x=fx, y=fy, width=frustum_w, height=frustum_h)

    def calculate_viewport_polygon(
        self,
        map_doc: MapDocument,
        camera: Camera,
        screen_w: float,
        screen_h: float,
        frame_x: float,
        frame_y: float,
        frame_w: float,
        frame_h: float,
        invert_y: bool = False,
    ) -> List[Tuple[float, float]]:
        """Calculates 4 polygon vertices of the camera viewport projected onto minimap.

        In isometric mode, this produces the diamond viewport frustum matching the original
        game editor minimap.
        """
        map_w = max(1.0, float(map_doc.width))
        map_h = max(1.0, float(map_doc.height))

        # 4 screen corners relative to viewport center
        half_w = screen_w / 2.0
        half_h = screen_h / 2.0
        corners = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
        ]

        z_plane = float(camera.isolated_layer if camera.isolated_layer is not None else camera.active_max_layer)
        pts: List[Tuple[float, float]] = []

        for cx, cy in corners:
            # Calculate world coordinate for each corner
            world_sx = -camera.x + (cx / camera.zoom)
            if invert_y:
                # In Arcade, screen Y increases upwards, so positive cy is visually upwards (North / smaller world_sy)
                world_sy = -camera.y - (cy / camera.zoom)
            else:
                # In Pygame, screen Y increases downwards, so negative cy is visually upwards (North / smaller world_sy)
                world_sy = -camera.y + (cy / camera.zoom)

            if camera.perspective == ViewPerspective.ISOMETRIC:
                gx, gy = self.iso_transform.screen_to_world_float(world_sx, world_sy, z_plane)
            else:
                gx = world_sx / 32.0
                gy = world_sy / 32.0

            px = frame_x + (gx / map_w) * frame_w
            if invert_y:
                # Arcade coordinate system (0 is bottom)
                py = frame_y + ((map_h - gy) / map_h) * frame_h
            else:
                # Pygame coordinate system (0 is top)
                py = frame_y + (gy / map_h) * frame_h

            pts.append((px, py))

        return pts

