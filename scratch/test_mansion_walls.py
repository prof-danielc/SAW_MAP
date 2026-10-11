import sys
from pathlib import Path
sys.path.insert(0, "src")
import struct
import gzip
from collections import Counter

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Mansion.map"
data = gzip.decompress(map_path.read_bytes())
tile_start = 187

w1_present = 0
w2_present = 0
w1_grps = Counter()
w2_grps = Counter()

for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
            if (w1 >> 15) & 1:
                w1_present += 1
                w1_grps[w1 & 0x7F] += 1
            if (w2 >> 15) & 1:
                w2_present += 1
                w2_grps[w2 & 0x7F] += 1

print(f"Mansion.map:")
print(f"  w1 present (bit 15 == 1): {w1_present}, grps: {w1_grps.most_common(5)}")
print(f"  w2 present (bit 15 == 1): {w2_present}, grps: {w2_grps.most_common(5)}")
