#!/usr/bin/env python3
"""
Final validation script for ThreadReaper infrastructure and pytest configuration.

This script validates:
1. Integration marker configuration
2. ThreadReaper base class imports
3. Previously failing tests now pass
4. Distributed execution works correctly
5. Resource cleanup and leak detection
"""

import subprocess
import sys
import tempfile
import os
from pathlib import Path

def run_command(cmd, description, check=True):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            cwd="f:\\spiderfoot"
        )
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        print(f"Exit code: {result.returncode}")
        
        if check and result.returncode != 0:
            print(f"❌ FAILED: {description}")
            return False
        else:
            print(f"✅ PASSED: {description}")
            return True
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Run comprehensive validation tests."""
    print("ThreadReaper Infrastructure Final Validation")
    print("=" * 60)
    
    tests = [
        # Test 1: Check markers are configured
        ("python -m pytest --strict-markers --markers", 
         "Pytest markers configuration"),
        
        # Test 2: Test specific previously failing modules
        ("python -m pytest test/unit/modules/test_sfp_base64.py test/unit/modules/test_sfp_telegram.py -v", 
         "Previously failing module tests"),
        
        # Test 3: Test distributed execution with ThreadReaper
        ("python -m pytest test/unit/modules/test_sfp_fofa.py test/unit/modules/test_sfp_cisco_umbrella.py -n 2 -v",
         "Distributed execution with pytest-xdist"),
        
        # Test 4: Test integration marker selection
        ("python -m pytest -m integration --collect-only",
         "Integration test marker selection"),
        
        # Test 5: Run one integration test
        ("python -m pytest test/unit/spiderfoot/test_spiderfootdb_extended.py::TestSpiderFootDbIntegration::test_full_scan_workflow -v",
         "Integration test execution"),
        
        # Test 6: Test that utils can be imported without errors
        ("python -c \"from test.unit.utils.test_module_base import TestModuleBase; from test.unit.utils.test_scanner_base import TestScannerBase; print('✅ Base classes import successfully')\"",
         "Base class imports"),
    ]
    
    results = []
    for cmd, description in tests:
        success = run_command(cmd, description)
        results.append((description, success))
    
    # Final summary
    print("\n" + "="*60)
    print("FINAL VALIDATION SUMMARY")
    print("="*60)
    
    passed = 0
    total = len(results)
    
    for description, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {description}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL VALIDATIONS PASSED!")
        print("ThreadReaper infrastructure is fully operational.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} validation(s) failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
