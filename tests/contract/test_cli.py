"""Contract tests for command-line interface arguments, exit codes, and help messages."""

import os
import subprocess
import sys
import pytest


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Helper to execute saw_map CLI as a subprocess."""
    cmd = [sys.executable, "-m", "saw_map.main", *args]
    env = os.environ.copy()
    src_dir = os.path.abspath("src")
    env["PYTHONPATH"] = src_dir if "PYTHONPATH" not in env else f"{src_dir}{os.path.pathsep}{env['PYTHONPATH']}"
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def test_cli_help():
    """Validates --help flag displays usage and exits with code 0."""
    result = run_cli("--help")
    assert result.returncode == 0
    assert "MAP_FILE" in result.stdout or "MAP_FILE" in result.stderr or "usage:" in result.stdout.lower()
    assert "--maximize" in result.stdout


def test_cli_missing_positional_map_file():
    """Validates missing required MAP_FILE exits with error code 1 or 2."""
    result = run_cli()
    assert result.returncode in (1, 2)


def test_cli_nonexistent_map_file():
    """Validates nonexistent MAP_FILE exits with exit code 1."""
    result = run_cli("non_existent_map_file.map")
    assert result.returncode == 1
    assert "not found" in (result.stderr + result.stdout).lower()
