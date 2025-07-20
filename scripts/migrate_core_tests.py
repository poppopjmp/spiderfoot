#!/usr/bin/env python3
"""
Core Test Migration - Phase 1
=============================

Migrate critical core tests to ThreadReaper infrastructure first.
"""

import sys
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from scripts.migrate_threadreaper import ThreadReaperMigrator

def migrate_core_tests():
    """Migrate core/critical tests first."""
    
    migrator = ThreadReaperMigrator()
    
    # Priority core test files
    core_tests = [
        "test/unit/test_sflib.py",
        "test/unit/test_sfwebui.py", 
        "test/unit/test_spiderfoot.py",
        "test/unit/spiderfoot/test_spiderfootdb.py",
        "test/unit/test_sfapi.py",
        "test/unit/test_sfcli.py"
    ]
    
    print("🎯 MIGRATING CORE TESTS (PHASE 1)")
    print("=" * 50)
    
    success_count = 0
    total_count = 0
    
    for test_path in core_tests:
        file_path = migrator.project_root / test_path
        
        if not file_path.exists():
            print(f"⏭️  Skipping {test_path} (not found)")
            continue
            
        total_count += 1
        print(f"🔧 Migrating: {test_path}")
        
        if migrator.migrate_file(file_path):
            success_count += 1
            print(f"✅ Success: {test_path}")
        else:
            print(f"❌ Failed: {test_path}")
    
    print(f"\n📊 CORE MIGRATION RESULTS:")
    print(f"  Migrated: {success_count}/{total_count}")
    print(f"  Success rate: {(success_count/total_count)*100:.1f}%" if total_count > 0 else "  No files processed")
    
    return success_count == total_count

if __name__ == "__main__":
    success = migrate_core_tests()
    if success:
        print("\n🎉 Core test migration completed successfully!")
    else:
        print("\n⚠️  Some core tests failed to migrate")
        sys.exit(1)
