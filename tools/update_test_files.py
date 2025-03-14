#!/usr/bin/env python3
"""Script to update SpiderFoot module test files to use the new wrapper
pattern. This script will modify test files to use the create_module_wrapper
method from the SpiderFootModuleTestCase class.

Enhanced version with better module detection and more robust handling.
"""

import os
import re
import sys
import glob
import importlib.util
from pathlib import Path

# Path configuration
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_DIR = BASE_DIR / "test" / "unit" / "modules"
MODULES_DIR = BASE_DIR / "modules"

# Regular expressions for matching patterns in test files
MODULE_IMPORT_RE = re.compile(r"from modules\.([^\s]+) import ([^\s]+)")
TEST_CLASS_RE = re.compile(
    r"class TestModule([a-zA-Z0-9_]*)\s*\(\s*SpiderFootModuleTestCase\s*\):"
)
MODULE_INSTANTIATION_RE = re.compile(
    r"(\s+)([a-zA-Z_]+)\s*=\s*([a-zA-Z0-9_]+)\(\)")

# Template for the updated setUp method
SETUP_TEMPLATE = """
    def setUp(self):

        super().setUp()
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()
        
        # Create module wrapper class dynamically
        module_attributes = {
            'descr': "{module_description}",
            # Add module-specific options
            {module_options}
        }
        
        self.module_class = self.create_module_wrapper(
            {module_name},
            module_attributes=module_attributes
        )
"""

# Template for test methods
TEST_METHODS_TEMPLATE = """
    def test_opts(self):

        module = self.module_class()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):

        sf = SpiderFoot(self.default_options)
        module = self.module_class()
        module.setup(sf, self.default_options)
        self.assertIsNotNone(module.options)
        self.assertTrue('_debug' in module.options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):

        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):

        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)
"""


