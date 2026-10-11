import sys
from pathlib import Path
sys.path.insert(0, "src")
import struct
import gzip
from collections import Counter
from saw_map.assets.loader import AssetLoader

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
data = gzip.decompress(map_path.read_bytes())
loader = AssetLoader(game_dir)
tileset = loader.load_tileset("Airfield")
tile_start = 187

print(f"Airfield surfaces ({len(tileset.surfaces)}): {tileset.surfaces}")

# Let's check non-empty w0
# What if w0 is:
# Case 1: (w >> 7) & 0x7F is group, w & 0x7F is frame?
case1_valid = 0
case1_invalid = 0

# Case 2: w & 0x7F is group, (w >> 7) & 0x7F is frame?
case2_valid = 0
case2_invalid = 0

for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0 = struct.unpack("<H", data[off:off+2])[0]
            if w0 not in (0x0000, 0xFF00):
                # Case 1:
                grp1 = (w0 >> 7) & 0x7F
                frm1 = w0 & 0x7F
                if grp1 < len(tileset.surfaces):
                    case1_valid += 1
                else:
                    case1_invalid += 1

                # Case 2:
                grp2 = w0 & 0x7F
                frm2 = (w0 >> 7) & 0x7F
                if grp2 < len(tileset.surfaces):
                    case2_valid += 1
                else:
                    case2_invalid += 1

print(f"Total non-empty w0: {case1_valid + case1_invalid}")
print(f"Case 1 (grp = (w>>7)&0x7F): valid={case1_valid}, invalid={case1_invalid}")
print(f"Case 2 (grp = w & 0x7F):    valid={case2_valid}, invalid={case2_invalid}")
