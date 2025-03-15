#!/usr/bin/env python3
"""Script to create test modules for SpiderFoot modules that don't have test
classes yet.

This will scan the modules directory, identify modules without test
files, and generate appropriate test files using our wrapper pattern.
"""

import os
import sys
import importlib.util
from pathlib import Path

# Add base directory to path for imports
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(BASE_DIR))

TEST_DIR = BASE_DIR / "test" / "unit" / "modules"
MODULES_DIR = BASE_DIR / "modules"

# Template for new test files
TEST_FILE_TEMPLATE = """# filepath: {test_file_path}
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.{module_file} import {module_class}
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


class TestModule{test_class_name}(SpiderFootModuleTestCase):
    \"""Test {readable_name} module.\"""

    def setUp(self):
        \"""Set up before each test.\"""
        super().setUp()
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()
        
        # Create module wrapper class dynamically
        module_attributes = {{
            'descr': "{module_description}",
            # Add module-specific options
{module_options}
        }}
        
        self.module_class = self.create_module_wrapper(
            {module_class},
            module_attributes=module_attributes
        )

    def test_opts(self):
        \"""Test the module options.\"""
        module = self.module_class()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        \"""Test setup function.\"""
        sf = SpiderFoot(self.default_options)
        module = self.module_class()
        module.setup(sf, self.default_options)
        self.assertIsNotNone(module.options)
        self.assertTrue('_debug' in module.options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        \"""Test the watchedEvents function returns a list.\"""
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        \"""Test the producedEvents function returns a list.\"""
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)
"""


def camel_case_to_readable(name):
    """Convert a camel case name to a more readable format."""
    if not name:
        return ""

    # Add spaces before uppercase letters and ensure first letter is capitalized
    result = name[0].upper()
    for c in name[1:]:
        if c.isupper():
            result += " " + c
        else:
            result += c

    return result


def clean_module_name(name):
    """Process a module name to get a clean class name."""
    # Remove sfp_ prefix if present
    if name.startswith("sfp_"):
        name = name[4:]

    # Handle special cases
    special_prefixes = {
        "i": True,  # e.g., sfp_iknowwhatyoudownload -> iKnowWhatYouDownload
        "x": True,  # e.g., sfp_xforce -> XForce
        "h": True,  # Hypothetical example
    }

    # If the name starts with a letter that should be capitalized specially
    first_letter = name[0] if name else ""
    if first_letter in special_prefixes:
        # Keep the first letter lowercase if it's a special case like 'i'
        rest = name[1:] if len(name) > 1 else ""
        parts = rest.split("_")
        # Capitalize the first part (after the special letter)
        camel_case = (
            first_letter +
            parts[0].capitalize() +
            "".join(part.capitalize() for part in parts[1:])
        )
    else:
        # Regular case conversion
        parts = name.split("_")
        camel_case = parts[0] + "".join(part.capitalize()
                                        for part in parts[1:])

    # Capitalize first letter for test class naming convention
    # unless it's a special case like 'i'
    if first_letter not in special_prefixes:
        camel_case = camel_case[0].upper() + camel_case[1:]

    return camel_case


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


def import_module_class(module_path):
    """Import a module class dynamically for inspection."""
    try:
        module_path_str = str(module_path)
        module_name = Path(module_path_str).stem

        # First try direct import
        try:
            # This ensures the spiderfoot module can be found
            import spiderfoot

            # Import the module
            spec = importlib.util.spec_from_file_location(
                module_name, module_path_str)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the main class from the module (match sfp_ pattern)
            for name in dir(module):
                if name.startswith("sfp_"):
                    return name, getattr(module, name)
        except ImportError as e:
            print(f"Warning: Error during module import: {e}")
            # Fall back to extracting information without importing
            return extract_class_name_from_file(module_path_str)

        return None, None
    except Exception as e:
        print(f"Error importing module {module_path}: {e}")
        return None, None


def extract_class_name_from_file(file_path):
    """Extract module class name from file without importing."""
    try:
        module_name = os.path.basename(file_path).replace(".py", "")
        class_name = module_name

        # Create a fake class for testing
        class FakeModule:
            def __init__(self):
                self.descr = f"Description for {module_name}"
                self.opts = {}
                self.optdescs = {}

            def watchedEvents(self):
                return []

            def producedEvents(self):
                return []

        return class_name, FakeModule()
    except Exception as e:
        print(f"Error extracting class info from {file_path}: {e}")
        return None, None


