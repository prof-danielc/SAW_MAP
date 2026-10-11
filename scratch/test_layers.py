import sys
from pathlib import Path
import struct
import gzip
from collections import Counter

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
data = gzip.decompress(map_path.read_bytes())
tile_start = 187

for z in range(7):
    c0 = Counter()
    c1 = Counter()
    c2 = Counter()
    c3 = Counter()
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
            c0[w0] += 1
            c1[w1] += 1
            c2[w2] += 1
            c3[w3] += 1
    print(f"--- Layer Z={z} ---")
    print(f"  w0 top 3: {[(hex(k), v) for k, v in c0.most_common(3)]}")
    print(f"  w1 top 3: {[(hex(k), v) for k, v in c1.most_common(3)]}")
    print(f"  w2 top 3: {[(hex(k), v) for k, v in c2.most_common(3)]}")
    print(f"  w3 top 3: {[(hex(k), v) for k, v in c3.most_common(3)]}")
