"""Central asset manager and caching provider for Soldiers at War visualizer.

Coordinates palette decoding, tileset definitions, sprite archive extraction,
and RGBA texture caching.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from PIL import Image, ImageDraw

from saw_map.assets.inventory import AssetInventory
from saw_map.diagnostics.logger import get_logger
from saw_map.formats.palette_reader import Palette, PaletteReader
from saw_map.formats.set_parser import TilesetParser
from saw_map.formats.sprite_reader import SpriteArchive, SpriteReader
from saw_map.maps.model import TilesetDefinition

logger = get_logger("assets.loader")


class IAssetLoader(ABC):
    """Internal contract for loading, decoding, and caching graphical assets."""

    @abstractmethod
    def set_game_root(self, root_path: Path) -> None:
        """Configures root path for resolving Sets/, Obj/, Misc/ directories."""
        ...

    @abstractmethod
    def load_palette(self, palette_path: Union[str, Path]) -> Palette:
        """Loads a 256-color palette from .pal or .col file."""
        ...

    @abstractmethod
    def load_tileset(self, set_name: str) -> TilesetDefinition:
        """Parses a companion .set file and maps component groups."""
        ...

    @abstractmethod
    def get_sprite_image(self, asset_name: str, frame_index: int, palette: Palette) -> Image.Image:
        """Retrieves or decodes a sprite frame as a true-color RGBA Pillow image."""
        ...

    @abstractmethod
    def get_sprite_image_and_offset(
        self, asset_name: str, frame_index: int, palette: Palette
    ) -> Tuple[Image.Image, int, int]:
        """Retrieves or decodes a sprite frame as RGBA Pillow image along with (offset_x, offset_y)."""
        ...


class AssetLoader(IAssetLoader):
    """Concrete implementation of IAssetLoader with two-tier in-memory caching."""

    def __init__(self, game_root: Optional[Union[str, Path]] = None) -> None:
        self.game_root = Path(game_root).resolve() if game_root else Path.cwd().resolve()
        self.inventory = AssetInventory(self.game_root)
        self.inventory.scan()

        self._palette_cache: Dict[str, Palette] = {}
        self._tileset_cache: Dict[str, TilesetDefinition] = {}
        self._archive_cache: Dict[str, Optional[SpriteArchive]] = {}
        self._rgba_cache: Dict[Tuple[str, int, str], Image.Image] = {}

    def set_game_root(self, root_path: Union[str, Path]) -> None:
        """Updates game root and rescans directory tree."""
        self.game_root = Path(root_path).resolve()
        self.inventory = AssetInventory(self.game_root)
        self.inventory.scan()
        self.clear_cache()

    def clear_cache(self) -> None:
        """Flushes all decoded image, archive, and tileset caches."""
        self._palette_cache.clear()
        self._tileset_cache.clear()
        self._archive_cache.clear()
        self._rgba_cache.clear()

    def load_palette(self, palette_path: Union[str, Path]) -> Palette:
        """Loads palette by direct path or locates by filename in inventory."""
        path = Path(palette_path)
        cache_key = path.name.lower()

        if cache_key in self._palette_cache:
            return self._palette_cache[cache_key]

        target_file: Optional[Path] = None
        if path.is_file():
            target_file = path
        else:
            # Check relative to game_root / Misc / Win.pal
            misc_candidate = self.game_root / "Misc" / path.name
            if misc_candidate.is_file():
                target_file = misc_candidate
            else:
                target_file = self.inventory.find_file(path.stem, category="palette")

        if not target_file or not target_file.is_file():
            logger.warning(f"Could not locate palette '{palette_path}'; creating fallback grayscale palette")
            fallback_colors = [(i, i, i) for i in range(256)]
            pal = Palette(name="fallback_gray.pal", rgb_table=fallback_colors)
            self._palette_cache[cache_key] = pal
            return pal

        pal = PaletteReader.read_palette(target_file)
        self._palette_cache[cache_key] = pal
        return pal

    def load_tileset(self, set_name: str) -> TilesetDefinition:
        """Loads and parses companion .set definition file."""
        clean_name = Path(set_name).stem
        cache_key = clean_name.lower()

        if cache_key in self._tileset_cache:
            return self._tileset_cache[cache_key]

        # Look in Sets/ directory first
        direct_path = self.game_root / "Sets" / f"{clean_name}.set"
        target_file: Optional[Path] = None

        if direct_path.is_file():
            target_file = direct_path
        else:
            target_file = self.inventory.find_file(clean_name, category="tileset")

        if not target_file or not target_file.is_file():
            logger.warning(f"Could not locate companion .set file for '{set_name}'")
            empty_def = TilesetDefinition(name=clean_name)
            self._tileset_cache[cache_key] = empty_def
            return empty_def

        tileset = TilesetParser.parse_file(target_file)
        self._tileset_cache[cache_key] = tileset
        return tileset

    def get_sprite_archive(self, asset_name: str) -> Optional[SpriteArchive]:
        """Loads or retrieves cached SpriteArchive by asset name."""
        clean_name = Path(asset_name).stem.lower()

        if clean_name in self._archive_cache:
            return self._archive_cache[clean_name]

        # Check in Obj/ directory
        direct_obj = self.game_root / "Obj" / f"{clean_name}.obj"
        direct_spr = self.game_root / "Obj" / f"{clean_name}.spr"
        target_path: Optional[Path] = None

        if direct_obj.is_file():
            target_path = direct_obj
        elif direct_spr.is_file():
            target_path = direct_spr
        else:
            target_path = self.inventory.find_file(clean_name, category="sprite")

        if not target_path or not target_path.is_file():
            self._archive_cache[clean_name] = None
            return None

        try:
            archive = SpriteReader.read_archive(target_path)
            self._archive_cache[clean_name] = archive
            return archive
        except Exception as exc:
            logger.warning(f"Failed to decode sprite archive '{target_path.name}': {exc}")
            self._archive_cache[clean_name] = None
            return None

    def get_sprite_image_and_offset(
        self, asset_name: str, frame_index: int, palette: Palette
    ) -> Tuple[Image.Image, int, int]:
        """Retrieves cached RGBA PIL image and (offset_x, offset_y) for sprite frame."""
        clean_name = Path(asset_name).stem.lower()
        cache_key = (clean_name, frame_index, palette.name)

        archive = self.get_sprite_archive(clean_name)
        if archive:
            frame = archive.get_frame(frame_index)
            if frame:
                if cache_key in self._rgba_cache:
                    img = self._rgba_cache[cache_key]
                else:
                    img = frame.to_rgba(palette)
                    self._rgba_cache[cache_key] = img
                return img, frame.offset_x, frame.offset_y

        # Fallback placeholder image
        if cache_key in self._rgba_cache:
            placeholder = self._rgba_cache[cache_key]
        else:
            placeholder = self._create_placeholder(clean_name, frame_index)
            self._rgba_cache[cache_key] = placeholder
        return placeholder, 209, 322

    def get_sprite_image(self, asset_name: str, frame_index: int, palette: Palette) -> Image.Image:
        """Retrieves cached RGBA PIL image for sprite frame or creates placeholder if missing."""
        img, _, _ = self.get_sprite_image_and_offset(asset_name, frame_index, palette)
        return img

    @staticmethod
    def _create_placeholder(label: str, frame_idx: int) -> Image.Image:
        """Generates distinctive diamond placeholder geometry for missing assets."""
        w, h = 64, 32
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw magenta diamond wireframe
        half_w, half_h = w // 2, h // 2
        diamond = [(half_w, 0), (w - 1, half_h), (half_w, h - 1), (0, half_h)]
        draw.polygon(diamond, outline=(255, 0, 255, 255), fill=(255, 0, 255, 60))
        return img
