import sys
from pathlib import Path
import struct
import gzip
from collections import Counter

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
data = gzip.decompress(map_path.read_bytes())
tile_start = 187

c = Counter()
for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0 = struct.unpack("<H", data[off:off+2])[0]
            if w0 != 0xFF00 and w0 != 0:
                c[w0] += 1

print(f"Non-empty w0 unique count: {len(c)}")
for w, count in c.most_common(20):
    b15 = (w >> 15) & 1
    high = (w >> 8) & 0xFF
    low = w & 0xFF
    b7_14 = (w >> 7) & 0xFF
    b0_6 = w & 0x7F
    print(f"  0x{w:04X} ({w:5d}): count={count:4d} | b15={b15} | high=0x{high:02X} low=0x{low:02X} | (>>7)={b7_14} (&0x7F)={b0_6}")
