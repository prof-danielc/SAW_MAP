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


AIRFIELD_MAP = "Research/SSI/Soldiers at War/Single_g/Airfield.map"
DEMO_MAP = "Research/SSI/Soldiers at War/Menu/Demo.MAP"


@pytest.mark.skipif(not os.path.exists(AIRFIELD_MAP), reason="Game assets not found")
def test_cli_dump_records():
    """Validates --dump-records prints the post-tile report and exits without a window."""
    result = run_cli(AIRFIELD_MAP, "--dump-records", "--log-level", "ERROR")
    assert result.returncode == 0
    assert "POST-TILE DATA: Airfield (version 21)" in result.stdout
    assert "0 bytes unassigned" in result.stdout
    assert "PLACED ENTITIES:" in result.stdout
    assert "(unused)" not in result.stdout

    with_unused = run_cli(AIRFIELD_MAP, "--dump-records", "--dump-unused", "--log-level", "ERROR")
    assert with_unused.returncode == 0
    assert "(unused)" in with_unused.stdout


@pytest.mark.skipif(not os.path.exists(DEMO_MAP), reason="Game assets not found")
def test_cli_dump_records_unsupported_version_is_not_a_failure():
    """An undecodable post-tile block is reported with exit code 0, since the map itself is valid."""
    result = run_cli(DEMO_MAP, "--dump-records", "--log-level", "ERROR")
    assert result.returncode == 0
    assert "UNSUPPORTED_VERSION" in result.stdout
