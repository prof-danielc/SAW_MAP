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

c_other = Counter()
for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0 = struct.unpack("<H", data[off:off+2])[0]
            if w0 not in (0x0000, 0xFF00) and (w0 & 0x7F) >= 13:
                c_other[w0] += 1

print(f"When w0 not in (0, 0xFF00) and (w0 & 0x7F) >= 13 (count={sum(c_other.values())}):")
for w, cnt in c_other.most_common(15):
    print(f"  0x{w:04X}: count={cnt:4d} | low8=0x{w&0xFF:02X}({w&0xFF:3d}) | (&0x7F)={w&0x7F:2d}")
