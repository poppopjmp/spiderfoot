#!/usr/bin/env python3
"""
ThreadReaper Integration Analysis
================================

Analyzes the current state of ThreadReaper infrastructure integration
across the SpiderFoot test suite.
"""

import os
import sys
from pathlib import Path
import re

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))


def analyze_test_integration():
    """Analyze ThreadReaper integration across test files."""
    
    print("🔍 THREADREAPER INTEGRATION ANALYSIS")
    print("=" * 60)
    
    test_dir = project_root / "test"
    
    # Find all test files
    test_files = []
    for pattern in ["**/test_*.py", "**/*_test.py"]:
        test_files.extend(test_dir.glob(pattern))
    
    print(f"📋 Found {len(test_files)} test files")
    
    # Categorize test files
    categories = {
        'scanner_tests': [],
        'module_tests': [],
        'other_tests': [],
        'using_old_base': [],
        'using_new_base': [],
        'using_threadreaper': []
    }
    
    # Keywords to look for
    threadreaper_keywords = [
        'TestScannerBase', 'TestModuleBase', 'resource_manager', 
        'thread_registry', 'leak_detector', 'shared_pool_cleanup'
    ]
    
    old_base_keywords = ['SpiderFootTestBase', 'unittest.TestCase']
    
    for test_file in test_files:
        try:
            content = test_file.read_text(encoding='utf-8')
            relative_path = test_file.relative_to(project_root)
            
            # Categorize by type
            if 'scanner' in test_file.name.lower():
                categories['scanner_tests'].append(relative_path)
            elif 'sfp_' in test_file.name:
                categories['module_tests'].append(relative_path)
            else:
                categories['other_tests'].append(relative_path)
            
            # Check for ThreadReaper usage
            uses_threadreaper = any(keyword in content for keyword in threadreaper_keywords)
            uses_old_base = any(keyword in content for keyword in old_base_keywords)
            
            if uses_threadreaper:
                categories['using_threadreaper'].append(relative_path)
                categories['using_new_base'].append(relative_path)
            elif uses_old_base:
                categories['using_old_base'].append(relative_path)
                
        except Exception as e:
            print(f"⚠️  Error reading {test_file}: {e}")
    
    # Report findings
    print("\n📊 TEST FILE CATEGORIZATION:")
    print("-" * 40)
    print(f"  🧪 Scanner tests: {len(categories['scanner_tests'])}")
    print(f"  🔌 Module tests: {len(categories['module_tests'])}")
    print(f"  📁 Other tests: {len(categories['other_tests'])}")
    
    print("\n📊 THREADREAPER INTEGRATION STATUS:")
    print("-" * 40)
    print(f"  ✅ Using ThreadReaper: {len(categories['using_threadreaper'])}")
    print(f"  ✅ Using new base classes: {len(categories['using_new_base'])}")
    print(f"  ❌ Using old base classes: {len(categories['using_old_base'])}")
    
    # Calculate integration percentage
    total_testable = len(categories['using_threadreaper']) + len(categories['using_old_base'])
    if total_testable > 0:
        integration_percent = (len(categories['using_threadreaper']) / total_testable) * 100
        print(f"  📈 Integration percentage: {integration_percent:.1f}%")
    
    print("\n📝 DETAILED FINDINGS:")
    print("-" * 40)
    
    if categories['using_threadreaper']:
        print(f"\n✅ Files using ThreadReaper ({len(categories['using_threadreaper'])}):")
        for file_path in categories['using_threadreaper'][:10]:  # Show first 10
            print(f"  • {file_path}")
        if len(categories['using_threadreaper']) > 10:
            print(f"  ... and {len(categories['using_threadreaper']) - 10} more")
    
    if categories['using_old_base']:
        print(f"\n❌ Files needing migration ({len(categories['using_old_base'])}):")
        # Show examples from each category
        scanner_old = [f for f in categories['using_old_base'] if 'scanner' in str(f).lower()]
        module_old = [f for f in categories['using_old_base'] if 'sfp_' in str(f)]
        other_old = [f for f in categories['using_old_base'] if f not in scanner_old + module_old]
        
        if scanner_old:
            print(f"    Scanner tests ({len(scanner_old)}):")
            for file_path in scanner_old[:5]:
                print(f"      • {file_path}")
            if len(scanner_old) > 5:
                print(f"      ... and {len(scanner_old) - 5} more")
        
        if module_old:
            print(f"    Module tests ({len(module_old)}):")
            for file_path in module_old[:5]:
                print(f"      • {file_path}")
            if len(module_old) > 5:
                print(f"      ... and {len(module_old) - 5} more")
        
        if other_old:
            print(f"    Other tests ({len(other_old)}):")
            for file_path in other_old[:5]:
                print(f"      • {file_path}")
            if len(other_old) > 5:
                print(f"      ... and {len(other_old) - 5} more")
    
    print("\n🎯 PRIORITY MIGRATION TARGETS:")
    print("-" * 40)
    
    # Identify high-priority files for migration
    priority_files = []
    
    # Scanner tests are high priority
    scanner_old = [f for f in categories['using_old_base'] if 'scanner' in str(f).lower()]
    priority_files.extend(scanner_old)
    
    # Main test files (not in modules subdirectory)
    main_test_old = [f for f in categories['using_old_base'] 
                     if 'modules' not in str(f) and 'sfp_' not in str(f)]
    priority_files.extend(main_test_old)
    
    for i, file_path in enumerate(priority_files[:10], 1):
        print(f"  {i}. {file_path}")
    
    if len(priority_files) > 10:
        print(f"  ... and {len(priority_files) - 10} more priority files")
    
    print("\n📋 MIGRATION RECOMMENDATIONS:")
    print("-" * 40)
    print("  1. Migrate scanner tests to TestScannerBase")
    print("  2. Migrate core test files to ThreadReaper infrastructure")
    print("  3. Update module tests to TestModuleBase (gradual)")
    print("  4. Add resource registration to existing SpiderFootScanner")
    print("  5. Integrate leak detection into CI pipeline")
    
    print("\n🚀 NEXT STEPS:")
    print("-" * 40)
    print("  • Run: python scripts/module_stabilizer.py migrate")
    print("  • Focus on scanner and core tests first")
    print("  • Test integration with pytest-xdist")
    print("  • Validate cross-platform compatibility")
    
    return {
        'total_files': len(test_files),
        'threadreaper_files': len(categories['using_threadreaper']),
        'old_base_files': len(categories['using_old_base']),
        'integration_percent': integration_percent if total_testable > 0 else 0,
        'priority_files': priority_files
    }


if __name__ == "__main__":
    results = analyze_test_integration()
    
    # Summary
    print(f"\n🏁 ANALYSIS SUMMARY:")
    print(f"   Total test files: {results['total_files']}")
    print(f"   Using ThreadReaper: {results['threadreaper_files']}")
    print(f"   Need migration: {results['old_base_files']}")
    print(f"   Integration: {results['integration_percent']:.1f}%")
    
    if results['integration_percent'] < 50:
        print("⚠️  ThreadReaper integration is incomplete!")
        print("   Run migration to achieve full thread leak prevention.")
        exit_code = 1
    else:
        print("✅ Good ThreadReaper integration progress!")
        exit_code = 0
    
    sys.exit(exit_code)
