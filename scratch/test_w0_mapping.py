import sys
from pathlib import Path
import struct
import gzip
from collections import Counter

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
data = gzip.decompress(map_path.read_bytes())
tile_start = 187

# In Airfield.set:
# 13 surfaces:
# 0: sgrass, 1: shill, 2: ssnow1, 3: sdirt, 4: sstone1, 5: sstone3, 6: swood1, 7: swood2, 8: smetal1, 9: strack2, 10..12: sgen

# Let's inspect all non-0xFF00, non-0 values of w0:
vals = Counter()
for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
            if w0 != 0 and w0 != 0xFF00:
                vals[w0] += 1

print(f"Total non-empty w0: {sum(vals.values())}")
print("Sample w0 values:")
for w, c in vals.most_common(15):
    # What if high byte is flags / elevation / presence, and low byte is index?
    # Or what if w0 is an offset / index?
    print(f"  0x{w:04X}: count={c}, high=0x{w>>8:02X}, low=0x{w&0xFF:02X}")
