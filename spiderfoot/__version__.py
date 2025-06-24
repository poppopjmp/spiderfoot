import os
import pathlib

def _get_version():
    """Read version from the VERSION file in the repository root."""
    try:
        version_file = pathlib.Path(__file__).parent.parent / "VERSION"
        with open(version_file, 'r', encoding='utf-8') as f:
            version_string = f.read().strip()
        return version_string
    except (FileNotFoundError, IOError):
        # Fallback version if VERSION file is not found
        return "5.2.7"

__version__ = _get_version()

# For backward compatibility, also provide VERSION tuple
VERSION = tuple(map(int, __version__.split('.')))
