import sys
from pathlib import Path
sys.path.insert(0, "src")

from saw_map.formats.map_reader import MapReader
from saw_map.assets.loader import AssetLoader

game_dir = Path("Research/SSI/Soldiers at War")
map_path = game_dir / "Single_g" / "Airfield.map"
doc = MapReader.parse_map(map_path)

present_floor = 0
present_left = 0
present_right = 0
present_clutter = 0

for (x, y, z), cell in doc.cells.items():
    if cell.floor.raw_word not in (0x0000, 0xFF00):
        present_floor += 1
    if cell.left_wall.raw_word != 0:
        present_left += 1
    if cell.right_wall.raw_word != 0:
        present_right += 1
    if cell.clutter.raw_word != 0:
        present_clutter += 1

print(f"Non-empty counts across all {len(doc.cells)} cells:")
print(f"  Floor (w0 not in 0, 0xFF00): {present_floor}")
print(f"  Left wall (w1 != 0):         {present_left}")
print(f"  Right wall (w2 != 0):        {present_right}")
print(f"  Clutter (w3 != 0):           {present_clutter}")
