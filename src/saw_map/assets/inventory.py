"""Recursive read-only file inventory and cataloger for Soldiers at War game assets.

Discovers, inventories, and categorizes maps, tilesets, sprite archives, palettes,
and mission metadata without modifying source files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from saw_map.diagnostics.logger import get_logger

logger = get_logger("assets.inventory")


@dataclass(slots=True)
class AssetFileInfo:
    """Metadata for an indexed asset file."""
    relative_path: str
    absolute_path: Path
    file_size: int
    extension: str
    category: str


@dataclass
class InventoryReport:
    """Statistical summary of cataloged assets."""
    root_path: Path
    total_files: int
    maps: List[AssetFileInfo] = field(default_factory=list)
    tilesets: List[AssetFileInfo] = field(default_factory=list)
    sprites: List[AssetFileInfo] = field(default_factory=list)
    palettes: List[AssetFileInfo] = field(default_factory=list)
    missions: List[AssetFileInfo] = field(default_factory=list)
    others: List[AssetFileInfo] = field(default_factory=list)


class AssetInventory:
    """Recursive cataloger and resolver for Soldiers at War directories."""

    EXTENSION_CATEGORIES = {
        ".map": "map",
        ".set": "tileset",
        ".obj": "sprite",
        ".spr": "sprite",
        ".pal": "palette",
        ".col": "palette",
        ".txt": "mission",
    }

    def __init__(self, root_dir: Optional[Union[str, Path]] = None) -> None:
        self.root_path = Path(root_dir).resolve() if root_dir else Path.cwd().resolve()
        self._catalog: Dict[str, AssetFileInfo] = {}
        self._by_stem: Dict[str, List[AssetFileInfo]] = {}

    def scan(self) -> InventoryReport:
        """Recursively scans the root directory and builds the catalog.

        Strictly read-only: does not create, touch, or modify any files.
        """
        if not self.root_path.is_dir():
            logger.warning(f"Scan target is not a valid directory: {self.root_path}")
            return InventoryReport(root_path=self.root_path, total_files=0)

        report = InventoryReport(root_path=self.root_path, total_files=0)
        self._catalog.clear()
        self._by_stem.clear()

        for current_root, _, filenames in os.walk(self.root_path):
            current_path = Path(current_root)
            for fname in filenames:
                file_abs = current_path / fname
                try:
                    rel_path = file_abs.relative_to(self.root_path).as_posix()
                    size = file_abs.stat().st_size
                except (OSError, ValueError):
                    continue

                ext = file_abs.suffix.lower()
                cat = self.EXTENSION_CATEGORIES.get(ext, "other")

                info = AssetFileInfo(
                    relative_path=rel_path,
                    absolute_path=file_abs,
                    file_size=size,
                    extension=ext,
                    category=cat,
                )

                self._catalog[rel_path.lower()] = info
                stem_key = file_abs.stem.lower()
                self._by_stem.setdefault(stem_key, []).append(info)

                report.total_files += 1
                if cat == "map":
                    report.maps.append(info)
                elif cat == "tileset":
                    report.tilesets.append(info)
                elif cat == "sprite":
                    report.sprites.append(info)
                elif cat == "palette":
                    report.palettes.append(info)
                elif cat == "mission":
                    report.missions.append(info)
                else:
                    report.others.append(info)

        logger.debug(
            f"Asset inventory complete: {report.total_files} files cataloged "
            f"({len(report.maps)} maps, {len(report.tilesets)} tilesets, "
            f"{len(report.sprites)} sprites, {len(report.palettes)} palettes)"
        )
        return report

    def find_file(self, name_or_stem: str, category: Optional[str] = None) -> Optional[Path]:
        """Resolves file path by name or stem across catalog."""
        key = name_or_stem.lower()

        # Direct path check
        if key in self._catalog:
            return self._catalog[key].absolute_path

        # Stem lookup
        candidates = self._by_stem.get(key, [])
        if category:
            candidates = [c for c in candidates if c.category == category]

        if candidates:
            return candidates[0].absolute_path
        return None
