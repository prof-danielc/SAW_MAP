import sys
from pathlib import Path
import struct
import gzip
from collections import Counter

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
data = gzip.decompress(map_path.read_bytes())
tile_start = 187

c_valid = Counter()
c_invalid = Counter()

for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
            bit15 = (w0 >> 15) & 1
            grp = (w0 >> 7) & 0xFF
            frame = w0 & 0x7F
            if bit15:
                if grp < 13:
                    c_valid[(grp, frame)] += 1
                else:
                    c_invalid[grp] += 1

print(f"Valid floor (grp < 13): {sum(c_valid.values())} cells")
print(f"Top 10 valid floor (grp, frame): {c_valid.most_common(10)}")
print(f"Invalid floor (grp >= 13): {sum(c_invalid.values())} cells")
print(f"Invalid floor groups: {c_invalid.most_common(10)}")
