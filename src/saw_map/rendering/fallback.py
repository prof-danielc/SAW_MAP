"""Distinctive placeholder geometry generator for missing, unresolved, or corrupted sprite assets.

Ensures the renderer never crashes on missing assets while clearly marking
unresolved assets for reverse-engineering inspection.
"""

from __future__ import annotations

from typing import Tuple
from PIL import Image, ImageChops, ImageDraw

from saw_map.maps.model import ComponentType

# Distinctive diagnostic colors per component category (RGBA)
CATEGORY_COLORS = {
    ComponentType.FLOOR: (34, 139, 34, 180),        # Forest Green
    ComponentType.LEFT_WALL: (30, 144, 255, 200),   # Dodger Blue
    ComponentType.RIGHT_WALL: (0, 206, 209, 200),   # Dark Turquoise
    ComponentType.CLUTTER: (255, 20, 147, 220),     # Deep Pink / Magenta
    ComponentType.ENTITY: (255, 215, 0, 220),       # Gold
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


# Width in pixels of the border added by expand_opaque_edges on every side
EDGE_BLEED = 1


def expand_opaque_edges(image: Image.Image) -> Image.Image:
    """Grows the opaque area of a sprite by one pixel, repeating its edge colors.

    Floor tiles meet exactly edge to edge. Once the view is scaled (zoom or display
    scaling) rounding leaves hairline gaps between neighbours, which show up as a
    grid pattern. Letting each floor tile overlap its neighbours by one pixel closes
    them. The result is EDGE_BLEED pixels larger on every side, so it must be drawn
    EDGE_BLEED pixels further up and left.
    """
    source = image if image.mode == "RGBA" else image.convert("RGBA")
    width, height = source.size
    grown = Image.new("RGBA", (width + 2 * EDGE_BLEED, height + 2 * EDGE_BLEED), (0, 0, 0, 0))
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2), (1, 1)):
        grown.paste(source, (dx * EDGE_BLEED, dy * EDGE_BLEED), source)
    return grown


# Color of the cell grid painted on floor sprite borders
GRID_COLOR: Tuple[int, int, int] = (70, 150, 165)


def outline_opaque_edges(image: Image.Image, color: Tuple[int, int, int] = GRID_COLOR) -> Image.Image:
    """Returns a copy of a sprite with the border of its opaque area painted in one color.

    A pixel belongs to the border when it is opaque and one of its four neighbours is
    transparent or lies outside the image. Painting the border of every floor sprite
    draws the cell grid on the terrain itself: it follows slopes and raised ground, and
    sprites drawn in front cover it like any other part of the floor.
    """
    source = image if image.mode == "RGBA" else image.convert("RGBA")
    width, height = source.size
    alpha = source.getchannel("A").point(lambda value: 255 if value else 0)
    # A pixel is interior when it and its four neighbours are all opaque: the minimum of
    # the mask and its four one-pixel shifts. Pixels shifted in from outside count as clear.
    interior = alpha
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        shifted = Image.new("L", (width, height), 0)
        shifted.paste(alpha, (dx, dy))
        interior = ImageChops.darker(interior, shifted)
    border = ImageChops.subtract(alpha, interior)
    outlined = source.copy()
    outlined.paste((*color, 255), (0, 0), border)
    return outlined


# Color of the highlight on the floor sprite of the inspected cell
HIGHLIGHT_COLOR: Tuple[int, int, int] = (0, 230, 255)
# Share of the highlight color mixed into the sprite's own colors
HIGHLIGHT_STRENGTH = 0.3


def highlight_opaque_area(
    image: Image.Image,
    color: Tuple[int, int, int] = HIGHLIGHT_COLOR,
    strength: float = HIGHLIGHT_STRENGTH,
) -> Image.Image:
    """Returns a copy of a sprite tinted with a color and outlined in that color.

    Used for the floor of the inspected cell: the highlight takes the exact shape of the
    sprite (slopes included) and is covered by whatever is drawn in front of the floor.
    Transparent pixels stay transparent.
    """
    source = image if image.mode == "RGBA" else image.convert("RGBA")
    opaque = source.getchannel("A").point(lambda value: 255 if value else 0)
    tinted = Image.blend(source, Image.new("RGBA", source.size, (*color, 255)), strength)
    highlighted = source.copy()
    highlighted.paste(tinted, (0, 0), opaque)
    return outline_opaque_edges(highlighted, color)

