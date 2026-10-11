# Data Model: Soldiers at War Map Visualizer

**Feature**: `001-map-visualizer` | **Date**: 2026-10-11

This document defines the core domain models, data structures, and relationships for the Soldiers at War map visualizer. All models are decoupled from any specific GUI or rendering library.

---

## 1. Domain Entities & Relationships

```mermaid
classDiagram
    class MapDocument {
        +str title
        +int width
        +int height
        +int layer_count
        +str version
        +list[str] tileset_names
        +dict[tuple, MapCell] cells
        +get_cell(x, y, z) MapCell
    }

    class MapCell {
        +int x
        +int y
        +int z
        +CellComponent floor
        +CellComponent left_wall
        +CellComponent right_wall
        +CellComponent clutter
        +int elevation_attr
        +int flags
        +is_empty() bool
    }

    class CellComponent {
        +ComponentType component_type
        +bool is_present
        +int tileset_group_index
        +int sprite_frame_index
        +int raw_word
    }

    class TilesetDefinition {
        +str name
        +list[str] surfaces
        +list[str] left_walls
        +list[str] right_walls
        +list[str] clutter
        +resolve_asset(comp_type, group_idx) str
    }

    class SpriteArchive {
        +str name
        +int sprite_count
        +list[SpriteFrame] frames
        +get_frame(index) SpriteFrame
    }

    class SpriteFrame {
        +int frame_index
        +int width
        +int height
        +int offset_x
        +int offset_y
        +bytes raw_indexed_data
        +bytes alpha_mask
        +to_rgba(palette) PIL.Image
    }

    class Palette {
        +str name
        +list[tuple[int, int, int]] rgb_table
        +get_color(index) tuple[int, int, int]
    }

    class Camera {
        +float x
        +float y
        +float zoom
        +int active_max_layer
        +bool show_floors
        +bool show_left_walls
        +bool show_right_walls
        +bool show_clutter
        +ViewPerspective perspective
    }

    MapDocument "1" *-- "many" MapCell : contains
    MapCell "1" *-- "4" CellComponent : composes
    MapDocument "1" ..> "1..*" TilesetDefinition : references
    TilesetDefinition "1" ..> "many" SpriteArchive : maps to
    SpriteArchive "1" *-- "many" SpriteFrame : contains
    SpriteFrame ..> Palette : colored by
```

---

## 2. Entity Specifications

### 2.1 MapDocument
Represents the loaded game map file and its associated mission parameters.

| Field | Type | Description | Validation |
|---|---|---|---|
| `title` | `str` | Internal map name decoded from 128-byte header buffer | Non-empty string |
| `version` | `str` | Engine version string (`"20"` or `"21"`) | Must be `"20"` or `"21"` |
| `width` | `int` | Active horizontal dimension (columns) | $20 \le \text{width} \le 130$ |
| `height` | `int` | Active vertical dimension (rows) | $20 \le \text{height} \le 100$ |
| `layer_count` | `int` | Number of elevation levels (fixed at 7) | Must equal `7` |
| `tileset_names`| `list[str]`| Companion `.set` definitions referenced by the map | At least 1 entry |
| `cells` | `dict[tuple[int, int, int], MapCell]` | Sparse or dense lookup of cells indexed by `(x, y, z)` | Keyed by valid coordinates |

### 2.2 MapCell
Represents a discrete 3D spatial cell at coordinate $(X, Y, Z)$.

| Field | Type | Description | Validation |
|---|---|---|---|
| `x` | `int` | Grid column index | $0 \le x < \text{width}$ |
| `y` | `int` | Grid row index | $0 \le y < \text{height}$ |
| `z` | `int` | Vertical elevation layer index | $0 \le z < 7$ |
| `floor` | `CellComponent` | Floor / terrain surface component | Required |
| `left_wall` | `CellComponent` | Left-facing wall component | Required |
| `right_wall`| `CellComponent` | Right-facing wall component | Required |
| `clutter` | `CellComponent` | Clutter / structure / object component | Required |
| `elevation_attr`| `int` | Raw elevation attribute byte | $0 \le \text{val} \le 255$ |
| `flags` | `int` | 32-bit visibility and occlusion bitmask | Standard integer |

### 2.3 CellComponent
Represents an individual structural piece within a cell.

| Field | Type | Description |
|---|---|---|
| `component_type` | `ComponentType` | Enum: `FLOOR`, `LEFT_WALL`, `RIGHT_WALL`, `CLUTTER` |
| `is_present` | `bool` | True if bit 15 was set (`word >> 15 & 1`) |
| `tileset_group_index` | `int` | Group/category index in `.set` (`word >> 7 & 0xFF`) |
| `sprite_frame_index` | `int` | Frame index within the target sprite archive (`word & 0x7F`) |
| `raw_word` | `int` | Original 16-bit integer read from stream |

### 2.4 TilesetDefinition
Parsed from companion `.set` files.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Name of the set (e.g. `Airfield`) |
| `surfaces` | `list[str]` | List of `.obj` asset names for floors (`s*`) |
| `left_walls` | `list[str]` | List of `.obj` asset names for left walls (`l*`) |
| `right_walls`| `list[str]` | List of `.obj` asset names for right walls (`r*`) |
| `clutter` | `list[str]` | List of `.obj` asset names for clutter/objects (`c*`) |

### 2.5 Palette
Represents a 256-color indexed lookup table.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Identifier (e.g. `"Win.pal"`, `"Darkpal.col"`) |
| `rgb_table` | `list[tuple[int, int, int]]` | 256 RGB tuples, each element in range $0 \dots 255$ |

### 2.6 Camera & Viewport State
Manages viewing transformations and interactive filters.

| Field | Type | Default | Description |
|---|---|---|---|
| `x`, `y` | `float` | `(0.0, 0.0)` | World screen center offsets |
| `zoom` | `float` | `1.0` | Zoom factor ($0.25 \le \text{zoom} \le 4.0$) |
| `active_max_layer`| `int` | `6` | Maximum visible elevation ($0 \dots 6$) |
| `show_floors` | `bool` | `True` | Visibility toggle for floors |
| `show_left_walls` | `bool` | `True` | Visibility toggle for left walls |
| `show_right_walls`| `bool` | `True` | Visibility toggle for right walls |
| `show_clutter` | `bool` | `True` | Visibility toggle for objects/clutter |
| `perspective` | `ViewPerspective` | `ISOMETRIC` | `ISOMETRIC` or `TOP_DOWN` |
| `show_minimap` | `bool` | `True` | Minimap corner overlay toggle |
| `show_sidebar` | `bool` | `False` | Detailed inspection sidebar toggle |
