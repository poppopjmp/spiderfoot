#!/usr/bin/env python3
"""
Pre-commit hook to verify version consistency.
This script can be used as a git pre-commit hook to ensure all version
references are consistent before committing changes.

To install as a git hook:
    cp version_check_hook.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

To run manually:
    python version_check_hook.py
"""

import subprocess
import sys
from pathlib import Path

def check_version_consistency():
    """Check version consistency using the update_version.py script."""
    try:
        # Run the version check
        result = subprocess.run(
            [sys.executable, "update_version.py", "--check"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
            encoding='utf-8',
            errors='replace'
        )
        
        # Check if the command succeeded
        if result.returncode != 0:
            print("ERROR: Version consistency check failed!")
            print(result.stdout)
            print(result.stderr)
            return False
        
        # Check for inconsistency warnings in output
        if "Found inconsistent version references" in result.stdout:
            print("ERROR: Version inconsistency detected!")
            print(result.stdout)
            print("\nTo fix version inconsistencies, run:")
            print("    python update_version.py")
            return False
        
        print("SUCCESS: Version consistency check passed")
        return True
        
    except Exception as e:
        print(f"ERROR: Error running version check: {e}")
        return False

def main():
    """Main function for pre-commit hook."""
    print("Checking version consistency...")
    
    if not check_version_consistency():
        print("\nCommit aborted due to version inconsistency.")
        print("Please fix version references and try again.")
        sys.exit(1)
    
    print("Version consistency verified. Proceeding with commit.")
    sys.exit(0)

if __name__ == "__main__":
    main()