def extract_module_attributes(module_class):
    """Extract important attributes from a module class."""
    attributes = {}

    # Try to extract description
    if hasattr(module_class, "descr") and module_class.descr:
        attributes["descr"] = module_class.descr
    else:
        attributes["descr"] = "Module description unavailable"

    # Try to extract opts and optdescs
    if hasattr(module_class, "opts") and module_class.opts:
        attributes["opts"] = module_class.opts

    if hasattr(module_class, "optdescs") and module_class.optdescs:
        attributes["optdescs"] = module_class.optdescs

    return attributes


def get_missing_test_files():
    """Find modules that don't have corresponding test files."""
    # Get all module files
    module_files = [
        f for f in os.listdir(MODULES_DIR) if f.startswith("sfp_") and f.endswith(".py")
    ]

    # Get all test files
    test_files = [
        f
        for f in os.listdir(TEST_DIR)
        if f.startswith("test_sfp_") and f.endswith(".py")
    ]

    # Convert test files to match module file names
    test_modules = [f.replace("test_", "") for f in test_files]

    # Find modules without tests
    missing_tests = []
    for module_file in module_files:
        if module_file not in test_modules:
            missing_tests.append(module_file)

    return missing_tests


def create_test_file(module_file, dry_run=False, verbose=False):
    """Create a test file for a given module file."""
    module_path = MODULES_DIR / module_file
    module_name = module_file[:-3]  # Remove .py extension
    test_file_name = f"test_{module_file}"
    test_file_path = TEST_DIR / test_file_name

    if verbose:
        print(f"Processing module: {module_file}")
        print(f"Module path: {module_path}")
        print(f"Will create test file: {test_file_path}")

    # Skip if test file already exists
    if os.path.exists(test_file_path):
        print(f"Test file {test_file_path} already exists, skipping...")
        return False

    # Import module to extract class and attributes
    class_name, module_class = import_module_class(module_path)
    if not class_name or not module_class:
        print(f"Failed to import module class from {module_path}, skipping...")
        return False

    # Extract module attributes
    module_attrs = extract_module_attributes(module_class)
    formatted_opts = format_python_dict(module_attrs.get("opts", {}))

    # Clean up class name for test class
    clean_name = clean_module_name(class_name)
    readable_name = camel_case_to_readable(clean_name)

    # Generate test file content
    test_file_content = TEST_FILE_TEMPLATE.format(
        test_file_path=test_file_path,
        module_file=module_name,
        module_class=class_name,
        test_class_name=clean_name,
        readable_name=readable_name,
        module_description=module_attrs.get(
            "descr", "Module description unavailable"),
        module_options=formatted_opts,
    )

    # Write the test file
    if not dry_run:
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(test_file_content)
        print(f"Created test file: {test_file_path}")
        return True
    else:
        print(f"Would create test file: {test_file_path}")
        return True


def create_missing_test_files(dry_run=False):
    """Create test files for all modules that don't have them."""
    missing_tests = get_missing_test_files()

    if not missing_tests:
        print("No missing test files found.")
        return

    print(f"Found {len(missing_tests)} modules without test files:")
    for module_file in missing_tests:
        print(f"  - {module_file}")

    if dry_run:
        print("\nDRY RUN: Not creating any files.")

    created = 0
    skipped = 0
    failed = 0

    for i, module_file in enumerate(missing_tests):
        print(f"\n[{i + 1}/{len(missing_tests)}] Processing {module_file}...")
        try:
            result = create_test_file(module_file, dry_run)
            if result:
                created += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"Failed to create test file for {module_file}: {e}")
            failed += 1

    print(
        f"\nSummary: {'Would create' if dry_run else 'Created'} {created} test files, skipped {skipped}, failed {failed}"
    )


if __name__ == "__main__":
    # Check command line arguments
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    specific_file = None

    for arg in sys.argv[1:]:
        if arg.startswith("--file="):
            specific_file = arg[7:]

    print(
        f"{'DRY RUN: ' if dry_run else ''}Creating missing test files for SpiderFoot modules..."
    )

    if verbose:
        print(f"BASE_DIR: {BASE_DIR}")
        print(f"TEST_DIR: {TEST_DIR}")
        print(f"MODULES_DIR: {MODULES_DIR}")

    if specific_file:
        if not specific_file.endswith(".py"):
            specific_file += ".py"

        if not os.path.exists(MODULES_DIR / specific_file):
            print(f"Module file not found: {specific_file}")
        else:
            create_test_file(specific_file, dry_run)
    else:
        create_missing_test_files(dry_run)
