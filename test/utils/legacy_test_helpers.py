# -*- coding: utf-8 -*-
"""Test helper utilities for SpiderFoot testing."""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any, Optional


class TestHelpers:
    """Collection of helper methods for testing."""
    
    @staticmethod
    def create_temp_file(content: str = "", suffix: str = ".txt") -> str:
        """Create a temporary file with content."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(content)
        except:
            os.close(fd)
            raise
        return path
    
    @staticmethod
    def create_temp_dir() -> str:
        """Create a temporary directory."""
        return tempfile.mkdtemp()
    
    @staticmethod
    def cleanup_temp_path(path: str):
        """Clean up temporary file or directory."""
        if os.path.isfile(path):
            os.unlink(path)
        elif os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
