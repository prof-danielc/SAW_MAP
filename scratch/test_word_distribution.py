import sys
from pathlib import Path
sys.path.insert(0, "src")
import struct
import gzip
from collections import Counter

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
data = gzip.decompress(map_path.read_bytes())

tile_start = 187
w0_counter = Counter()
w1_counter = Counter()
w2_counter = Counter()
w3_counter = Counter()

# Let's count for z=0
for y in range(80):
    for x in range(104):
        idx = (0 * 100 * 130) + (y * 130) + x
        off = tile_start + idx * 13
        w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
        w0_counter[w0] += 1
        w1_counter[w1] += 1
        w2_counter[w2] += 1
        w3_counter[w3] += 1

print(f"Top 10 w0 values on layer 0:")
for val, count in w0_counter.most_common(10):
    bit15 = (val >> 15) & 1
    grp = (val >> 7) & 0xFF
    frame = val & 0x7F
    print(f"  0x{val:04X} ({val}): count={count}, bit15={bit15}, grp={grp}, frame={frame}")

print(f"\nTop 10 w1 values on layer 0:")
for val, count in w1_counter.most_common(5):
    print(f"  0x{val:04X} ({val}): count={count}, bit15={(val >> 15) & 1}, grp={(val >> 7) & 0xFF}, frame={val & 0x7F}")

print(f"\nTop 10 w2 values on layer 0:")
for val, count in w2_counter.most_common(5):
    print(f"  0x{val:04X} ({val}): count={count}, bit15={(val >> 15) & 1}, grp={(val >> 7) & 0xFF}, frame={val & 0x7F}")

print(f"\nTop 10 w3 values on layer 0:")
for val, count in w3_counter.most_common(5):
    print(f"  0x{val:04X} ({val}): count={count}, bit15={(val >> 15) & 1}, grp={(val >> 7) & 0xFF}, frame={val & 0x7F}")

# Let's check other layers (z=1..6)
print(f"\nLayers z=1..6 non-zero counts:")
for z in range(1, 7):
    non_zeros = 0
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
            if (w0 >> 15) & 1 or (w1 >> 15) & 1 or (w2 >> 15) & 1 or (w3 >> 15) & 1:
                non_zeros += 1
    print(f"  Layer z={z}: {non_zeros} active cells (out of {80*104})")
