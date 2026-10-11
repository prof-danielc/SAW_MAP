"""Coordinate transformation utilities for dimetric isometric and orthogonal top-down projections.

Strictly independent of Arcade and Pygame.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Tuple


class IGeometryTransformer(ABC):
    """Abstract contract for world/screen coordinate transformations."""

    @abstractmethod
    def world_to_screen(self, grid_x: float, grid_y: float, grid_z: float = 0.0) -> Tuple[float, float]:
        """Converts logical 3D map grid coordinates to 2D screen coordinates."""
        ...

    @abstractmethod
    def screen_to_world(self, screen_x: float, screen_y: float, elevation_z: float = 0.0) -> Tuple[int, int]:
        """Converts 2D screen coordinates to discrete integer grid cell (x, y) at plane z."""
        ...


class IsometricTransform(IGeometryTransformer):
    """Dimetric 2:1 isometric coordinate transformation.

    Tile Dimensions:
        tile_width: Horizontal diamond span (default: 64 px)
        tile_height: Vertical diamond span (default: 32 px)
        elevation_step: Vertical displacement per elevation layer Z (default: 16 px)
    """

    def __init__(
        self,
        tile_width: float = 64.0,
        tile_height: float = 32.0,
        elevation_step: float = 16.0,
    ) -> None:
        if tile_width <= 0 or tile_height <= 0:
            raise ValueError("Tile dimensions must be positive.")
        self.tile_width = float(tile_width)
        self.tile_height = float(tile_height)
        self.elevation_step = float(elevation_step)

        self._half_w = self.tile_width / 2.0
        self._half_h = self.tile_height / 2.0

    def world_to_screen(self, grid_x: float, grid_y: float, grid_z: float = 0.0) -> Tuple[float, float]:
        """Converts logical 3D map coordinates to 2D screen coordinates.

        Formula:
            screen_x = (grid_x - grid_y) * (tile_width / 2)
            screen_y = (grid_x + grid_y) * (tile_height / 2) - grid_z * elevation_step
        """
        screen_x = (grid_x - grid_y) * self._half_w
        screen_y = (grid_x + grid_y) * self._half_h - (grid_z * self.elevation_step)
        return (screen_x, screen_y)

    def screen_to_world_float(
        self, screen_x: float, screen_y: float, elevation_z: float = 0.0
    ) -> Tuple[float, float]:
        """Converts 2D screen coordinates to continuous floating-point grid coordinates (x, y)."""
        adj_y = screen_y + (elevation_z * self.elevation_step)
        term_x = screen_x / self._half_w
        term_y = adj_y / self._half_h
        grid_x = (term_x + term_y) / 2.0
        grid_y = (term_y - term_x) / 2.0
        return (grid_x, grid_y)

    def screen_to_world(self, screen_x: float, screen_y: float, elevation_z: float = 0.0) -> Tuple[int, int]:
        """Converts 2D screen coordinates to discrete integer grid coordinates (floor)."""
        gx, gy = self.screen_to_world_float(screen_x, screen_y, elevation_z)
        return (int(math.floor(gx)), int(math.floor(gy)))


class TopDownTransform(IGeometryTransformer):
    """Orthogonal 2D top-down grid coordinate transformation."""

    def __init__(self, cell_size: float = 32.0) -> None:
        if cell_size <= 0:
            raise ValueError("cell_size must be positive.")
        self.cell_size = float(cell_size)

    def world_to_screen(self, grid_x: float, grid_y: float, grid_z: float = 0.0) -> Tuple[float, float]:
        """Orthogonal mapping: screen_x = grid_x * cell_size, screen_y = grid_y * cell_size."""
        return (grid_x * self.cell_size, grid_y * self.cell_size)

    def screen_to_world(self, screen_x: float, screen_y: float, elevation_z: float = 0.0) -> Tuple[int, int]:
        """Orthogonal inverse mapping."""
        return (int(math.floor(screen_x / self.cell_size)), int(math.floor(screen_y / self.cell_size)))
