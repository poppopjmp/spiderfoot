"""
SpiderFoot logging configuration module.

This module provides utilities and configuration for the SpiderFoot logging system.
It centralizes logging setup to ensure consistency across the application.
"""

import logging
import os
import sys
from typing import Dict, Any, Optional

from spiderfoot import SpiderFootHelpers

# Store module loggers to avoid creating duplicates
_module_loggers: Dict[str, logging.Logger] = {}


def configure_root_logger(debug: bool = False) -> None:
    """Configure the root logger with basic settings.

    This sets up minimal console logging for the root logger.
    Modules should generally use their own named loggers.

    Args:
        debug: Whether to enable debug logging
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


def get_module_logger(module_name: str) -> logging.Logger:
    """Get or create a logger for the specified module.

    This function ensures that each module gets its own logger with consistent
    configuration. Loggers are cached to avoid creating duplicates.

    Args:
        module_name: The name of the module requesting a logger

    Returns:
        logging.Logger: Configured logger for the module
    """
    if module_name in _module_loggers:
        return _module_loggers[module_name]

    # Create a new logger for this module
    logger = logging.getLogger(f"spiderfoot.{module_name}")

    # Cache the logger for future use
    _module_loggers[module_name] = logger

    return logger


def get_log_paths() -> Dict[str, str]:
    """Get standard paths for SpiderFoot log files.

    Returns:
        Dict containing paths for different log files
    """
    log_dir = SpiderFootHelpers.logPath()
    return {
        "debug": os.path.join(log_dir, "spiderfoot.debug.log"),
        "error": os.path.join(log_dir, "spiderfoot.error.log"),
        "syslog": os.path.join(log_dir, "spiderfoot.syslog.log"),
    }


def get_log_level_from_config(config: Optional[Dict[str, Any]] = None) -> int:
    """Determine the appropriate log level from configuration.

    Args:
        config: SpiderFoot configuration dictionary

    Returns:
        int: The logging level (from logging module constants)
    """
    if config is None:
        return logging.INFO

    if config.get("_debug", False):
        return logging.DEBUG

    return logging.INFO
