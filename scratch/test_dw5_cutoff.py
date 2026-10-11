import sys
from pathlib import Path
import struct
import gzip
from collections import Counter

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
data = gzip.decompress(map_path.read_bytes())
tile_start = 187

c_dw5_cutoff = Counter()
c_b4 = Counter()

for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
            if w0 == 0xFF00:
                cutoff = (dw5 >> 18) & 7
                c_dw5_cutoff[cutoff] += 1
                c_b4[b4] += 1

print(f"When w0 == 0xFF00:")
print(f"  dw5 bits 18..20 (cutoff): {c_dw5_cutoff}")
print(f"  byte 4: {c_b4.most_common(5)}")

# What about when w0 != 0xFF00 and w0 != 0?
c_dw5_valid = Counter()
c_b4_valid = Counter()
for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
            if w0 != 0xFF00 and w0 != 0:
                cutoff = (dw5 >> 18) & 7
                c_dw5_cutoff_val = cutoff
                c_dw5_valid[cutoff] += 1
                c_b4_valid[b4] += 1

print(f"\nWhen w0 != 0xFF00 and w0 != 0:")
print(f"  dw5 bits 18..20 (cutoff): {c_dw5_valid}")
print(f"  byte 4: {c_b4_valid.most_common(5)}")
