#!/usr/bin/env python3
"""
Script to create integration test modules for SpiderFoot modules.
This script will create integration tests that test the modules with real data,
verifying that they integrate correctly with external services and APIs.
"""

import os
import sys
import importlib.util
import re
from pathlib import Path

# Add base directory to path for imports
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(BASE_DIR))

# Directories
TEST_DIR = BASE_DIR / "test" / "integration" / "modules"
MODULES_DIR = BASE_DIR / "modules"

# Create integration test directory if it doesn't exist
os.makedirs(TEST_DIR, exist_ok=True)

# Template for new integration test files
INTEGRATION_TEST_TEMPLATE = """# filepath: {test_file_path}
import pytest
from unittest.mock import patch, MagicMock
import os

from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.{module_file} import {module_class}

# This test requires credentials for the {readable_name} service
# To run this test, set the environment variables:
{env_var_list}

@pytest.mark.skipif(
    not all(os.environ.get(env_var) for env_var in [{env_var_array}]),
    reason="Integration test - requires {readable_name} credentials"
)
class TestModuleIntegration{test_class_name}:
    \"""Integration testing for the {readable_name} module.\"""

    @pytest.fixture
    def module(self):
        \"""Return a {readable_name} module.\"""
        sf = SpiderFoot({options})
        module = {module_class}()
        module.setup(sf, {setup_options})
        return module

    def test_module_produces_events(self, module):
        \"""Test whether the module produces events when given input data.\"""
        target_value = "{test_target}"
        target_type = "DOMAIN_NAME"
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = "{watched_event}"
        event_data = "{test_data}"
        event_module = "test"
        source_event = SpiderFootEvent("ROOT", "", "", "")
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        # We're using a direct call to handleEvent, bypassing the framework's logic
        # for calling it in order to test it directly.
        result = module.handleEvent(evt)

        # Assert that the module produced events
        assert len(module.sf.events) > 0
        
        # Each event should be a dict with certain required fields
        for event in module.sf.events:
            assert event.get('type') is not None
            assert event.get('data') is not None
"""


def get_env_vars_for_module(module_name, module_class):
    """Determine environment variables needed for this module based on opts."""
    env_vars = []

    # Check common module patterns for API keys
    if hasattr(module_class, "opts"):
        for opt_name in module_class.opts:
            if any(
                keyword in opt_name.lower()
                for keyword in ["api_key", "apikey", "username", "password", "secret"]
            ):
                # Convert option name to environment variable name
                env_var = f"SF_{module_name.upper()}_{opt_name.upper()}"
                env_vars.append(env_var)

    return env_vars


def get_watched_event(module_class):
    """Get a sample watched event for the module."""
    if hasattr(module_class, "watchedEvents") and callable(module_class.watchedEvents):
        try:
            watched_events = module_class.watchedEvents()
            if watched_events and len(watched_events) > 0:
                return watched_events[0]
        except:
            pass

    # Default fallback events if we can't determine the watched events
    return "DOMAIN_NAME"


def get_test_data_for_event(event_type):
    """Get sample test data for a given event type."""
    test_data = {
        "DOMAIN_NAME": "example.com",
        "EMAILADDR": "test@example.com",
        "IP_ADDRESS": "8.8.8.8",
        "PHONE_NUMBER": "+12125552368",
        "USERNAME": "testuser",
        "BITCOIN_ADDRESS": "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        "URL": "https://example.com/page",
        "COMPANY_NAME": "Example Company Inc",
    }

    return test_data.get(event_type, "example.com")


def clean_module_name(name):
    """Process a module name to get a clean class name."""
    # Remove sfp_ prefix if present
    if name.startswith("sfp_"):
        name = name[4:]

    # Handle special cases
    special_prefixes = {
        "i": True,  # e.g., sfp_iknowwhatyoudownload -> iKnowWhatYouDownload
        "x": True,  # e.g., sfp_xforce -> XForce
        "h": True,
    }

    # If the name starts with a letter that should be capitalized specially
    first_letter = name[0] if name else ""
    if first_letter in special_prefixes:
        # Keep the first letter lowercase if it's a special case like 'i'
        rest = name[1:] if len(name) > 1 else ""
        parts = rest.split("_")
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


def camel_case_to_readable(name):
    """Convert a camel case name to a more readable format."""
    if not name:
        return ""

    # Special cases for names with lowercase followed by uppercase
    if len(name) > 1 and name[0].islower() and name[1].isupper():
        first_letter = name[0].lower()
        result = name[0].upper() + name[1:]
    else:
        result = name[0].upper()
        for i, c in enumerate(name[1:], 1):
            if c.isupper() and (i == 1 or name[i - 1] != "_"):
                result += " " + c
            else:
                result += c

    # Special case handling for acronyms
    result = re.sub(r"(\w)([A-Z]+)", r"\1 \2", result)

    return result


def import_module_class(module_path):
    """Import a module class dynamically for inspection."""
    try:
        module_path_str = str(module_path)
        module_name = Path(module_path_str).stem

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
            return None, None

        return None, None
    except Exception as e:
        print(f"Error importing module {module_path}: {e}")
        return None, None


