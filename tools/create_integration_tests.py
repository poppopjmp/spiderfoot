#!/usr/bin/env python3
"""Script to create integration test modules for SpiderFoot modules.

This script will create integration tests that test the modules with
real data, verifying that they integrate correctly with external
services and APIs.
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

        # Special handling for double-underscore modules
        is_special_module = "__" in module_name
        if is_special_module:
            print(f"Special module detected: {module_name}")

            # Determine module type
            if "_stor_" in module_name:
                module_type = "storage"
            elif "_output_" in module_name:
                module_type = "output"
            else:
                module_type = "internal"

            print(f"Module type: {module_type}")

            # For these modules, we'll create a specific fallback without attempting import
            # as they often have special dependencies or initialization requirements
            if module_type in ["storage", "output"]:
                return create_fallback_class(
                    module_path_str, is_special=True, module_type=module_type
                )

        # First ensure we have access to the spiderfoot module
        # by adding the parent directory to the Python path
        parent_dir = os.path.dirname(os.path.dirname(module_path_str))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        try:
            # List of common dependencies that might be missing
            known_dependencies = [
                "psycopg2",  # PostgreSQL
                "elasticsearch",  # Elasticsearch
                "shodan",  # Shodan API
                "censys",  # Censys API
                "IPWhois",  # IPWhois library
                "networkx",  # Network analysis
                "cryptography",  # Cryptography functions
                "pyspark",  # Spark integration
                "kafka",  # Kafka integration
                "pymongo",  # MongoDB
                "dns",  # DNS queries
                "requests_ntlm",  # NTLM authentication
                "M2Crypto",  # Crypto functions
            ]

            # Check if we're trying to import a module with known external dependencies
            has_dependency_issue = False
            for dependency in known_dependencies:
                if dependency.lower() in module_path_str.lower():
                    try:
                        # Try to import the dependency to see if it's installed
                        __import__(dependency)
                    except ImportError:
                        print(
                            f"Module may require the '{dependency}' package. Continuing with fallback."
                        )
                        has_dependency_issue = True
                        return create_fallback_class(
                            module_path_str, dependency_issue=True
                        )

            # Import the module by file path
            spec = importlib.util.spec_from_file_location(
                module_name, module_path_str)
            if not spec:
                raise ImportError(
                    f"Could not create spec for {module_path_str}")

            module = importlib.util.module_from_spec(spec)
            if not module:
                raise ImportError(f"Could not create module from spec")

            sys.modules[module_name] = (
                module  # Add to sys.modules to avoid import errors
            )

            # Use a custom loader that catches import errors
            try:
                spec.loader.exec_module(module)
            except ImportError as e:
                # If it's a dependency error, create a fallback
                if any(dep in str(e).lower() for dep in known_dependencies):
                    dependency = next(
                        (dep for dep in known_dependencies if dep in str(e).lower()),
                        "unknown",
                    )
                    print(
                        f"Missing dependency '{dependency}' for module {module_name}. Using fallback."
                    )
                    return create_fallback_class(module_path_str, dependency_issue=True)
                else:
                    # Re-raise if it's not a known dependency
                    raise

            # Get the main class from the module (match sfp_ pattern)
            for name in dir(module):
                if name.startswith("sfp_"):
                    return name, getattr(module, name)

            # If no class found, try to create a class from the module name
            if hasattr(module, module_name):
                return module_name, getattr(module, module_name)

            # Last resort - create a fallback
            print(f"No sfp_ class found in {module_path_str}, using fallback")
            return create_fallback_class(module_path_str)

        except ImportError as e:
            print(f"Warning: Error during module import: {e}")
            return create_fallback_class(module_path_str, dependency_issue=True)
        except Exception as e:
            print(f"Error during module import: {e}")
            return create_fallback_class(module_path_str)

    except Exception as e:
        print(f"Error importing module {module_path}: {e}")
        return create_fallback_class(module_path_str)


def create_fallback_class(
    file_path, dependency_issue=False, is_special=False, module_type=None
):
    """Create a fallback class for when a module can't be imported."""
    module_name = os.path.basename(file_path).replace(".py", "")

    if dependency_issue:
        print(f"Creating fallback class for {file_path} (dependency issue)")
    elif is_special:
        print(
            f"Creating fallback class for {file_path} (special {module_type} module)")
    else:
        print(f"Creating fallback class for {file_path}")

    # For storage modules
    if module_type == "storage" or "_stor_" in module_name:

        class StorageModule:
            def __init__(self):
                self.descr = f"Storage module: {module_name}"
                self.opts = {
                    "enabled": True,
                    "storagetype": "file",
                }
                self.optdescs = {
                    "enabled": "Enable this module for storing scan results",
                    "storagetype": "Type of storage (file, database, etc.)",
                }

            def watchedEvents(self):
                # Storage modules typically watch all events
                return ["*"]

            def producedEvents(self):
                # Storage modules don't typically produce events
                return []

            def handleEvent(self, evt):
                # Storage modules just store events
                pass

        return module_name, StorageModule()

    # For output modules
    elif module_type == "output" or "_output_" in module_name:

        class OutputModule:
            def __init__(self):
                self.descr = f"Output module: {module_name}"
                self.opts = {
                    "enabled": True,
                    "format": "json",
                }
                self.optdescs = {
                    "enabled": "Enable this module for output",
                    "format": "Output format (json, csv, etc.)",
                }

            def watchedEvents(self):
                # Output modules typically watch all events
                return ["*"]

            def producedEvents(self):
                # Output modules don't typically produce events
                return []

            def handleEvent(self, evt):
                # Output modules process events for output
                pass

        return module_name, OutputModule()

    # For internal modules
    elif is_special or "__" in module_name:

        class InternalModule:
            def __init__(self):
                self.descr = f"Internal module: {module_name}"
                self.opts = {
                    "enabled": True,
                }
                self.optdescs = {
                    "enabled": "Enable this internal module",
                }

            def watchedEvents(self):
                return ["INTERNAL"]

            def producedEvents(self):
                return ["INTERNAL_RESULT"]

            def handleEvent(self, evt):
                # Internal processing
                pass

        return module_name, InternalModule()

    # Standard module fallback
    else:
        # Standard module fallback
        class FallbackModule:
            def __init__(self):
                self.descr = f"Description for {module_name}"
                self.opts = {
                    # Common options many modules have
                    "api_key": "",
                    "checkaffiliates": True,
                }
                self.optdescs = {
                    "api_key": "API key for the service",
                    "checkaffiliates": "Check affiliates?",
                }

            def watchedEvents(self):
                # Common event types that many modules watch
                return ["DOMAIN_NAME", "IP_ADDRESS", "EMAILADDR"]

            def producedEvents(self):
                # Common event types that many modules produce
                return ["MALICIOUS_IPADDR", "MALICIOUS_DOMAIN", "RAW_RIR_DATA"]

        return module_name, FallbackModule()


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
    # Skip storage/output modules
    if "__" in module_file:
        print(f"Skipping storage/output module: {module_file}")
        return False

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

    # Import module to extract class and attributes - handle errors more gracefully
    class_name, module_class = import_module_class(module_path)
    if not class_name:
        print(
            f"Failed to import module class from {module_path}, using fallback...")
        # Ensure we have a minimal class_name for cases where the import completely fails
        class_name = module_name
        if not module_class:
            module_class = object()  # Use a basic object if we have no fallback

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

    # Get all module files - separate regular modules from storage/output modules
    all_module_files = [f for f in os.listdir(
        MODULES_DIR) if f.endswith(".py")]

    # Properly categorize the different module types
    regular_modules = [
        f for f in all_module_files if f.startswith("sfp_") and "__" not in f
    ]
    storage_modules = [
        f for f in all_module_files if f.startswith("sfp__stor_")]
    output_modules = [
        f for f in all_module_files if f.startswith("sfp__output_")]
    internal_modules = [
        f
        for f in all_module_files
        if "__" in f and
        f not in storage_modules and
        f not in output_modules and
        f.startswith("sfp_")
    ]

    print(
        f"Found {len(regular_modules)} regular modules, {len(storage_modules)} storage modules, "
        f"{len(output_modules)} output modules, and {len(internal_modules)} internal modules"
    )
    print(
        "Storage and output modules will be skipped as they don't need integration tests"
    )

    created = 0
    skipped = 0
    failed = 0

    for i, module_file in enumerate(regular_modules):
        print(f"\n[{i + 1}/{len(regular_modules)}] Processing {module_file}...")
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
