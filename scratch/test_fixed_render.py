import sys
from pathlib import Path
sys.path.insert(0, "src")

from saw_map.formats.map_reader import MapReader
from saw_map.assets.loader import AssetLoader
from saw_map.maps.model import ComponentType, CellComponent
from saw_map.geometry.transform import IsometricTransform

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
doc = MapReader.parse_map(map_path)
loader = AssetLoader(game_dir)
tileset = loader.load_tileset("Airfield")
palette = loader.load_palette("Win.pal")

print(f"Airfield map: {doc.width}x{doc.height}")
print(f"Tileset surfaces: {tileset.surfaces}")

# Let's count valid items with the proposed fixes:
iso = IsometricTransform(tile_width=128.0, tile_height=64.0, elevation_step=48.0)

render_items = []
for (x, y, z), cell in doc.cells.items():
    # Floor:
    w0 = cell.floor.raw_word
    if w0 not in (0x0000, 0xFF00):
        # Surface index is w0 & 0x7F
        s_idx = w0 & 0x7F
        if s_idx < len(tileset.surfaces):
            asset = tileset.surfaces[s_idx]
            render_items.append((z, x, y, ComponentType.FLOOR, asset, 0))

    # Clutter:
    w3 = cell.clutter.raw_word
    if (w3 >> 15) & 1:
        c_idx = (w3 >> 7) & 0x7F
        c_frame = w3 & 0x7F
        if c_idx < len(tileset.clutter):
            asset = tileset.clutter[c_idx]
            render_items.append((z, x, y, ComponentType.CLUTTER, asset, c_frame))

print(f"Total proposed render items: {len(render_items)}")
from collections import Counter
by_type = Counter(it[3].name for it in render_items)
print(f"Items by type: {by_type}")

# Check if sprites exist for all items
loaded = 0
missing = 0
for it in render_items:
    img = loader.get_sprite_image(it[4], it[5], palette)
    if img: loaded += 1
    else: missing += 1

print(f"Sprite loading: loaded={loaded}, missing={missing}")