def format_options_dict(options):
    """Format Python dict for integration test template."""
    options_str = "{\n"
    for key, value in options.items():
        if isinstance(value, str):
            options_str += f"        '{key}': os.environ.get('SF_{key.upper()}', ''),\n"
        elif isinstance(value, bool):
            options_str += f"        '{key}': {value},\n"
        else:
            options_str += f"        '{key}': {value},\n"
    options_str += "    }"
    return options_str


def create_integration_test(module_file, dry_run=False, verbose=False):
    """Create an integration test file for a given module."""
    module_path = MODULES_DIR / module_file
    module_name = module_file[:-3]  # Remove .py extension
    test_file_name = f"test_integration_{module_file}"
    test_file_path = TEST_DIR / test_file_name

    if verbose:
        print(f"Processing module: {module_file}")
        print(f"Module path: {module_path}")
        print(f"Will create integration test file: {test_file_path}")

    # Skip if integration test file already exists
    if os.path.exists(test_file_path):
        print(
            f"Integration test file {test_file_path} already exists, skipping...")
        return False

    # Import module to extract class and attributes
    class_name, module_class = import_module_class(module_path)
    if not class_name or not module_class:
        print(f"Failed to import module class from {module_path}, skipping...")
        return False

    # Get clean module name for class name
    clean_name = clean_module_name(class_name)
    readable_name = camel_case_to_readable(clean_name)

    # Determine environment variables needed
    env_vars = get_env_vars_for_module(module_name, module_class)
    env_var_list = "\n".join([f"# - {var}" for var in env_vars])
    env_var_array = ", ".join([f"'{var}'" for var in env_vars])
    if not env_vars:
        env_var_list = (
            "# None required, but your module might need API keys or other credentials"
        )
        env_var_array = ""

    # Get a watched event type for testing
    watched_event = get_watched_event(module_class)
    test_data = get_test_data_for_event(watched_event)

    # Prepare options dict
    default_options = {
        "_debug": True,
        "__logging": True,
        "__outputfilter": None,
    }

    # Add module-specific options
    if hasattr(module_class, "opts"):
        for opt, default_val in module_class.opts.items():
            if any(
                keyword in opt.lower()
                for keyword in ["api_key", "apikey", "username", "password", "secret"]
            ):
                # Use environment variable for sensitive options
                default_options[opt] = (
                    f"os.environ.get('SF_{module_name.upper()}_{opt.upper()}', '')"
                )
            else:
                default_options[opt] = default_val

    # Format options for template
    options_str = format_options_dict(default_options)
    setup_options_str = options_str  # In most cases, these will be the same

    # Generate integration test content
    test_content = INTEGRATION_TEST_TEMPLATE.format(
        test_file_path=test_file_path,
        module_file=module_name,
        module_class=class_name,
        test_class_name=clean_name,
        readable_name=readable_name,
        env_var_list=env_var_list,
        env_var_array=env_var_array,
        options=options_str,
        setup_options=setup_options_str,
        watched_event=watched_event,
        test_target="example.com",
        test_data=test_data,
    )

    # Write the integration test file
    if not dry_run:
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(test_content)
        print(f"Created integration test: {test_file_path}")
        return True
    else:
        print(f"Would create integration test: {test_file_path}")
        return True


def create_init_py(dir_path, dry_run=False):
    """Create __init__.py file in the given directory."""
    init_file = dir_path / "__init__.py"
    if not os.path.exists(init_file):
        if not dry_run:
            with open(init_file, "w", encoding="utf-8") as f:
                f.write("# This file makes the directory a Python package\n")
            print(f"Created {init_file}")
        else:
            print(f"Would create {init_file}")


def create_all_integration_tests(dry_run=False):
    """Create integration tests for all modules."""
    # Create necessary directories and __init__.py files
    os.makedirs(TEST_DIR, exist_ok=True)
    create_init_py(TEST_DIR, dry_run)

    # Get all module files
    module_files = [
        f for f in os.listdir(MODULES_DIR) if f.startswith("sfp_") and f.endswith(".py")
    ]

    print(f"Found {len(module_files)} modules to process.")

    created = 0
    skipped = 0
    failed = 0

    for i, module_file in enumerate(module_files):
        print(f"\n[{i + 1}/{len(module_files)}] Processing {module_file}...")
        try:
            result = create_integration_test(module_file, dry_run)
            if result:
                created += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"Failed to create integration test for {module_file}: {e}")
            failed += 1

    print(
        f"\nSummary: {'Would create' if dry_run else 'Created'} {created} integration tests, skipped {skipped}, failed {failed}"
    )


if __name__ == "__main__":
    # Parse command-line arguments
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    specific_file = None

    for arg in sys.argv[1:]:
        if arg.startswith("--file="):
            specific_file = arg[7:]

    print(
        f"{'DRY RUN: ' if dry_run else ''}Creating integration tests for SpiderFoot modules..."
    )

    if specific_file:
        if not specific_file.endswith(".py"):
            specific_file += ".py"

        if not os.path.exists(MODULES_DIR / specific_file):
            print(f"Module file not found: {specific_file}")
        else:
            create_integration_test(specific_file, dry_run, verbose)
    else:
        create_all_integration_tests(dry_run)
