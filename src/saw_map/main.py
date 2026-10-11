"""CLI entry point for Soldiers at War original map visualizer.

Parses command line arguments, configures logging, initializes the asset
loader and rendering backends, and handles error exit codes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from saw_map.assets.loader import AssetLoader
from saw_map.diagnostics.logger import configure_logging, get_logger
from saw_map.formats.map_reader import MapReader
from saw_map.rendering.arcade_backend import ArcadeRenderer
from saw_map.rendering.backend_base import IRenderer
from saw_map.rendering.pygame_backend import PygameRenderer
from saw_map.viewer.camera import ViewPerspective

logger = get_logger("main")


def build_arg_parser() -> argparse.ArgumentParser:
    """Constructs command-line argument parser matching cli-contract.md."""
    parser = argparse.ArgumentParser(
        prog="saw_map",
        description="Inspect and visualize Soldiers at War original maps and graphical assets.",
    )
    parser.add_argument(
        "map_file",
        metavar="MAP_FILE",
        type=str,
        nargs="?",
        help="Path to the Soldiers at War .map file (e.g. Airfield.map)",
    )
    parser.add_argument(
        "--game-dir",
        "-g",
        type=str,
        default=None,
        help="Root directory of game installation containing Obj/, Sets/, Misc/ (default: auto)",
    )
    parser.add_argument(
        "--palette",
        "-p",
        type=str,
        default=None,
        help="Explicit color palette file path (.pal or .col, default: Win.pal)",
    )
    parser.add_argument(
        "--layer",
        "-l",
        type=int,
        default=6,
        choices=range(7),
        help="Initial maximum visible elevation layer (0..6, default: 6)",
    )
    parser.add_argument(
        "--view",
        "-v",
        type=str,
        default="isometric",
        choices=["isometric", "top-down"],
        help="Initial view perspective: isometric or top-down (default: isometric)",
    )
    parser.add_argument(
        "--diagnostics",
        "-d",
        action="store_true",
        default=False,
        help="Enable verbose reverse-engineering inspection output in console",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="arcade",
        choices=["arcade", "pygame"],
        help="Rendering backend: arcade (default) or pygame",
    )
    return parser


def resolve_game_root(explicit_root: Optional[str], map_path: Path) -> Path:
    """Locates the root directory containing Obj/, Sets/, Misc/."""
    if explicit_root:
        candidate = Path(explicit_root).resolve()
        if candidate.is_dir():
            return candidate

    # Check current working directory
    cwd = Path.cwd().resolve()
    if (cwd / "Obj").is_dir() and (cwd / "Sets").is_dir():
        return cwd

    # Check parent trees of map_path
    cur = map_path.parent
    for _ in range(5):
        if (cur / "Obj").is_dir() and (cur / "Sets").is_dir():
            return cur.resolve()
        if cur.parent == cur:
            break
        cur = cur.parent

    # Check standard research directory
    research_candidate = cwd / "Research" / "SSI" / "Soldiers at War"
    if research_candidate.is_dir():
        return research_candidate.resolve()

    return cwd


def main(args: Optional[List[str]] = None) -> int:
    """Main CLI execution flow."""
    parser = build_arg_parser()
    parsed = parser.parse_args(args)

    # Validate MAP_FILE presence
    if not parsed.map_file:
        parser.print_usage()
        sys.stderr.write("saw_map: error: MAP_FILE is required\n")
        return 1

    # Configure logging
    configure_logging(level=parsed.log_level, diagnostics=parsed.diagnostics)

    map_path = Path(parsed.map_file).resolve()
    if not map_path.is_file():
        logger.error(f"Map file not found: '{parsed.map_file}'")
        return 1

    # Resolve game root
    game_root = resolve_game_root(parsed.game_dir, map_path)
    logger.info(f"Using game assets directory: {game_root}")

    # Initialize asset loader
    try:
        asset_loader = AssetLoader(game_root)
    except Exception as exc:
        logger.error(f"Failed to initialize asset loader: {exc}")
        return 3

    # Load and parse map
    try:
        logger.info(f"Loading map: {map_path}")
        map_doc = MapReader.parse_map(map_path)
    except FileNotFoundError as exc:
        logger.error(f"File not found error: {exc}")
        return 1
    except ValueError as exc:
        logger.error(f"Corrupted or invalid map file: {exc}")
        return 2
    except Exception as exc:
        logger.error(f"Unexpected error parsing map: {exc}")
        return 2

    # Resolve companion tileset
    tileset = None
    if map_doc.tileset_names:
        set_name = map_doc.tileset_names[0]
        logger.info(f"Resolving companion tileset: {set_name}")
        tileset = asset_loader.load_tileset(set_name)

    # Load palette
    pal_target = parsed.palette or "Win.pal"
    logger.info(f"Loading palette: {pal_target}")
    palette = asset_loader.load_palette(pal_target)

    # Initialize renderer
    renderer: IRenderer
    if parsed.backend == "pygame":
        renderer = PygameRenderer()
    else:
        try:
            renderer = ArcadeRenderer()
        except Exception as exc:
            logger.warning(f"Failed to initialize Arcade backend ({exc}); falling back to Pygame")
            renderer = PygameRenderer()

    title = f"Soldiers at War Map Visualizer - {map_doc.title}"
    try:
        renderer.initialize(1280, 720, title)
    except Exception as exc:
        logger.error(f"Renderer initialization error: {exc}")
        return 4

    # Configure initial camera
    if hasattr(renderer, "camera"):
        renderer.camera.active_max_layer = parsed.layer
        renderer.camera.perspective = (
            ViewPerspective.TOP_DOWN if parsed.view == "top-down" else ViewPerspective.ISOMETRIC
        )

    # Bind map to renderer
    try:
        renderer.set_map(map_doc, asset_loader, tileset, palette)
    except Exception as exc:
        logger.error(f"Error binding map to renderer: {exc}")
        return 4

    # Run application
    try:
        logger.info("Entering visualizer event loop...")
        renderer.run_loop()
    except KeyboardInterrupt:
        logger.info("Visualizer interrupted by user.")
    except Exception as exc:
        logger.error(f"Runtime renderer error: {exc}")
        return 4
    finally:
        renderer.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
