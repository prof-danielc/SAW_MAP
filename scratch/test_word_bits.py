import sys
from pathlib import Path
import struct
import gzip
from collections import Counter

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
data = gzip.decompress(map_path.read_bytes())
tile_start = 187

print("Examining words in Airfield.map:")
for name, word_idx in [("w0 (floor)", 0), ("w1 (left wall)", 2), ("w2 (right wall)", 4), ("w3 (clutter)", 6)]:
    vals = Counter()
    for z in range(7):
        for y in range(80):
            for x in range(104):
                idx = (z * 100 * 130) + (y * 130) + x
                off = tile_start + idx * 13 + word_idx
                w = struct.unpack("<H", data[off:off+2])[0]
                if w != 0:
                    vals[w] += 1
    print(f"\n{name}: {len(vals)} unique non-zero values, total non-zeros = {sum(vals.values())}")
    print(f"Top 10 most common non-zero values:")
    for w, count in vals.most_common(10):
        # Examine different bit slicing:
        b15 = (w >> 15) & 1
        b_high = (w >> 8) & 0xFF
        b_low = w & 0xFF
        b7_14 = (w >> 7) & 0xFF
        b0_6 = w & 0x7F
        print(f"  0x{w:04X} ({w:5d}): count={count:5d} | b15={b15} | high8=0x{b_high:02X}({b_high:3d}) low8=0x{b_low:02X}({b_low:3d}) | (>>7)=0x{b7_14:02X}({b7_14:3d}) (&0x7F)={b0_6:2d}")
