#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         run_api_tests
# Purpose:      Run API compatibility tests
#
# Author:       Steve Micallef <steve@binarypool.com>
#
# Created:      Current Date
# Copyright:    (c) Steve Micallef
# License:      MIT
# -----------------------------------------------------------------
import os
import sys
import unittest

if __name__ == "__main__":
    # Add parent directory to path to import test modules
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Discover and run all API compatibility tests
    loader = unittest.TestLoader()
    api_test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unit")
    suite = loader.discover(api_test_dir, pattern="test_api_*.py")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    sys.exit(0 if result.wasSuccessful() else 1)
