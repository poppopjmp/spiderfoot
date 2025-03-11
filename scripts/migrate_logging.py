#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        migrate_logging.py
# Purpose:     Migrate SpiderFoot modules to the new logging system
#
# Author:      SpiderFoot Team
#
# Created:     2023-02-25
# Copyright:   (c) SpiderFoot Team 2023
# Licence:     MIT
# -------------------------------------------------------------------------------

import os
import sys
import glob
import re
import argparse


def update_module_file(filepath, dry_run=False, verbose=False):
    """
    Update a single module file to use the new logging system

    Args:
        filepath (str): Path to the module file
        dry_run (bool): If True, don't write changes to the file
        verbose (bool): If True, print detailed information about changes

    Returns:
        bool: True if changes were made, False otherwise
    """
    if verbose:
        print(f"Processing {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content

    # Replace import statements
    import_pattern = r"from spiderfoot\.logconfig import get_module_logger\s*\n\s*# Get a module-specific logger\s*\nlog = get_module_logger\(__name__\)"
    if re.search(import_pattern, content):
        content = re.sub(
            import_pattern,
            "# Module now uses the logging from the SpiderFootPlugin base class",
            content,
        )
        if verbose:
            print("  - Removed logconfig import")

    # Replace log calls with self methods
    patterns = [
        (r"log\.debug\((.*?)\)", r"self.debug(\1)"),
        (r"log\.info\((.*?)\)", r"self.info(\1)"),
        (r"log\.error\((.*?)\)", r"self.error(\1)"),
        (r"log\.warning\((.*?)\)", r"self.debug(\1)"),
        (r"self\.log\.debug\((.*?)\)", r"self.debug(\1)"),
        (r"self\.log\.info\((.*?)\)", r"self.info(\1)"),
        (r"self\.log\.error\((.*?)\)", r"self.error(\1)"),
        (r"self\.log\.warning\((.*?)\)", r"self.debug(\1)"),
    ]

    for pattern, replacement in patterns:
        matches = re.findall(pattern, content)
        if matches:
            content = re.sub(pattern, replacement, content)
            if verbose:
                print(
                    f"  - Replaced {len(matches)} instances of {pattern.split('(')[0]} with {replacement.split('(')[0]}"
                )

    if content != original_content:
        if not dry_run:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated {filepath}")
        else:
            print(f"Would update {filepath}")
        return True
    else:
        if verbose:
            print("  - No changes needed")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Migrate SpiderFoot modules to the new logging system"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't write any changes to files"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print detailed information"
    )
    parser.add_argument(
        "--module", help="Process only a specific module (e.g., sfp_example)"
    )
    parser.add_argument(
        "--dir", "-d", help="Directory containing SpiderFoot modules")
    args = parser.parse_args()

    # Determine the correct modules directory
    if args.dir:
        modules_dir = args.dir
    else:
        # Try to find the SpiderFoot modules directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(script_dir)
        modules_dir = os.path.join(root_dir, "modules")

        # If modules directory doesn't exist, try other common locations
        if not os.path.isdir(modules_dir):
            potential_dirs = [
                os.path.join(os.getcwd(), "modules"),
                os.path.join(os.getcwd(), "spiderfoot", "modules"),
            ]

            for potential_dir in potential_dirs:
                if os.path.isdir(potential_dir):
                    modules_dir = potential_dir
                    break
            else:
                print("Error: Could not find SpiderFoot modules directory.")
                print(
                    "Please specify the directory with --dir or run from the SpiderFoot root directory."
                )
                sys.exit(1)

    print(f"Using modules directory: {modules_dir}")

    # Process specific module or all modules
    if args.module:
        if not args.module.startswith("sfp_"):
            module_name = f"sfp_{args.module}"
        else:
            module_name = args.module

        module_path = os.path.join(modules_dir, f"{module_name}.py")

        if not os.path.isfile(module_path):
            print(f"Error: Module file not found: {module_path}")
            sys.exit(1)

        update_module_file(module_path, args.dry_run, args.verbose)
    else:
        # Process all module files
        module_files = glob.glob(os.path.join(modules_dir, "sfp_*.py"))

        # Skip template module
        module_files = [f for f in module_files if "sfp_template.py" not in f]

        total = len(module_files)
        updated = 0

        for i, module_file in enumerate(module_files):
            print(f"[{i + 1}/{total}] Processing {os.path.basename(module_file)}...")
            if update_module_file(module_file, args.dry_run, args.verbose):
                updated += 1

        print(
            f"Summary: {updated}/{total} modules {'would be' if args.dry_run else 'were'} updated."
        )


if __name__ == "__main__":
    main()
