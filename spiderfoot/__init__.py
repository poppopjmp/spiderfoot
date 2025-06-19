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
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try multiple possible locations
    possible_paths = [
        os.path.join(PROJECT_ROOT, "modules"),
        os.path.join(script_dir, "..", "modules"),
        os.path.join(os.getcwd(), "modules"),
        "/home/spiderfoot/modules",  # Container path
        os.path.join(os.path.dirname(script_dir), "modules")
    ]
    
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path) and os.path.isdir(abs_path):
            # Check if it actually contains module files
            try:
                files = os.listdir(abs_path)
                module_files = [f for f in files if f.startswith('sfp_') and f.endswith('.py')]
                if module_files:
                    return abs_path
            except OSError:
                continue
    
    # Default fallback
    return os.path.join(PROJECT_ROOT, "modules")

import sys
import importlib.util
from .helpers import SpiderFootHelpers

class SpiderFootModuleFinder:
    """Custom module finder to fix SpiderFoot module imports."""
    
    def find_spec(self, name, path, target=None):
        # Only intercept sfp_ module imports
        if name.startswith('modules.sfp_') or name.startswith('sfp_'):
            return None  # Let default finder handle it, we'll fix in exec_module
        return None

class SpiderFootModuleLoader:
    """Custom module loader to fix SpiderFoot module imports."""
    
    def __init__(self, spec):
        self.spec = spec
    
    def create_module(self, spec):
        return None  # Use default module creation
    
    def exec_module(self, module):
        # Execute the module normally first
        spec = importlib.util.find_spec(module.__name__)
        if spec and spec.loader:
            spec.loader.exec_module(module)
        
        # Then fix the module
        module_name = module.__name__.split('.')[-1]
        if module_name.startswith('sfp_'):
            SpiderFootHelpers.fixModuleImport(module, module_name)

# Install the import hook
if not any(isinstance(finder, SpiderFootModuleFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, SpiderFootModuleFinder())
