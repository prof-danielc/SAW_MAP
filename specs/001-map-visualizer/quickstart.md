# Quickstart & Validation Guide: Soldiers at War Map Visualizer

**Feature**: `001-map-visualizer` | **Date**: 2026-10-11

This guide provides instructions for verifying, testing, and running the Soldiers at War Map Visualizer.

---

## 1. Prerequisites

- Python 3.12+ (verified active in workspace)
- Required Python dependencies:
  - `arcade >= 3.3.0`
  - `pillow >= 10.0.0`
  - `pytest >= 7.0.0`
  - *(Optional fallback)*: `pygame >= 2.6.0`

---

## 2. Test Execution Scenarios

### Scenario 1: Run the Automated Unit Test Suite
Verify that pure parsers, mathematical transformations, and asset loaders execute without launching a GUI:

```bash
pytest tests/unit -v
```

**Expected Outcome**:
- 100% of unit tests pass in under 5 seconds.
- All coordinate transforms (isometric forward and inverse) verify round-trip numerical accuracy.
- Bitmask decoders verify exact extraction for sample 16-bit word values.
- RLE decompressor successfully decodes synthetic test sprites.

### Scenario 2: Run Integration Tests Against Sample Game Data
Validate end-to-end decoding on actual research files:

```bash
pytest tests/integration -v
```

**Expected Outcome**:
- `Airfield.map` is decompressed and parsed with dimension verification (104x80).
- `Airfield.set` partitions 65 entries into the 4 component groups.
- `Win.pal` loads 256 RGB values.
- `sgrass.obj` decodes all sprite frames into valid Pillow RGBA images.

---

## 3. Running the Visualizer

### Scenario 3: Launch Map Visualizer with Auto-Detected Game Root
Run from the repository root:

```bash
python -m saw_map.main "Research/SSI/Soldiers at War/Single_g/Airfield.map" --game-dir "Research/SSI/Soldiers at War"
```

**Expected Outcome**:
- Application window opens displaying the isometric view of the Airfield map.
- Viewport renders ground tiles, trees, and buildings at 60 FPS.
- Status bar at bottom displays `X, Y, Z` coordinates as the mouse moves.

### Scenario 4: Viewport Navigation & Layer Filtering
With the visualizer open:
1. **Pan**: Click and drag with Left Mouse or use Arrow keys.
2. **Zoom**: Scroll mouse wheel to zoom in and out.
3. **Layer Step**: Press `PageDown` or `Q` to filter upper elevation layers; observe lower-level building interiors become visible.
4. **Perspective Toggle**: Press `Tab` or `T` to toggle between Isometric and Top-Down grid view.
5. **Minimap**: Press `M` to toggle the corner minimap overlay.
6. **Inspection Panel**: Press `I` to open the sidebar for deep cell diagnostic properties.
7. **Palette Switch**: Press `P` to cycle between standard daylight and dark/nighttime palettes.

### Scenario 5: Error Handling for Nonexistent File
Run with an invalid path:

```bash
python -m saw_map.main "nonexistent_map.map"
```

**Expected Outcome**:
- Process terminates in under 500ms with exit code `1`.
- Clean error message in console: `[ERROR] Map file not found: nonexistent_map.map`.
