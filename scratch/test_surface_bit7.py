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

# Let's check how many cells have bit 7 of w0 set:
floors = []
for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
            # Check bit 7 of w0
            if (w0 >> 7) & 1:
                surface_idx = w0 & 0x7F
                floors.append((z, y, x, surface_idx, b4, dw5))

print(f"Total cells with bit 7 of w0 set: {len(floors)}")
surface_counts = Counter(f[3] for f in floors)
print(f"Surface indices distribution:")
for s_idx, count in sorted(surface_counts.items()):
    print(f"  surface_idx {s_idx:2d}: count={count:4d}")

# Which layers do these floors appear on?
layer_counts = Counter(f[0] for f in floors)
print(f"\nFloors by layer Z:")
for z, count in sorted(layer_counts.items()):
    print(f"  Layer Z={z}: {count} floors")
