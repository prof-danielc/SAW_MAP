"""Distinctive placeholder geometry generator for missing, unresolved, or corrupted sprite assets.

Ensures the renderer never crashes on missing assets while clearly marking
unresolved assets for reverse-engineering inspection.
"""

from __future__ import annotations

from typing import Tuple
from PIL import Image, ImageDraw

from saw_map.maps.model import ComponentType

# Distinctive diagnostic colors per component category (RGBA)
CATEGORY_COLORS = {
    ComponentType.FLOOR: (34, 139, 34, 180),        # Forest Green
    ComponentType.LEFT_WALL: (30, 144, 255, 200),   # Dodger Blue
    ComponentType.RIGHT_WALL: (0, 206, 209, 200),   # Dark Turquoise
    ComponentType.CLUTTER: (255, 20, 147, 220),     # Deep Pink / Magenta
}


def create_placeholder_sprite(
    component_type: ComponentType,
    width: int = 64,
    height: int = 32,
    label: str = "",
) -> Image.Image:
    """Generates an RGBA Pillow image representing placeholder tile geometry.

    Args:
        component_type: Structural category of the tile.
        width: Tile width in pixels (default: 64).
        height: Tile height in pixels (default: 32).
        label: Optional debug label or index.

    Returns:
        Pillow RGBA Image containing diamond wireframe and category colors.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    color = CATEGORY_COLORS.get(component_type, (255, 0, 255, 200))
    outline_color = (255, 255, 255, 255)

    half_w = width // 2
    half_h = height // 2

    # Dimetric diamond contour
    diamond = [
        (half_w, 0),
        (width - 1, half_h),
        (half_w, height - 1),
        (0, half_h),
    ]

    draw.polygon(diamond, fill=color, outline=outline_color)
    # Inner diagonal cross for diagnostic clarity
    draw.line([(0, half_h), (width - 1, half_h)], fill=outline_color, width=1)
    draw.line([(half_w, 0), (half_w, height - 1)], fill=outline_color, width=1)

    return img
