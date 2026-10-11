import sys
from pathlib import Path
import struct
import gzip
from collections import Counter

game_dir = Path("Research/SSI/Soldiers at War")
tile_start = 187

for map_file in ["Airfield.map", "Cassino.map", "Normandy.map", "Mansion.map"]:
    p = game_dir / "Single_g" / map_file
    data = gzip.decompress(p.read_bytes())
    w0_c = Counter()
    for z in range(7):
        for y in range(80):
            for x in range(104):
                idx = (z * 100 * 130) + (y * 130) + x
                off = tile_start + idx * 13
                w0 = struct.unpack("<H", data[off:off+2])[0]
                w0_c[w0] += 1
    print(f"\n{map_file} w0 top 5:")
    for k, v in w0_c.most_common(5):
        print(f"  0x{k:04X} ({k:5d}): count={v}")
