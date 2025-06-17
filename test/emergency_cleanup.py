#!/usr/bin/env python3
"""
Emergency cleanup script for when tests hang.
Kills hanging processes and cleans up test artifacts.
"""

import os
import sys
import subprocess
import signal
import glob
import shutil
import psutil


def kill_hanging_processes():
    """Kill any hanging pytest or SpiderFoot processes."""
    print("Looking for hanging test processes...")
    
    killed_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if any(keyword in cmdline.lower() for keyword in ['pytest', 'spiderfoot', 'sf.py']):
                print(f"Killing process {proc.info['pid']}: {proc.info['name']}")
                proc.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    print(f"Killed {killed_count} processes")


def cleanup_test_artifacts():
    """Clean up test database files and temporary files."""
    print("Cleaning up test artifacts...")
    
    cleanup_patterns = [
        "*.test.db",
        "test_*.db", 
        "spiderfoot_test*.db",
        "pytest-debug.log",
        "*.pyc",
        "__pycache__"
    ]
    
    cleaned_count = 0
    for pattern in cleanup_patterns:
        for filepath in glob.glob(pattern, recursive=True):
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                elif os.path.isdir(filepath):
                    shutil.rmtree(filepath)
                cleaned_count += 1
                print(f"Removed: {filepath}")
            except OSError:
                pass
    
    print(f"Cleaned up {cleaned_count} artifacts")


def main():
    print("Emergency test cleanup starting...")
    
    kill_hanging_processes()
    cleanup_test_artifacts()
    
    print("Emergency cleanup completed.")
    print("You can now try running tests again.")


if __name__ == "__main__":
    main()
