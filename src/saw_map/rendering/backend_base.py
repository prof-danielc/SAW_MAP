"""Abstract rendering backend contract (IRenderer).

Decouples the map document, camera, and asset decoders from concrete graphics
libraries (Arcade, Pygame).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from saw_map.assets.loader import IAssetLoader
from saw_map.formats.palette_reader import Palette
from saw_map.maps.model import MapDocument, TilesetDefinition
from saw_map.viewer.camera import Camera


class IRenderer(ABC):
    """Abstract interface for graphical viewport rendering engines."""

    @abstractmethod
    def initialize(self, width: int, height: int, title: str) -> None:
        """Initializes the window display and graphics context."""
        ...

    @abstractmethod
    def set_map(
        self,
        map_doc: MapDocument,
        asset_loader: IAssetLoader,
        tileset: Optional[TilesetDefinition] = None,
        palette: Optional[Palette] = None,
    ) -> None:
        """Binds the map document and asset dependencies for rendering."""
        ...

    @abstractmethod
    def render_frame(self, camera: Camera) -> None:
        """Renders one frame consisting of visible layers, HUD, and overlays."""
        ...

    @abstractmethod
    def run_loop(self) -> None:
        """Starts the interactive application main loop."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Cleans up resources and closes the viewport window."""
        ...
