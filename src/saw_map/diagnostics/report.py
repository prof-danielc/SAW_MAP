"""Asset inventory and discovery report generator.

Scans the game directory and generates a comprehensive markdown diagnostics
report detailing discovered maps, tilesets, sprite archives, and palettes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from saw_map.assets.inventory import AssetInventory, InventoryReport
from saw_map.formats.map_reader import MapReader
from saw_map.formats.set_parser import TilesetParser


def generate_discovery_report(
    game_dir: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """Scans game installation directory and produces a detailed markdown report.

    Args:
        game_dir: Root directory of game installation.
        output_path: Optional file destination to write the markdown report.

    Returns:
        Formatted markdown report string.
    """
    root = Path(game_dir).resolve()
    inventory = AssetInventory(root)
    rep: InventoryReport = inventory.scan()

    lines = [
        "# Soldiers at War Asset Discovery & Reverse-Engineering Report",
        "",
        f"**Game Directory**: `{root}`  ",
        f"**Total Cataloged Files**: {rep.total_files:,}  ",
        "",
        "## Summary by Asset Category",
        "",
        "| Category | Extension | Count |",
        "|---|---|---|",
        f"| Maps | `.map` | {len(rep.maps)} |",
        f"| Tilesets | `.set` | {len(rep.tilesets)} |",
        f"| Sprites / Objects | `.obj`, `.spr` | {len(rep.sprites)} |",
        f"| Palettes | `.pal`, `.col` | {len(rep.palettes)} |",
        f"| Missions / Text | `.txt` | {len(rep.missions)} |",
        f"| Other Files | various | {len(rep.others)} |",
        "",
        "## Discovered Maps",
        "",
        "| Map Filename | Relative Path | File Size | Version | Dimensions |",
        "|---|---|---|---|---|",
    ]

    for m in rep.maps[:20]:
        ver_str = "Unknown"
        dim_str = "Unknown"
        try:
            doc = MapReader.parse_map(m.absolute_path)
            ver_str = f"v{doc.version}"
            dim_str = f"{doc.width}x{doc.height}x{doc.layer_count}"
        except Exception:
            pass
        lines.append(f"| `{m.absolute_path.name}` | `{m.relative_path}` | {m.file_size:,} B | {ver_str} | {dim_str} |")

    if len(rep.maps) > 20:
        lines.append(f"| *... and {len(rep.maps) - 20} more maps* | | | | |")

    lines.extend([
        "",
        "## Discovered Tilesets",
        "",
        "| Set Name | Relative Path | Surfaces | Left Walls | Right Walls | Clutter |",
        "|---|---|---|---|---|---|",
    ])

    for ts_info in rep.tilesets[:20]:
        try:
            ts_def = TilesetParser.parse_file(ts_info.absolute_path)
            lines.append(
                f"| `{ts_def.name}` | `{ts_info.relative_path}` | "
                f"{len(ts_def.surfaces)} | {len(ts_def.left_walls)} | "
                f"{len(ts_def.right_walls)} | {len(ts_def.clutter)} |"
            )
        except Exception:
            lines.append(f"| `{ts_info.absolute_path.stem}` | `{ts_info.relative_path}` | - | - | - | - |")

    if len(rep.tilesets) > 20:
        lines.append(f"| *... and {len(rep.tilesets) - 20} more tilesets* | | | | | |")

    lines.extend([
        "",
        "## Color Palettes",
        "",
        "| Palette File | Relative Path | File Size | Format |",
        "|---|---|---|---|",
    ])

    for pal in rep.palettes:
        fmt = "Autodesk COL (776 B)" if pal.file_size == 776 else "Custom/Raw"
        lines.append(f"| `{pal.absolute_path.name}` | `{pal.relative_path}` | {pal.file_size} B | {fmt} |")

    report_content = "\n".join(lines) + "\n"

    if output_path:
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(report_content, encoding="utf-8")

    return report_content
