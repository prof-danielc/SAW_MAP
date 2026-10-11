"""Diagnostic logging infrastructure for Soldiers at War Map Visualizer.

Provides structured, configurable logging with support for verbosity levels
and reverse-engineering diagnostics.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

DEFAULT_LOGGER_NAME = "saw_map"


class ColorFormatter(logging.Formatter):
    """Optional ANSI colorized formatter for terminal diagnostics."""

    LEVEL_COLORS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool = True) -> None:
        super().__init__(fmt="[%(levelname)s] [%(name)s] %(message)s")
        self.use_color = use_color and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        if self.use_color and record.levelno in self.LEVEL_COLORS:
            color = self.LEVEL_COLORS[record.levelno]
            return f"{color}{formatted}{self.RESET}"
        return formatted


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Retrieves or creates a namespaced logger instance.

    Args:
        name: Sub-logger name. If omitted or None, returns the root saw_map logger.

    Returns:
        Configured logging.Logger instance.
    """
    if name is None or name == DEFAULT_LOGGER_NAME:
        return logging.getLogger(DEFAULT_LOGGER_NAME)
    return logging.getLogger(f"{DEFAULT_LOGGER_NAME}.{name}")


def configure_logging(level: str = "INFO", diagnostics: bool = False) -> logging.Logger:
    """Configures application-wide logging handlers and threshold.

    Args:
        level: Logging verbosity level string ('DEBUG', 'INFO', 'WARNING', 'ERROR').
        diagnostics: If True, forces level to DEBUG regardless of the level parameter.

    Returns:
        Configured root saw_map logger.
    """
    if diagnostics:
        target_level = logging.DEBUG
    else:
        target_level = getattr(logging, level.upper(), logging.INFO)

    logger = logging.getLogger(DEFAULT_LOGGER_NAME)
    logger.setLevel(target_level)

    # Avoid duplicate handlers on re-configuration
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColorFormatter())
        logger.addHandler(handler)
    else:
        for handler in logger.handlers:
            handler.setLevel(target_level)

    return logger
