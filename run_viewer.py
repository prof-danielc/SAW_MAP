#!/usr/bin/env python3
"""Convenience runner script for Soldiers at War original map visualizer."""

import sys
from pathlib import Path

# Ensure src/ is on sys.path
root_dir = Path(__file__).resolve().parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from saw_map.main import main

if __name__ == "__main__":
    sys.exit(main())
