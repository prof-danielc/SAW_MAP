import sys
from pathlib import Path
sys.path.insert(0, "src")

from saw_map.formats.map_reader import MapReader
from saw_map.assets.loader import AssetLoader
from saw_map.rendering.draw_order import DrawOrderStrategy

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
doc = MapReader.parse_map(map_path)
print(f"Map doc: {doc.title}, dims={doc.width}x{doc.height}, cells={len(doc.cells)}")

loader = AssetLoader(game_dir)
tileset = loader.load_tileset("Airfield")
print(f"Tileset: {tileset.name if tileset else None}")
if tileset:
    print(f"Surfaces: {len(tileset.surfaces)}, Left: {len(tileset.left_walls)}, Right: {len(tileset.right_walls)}, Clutter: {len(tileset.clutter)}")

items = DrawOrderStrategy.generate_render_list(doc, tileset=tileset, max_layer=6)
print(f"Total render items: {len(items)}")

palette = loader.load_palette("Win.pal")
missing_assets = 0
found_assets = 0
for it in items[:100]:
    img = loader.get_sprite_image(it.asset_name, it.sprite_frame_index, palette) if it.asset_name else None
    if img: found_assets += 1
    else: missing_assets += 1
print(f"First 100 items: found={found_assets}, missing={missing_assets}")
print(f"Sample items:")
for it in items[:25]:
    img = loader.get_sprite_image(it.asset_name, it.sprite_frame_index, palette) if it.asset_name else None
    print(f"  z={it.grid_z} (x={it.grid_x}, y={it.grid_y}) comp={it.component_type.name}, name={it.asset_name}, frame={it.sprite_frame_index}, group_idx={it.component.tileset_group_index}, img={'YES' if img else 'NO'}")
