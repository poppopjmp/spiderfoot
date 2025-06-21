#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from update_version import get_version, check_version_consistency

print(f"Current version: {get_version()}")
check_version_consistency()
