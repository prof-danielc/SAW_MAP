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
        Bits 7-14: Sprite frame index within target archive (0..255)
        Bits 0-6: Tileset group index / object index in flat registry (0..127)

        Values with frame index >= 200 (such as 0xFE00 / 0xFF93) represent height/roof
        attributes or empty masks rather than valid sprite frames.
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


GLOBAL_CLUTTER: List[str] = [
    "People", "Can", "Turret", "Token", "Specials", "Cgendam",
    "Newtree1", "Newtree2", "Newtree3", "Newtree4", "Newtree5", "Newtree6", "Newtree7",
]


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
    def has_clutter_object(self) -> bool:
        """True if cell flags indicate a placed visual clutter object (bit 31 set and group > 0)."""
        return bool(((self.flags >> 31) & 1) and (((self.flags >> 24) & 0x7F) > 0))

    @property
    def clutter_object_group(self) -> int:
        """Tileset group index of clutter object in flat registry (37..N)."""
        return (self.flags >> 24) & 0x7F

    @property
    def roof_cutoff_layer(self) -> int:
        """Elevation cutoff layer for roof/ceiling geometry encoded in flags bits 18..20."""
        return (self.flags >> 18) & 7

    @property
    def clutter_object_frame(self) -> int:
        """Sprite frame index of clutter object within its archive."""
        return self.floor.raw_word & 0x7F

    def is_empty(self) -> bool:
        """Returns True if none of the 4 components and no clutter object are active/present."""
        return not (
            self.floor.is_present
            or self.left_wall.is_present
            or self.right_wall.is_present
            or self.clutter.is_present
            or self.has_clutter_object
        )

    def has_visual_content(self) -> bool:
        """Returns True if any component has an active renderable sprite or clutter object."""
        return (
            (self.floor.is_present and (self.floor.sprite_frame_index < 200 or self.floor.tileset_group_index > 0))
            or (self.left_wall.is_present and (self.left_wall.sprite_frame_index < 200 or self.left_wall.tileset_group_index > 0))
            or (self.right_wall.is_present and (self.right_wall.sprite_frame_index < 200 or self.right_wall.tileset_group_index > 0))
            or (self.clutter.is_present and (self.clutter.sprite_frame_index < 200 or self.clutter.tileset_group_index > 0))
            or self.has_clutter_object
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

    def get_all_assets(self) -> List[str]:
        """Returns the flat registry of assets (surfaces + left_walls + right_walls + clutter + GLOBAL_CLUTTER)."""
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
            asset = all_assets[group_idx]
            # In winter maps where ssnow1 is present, default surface 0 (sgrass) renders as ssnow1
            if group_idx == 0 and asset == "sgrass" and "ssnow1" in self.surfaces:
                return "ssnow1"
            return asset
        return None

    def resolve_asset(self, comp_type: ComponentType, group_idx: int) -> Optional[str]:
        """Resolves target .obj archive name given component type and group index.

        Supports flat registry indexing as well as partitioned category indexing.
        """
        # Check partitioned resolution
        if comp_type == ComponentType.FLOOR:
            if 0 <= group_idx < len(self.surfaces):
                asset = self.surfaces[group_idx]
                if group_idx == 0 and asset == "sgrass" and "ssnow1" in self.surfaces:
                    return "ssnow1"
                return asset
            return None
        elif comp_type == ComponentType.LEFT_WALL:
            if 0 <= group_idx < len(self.left_walls):
                return self.left_walls[group_idx]
            num_surf = len(self.surfaces)
            rel_idx = group_idx - num_surf
            if 0 <= rel_idx < len(self.left_walls):
                return self.left_walls[rel_idx]
            return None
        elif comp_type == ComponentType.RIGHT_WALL:
            if 0 <= group_idx < len(self.right_walls):
                return self.right_walls[group_idx]
            num_surf = len(self.surfaces)
            num_lwall = len(self.left_walls)
            rel_idx = group_idx - num_surf - num_lwall
            if 0 <= rel_idx < len(self.right_walls):
                return self.right_walls[rel_idx]
            return None
        elif comp_type == ComponentType.CLUTTER:
            if 0 <= group_idx < len(self.clutter):
                return self.clutter[group_idx]
            global_offset = group_idx - len(self.clutter)
            if 0 <= global_offset < len(GLOBAL_CLUTTER):
                return GLOBAL_CLUTTER[global_offset]
            num_surf = len(self.surfaces)
            num_lwall = len(self.left_walls)
            num_rwall = len(self.right_walls)
            rel_idx = group_idx - num_surf - num_lwall - num_rwall
            if 0 <= rel_idx < len(self.clutter):
                return self.clutter[rel_idx]
            rel_global = rel_idx - len(self.clutter)
            if 0 <= rel_global < len(GLOBAL_CLUTTER):
                return GLOBAL_CLUTTER[rel_global]
            return None

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
