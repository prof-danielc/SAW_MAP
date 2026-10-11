import sys
from pathlib import Path
sys.path.insert(0, "src")

from PIL import Image
from saw_map.formats.map_reader import MapReader
from saw_map.assets.loader import AssetLoader
from saw_map.maps.model import ComponentType

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
doc = MapReader.parse_map(map_path)
loader = AssetLoader(game_dir)
tileset = loader.load_tileset("Airfield")
palette = loader.load_palette("Win.pal")

# Create a test render of a 800x600 region around center
out_img = Image.new("RGBA", (1200, 800), (20, 25, 30, 255))

# Half dimensions
hw = 64.0
hh = 32.0
estep = 48.0

# Collect render items
items = []
for (x, y, z), cell in doc.cells.items():
    if z > 2:  # layers 0..2 for clean overview
        continue

    # Floor:
    w0 = cell.floor.raw_word
    if w0 not in (0x0000, 0xFF00):
        s_idx = w0 & 0x7F
        if s_idx < len(tileset.surfaces):
            items.append((z, x + y, 0, y, x, y, z, tileset.surfaces[s_idx], 0))

    # Clutter:
    w3 = cell.clutter.raw_word
    if (w3 >> 15) & 1:
        c_idx = (w3 >> 7) & 0x7F
        c_frame = w3 & 0x7F
        if c_idx < len(tileset.clutter):
            items.append((z, x + y, 3, y, x, y, z, tileset.clutter[c_idx], c_frame))

# Sort back-to-front: (z, x+y, type_priority, y)
items.sort(key=lambda it: (it[0], it[1], it[2], it[3]))

# Viewport center at grid (50, 40)
cam_gx, cam_gy = 50, 40
cam_sx = hw * (cam_gx - cam_gy)
cam_sy = hh * (cam_gx + cam_gy)

view_cx = 600
view_cy = 400

drawn_count = 0
for it in items:
    z, _, _, _, gx, gy, gz, asset_name, frame_idx = it
    arch = loader.get_sprite_archive(asset_name)
    if not arch:
        continue
    frame = arch.get_frame(frame_idx)
    if not frame:
        continue

    img = loader.get_sprite_image(asset_name, frame_idx, palette)
    if not img:
        continue

    # Screen coord
    sx = hw * (gx - gy)
    sy = hh * (gx + gy) - (gz * estep)

    # Relative offset from reference (209, 322)
    rel_ox = frame.offset_x - 209
    rel_oy = frame.offset_y - 322

    px = int(view_cx + (sx - cam_sx) + rel_ox)
    py = int(view_cy + (sy - cam_sy) + rel_oy)

    if -150 <= px < 1300 and -150 <= py < 900:
        out_img.alpha_composite(img, (px, py))
        drawn_count += 1

out_path = Path("scratch/test_airfield_view.png")
out_img.save(out_path)
print(f"Saved test render with {drawn_count} items to {out_path}!")
print(f"Image size: {out_img.size}")
