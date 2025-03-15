#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         migrate_cherrypy_to_fastapi
# Purpose:      Migration tool to help users migrate from CherryPy to FastAPI
#
# Author:       Agostino Panico <van1sh@van1shland.io>
#
# Created:      01/03/2025
# License:      MIT
# -----------------------------------------------------------------
"""Migration tool to help users migrate from CherryPy to FastAPI.

This script facilitates migrating custom SpiderFoot implementations from
the legacy CherryPy web interface to the new FastAPI implementation.
"""

import os
import sys
import re
import argparse
import shutil
from pathlib import Path
from datetime import datetime


def backup_file(filepath: str) -> str:
    """Create a backup of a file.

    Args:
        filepath: Path to file

    Returns:
        Path to backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.{timestamp}.bak"
    shutil.copy2(filepath, backup_path)
    print(f"Created backup: {backup_path}")
    return backup_path


def check_for_cherrypy_imports(filepath: str) -> bool:
    """Check if file imports CherryPy.

    Args:
        filepath: Path to file

    Returns:
        True if file imports CherryPy
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        return "import cherrypy" in content or "from cherrypy" in content


def check_for_sfwebui_imports(filepath: str) -> bool:
    """Check if file imports SpiderFootWebUi.

    Args:
        filepath: Path to file

    Returns:
        True if file imports SpiderFootWebUi
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        return "from sfwebui" in content or "import sfwebui" in content


def replace_cherrypy_imports(filepath: str) -> bool:
    """Replace CherryPy imports with FastAPI imports.

    Args:
        filepath: Path to file

    Returns:
        True if changes were made
    """
    # Create backup
    backup_file(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace imports
    new_content = re.sub(
        r'import cherrypy',
        'from spiderfoot.cherrypy_compat import cherrypy # Using compatibility layer',
        content
    )

    new_content = re.sub(
        r'from cherrypy',
        'from spiderfoot.cherrypy_compat import cherrypy # Using compatibility layer\nfrom spiderfoot.cherrypy_compat.cherrypy',
        new_content
    )

    # Replace SpiderFootWebUi with SpiderFootFastApi
    new_content = re.sub(
        r'from sfwebui import SpiderFootWebUi',
        'from sfwebui_fastapi import SpiderFootFastApi',
        new_content
    )

    new_content = re.sub(
        r'SpiderFootWebUi\(',
        'SpiderFootFastApi(',
        new_content
    )

    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return content != new_content


def update_startup_script(filepath: str) -> bool:
    """Update startup script to use FastAPI.

    Args:
        filepath: Path to file

    Returns:
        True if changes were made
    """
    # Create backup
    backup_file(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add FastAPI startup code
    cherrypy_start = re.search(r'cherrypy\.quickstart\(', content)
    if cherrypy_start:
        indent = re.match(r'^([ \t]*)', content[content.rfind('\n',
                          0, cherrypy_start.start()) + 1:cherrypy_start.start()])
        indent = indent.group(1) if indent else '    '

        fastapi_code = f"""
{indent}# Check if FastAPI should be used
{indent}if args.fastapi:
{indent}    try:
{indent}        from sfwebui_fastapi_main import main as fastapi_main
{indent}        
{indent}        # Override sys.argv to pass the web server configuration
{indent}        orig_argv = sys.argv
{indent}        sys.argv = [sys.argv[0], 
{indent}                    '--listen', host, 
{indent}                    '--port', str(port)]
{indent}        if args.debug:
{indent}            sys.argv.append('--debug')
{indent}        
{indent}        print(f"Starting FastAPI web server at http://{{host}}:{{port}}/")
{indent}        fastapi_main()
{indent}        sys.argv = orig_argv  # Restore original argv
{indent}        return
{indent}    except Exception as e:
{indent}        print(f"Failed to start FastAPI web server: {{e}}")
{indent}        print("Falling back to CherryPy web server")
{indent}
{indent}# Fall back to CherryPy"""

        new_content = content[:cherrypy_start.start()] + \
            fastapi_code + content[cherrypy_start.start():]

        # Add --fastapi argument
        parser_args = re.search(r'parser\.add_argument\(', content)
        if parser_args:
            last_arg = content.rfind(
                'parser.add_argument(', 0, cherrypy_start.start())
            if last_arg > 0:
                end_of_line = content.find('\n', last_arg)
                fastapi_arg = f"\nparser.add_argument('-F', '--fastapi', help='Use FastAPI web interface instead of CherryPy.', action='store_true')"
                new_content = new_content[:end_of_line + 1] + \
                    fastapi_arg + new_content[end_of_line + 1:]

        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True

    return False


def scan_directory(directory: str) -> list:
    """Scan directory for Python files.

    Args:
        directory: Directory to scan

    Returns:
        List of Python files
    """
    py_files = []

    for root, dirs, files in os.walk(directory):
        # Skip venv directories
        if 'venv' in dirs:
            dirs.remove('venv')
        if '.venv' in dirs:
            dirs.remove('.venv')

        # Skip __pycache__ directories
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')

        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))

    return py_files


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Migrate from CherryPy to FastAPI')
    parser.add_argument('-d', '--directory', default='.',
                        help='Root directory to scan')
    parser.add_argument('-y', '--yes', action='store_true',
                        help='Auto confirm all changes')
    args = parser.parse_args()

    # Get project directory
    project_dir = os.path.abspath(args.directory)
    print(f"Scanning directory: {project_dir}")

    # Find Python files
    py_files = scan_directory(project_dir)
    print(f"Found {len(py_files)} Python files")

    # Find files using CherryPy
    cherrypy_files = []
    for file in py_files:
        if check_for_cherrypy_imports(file):
            cherrypy_files.append(file)

    print(f"Found {len(cherrypy_files)} files using CherryPy")

    # Update startup script - usually sf.py
    sf_py = os.path.join(project_dir, 'sf.py')
    if os.path.exists(sf_py):
        print(f"Updating {sf_py}...")
        if args.yes or input("Update sf.py with FastAPI support? [y/N] ").lower() == 'y':
            if update_startup_script(sf_py):
                print("Updated sf.py successfully")
            else:
                print("Failed to update sf.py")

    # Replace CherryPy imports with compatibility layer
    for file in cherrypy_files:
        filename = os.path.basename(file)
        print(f"\nProcessing {filename}...")
        if args.yes or input(f"Replace CherryPy imports in {filename}? [y/N] ").lower() == 'y':
            if replace_cherrypy_imports(file):
                print(f"Updated {filename}")
            else:
                print(f"No changes made to {filename}")

    print("\nMigration completed.")
    print("Note: You may need to manually review and fix some files.")


if __name__ == "__main__":
    main()
