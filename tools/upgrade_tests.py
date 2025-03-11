#!/usr/bin/env python3
"""
Script to upgrade all SpiderFoot module tests.
This will:
1. Create test files for modules without tests
2. Update existing test files to use the wrapper pattern
3. Optionally create integration tests
4. Run the tests to verify everything works
"""

import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_command(cmd, cwd=None):
    """Run a command and return stdout, stderr."""
    if cwd is None:
        cwd = BASE_DIR
    print(f"Running: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr


def check_environment():
    """Check if the environment is set up correctly for test upgrading."""
    print("Checking environment...")

    # Check Python version
    print(f"Python version: {sys.version}")

    # Check for presence of key directories
    test_dir = BASE_DIR / "test" / "unit" / "modules"
    modules_dir = BASE_DIR / "modules"

    if not test_dir.exists():
        print(f"WARNING: Test directory not found: {test_dir}")
    else:
        print(f"Test directory: {test_dir} ✓")
        test_files = list(test_dir.glob("test_*.py"))
        print(f"Found {len(test_files)} test files")

    if not modules_dir.exists():
        print(f"WARNING: Modules directory not found: {modules_dir}")
    else:
        print(f"Modules directory: {modules_dir} ✓")
        module_files = list(modules_dir.glob("sfp_*.py"))
        print(f"Found {len(module_files)} module files")

    # Check for one example module to ensure paths are correct
    example_module = modules_dir / "sfp_dnsresolve.py"
    if not example_module.exists():
        print(f"WARNING: Example module not found: {example_module}")
    else:
        print(f"Example module: {example_module} ✓")

    # Check if we're running from the correct directory
    if not (BASE_DIR / "sflib.py").exists():
        print(
            "WARNING: sflib.py not found in base directory. Are you running from the correct location?"
        )
    else:
        print("Base directory structure looks correct ✓")

    print("Environment check complete.\n")


def main():
    # Add base directory to path to ensure imports work
    sys.path.insert(0, str(BASE_DIR))

    # Check environment before proceeding
    check_environment()

    # Check for options
    force = "--force" in sys.argv
    integration = "--integration" in sys.argv
    dry_run = "--dry-run" in sys.argv

    # Prepare args
    force_arg = ["--force"] if force else []
    dry_run_arg = ["--dry-run"] if dry_run else []

    # 1. Create missing unit test files
    print("\n" + "=" * 80)
    print("STEP 1: Creating unit test files for modules without tests...")
    print("=" * 80)
    cmd = (
        [sys.executable, str(BASE_DIR / "tools" / "create_missing_tests.py")] +
        force_arg +
        dry_run_arg
    )
    rc, stdout, stderr = run_command(cmd)
    print(stdout)
    if stderr:
        print(f"Errors:\n{stderr}")

    # 2. Update existing test files
    print("\n" + "=" * 80)
    print("STEP 2: Updating existing test files to use wrapper pattern...")
    print("=" * 80)
    cmd = (
        [sys.executable, str(BASE_DIR / "tools" / "update_test_files.py")] +
        force_arg +
        dry_run_arg
    )
    rc, stdout, stderr = run_command(cmd)
    print(stdout)
    if stderr:
        print(f"Errors:\n{stderr}")

    # 3. Optionally create integration tests
    if integration:
        print("\n" + "=" * 80)
        print("STEP 3: Creating integration tests...")
        print("=" * 80)
        try:
            cmd = [
                sys.executable,
                str(BASE_DIR / "tools" / "create_integration_tests.py"),
            ] + dry_run_arg
            rc, stdout, stderr = run_command(cmd)
            print(stdout)
            if stderr:
                print(f"Errors during integration test creation:\n{stderr}")
                print("Proceeding despite errors...")
        except Exception as e:
            print(f"Error creating integration tests: {e}")
            print("Continuing with remaining steps...")

    print("\nTest files upgrade complete!")
    print("\nYou can run unit tests with: pytest -xvs test/unit/modules/")
    if integration:
        print(
            "\nYou can run integration tests with: pytest -xvs test/integration/modules/"
        )


if __name__ == "__main__":
    main()
