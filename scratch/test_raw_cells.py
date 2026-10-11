import sys
from pathlib import Path
sys.path.insert(0, "src")
import struct
import gzip

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
data = gzip.decompress(map_path.read_bytes())

tile_start = 187
# Let's inspect cell at z=0, y=0, x=1
# idx = (z * 100 * 130) + (y * 130) + x
idx = (0 * 100 * 130) + (0 * 130) + 1
off = tile_start + idx * 13
chunk = data[off : off + 13]
w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", chunk)
print(f"Cell (1, 0, 0):")
print(f"  w0: 0x{w0:04X} ({w0})")
print(f"  w1: 0x{w1:04X} ({w1})")
print(f"  w2: 0x{w2:04X} ({w2})")
print(f"  w3: 0x{w3:04X} ({w3})")
print(f"  b4: {b4}, dw5: 0x{dw5:08X}")

# Let's check bit 15, bits 7-14, bits 0-6 of w0
bit15 = (w0 >> 15) & 1
bits7_14 = (w0 >> 7) & 0xFF
bits0_6 = w0 & 0x7F
print(f"  w0: bit15={bit15}, bits7_14={bits7_14}, bits0_6={bits0_6}")

# Let's check more cells
unique_w0 = set()
for z in range(7):
    for y in range(80):
        for x in range(104):
            idx = (z * 100 * 130) + (y * 130) + x
            off = tile_start + idx * 13
            w0, w1, w2, w3, b4, dw5 = struct.unpack("<HHHHBI", data[off:off+13])
            unique_w0.add(w0)

print(f"Total unique w0 values in active grid: {len(unique_w0)}")
sample_w0 = sorted(list(unique_w0))
print(f"First 20 unique w0: {[hex(x) for x in sample_w0[:20]]}")
print(f"Last 20 unique w0: {[hex(x) for x in sample_w0[-20:]]}")
