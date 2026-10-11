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

print(f"Airfield.set partition counts:")
print(f"  Surfaces ({len(tileset.surfaces)}): {tileset.surfaces}")
print(f"  Left walls ({len(tileset.left_walls)}): {tileset.left_walls}")
print(f"  Right walls ({len(tileset.right_walls)}): {tileset.right_walls}")
print(f"  Clutter ({len(tileset.clutter)}): {tileset.clutter[:10]}...")

# For each of the 4 words (w0, w1, w2, w3):
# Let's check which tileset category its group index (w >> 7) & 0x7F fits!
for w_idx, w_name in enumerate(["w0", "w1", "w2", "w3"]):
    c_grp = Counter()
    for z in range(7):
        for y in range(80):
            for x in range(104):
                idx = (z * 100 * 130) + (y * 130) + x
                off = tile_start + idx * 13 + w_idx * 2
                w = struct.unpack("<H", data[off:off+2])[0]
                if (w >> 15) & 1:
                    grp = (w >> 7) & 0x7F
                    frm = w & 0x7F
                    c_grp[grp] += 1
    print(f"\n{w_name} when bit 15 == 1 (total={sum(c_grp.values())}):")
    print(f"  Max group index: {max(c_grp.keys()) if c_grp else 'none'}")
    print(f"  Groups in 0..12 (surfaces range): {sum(v for k,v in c_grp.items() if k < 13)}")
    print(f"  Groups in 0..11 (walls range):    {sum(v for k,v in c_grp.items() if k < 12)}")
    print(f"  Groups in 0..27 (clutter range):  {sum(v for k,v in c_grp.items() if k < 28)}")
    print(f"  Groups >= 28:                     {sum(v for k,v in c_grp.items() if k >= 28)}")
    print(f"  Top 10 groups: {c_grp.most_common(10)}")