def import_module_class(module_path):
    """Import a module class dynamically for inspection."""
    try:
        # Make sure module_path is a string, not a Path object
        module_path_str = str(module_path)

        spec = importlib.util.spec_from_file_location(
            Path(module_path_str).stem, module_path_str
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get the main class from the module (match sfp_ pattern)
        for name in dir(module):
            if name.startswith("sfp_"):
                return getattr(module, name)

        return None
    except Exception as e:
        print(f"Error importing module {module_path}: {e}")
        return None


def extract_module_attributes(module_class):
    """Extract important attributes from a module class."""
    attributes = {}

    # Try to extract description
    if hasattr(module_class, "descr"):
        attributes["descr"] = module_class.descr
    else:
        attributes["descr"] = "Module description unavailable"

    # Try to extract opts and optdescs
    if hasattr(module_class, "opts") and module_class.opts:
        attributes["opts"] = module_class.opts

    if hasattr(module_class, "optdescs") and module_class.optdescs:
        attributes["optdescs"] = module_class.optdescs

    return attributes


def format_python_dict(python_dict, indent=12):
    """Format a Python dictionary for insertion into code with proper
    indentation."""
    if not python_dict:
        return ""

    indent_str = " " * indent
    lines = []
    lines.append(f"{indent_str}'opts': {{")

    for key, value in python_dict.items():
        if isinstance(value, str):
            # Escape any single quotes in the string
            value = value.replace("'", "\\'")
            lines.append(f"{indent_str}    '{key}': '{value}',")
        elif isinstance(value, bool):
            lines.append(f"{indent_str}    '{key}': {str(value)},")
        else:
            lines.append(f"{indent_str}    '{key}': {value},")

    lines.append(f"{indent_str}}}")

    return "\n".join(lines)


def update_test_file(file_path, dry_run=False, force=False):
    """Update a single test file to use the wrapper pattern."""
    try:
        # Convert to string if it's a Path object
        file_path_str = str(file_path)

        # Skip template and base files
        if (
            "test_module_base.py" in file_path_str or
            "test_module_template.py" in file_path_str
        ):
            print(f"Skipping base/template file: {file_path_str}")
            return False

        with open(file_path_str, "r", encoding="utf-8", errors="replace") as file:
            content = file.read()

        # Extract module import
        module_import = MODULE_IMPORT_RE.search(content)
        if not module_import:
            print(f"No module import found in {file_path_str}, skipping...")
            return False

        module_file = module_import.group(1)
        module_name = module_import.group(2)

        # Extract test class name with improved detection
        test_class_match = re.search(
            r"class\s+(\w+)\s*\(\s*SpiderFootModuleTestCase\s*\):", content
        )
        if not test_class_match:
            print(f"No test class found in {file_path_str}, skipping...")
            return False

        test_class_name = test_class_match.group(1)
        print(f"Found test class: {test_class_name}")

        # Check if file already has our wrapper pattern (but proceed if force=True)
        if not force and "self.module_class = self.create_module_wrapper(" in content:
            print(
                f"File {file_path_str} already uses wrapper pattern, skipping...")
            return False

        # Load the actual module to extract attributes
        module_path = MODULES_DIR / f"{module_file}.py"
        if not os.path.exists(module_path):
            print(f"Module file {module_path} not found, using fallback...")
            module_class = None
            module_attrs = {"descr": "Module description unavailable"}
            formatted_opts = ""
        else:
            module_class = import_module_class(module_path)
            if module_class:
                module_attrs = extract_module_attributes(module_class)
                formatted_opts = format_python_dict(
                    module_attrs.get("opts", {}))
            else:
                module_attrs = {"descr": "Module description unavailable"}
                formatted_opts = ""

        # Make sure the necessary imports are included
        if "unittest.mock" not in content:
            if "import unittest" in content:
                content = content.replace(
                    "import unittest",
                    "import unittest\nfrom unittest.mock import patch, MagicMock",
                )
            else:
                content = "from unittest.mock import patch, MagicMock\n" + content

        if "from sflib import SpiderFoot" not in content:
            content = "from sflib import SpiderFoot\n" + content

        # Replace any direct module instantiation patterns
        content = re.sub(rf"\b{module_name}\(\)",
                         "self.module_class()", content)

        # Add or update setUp method
        setup_content = SETUP_TEMPLATE.format(
            module_name=module_name,
            module_description=module_attrs.get(
                "descr", "Module description unavailable"
            ),
            module_options=formatted_opts,
        )

        if "def setUp(self):" in content:
            # Replace existing setUp method
            content = re.sub(
                r"def setUp\(self\):.*?(?=\n    def |$)",
                setup_content,
                content,
                flags=re.DOTALL,
            )
        else:
            # Add setUp method after class definition
            insert_point = content.find("):") + 2
            content = (
                content[:insert_point] + "\n" +
                setup_content + content[insert_point:]
            )

        # Check if we need to update test methods
        basic_tests_exist = all(
            method in content
            for method in [
                "test_opts",
                "test_setup",
                "test_watchedEvents_should_return_list",
                "test_producedEvents_should_return_list",
            ]
        )

        if not basic_tests_exist:
            # Find a good insertion point for test methods
            if "def test_" in content:
                # Insert before first test method
                match = re.search(r"\n    def test_", content)
                if match:
                    insert_point = match.start()
                    content = (
                        content[:insert_point] +
                        TEST_METHODS_TEMPLATE +
                        content[insert_point:]
                    )
            else:
                # Append at the end of the class
                content += TEST_METHODS_TEMPLATE

        # Write the updated content back
        if not dry_run:
            with open(file_path_str, "w", encoding="utf-8") as file:
                file.write(content)

        print(f"{'Would update' if dry_run else 'Updated'} {file_path_str}")
        return True

    except Exception as e:
        print(f"Error updating {file_path_str}: {e}")
        return False


def camel_case_to_readable(name):
    """Convert a camel case name to a more readable format with special
    handling."""
    if not name:
        return ""

    # Special case for names starting with lowercase letters followed by uppercase
    if len(name) > 1 and name[0].islower() and name[1].isupper():
        # Example: iCertspotter -> Certspotter
        # We keep the first letter but format it appropriately
        first_letter = name[0]
        result = first_letter + " " + name[1:]
    else:
        # Normal camel case processing
        result = name[0]
        for c in name[1:]:
            if c.isupper():
                result += " " + c
            else:
                result += c

    # Ensure first letter of output is capitalized
    if result:
        result = result[0].upper() + result[1:]

    return result


def update_all_test_files(dry_run=False, force=False):
    """Update all test files in the test directory."""
    count = 0
    skipped = 0
    failed = 0

    # Use str(TEST_DIR) to convert Path to string and use glob
    test_files = glob.glob(f"{TEST_DIR}/test_sfp_*.py")
    total = len(test_files)

    print(f"Found {total} test files to process")

    for i, file_path in enumerate(test_files):
        print(f"[{i + 1}/{total}] Processing {file_path}...")

        try:
            result = update_test_file(file_path, dry_run, force)
            if result:
                count += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"Failed to process {file_path}: {e}")
            failed += 1

    print(
        f"\nSummary: {'Would update' if dry_run else 'Updated'} {count} files, skipped {skipped} files, failed {failed} files"
    )


if __name__ == "__main__":
    # Check command line arguments
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    specific_file = None

    for arg in sys.argv[1:]:
        if arg.startswith("--file="):
            specific_file = arg[7:]

    print(
        f"{'DRY RUN: ' if dry_run else ''}Updating SpiderFoot test files to use the wrapper pattern..."
    )

    if specific_file:
        file_path = Path(specific_file)
        if not file_path.is_absolute():
            file_path = TEST_DIR / file_path

        if os.path.exists(file_path):
            print(f"Processing specific file: {file_path}")
            update_test_file(file_path, dry_run, force)
        else:
            print(f"File not found: {file_path}")
    else:
        update_all_test_files(dry_run, force)
