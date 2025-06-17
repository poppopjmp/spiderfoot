"""SpiderFoot - Open Source Intelligence Automation Tool.

This package contains the core SpiderFoot functionality including:
- Database operations
- Event handling
- Helper utilities
- Web interface components
"""

__version__ = "5.1.0"
__author__ = "Steve Micallef, Agostino Panico"
__license__ = "MIT"
__email__ = "steve@binarypool.com, van1sh@van1shland.io"
__url__ = "https://github.com/poppopjmp/spiderfoot"

# Core imports for package
from .db import SpiderFootDb
from .event import SpiderFootEvent
from .helpers import SpiderFootHelpers
from .plugin import SpiderFootPlugin
from .target import SpiderFootTarget
from .threadpool import SpiderFootThreadPool
from .correlation import SpiderFootCorrelator

# Logger import - assuming it exists in the package
try:
    from .logger import logger
except ImportError:
    # Fallback if logger module doesn't exist
    import logging
    logger = logging.getLogger(__name__)

__all__ = [
    'SpiderFootDb', 
    'SpiderFootEvent', 
    'SpiderFootHelpers', 
    'SpiderFootPlugin',
    'SpiderFootTarget',
    'SpiderFootThreadPool',
    'SpiderFootCorrelator',
    'logger',
    '__version__'
]

import os
import sys
from pathlib import Path

# Add the project root to Python path for module imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def get_modules_path():
    """Get the correct path to the modules directory."""
    # Try multiple possible locations
    possible_paths = [
        PROJECT_ROOT / "modules",
        Path(__file__).parent.parent / "modules", 
        Path.cwd() / "modules",
        Path("/home/spiderfoot/modules") if Path("/home/spiderfoot/modules").exists() else None
    ]
    
    for path in possible_paths:
        if path and path.exists() and path.is_dir():
            # Check if it actually contains module files
            if any(f.name.startswith('sfp_') and f.suffix == '.py' for f in path.glob('*.py')):
                return str(path)
    
    # Default fallback
    return str(PROJECT_ROOT / "modules")
