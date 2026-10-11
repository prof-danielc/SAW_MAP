"""Core domain models for Soldiers at War map documents, cells, and components.

Decoupled from all UI and rendering libraries (Arcade, Pygame).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple


# AMB_MAP stream versions sharing the 193-byte header and 13-byte cell layout.
# Version 19 (Menu/Demo.MAP) only differs in the records following the tile array.
SUPPORTED_MAP_VERSIONS: Tuple[str, ...] = ("19", "20", "21")


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
        Bits 7-14: Sprite frame index within target archive (0..255)
        Bits 0-6: Object group index in the flat tileset registry (0..127)
        """
        is_present = bool((raw_word >> 15) & 1)
        tileset_group_index = raw_word & 0x7F
        sprite_frame_index = (raw_word >> 7) & 0xFF
        return cls(
            component_type=comp_type,
            is_present=is_present,
            tileset_group_index=tileset_group_index,
            sprite_frame_index=sprite_frame_index,
            raw_word=raw_word,
        )


# Engine built-in archives appended to the flat registry directly after the .set
# entries, in the load order of the tileset loader (SAW_TD sub_443D4A).
GLOBAL_CLUTTER: List[str] = ["Cgendam", "Can", "Token", "People", "Turret"]


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

    @property
    def roof_cutoff_layer(self) -> int:
        """Cover level of the floor component, encoded in flags bits 18..20.

        The engine draws word 0 only while this value is greater than the active
        view level; 7 means the floor is never hidden by a higher level.
        """
        return (self.flags >> 18) & 7

    def is_empty(self) -> bool:
        """Returns True if none of the 4 components is present."""
        return not (
            self.floor.is_present
            or self.left_wall.is_present
            or self.right_wall.is_present
            or self.clutter.is_present
        )

    def has_visual_content(self) -> bool:
        """Returns True if any component has a renderable sprite."""
        return not self.is_empty()

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

    def get_all_assets(self) -> List[str]:
        """Returns the flat registry of assets (.set entries in file order + GLOBAL_CLUTTER)."""
        return self.surfaces + self.left_walls + self.right_walls + self.clutter + GLOBAL_CLUTTER

    def get_component_type_for_group(self, group_idx: int) -> ComponentType:
        """Determines the component category from the flat registry group index."""
        num_surf = len(self.surfaces)
        num_lwall = len(self.left_walls)
        num_rwall = len(self.right_walls)
        if group_idx < num_surf:
            return ComponentType.FLOOR
        elif group_idx < num_surf + num_lwall:
            return ComponentType.LEFT_WALL
        elif group_idx < num_surf + num_lwall + num_rwall:
            return ComponentType.RIGHT_WALL
        else:
            return ComponentType.CLUTTER

    def resolve_flat_asset(self, group_idx: int) -> Optional[str]:
        """Resolves target .obj archive name by flat index in registry (0..N)."""
        all_assets = self.get_all_assets()
        if 0 <= group_idx < len(all_assets):
            return all_assets[group_idx]
        return None


@dataclass
class MapDocument:
    """Fully loaded Soldiers at War map document.

    `title` is the 128-byte header string, which the engine uses as the name of
    the companion tileset (Sets/<title>.set). `name` is the map file stem and
    `mission_text` the briefing text of the companion .txt file, when available.

    The stream always stores a 130x100x7 grid; the playable area is a
    `width` x `height` window starting at (`origin_x`, `origin_y`). Cell
    coordinates are absolute grid indices, as shown by the Scenario Builder.
    """
    title: str
    version: str
    width: int
    height: int
    layer_count: int = 7
    tileset_names: List[str] = field(default_factory=list)
    cells: Dict[Tuple[int, int, int], MapCell] = field(default_factory=dict)
    name: str = ""
    mission_text: str = ""
    origin_x: int = 0
    origin_y: int = 0

    def __post_init__(self) -> None:
        """Validates map constraints per specification."""
        if self.version not in SUPPORTED_MAP_VERSIONS:
            raise ValueError(f"Unsupported map version: '{self.version}'. Expected '19', '20' or '21'.")
        if not (20 <= self.width <= 130):
            raise ValueError(f"Map width {self.width} outside valid range [20, 130].")
        if not (20 <= self.height <= 100):
            raise ValueError(f"Map height {self.height} outside valid range [20, 100].")
        if self.layer_count != 7:
            raise ValueError(f"Map layer_count {self.layer_count} must equal 7.")
        if self.origin_x < 0 or self.origin_x + self.width > 130:
            raise ValueError(f"Map window x range [{self.origin_x}, {self.origin_x + self.width}) exceeds [0, 130).")
        if self.origin_y < 0 or self.origin_y + self.height > 100:
            raise ValueError(f"Map window y range [{self.origin_y}, {self.origin_y + self.height}) exceeds [0, 100).")

    def contains(self, x: int, y: int) -> bool:
        """Returns True if grid column x and row y lie inside the playable window."""
        return (
            self.origin_x <= x < self.origin_x + self.width
            and self.origin_y <= y < self.origin_y + self.height
        )

    @property
    def center(self) -> Tuple[float, float]:
        """Grid coordinates (x, y) of the middle of the playable window."""
        return (self.origin_x + self.width / 2.0, self.origin_y + self.height / 2.0)

    def get_cell(self, x: int, y: int, z: int) -> Optional[MapCell]:
        """Retrieves cell at coordinate (x, y, z), or None if unpopulated or out of bounds."""
        return self.cells.get((x, y, z))
