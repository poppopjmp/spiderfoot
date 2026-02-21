"""Version string for the SpiderFoot package.

Reads the canonical version from the ``VERSION`` file at the repository root
and exposes it as :data:`__version__`.
"""

import os
import pathlib

def _get_version():
    """Read version from the VERSION file in the repository root."""
    try:
        version_file = pathlib.Path(__file__).parent.parent / "VERSION"
        with open(version_file, encoding='utf-8') as f:
            version_string = f.read().strip()
        return version_string
    except (FileNotFoundError, OSError):
        # Fallback version if VERSION file is not found
        return "6.0.0"

__version__ = _get_version()

# For backward compatibility, also provide VERSION tuple.
# Strip any pre-release suffix (e.g. "6.0.0-rc.1" → "6.0.0") before
# converting to ints so that VERSION is always a clean (major, minor, patch).
VERSION = tuple(map(int, __version__.split('-')[0].split('.')))
