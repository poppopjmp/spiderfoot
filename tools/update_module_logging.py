#!/usr/bin/env python3
# Update SpiderFoot modules to use the new logging system
import os
import re
import glob
import argparse


def update_module_logging(file_path, dry_run=False):
    """Update a module to use the new logging system.

    Args:
        file_path (str): Path to the module file
        dry_run (bool): If True, don't modify files, just show what would be done

    Returns:
        tuple: (bool, str) - Success flag and message about changes
    """
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    original_content = content
    changes = []

    # Replace logger import and initialization
    logger_import_pattern = r"from spiderfoot\.logconfig import get_module_logger\s*\n\s*# Get a module-specific logger\s*\nlog = get_module_logger\(__name__\)"
    if re.search(logger_import_pattern, content):
        content = re.sub(
            logger_import_pattern,
            "# Module now uses the logging from the SpiderFootPlugin base class",
            content,
        )
        changes.append("Removed logger import and initialization")

    # Replace log.debug calls with self.debug
    debug_count = len(re.findall(r"log\.debug\(", content))
    if debug_count > 0:
        content = re.sub(r"log\.debug\((.*?)\)", r"self.debug(\1)", content)
        changes.append(
            f"Replaced {debug_count} log.debug calls with self.debug")

    # Replace log.info calls with self.info
    info_count = len(re.findall(r"log\.info\(", content))
    if info_count > 0:
        content = re.sub(r"log\.info\((.*?)\)", r"self.info(\1)", content)
        changes.append(f"Replaced {info_count} log.info calls with self.info")

    # Replace log.error calls with self.error
    error_count = len(re.findall(r"log\.error\(", content))
    if error_count > 0:
        content = re.sub(r"log\.error\((.*?)\)", r"self.error(\1)", content)
        changes.append(
            f"Replaced {error_count} log.error calls with self.error")

    # Replace log.warning calls with self.debug
    warning_count = len(re.findall(r"log\.warning\(", content))
    if warning_count > 0:
        content = re.sub(r"log\.warning\((.*?)\)", r"self.debug(\1)", content)
        changes.append(
            f"Replaced {warning_count} log.warning calls with self.debug")

    # Handle cases where 'self.log' is used instead of 'log'
    self_log_count = len(re.findall(r"self\.log\.debug\(", content))
    if self_log_count > 0:
        content = re.sub(r"self\.log\.debug\((.*?)\)",
                         r"self.debug(\1)", content)
        changes.append(
            f"Replaced {self_log_count} self.log.debug calls with self.debug"
        )

    self_log_info_count = len(re.findall(r"self\.log\.info\(", content))
    if self_log_info_count > 0:
        content = re.sub(r"self\.log\.info\((.*?)\)",
                         r"self.info(\1)", content)
        changes.append(
            f"Replaced {self_log_info_count} self.log.info calls with self.info"
        )

    self_log_error_count = len(re.findall(r"self\.log\.error\(", content))
    if self_log_error_count > 0:
        content = re.sub(r"self\.log\.error\((.*?)\)",
                         r"self.error(\1)", content)
        changes.append(
            f"Replaced {self_log_error_count} self.log.error calls with self.error"
        )

    if content != original_content:
        if not dry_run:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
            return True, f"Updated {file_path}: {', '.join(changes)}"
        else:
            return True, f"Would update {file_path}: {', '.join(changes)}"
    else:
        return False, f"No changes needed for {file_path}"


def main():
    parser = argparse.ArgumentParser(
        description="Update SpiderFoot modules to use the new logging system"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't modify files, just show what would be done",
    )
    parser.add_argument(
        "--module", help="Update specific module (e.g., sfp_example)")
    args = parser.parse_args()

    # Get the SpiderFoot root directory
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    module_dir = os.path.join(root_dir, "modules")

    # Update specific module or all modules
    if args.module:
        if not args.module.startswith("sfp_"):
            args.module = f"sfp_{args.module}"
        module_path = os.path.join(module_dir, f"{args.module}.py")
        if not os.path.exists(module_path):
            print(f"Error: Module {args.module} not found at {module_path}")
            return
        success, message = update_module_logging(module_path, args.dry_run)
        print(message)
    else:
        # Process all module files
        module_files = glob.glob(os.path.join(module_dir, "sfp_*.py"))
        updated = 0
        unchanged = 0

        for module_file in module_files:
            success, message = update_module_logging(module_file, args.dry_run)
            if success:
                updated += 1
                print(message)
            else:
                unchanged += 1

        print(
            f"\nSummary: {updated} modules {'would be' if args.dry_run else 'were'} updated, {unchanged} modules unchanged."
        )


if __name__ == "__main__":
    main()
