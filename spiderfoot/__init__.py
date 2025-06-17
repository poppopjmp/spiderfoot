"""SpiderFoot - Open Source Intelligence Automation Tool.

This package contains the core SpiderFoot functionality including:
- Database operations
- Event handling
- Helper utilities
- Web interface components
"""

__version__ = "5.0.3"
__author__ = "Steve Micallef, Agostino Panico"
__license__ = "MIT"
__email__ = "steve@binarypool.com, van1sh@van1shland.io"
__url__ = "https://github.com/poppopjmp/spiderfoot"

# Core imports for package
from .db import SpiderFootDb
from .event import SpiderFootEvent
from .helpers import SpiderFootHelpers

__all__ = ['SpiderFootDb', 'SpiderFootEvent', 'SpiderFootHelpers', '__version__']
