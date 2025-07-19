#!/usr/bin/env python3
"""
Test xdist (distributed testing) stability with the improved conftest.py and logging fixes.
This script validates that our BrokenPipeError and timeout fixes work correctly.
"""

import os
import sys
import subprocess
import time
import json
from pathlib import Path


def run_test_with_xdist(test_pattern, workers=2, timeout_seconds=300):
    """Run tests with xdist and capture results."""
    cmd = [
        sys.executable, '-m', 'pytest',
        test_pattern,
        f'-n{workers}',  # Number of workers
        '--tb=short',
        '--quiet',
        '--disable-warnings'
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 60,  # Give extra time for process termination
            cwd=Path(__file__).parent
        )
        elapsed = time.time() - start_time
        
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'elapsed': elapsed,
            'timeout': False
        }
    except subprocess.TimeoutExpired as e:
        elapsed = time.time() - start_time
        return {
            'returncode': -1,
            'stdout': e.stdout.decode() if e.stdout else '',
            'stderr': e.stderr.decode() if e.stderr else '',
            'elapsed': elapsed,
            'timeout': True
        }


def analyze_xdist_output(result):
    """Analyze test output for xdist-specific issues."""
    issues = []
    
    # Check for BrokenPipeError
    if 'BrokenPipeError' in result['stderr']:
        issues.append('BrokenPipeError detected in stderr')
    
    # Check for OSError: cannot send
    if 'OSError: cannot send' in result['stderr']:
        issues.append('OSError communication issue detected')
    
    # Check for logging errors
    if 'Logging error' in result['stderr']:
        issues.append('Logging error detected')
    
    # Check for global timeout
    if 'Global timeout exceeded' in result['stderr']:
        issues.append('Global timeout exceeded')
    
    # Check for successful completion
    if result['returncode'] == 0:
        issues.append('SUCCESS: Tests completed without errors')
    elif result['timeout']:
        issues.append('TIMEOUT: Process timeout exceeded')
    else:
        issues.append(f'FAILURE: Tests failed with return code {result["returncode"]}')
    
    return issues


def main():
    """Main test execution."""
    print("=" * 80)
    print("XDIST STABILITY TESTING")
    print("=" * 80)
    
    # Test patterns with different complexities
    test_cases = [
        {
            'name': 'SecurityTrails Module Test (Fixed)',
            'pattern': 'test/unit/modules/test_sfp_securitytrails.py::TestModuleSecuritytrails::test_handleEvent_no_api_key_should_set_errorState',
            'workers': 2,
            'timeout': 60
        },
        {
            'name': 'SecurityTrails Full Module',
            'pattern': 'test/unit/modules/test_sfp_securitytrails.py',
            'workers': 2,
            'timeout': 120
        },
        {
            'name': 'Web UI Lightweight Tests',
            'pattern': 'test/unit/test_sfwebui_lightweight.py',
            'workers': 2,
            'timeout': 60
        },
        {
            'name': 'Base Test Utilities',
            'pattern': 'test/unit/utils/test_base.py',
            'workers': 2,
            'timeout': 30
        },
        {
            'name': 'Mixed Module Tests (Sample)',
            'pattern': 'test/unit/modules/test_sfp_securitytrails.py test/unit/test_sfwebui_lightweight.py',
            'workers': 3,
            'timeout': 180
        }
    ]
    
    results = {}
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] Testing: {test_case['name']}")
        print("-" * 60)
        
        result = run_test_with_xdist(
            test_case['pattern'],
            test_case['workers'],
            test_case['timeout']
        )
        
        issues = analyze_xdist_output(result)
        
        print(f"Elapsed time: {result['elapsed']:.2f}s")
        print(f"Return code: {result['returncode']}")
        print("Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        
        # Show critical stderr content (but limit it)
        if result['stderr']:
            stderr_lines = result['stderr'].split('\n')
            critical_lines = [line for line in stderr_lines 
                            if any(keyword in line for keyword in 
                                   ['BrokenPipeError', 'OSError: cannot send', 'Global timeout', 'Logging error'])]
            if critical_lines:
                print("\nCritical stderr content:")
                for line in critical_lines[:10]:  # Limit to first 10 critical lines
                    print(f"  {line}")
        
        results[test_case['name']] = {
            'result': result,
            'issues': issues
        }
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    successful_tests = 0
    tests_with_xdist_issues = 0
    
    for test_name, test_data in results.items():
        issues = test_data['issues']
        has_success = any('SUCCESS' in issue for issue in issues)
        has_xdist_issues = any(keyword in ' '.join(issues) for keyword in 
                              ['BrokenPipeError', 'OSError: cannot send', 'Logging error'])
        
        if has_success:
            successful_tests += 1
            status = "✓ PASS"
        else:
            status = "✗ FAIL"
        
        if has_xdist_issues:
            tests_with_xdist_issues += 1
            status += " (XDIST ISSUES)"
        
        print(f"{status:20} {test_name}")
    
    print(f"\nSuccessful tests: {successful_tests}/{len(test_cases)}")
    print(f"Tests with xdist issues: {tests_with_xdist_issues}/{len(test_cases)}")
    
    # Save detailed results
    results_file = 'xdist_stability_results.json'
    with open(results_file, 'w') as f:
        # Convert to JSON-serializable format
        json_results = {}
        for test_name, test_data in results.items():
            json_results[test_name] = {
                'returncode': test_data['result']['returncode'],
                'elapsed': test_data['result']['elapsed'],
                'timeout': test_data['result']['timeout'],
                'issues': test_data['issues'],
                'stderr_length': len(test_data['result']['stderr']),
                'stdout_length': len(test_data['result']['stdout'])
            }
        json.dump(json_results, f, indent=2)
    
    print(f"\nDetailed results saved to: {results_file}")
    
    # Final assessment
    if tests_with_xdist_issues == 0:
        print("\n🎉 ALL XDIST ISSUES RESOLVED! No BrokenPipeError or communication issues detected.")
        return 0
    else:
        print(f"\n⚠️  {tests_with_xdist_issues} test(s) still have xdist-related issues.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
