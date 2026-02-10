#!/usr/bin/env python3
"""
Module Test Migration - Phase 2
===============================

Migrate module tests to ThreadReaper infrastructure in batches.
"""

from __future__ import annotations

import sys
from pathlib import Path
import time

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from scripts.migrate_threadreaper import ThreadReaperMigrator


def migrate_module_tests_batch(batch_size: int = 50):
    """Migrate module tests in batches to prevent overwhelming the system."""
    
    migrator = ThreadReaperMigrator()
    
    # Find all module test files
    test_files = []
    for pattern in ["**/test_sfp_*.py"]:
        test_files.extend(migrator.test_dir.glob(pattern))
    
    # Filter for files that need migration
    module_tests = []
    for file_path in test_files:
        try:
            content = file_path.read_text(encoding='utf-8')
            # Skip if already using ThreadReaper
            if any(keyword in content for keyword in ['TestModuleBase', 'TestScannerBase']):
                continue
            # Only include if using SpiderFootTestBase
            if 'SpiderFootTestBase' in content:
                module_tests.append(file_path)
        except Exception:
            continue
    
    print(f"🎯 MIGRATING MODULE TESTS (PHASE 2)")
    print(f"=" * 50)
    print(f"📋 Found {len(module_tests)} module tests to migrate")
    
    # Process in batches
    total_success = 0
    total_failed = 0
    batch_num = 0
    
    for i in range(0, len(module_tests), batch_size):
        batch_num += 1
        batch = module_tests[i:i + batch_size]
        
        print(f"\n🔧 BATCH {batch_num}/{(len(module_tests) + batch_size - 1) // batch_size}")
        print(f"   Processing files {i+1}-{min(i+batch_size, len(module_tests))} of {len(module_tests)}")
        
        batch_success = 0
        
        for j, file_path in enumerate(batch, 1):
            relative_path = file_path.relative_to(migrator.project_root)
            
            print(f"  [{j:2d}/{len(batch)}] {relative_path}")
            
            try:
                if migrator.migrate_file(file_path):
                    batch_success += 1
                    total_success += 1
                else:
                    total_failed += 1
                    print(f"    ❌ Migration failed")
            except Exception as e:
                total_failed += 1
                print(f"    ❌ Error: {e}")
        
        print(f"  📊 Batch {batch_num} results: {batch_success}/{len(batch)} successful")
        
        # Brief pause between batches to allow system to stabilize
        if batch_num < (len(module_tests) + batch_size - 1) // batch_size:
            time.sleep(0.5)
    
    print(f"\n📊 FINAL RESULTS:")
    print(f"  Total files: {len(module_tests)}")
    print(f"  ✅ Successful: {total_success}")
    print(f"  ❌ Failed: {total_failed}")
    print(f"  📈 Success rate: {(total_success/len(module_tests)*100):.1f}%")
    
    return total_success, total_failed


def main():
    """Main entry point for module test migration."""
    
    # Check command line arguments
    batch_size = 25  # Smaller batches for stability
    if '--batch-size' in sys.argv:
        try:
            idx = sys.argv.index('--batch-size')
            batch_size = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            print("⚠️  Invalid batch size, using default of 25")
    
    success_count, failed_count = migrate_module_tests_batch(batch_size)
    
    if failed_count == 0:
        print("\n🎉 ALL MODULE TESTS MIGRATED SUCCESSFULLY!")
        print("🔧 Module tests now have comprehensive thread leak prevention.")
    elif success_count > failed_count:
        print(f"\n✅ MOSTLY SUCCESSFUL - {success_count} migrated, {failed_count} failed")
        print("🔍 Check error messages above for failed migrations.")
    else:
        print(f"\n⚠️  MIGRATION HAD ISSUES - {success_count} migrated, {failed_count} failed")
        print("🔍 Review errors and retry failed migrations.")
        sys.exit(1)


if __name__ == "__main__":
    main()
