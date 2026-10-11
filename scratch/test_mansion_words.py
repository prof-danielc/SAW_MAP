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

c1 = Counter()
c2 = Counter()
c3 = Counter()

for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
            if w1 != 0: c1[w1] += 1
            if w2 != 0: c2[w2] += 1
            if w3 != 0: c3[w3] += 1

print("Mansion.map:")
print(f"  w1 top 5 non-zeros: {[(hex(k), v) for k, v in c1.most_common(5)]}")
print(f"  w2 top 5 non-zeros: {[(hex(k), v) for k, v in c2.most_common(5)]}")
print(f"  w3 top 5 non-zeros: {[(hex(k), v) for k, v in c3.most_common(5)]}")
