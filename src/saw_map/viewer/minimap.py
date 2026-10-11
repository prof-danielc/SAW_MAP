from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Tuple

from PIL import Image

from saw_map.geometry.transform import IsometricTransform, TopDownTransform
from saw_map.maps.model import MapDocument, TilesetDefinition
from saw_map.maps.records import EntityCategory, PlacedEntity
from saw_map.viewer.camera import Camera, ViewPerspective


@dataclass(slots=True)
class MinimapBounds:
    """Screen-space rectangle coordinates for the minimap."""
    left: float
    top: float
    width: float
    height: float


# Soldier marker colors
ALLIED_COLOR: Tuple[int, int, int] = (60, 225, 80)
ENEMY_COLOR: Tuple[int, int, int] = (240, 60, 60)
CIVILIAN_COLOR: Tuple[int, int, int] = (70, 150, 255)

# Nationality codes of the soldier record, grouped by side
_ALLIES: FrozenSet[int] = frozenset({1, 8})  # American, French
_AXIS: FrozenSet[int] = frozenset({2, 16})  # German, Italian
_NEUTRAL = 4
_HUMAN = "Human"


@dataclass(slots=True)
class MinimapMarker:
    """A soldier dot on the minimap, in cells relative to the playable window origin."""
    x: int
    y: int
    color: Tuple[int, int, int]


def _is_civilian(entity: PlacedEntity) -> bool:
    """Neutral characters and characters with a civilian body type."""
    if entity.attributes.get("nationality") == _NEUTRAL:
        return True
    return "civilian" in str(entity.attributes.get("appearance", "")).lower()


def _player_side(soldiers: List[PlacedEntity]) -> FrozenSet[int]:
    """Nationalities fighting on the player's side.

    The side is taken from the human-controlled soldiers; a map without any is
    read as an Allied mission.
    """
    human = {s.attributes.get("nationality") for s in soldiers if s.attributes.get("controller") == _HUMAN}
    side: FrozenSet[int] = frozenset()
    if human & _ALLIES:
        side |= _ALLIES
    if human & _AXIS:
        side |= _AXIS
    return side or _ALLIES


def get_minimap_markers(
    map_doc: MapDocument,
    active_layer: Optional[int] = None,
    isolated_layer: Optional[int] = None,
) -> List[MinimapMarker]:
    """Returns soldier dots: allied green, enemy red, civilian blue.

    Soldiers the game does not draw (hidden flag), soldiers outside the playable
    window, and soldiers above the visible levels are left out. Allied dots come
    last so they are drawn on top.
    """
    max_z = active_layer if active_layer is not None else (map_doc.layer_count - 1)
    soldiers = [e for e in map_doc.entities if e.category == EntityCategory.SOLDIER]
    player_side = _player_side(soldiers)

    civilians: List[MinimapMarker] = []
    enemies: List[MinimapMarker] = []
    allies: List[MinimapMarker] = []
    for soldier in soldiers:
        if soldier.attributes.get("hidden") or not map_doc.contains(soldier.x, soldier.y):
            continue
        if isolated_layer is not None:
            if soldier.z != isolated_layer:
                continue
        elif soldier.z > max_z:
            continue
        px = soldier.x - map_doc.origin_x
        py = soldier.y - map_doc.origin_y
        if _is_civilian(soldier):
            civilians.append(MinimapMarker(px, py, CIVILIAN_COLOR))
        elif soldier.attributes.get("nationality") in player_side:
            allies.append(MinimapMarker(px, py, ALLIED_COLOR))
        else:
            enemies.append(MinimapMarker(px, py, ENEMY_COLOR))
    return civilians + enemies + allies


def get_surface_color(asset_name: Optional[str]) -> Tuple[int, int, int]:
    """Maps a surface asset name to RGB color based on Soldiers at War surface classes."""
    if not asset_name:
        return (10, 12, 16)
    name = asset_name.lower()

    # Snow surfaces (e.g. ssnow1, c_snow, etc.)
    if "snow" in name or "snw" in name:
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
    """Generates a 2D top-down orthogonal RGBA PIL image of the playable map window."""
    w = max(1, map_doc.width)
    h = max(1, map_doc.height)
    img = Image.new("RGBA", (w, h), (10, 12, 16, 255))

    max_z = active_layer if active_layer is not None else (map_doc.layer_count - 1)

    for py in range(h):
        for px in range(w):
            # Image pixels are relative to the playable window origin
            x = map_doc.origin_x + px
            y = map_doc.origin_y + py
            color: Optional[Tuple[int, int, int]] = None
            object_color: Optional[Tuple[int, int, int]] = None

            for z in range(max_z + 1):
                cell = map_doc.get_cell(x, y, z)
                if not cell:
                    continue

                # Ground color comes from the lowest floor (word 0) in the column
                if color is None and cell.floor.is_present:
                    asset = tileset.resolve_flat_asset(cell.floor.tileset_group_index) if tileset else None
                    color = get_surface_color(asset)

                # Clutter objects (word 3) and walls (words 1-2) override the ground color
                if cell.clutter.is_present and tileset:
                    c_asset = tileset.resolve_flat_asset(cell.clutter.tileset_group_index)
                    c_low = c_asset.lower() if c_asset else ""
                    if "plane" in c_low:
                        object_color = (130, 140, 155)  # Aircraft
                        break
                    elif "tree" in c_low:
                        object_color = (35, 75, 30)  # Trees
                        break
                    elif any(k in c_low for k in ("vehic", "gun", "filler", "wrhouse", "sandbag")):
                        object_color = (65, 70, 75)  # Military vehicles and installations
                        break
                if cell.left_wall.is_present or cell.right_wall.is_present:
                    object_color = (45, 45, 50)  # Walls and fences

            if object_color is not None:
                color = object_color
            if color is not None:
                img.putpixel((px, py), (*color, 255))

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

            # Minimap pixels are relative to the playable window origin
            gx -= map_doc.origin_x
            gy -= map_doc.origin_y

            px = frame_x + (gx / map_w) * frame_w
            if invert_y:
                # Arcade coordinate system (0 is bottom)
                py = frame_y + ((map_h - gy) / map_h) * frame_h
            else:
                # Pygame coordinate system (0 is top)
                py = frame_y + (gy / map_h) * frame_h

            pts.append((px, py))

        return pts

