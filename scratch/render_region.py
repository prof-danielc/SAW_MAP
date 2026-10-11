"""Render the airplane region of Airfield.map with a chosen object-decoding hypothesis.

Usage: python scratch/render_region.py <hyp> <out.png>
  hyp = obj      -> flags-object cells with bit31 only, frame = w0 & 0x7F
  hyp = all      -> every cell with flags group > 0, frame = w0 & 0x7F
"""
import sys
sys.path.insert(0, "src")
from PIL import Image
from saw_map.formats.map_reader import MapReader
from saw_map.assets.loader import AssetLoader

hyp = sys.argv[1]
out = sys.argv[2]
game = "Research/SSI/Soldiers at War"
L = AssetLoader(game)
ts = L.load_tileset("Airfield")
pal = L.load_palette("Win.pal")
doc = MapReader.parse_map(game + "/Single_g/Airfield.map")
A = ts.get_all_assets()

X0, X1, Y0, Y1 = 36, 62, 34, 60
items = []
for z in range(7):
    for y in range(Y0, Y1):
        for x in range(X0, X1):
            c = doc.cells.get((x, y, z))
            if c is None:
                continue
            w3 = c.clutter
            if w3.is_present and w3.sprite_frame_index < 200 and w3.tileset_group_index < len(A):
                items.append((z, x + y, 0, y, x, A[w3.tileset_group_index], w3.sprite_frame_index))
            grp = (c.flags >> 24) & 0x7F
            bit31 = (c.flags >> 31) & 1
            if grp and grp < len(A) and (bit31 or hyp == "all"):
                items.append((z, x + y, 1, y, x, A[grp], c.floor.raw_word & 0x7F))
items.sort()

W, H = 2600, 1700
img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
cx, cy = 45, 42
for z, _, _, y, x, asset, frame in items:
    data = L.get_sprite_image_and_offset(asset, frame, pal)
    if not data:
        continue
    spr, ox, oy = data
    sx = 64 * (x - y) - 64 * (cx - cy)
    sy = 32 * (x + y) - 48 * z - 32 * (cx + cy)
    px = int(W / 2 + sx - 64 + (ox - 209))
    py = int(H / 3 + sy + (oy - 322))
    img.alpha_composite(spr, (px, py))
# mark cursor cell (45,42,0)
from PIL import ImageDraw
d = ImageDraw.Draw(img)
bx, by = W / 2, H / 3
d.polygon([(bx, by), (bx + 64, by + 32), (bx, by + 64), (bx - 64, by + 32)], outline=(0, 255, 255))
img = img.resize((W // 2, H // 2), Image.Resampling.LANCZOS)
img.crop((W // 4 - 320, H // 6 - 140, W // 4 + 320, H // 6 + 230)).save(out)
print("saved", out)
