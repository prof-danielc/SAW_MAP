# Internal API Contracts: Soldiers at War Map Visualizer

**Feature**: `001-map-visualizer` | **Date**: 2026-10-11

This document specifies the abstract interfaces decoupling the data model, parsers, geometry math, and rendering backends.

---

## 1. Map Parser Contract (`IMapParser`)

```python
from abc import ABC, abstractmethod
from pathlib import Path
from saw_map.maps.model import MapDocument

class IMapParser(ABC):
    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Inspects file signature and returns True if format is supported."""
        ...

    @abstractmethod
    def parse_map(self, file_path: Path) -> MapDocument:
        """Parses a map file and returns a complete, populated MapDocument."""
        ...
```

---

## 2. Asset Loader Contract (`IAssetLoader`)

```python
from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image
from saw_map.formats.palette import Palette
from saw_map.formats.tileset import TilesetDefinition

class IAssetLoader(ABC):
    @abstractmethod
    def set_game_root(self, root_path: Path) -> None:
        """Configures root path for resolving Sets/, Obj/, Misc/ directories."""
        ...

    @abstractmethod
    def load_palette(self, palette_path: Path) -> Palette:
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
```

---

## 3. Geometry Transformer Contract (`IGeometryTransformer`)

```python
from abc import ABC, abstractmethod
from typing import Tuple

class IGeometryTransformer(ABC):
    @abstractmethod
    def world_to_screen(self, grid_x: float, grid_y: float, grid_z: float) -> Tuple[float, float]:
        """Converts logical 3D map grid coordinates to 2D screen pixel coordinates."""
        ...

    @abstractmethod
    def screen_to_world(self, screen_x: float, screen_y: float, elevation_z: float) -> Tuple[int, int]:
        """Converts screen pixel coordinates into integer grid cell (X, Y) at plane Z."""
        ...
```

---

## 4. Renderer Backend Contract (`IRenderer`)

```python
from abc import ABC, abstractmethod
from saw_map.maps.model import MapDocument
from saw_map.viewer.camera import Camera

class IRenderer(ABC):
    @abstractmethod
    def initialize(self, width: int, height: int, title: str) -> None:
        """Initializes window and rendering context."""
        ...

    @abstractmethod
    def set_map(self, map_doc: MapDocument) -> None:
        """Binds the map document and builds cached render items."""
        ...

    @abstractmethod
    def render_frame(self, camera: Camera) -> None:
        """Draws visible layers, minimap overlay, and HUD status bar."""
        ...

    @abstractmethod
    def run_loop(self) -> None:
        """Starts main application event loop."""
        ...
```

---

## 5. Viewport Keyboard & Mouse Interaction Contract

| Input Action | Primary Key / Event | Function |
|---|---|---|
| **Pan** | Left Mouse Drag, Arrow Keys, WASD | Moves camera center across map board |
| **Zoom In** | Mouse Wheel Up, `+` / `=` | Increases zoom scale ($1.25\times$ per step) |
| **Zoom Out** | Mouse Wheel Down, `-` | Decreases zoom scale ($0.8\times$ per step) |
| **Reset View** | `Home` or `R` | Centers camera on map origin at $1.0\times$ zoom |
| **Elevation Up** | `PageUp` or `E` | Increments `active_max_layer` ($0 \dots 6$) |
| **Elevation Down**| `PageDown` or `Q` | Decrements `active_max_layer` ($0 \dots 6$) |
| **Toggle Perspective**| `Tab` or `T` | Switches between Isometric and 2D Top-Down grid |
| **Toggle Minimap** | `M` | Toggles 2D minimap corner overview |
| **Toggle Sidebar** | `I` | Toggles detailed cell inspection panel |
| **Toggle Floors** | `1` | Toggles ground surface visibility |
| **Toggle Left Walls** | `2` | Toggles left-facing wall visibility |
| **Toggle Right Walls** | `3` | Toggles right-facing wall visibility |
| **Toggle Clutter**| `4` | Toggles objects / clutter visibility |
| **Cycle Palette** | `P` | Switches between loaded daylight and ambient palettes |
| **Exit** | `Escape` | Closes application cleanly |
