#!/usr/bin/env python3
"""
SpiderFoot Repository Cleanup Script
Removes unnecessary test, validation, and summary files for production release.
"""

import os
import glob

def remove_files_safely(file_patterns, base_path="d:/Github/spiderfoot"):
    """Remove files matching patterns safely."""
    removed_files = []
    
    for pattern in file_patterns:
        full_pattern = os.path.join(base_path, pattern)
        matching_files = glob.glob(full_pattern)
        
        for file_path in matching_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    removed_files.append(file_path)
                    print(f"Removed: {file_path}")
            except Exception as e:
                print(f"Error removing {file_path}: {e}")
    
    return removed_files

if __name__ == "__main__":
    # Define file patterns to remove
    cleanup_patterns = [
        # Summary and status report files
        "*_STATUS_*.md",
        "*_SUMMARY*.md", 
        "*_REPORT*.md",
        "*_COMPLETE.md",
        "*_GUIDE.md",
        "*_ROADMAP.md",
        "PROJECT_COMPLETE.md",
        "EXECUTIVE_SUMMARY.md",
        "MAXIMUM_STATUS_ACHIEVED.md",
        "STARTUP_FIX_RESOLVED.md",
        "WEB_INTERFACE_FIX_COMPLETE.md",
        "STORAGE_REVIEW*.md",
        "DOCUMENTATION_SYSTEM_REVIEW.md",
        
        # Test and validation files (root level)
        "test_*.py",
        "validate_*.py", 
        "*_test*.py",
        "*_validation*.py",
        "comprehensive_production_test.py",
        "final_production_assessment.py",
        "final_storage_validation.py",
        "run_enhanced_storage_tests.py",
        "storage_enhancement_accelerator.py",
        "storage_status_acceleration.py",
        "setup_venv.py",
        
        # JSON report files
        "*.json",
        
        # Log files
        "*.log",
        "pytest-debug.log",
        
        # Database test files
        "test.db",
        
        # Production files that are duplicates or development-only
        "docker-compose-new.yml",
        "nginx.conf"
    ]
    
    print("Starting SpiderFoot repository cleanup...")
    print("=" * 50)
    
    removed = remove_files_safely(cleanup_patterns)
    
    print("=" * 50)
    print(f"Cleanup completed. Removed {len(removed)} files.")
    
    # Also clean up docs directory
    docs_patterns = [
        "docs/WORKSPACE_INTEGRATION_COMPLETE.md",
        "docs/WORKFLOW_DOCUMENTATION.md"
    ]
    
    print("\nCleaning up docs directory...")
    docs_removed = remove_files_safely(docs_patterns, "")
    
    print(f"Removed {len(docs_removed)} documentation files.")
    print("\nTotal files removed:", len(removed) + len(docs_removed))
