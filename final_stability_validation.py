#!/usr/bin/env python3
"""
Final validation of all SpiderFoot test suite stability fixes.
This script demonstrates that all critical issues have been resolved.
"""

import subprocess
import sys
import time
from pathlib import Path


def run_test_command(description, command, expected_returncode=0):
    """Run a test command and validate the result."""
    print(f"\n🔍 {description}")
    print("=" * 60)
    print(f"Command: {' '.join(command)}")
    
    start_time = time.time()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,  # 2-minute timeout per test
            cwd=Path(__file__).parent
        )
        elapsed = time.time() - start_time
        
        # Check for critical issues in stderr
        issues = []
        if 'BrokenPipeError' in result.stderr:
            issues.append('❌ BrokenPipeError detected')
        if 'OSError: cannot send' in result.stderr:
            issues.append('❌ OSError communication issue')
        if 'Global timeout exceeded' in result.stderr:
            issues.append('❌ Global timeout issue')
        if 'Logging error' in result.stderr:
            issues.append('❌ Logging error')
        
        if result.returncode == expected_returncode and not issues:
            print(f"✅ SUCCESS (⏱️ {elapsed:.2f}s)")
            if result.stdout.strip():
                # Show test results summary if available
                lines = result.stdout.split('\n')
                summary_lines = [line for line in lines if any(word in line.lower() for word in ['passed', 'failed', 'error'])]
                if summary_lines:
                    print(f"📊 Results: {summary_lines[-1]}")
            return True
        else:
            print(f"❌ FAILED (⏱️ {elapsed:.2f}s, return code: {result.returncode})")
            if issues:
                for issue in issues:
                    print(f"   {issue}")
            if result.stderr:
                print("📄 Error output (first 500 chars):")
                print(result.stderr[:500])
            return False
            
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"⏰ TIMEOUT after {elapsed:.2f}s")
        return False
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"💥 EXCEPTION after {elapsed:.2f}s: {e}")
        return False


def main():
    """Run comprehensive validation tests."""
    print("🚀 SPIDERFOOT TEST SUITE STABILITY VALIDATION")
    print("=" * 80)
    print("Validating all critical fixes:")
    print("  • Thread cleanup fixes")
    print("  • Web UI timeout resolution")
    print("  • Module test stabilization")
    print("  • Distributed testing (xdist) compatibility")
    print("  • Logging error suppression")
    
    tests = [
        {
            'description': 'Thread Cleanup (Base Test)',
            'command': [sys.executable, '-m', 'pytest', 'test/unit/test_spiderfootscanner.py', '-v', '--tb=short'],
            'expected': 0
        },
        {
            'description': 'Web UI Lightweight Tests',
            'command': [sys.executable, '-m', 'pytest', 'test/unit/test_sfwebui_lightweight.py', '-v'],
            'expected': 0
        },
        {
            'description': 'SecurityTrails Module Test (Previously Hanging)',
            'command': [sys.executable, '-m', 'pytest', 
                       'test/unit/modules/test_sfp_securitytrails.py::TestModuleSecuritytrails::test_handleEvent_no_api_key_should_set_errorState', 
                       '-v'],
            'expected': 0
        },
        {
            'description': 'Distributed Testing (xdist) - Web UI',
            'command': [sys.executable, '-m', 'pytest', 'test/unit/test_sfwebui_lightweight.py', '-n2', '--tb=short'],
            'expected': 0
        },
        {
            'description': 'Distributed Testing (xdist) - SecurityTrails',
            'command': [sys.executable, '-m', 'pytest', 'test/unit/modules/test_sfp_securitytrails.py', '-n2', '--tb=short'],
            'expected': 0
        },
        {
            'description': 'Mixed Distributed Testing',
            'command': [sys.executable, '-m', 'pytest', 
                       'test/unit/test_sfwebui_lightweight.py',
                       'test/unit/modules/test_sfp_securitytrails.py::TestModuleSecuritytrails::test_handleEvent_no_api_key_should_set_errorState',
                       '-n2', '--quiet'],
            'expected': 0
        }
    ]
    
    successful_tests = 0
    total_tests = len(tests)
    
    for i, test in enumerate(tests, 1):
        print(f"\n[{i}/{total_tests}]", end=" ")
        success = run_test_command(
            test['description'],
            test['command'],
            test['expected']
        )
        if success:
            successful_tests += 1
    
    print("\n" + "=" * 80)
    print("🏁 VALIDATION SUMMARY")
    print("=" * 80)
    
    if successful_tests == total_tests:
        print(f"🎉 ALL TESTS PASSED: {successful_tests}/{total_tests}")
        print("\n✅ STABILITY VALIDATION COMPLETE")
        print("   • Thread cleanup: WORKING")
        print("   • Web UI tests: WORKING") 
        print("   • Module timeouts: RESOLVED")
        print("   • Distributed testing: STABLE")
        print("   • Logging errors: SUPPRESSED")
        print("\n🚀 SpiderFoot test suite is now PRODUCTION READY!")
        return 0
    else:
        print(f"⚠️  PARTIAL SUCCESS: {successful_tests}/{total_tests} tests passed")
        failed_count = total_tests - successful_tests
        print(f"   {failed_count} test(s) still have issues")
        return 1


if __name__ == '__main__':
    sys.exit(main())
