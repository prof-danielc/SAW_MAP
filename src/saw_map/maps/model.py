"""Core domain models for Soldiers at War map documents, cells, and components.

Decoupled from all UI and rendering libraries (Arcade, Pygame).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple


class ComponentType(IntEnum):
    """Component categories corresponding to word positions in a 13-byte map cell."""
    FLOOR = 0
    LEFT_WALL = 1
    RIGHT_WALL = 2
    CLUTTER = 3


@dataclass(frozen=True, slots=True)
class CellComponent:
    """Represents one of the 4 structural components in a map cell."""
    component_type: ComponentType
    is_present: bool
    tileset_group_index: int
    sprite_frame_index: int
    raw_word: int

    @classmethod
    def from_raw_word(cls, comp_type: ComponentType, raw_word: int) -> CellComponent:
        """Unpacks 16-bit word into presence bit, tileset group index, and frame index.

        Bit 15: Presence (1 = present, 0 = absent)
        Bits 7-14: Tileset group index (0..255)
        Bits 0-6: Sprite frame index within target archive (0..127)
        """
        is_present = bool((raw_word >> 15) & 1)
        tileset_group_index = (raw_word >> 7) & 0xFF
        sprite_frame_index = raw_word & 0x7F
        return cls(
            component_type=comp_type,
            is_present=is_present,
            tileset_group_index=tileset_group_index,
            sprite_frame_index=sprite_frame_index,
            raw_word=raw_word,
        )


@dataclass(slots=True)
class MapCell:
    """Represents a discrete 3D cell at coordinate (x, y, z) in the map array."""
    x: int
    y: int
    z: int
    floor: CellComponent
    left_wall: CellComponent
    right_wall: CellComponent
    clutter: CellComponent
    elevation_attr: int = 0
    flags: int = 0

    def is_empty(self) -> bool:
        """Returns True if none of the 4 components are active/present."""
        return not (
            self.floor.is_present
            or self.left_wall.is_present
            or self.right_wall.is_present
            or self.clutter.is_present
        )

    def get_component(self, comp_type: ComponentType) -> CellComponent:
        """Retrieves component by type enum."""
        if comp_type == ComponentType.FLOOR:
            return self.floor
        elif comp_type == ComponentType.LEFT_WALL:
            return self.left_wall
        elif comp_type == ComponentType.RIGHT_WALL:
            return self.right_wall
        elif comp_type == ComponentType.CLUTTER:
            return self.clutter
        raise ValueError(f"Unknown ComponentType: {comp_type}")


@dataclass
class TilesetDefinition:
    """Parsed tileset definition from companion .set file."""
    name: str
    surfaces: List[str] = field(default_factory=list)
    left_walls: List[str] = field(default_factory=list)
    right_walls: List[str] = field(default_factory=list)
    clutter: List[str] = field(default_factory=list)

    def resolve_asset(self, comp_type: ComponentType, group_idx: int) -> Optional[str]:
        """Resolves target .obj archive name given component type and group index."""
        target_list: List[str]
        if comp_type == ComponentType.FLOOR:
            target_list = self.surfaces
        elif comp_type == ComponentType.LEFT_WALL:
            target_list = self.left_walls
        elif comp_type == ComponentType.RIGHT_WALL:
            target_list = self.right_walls
        elif comp_type == ComponentType.CLUTTER:
            target_list = self.clutter
        else:
            return None

        if 0 <= group_idx < len(target_list):
            return target_list[group_idx]
        return None


@dataclass
class MapDocument:
    """Fully loaded Soldiers at War map document."""
    title: str
    version: str
    width: int
    height: int
    layer_count: int = 7
    tileset_names: List[str] = field(default_factory=list)
    cells: Dict[Tuple[int, int, int], MapCell] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validates map constraints per specification."""
        if self.version not in ("20", "21"):
            raise ValueError(f"Unsupported map version: '{self.version}'. Expected '20' or '21'.")
        if not (20 <= self.width <= 130):
            raise ValueError(f"Map width {self.width} outside valid range [20, 130].")
        if not (20 <= self.height <= 100):
            raise ValueError(f"Map height {self.height} outside valid range [20, 100].")
        if self.layer_count != 7:
            raise ValueError(f"Map layer_count {self.layer_count} must equal 7.")

    def get_cell(self, x: int, y: int, z: int) -> Optional[MapCell]:
        """Retrieves cell at coordinate (x, y, z), or None if unpopulated or out of bounds."""
        return self.cells.get((x, y, z))
