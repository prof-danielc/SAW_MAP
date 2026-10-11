# CLI Interface Contract: Soldiers at War Map Visualizer

**Feature**: `001-map-visualizer` | **Date**: 2026-10-11

This document specifies the command-line interface, argument syntax, environment flags, exit codes, and output formats for the `saw_map` desktop application.

---

## 1. Invocation Syntax

```bash
python -m saw_map.main <MAP_FILE> [OPTIONS]
```
Or directly via the runner:
```bash
python run_viewer.py <MAP_FILE> [OPTIONS]
```

---

## 2. Arguments & Options

| Argument / Option | Type | Required | Default | Description |
|---|---|---|---|---|
| `MAP_FILE` | Positional | **Yes** | — | Path to the Soldiers at War `.map` file (e.g. `Airfield.map`) |
| `--game-dir`, `-g` | Option | No | Auto (cwd) | Root directory of the Soldiers at War game installation containing `Obj/`, `Sets/`, `Misc/` |
| `--palette`, `-p` | Option | No | Auto (`Win.pal`)| Explicit color palette file path (`.pal` or `.col`) |
| `--layer`, `-l` | Option | No | `6` | Initial maximum visible elevation layer ($0 \dots 6$) |
| `--view`, `-v` | Option | No | `isometric` | Initial view perspective: `isometric` or `top-down` |
| `--diagnostics`, `-d`| Flag | No | `False` | Enable verbose reverse-engineering inspection output in console |
| `--log-level` | Option | No | `INFO` | Console logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `--backend`, `-b` | Option | No | `arcade` | Rendering backend selection: `arcade` (default) or `pygame` |
| `--maximize` | Flag | No | `False` | Start the visualizer window maximized |
| `--help`, `-h` | Flag | No | — | Display help message and options usage |

---

## 3. Exit Codes

| Exit Code | Meaning | Behavior |
|---|---|---|
| `0` | Success | Map successfully loaded, visualizer ran and was closed cleanly by user |
| `1` | File Not Found | Specified `MAP_FILE` or required companion asset does not exist |
| `2` | Corrupted / Invalid File | File header mismatch, invalid decompression, or corrupted binary payload |
| `3` | Missing Assets Directory | Game assets not found in current directory and `--game-dir` not supplied |
| `4` | Renderer Initialization Error | OpenGL or window creation failure on host system |

---

## 4. Console Diagnostic Output Example

When launching with `--diagnostics`:

```text
[INFO] Loading Soldiers at War Map: Research/SSI/Soldiers at War/Single_g/Airfield.map
[DEBUG] Detected Gzip compression header (magic 1F 8B 08)
[DEBUG] Decompressed map stream: 1,214,559 bytes
[DEBUG] Map header verified: version=21, title='Airfield'
[INFO] Loaded map 'Airfield' (tileset 'Airfield'): active window 104x80 at (13, 10) (max 130x100x7)
[INFO] Resolving companion set: Sets/Airfield.set
[DEBUG] Parsed set 'Airfield': 13 surfaces, 12 left walls, 12 right walls, 28 clutter
[INFO] Loading palette: Misc/Win.pal (256 RGB colors)
[INFO] Loaded 65 sprite archives from Obj/
[INFO] Launching Arcade 3.3.1 hardware-accelerated viewport at 60 FPS
```
