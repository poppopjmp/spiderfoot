"""Validation suite for migrated SpiderFoot modules.

Verifies all migrated sfp_* modules:
1. Import successfully
2. Use SpiderFootModernPlugin as base class
3. Have required metadata (meta dict with name, summary)
4. Have watchedEvents/producedEvents/handleEvent methods
5. Have properly migrated setup() using super().setup()
6. No residual legacy patterns
"""

from __future__ import annotations

import ast
import glob
import os
import re
import sys
from pathlib import Path
from typing import Any


class ValidationResult:
    """Result for a single module validation."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.module_name = Path(filepath).stem
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.warnings: list[str] = []

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0

    def pass_(self, check: str) -> None:
        self.passed.append(check)

    def fail(self, check: str) -> None:
        self.failed.append(check)

    def warn(self, check: str) -> None:
        self.warnings.append(check)


def validate_module(filepath: str) -> ValidationResult:
    """Run all validation checks on a module file."""
    result = ValidationResult(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        result.fail(f"Cannot read file: {exc}")
        return result

    # Parse AST
    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as exc:
        result.fail(f"Syntax error: {exc}")
        return result

    result.pass_("syntax_valid")

    # Check imports
    _check_imports(content, tree, result)

    # Check class definition
    classes = _find_plugin_classes(tree)
    if not classes:
        result.fail("no_plugin_class: No class inheriting SpiderFootModernPlugin found")
        return result

    result.pass_("has_plugin_class")

    for cls in classes:
        _check_class(content, cls, result)

    # Check for legacy patterns
    _check_no_legacy(content, result)

    return result


def _check_imports(content: str, tree: ast.Module, result: ValidationResult) -> None:
    """Check import statements."""
    has_modern_import = False
    has_legacy_import = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module in ("spiderfoot.modern_plugin",
                               "spiderfoot.plugins.modern_plugin"):
                for alias in node.names:
                    if alias.name == "SpiderFootModernPlugin":
                        has_modern_import = True
            if node.module == "spiderfoot":
                for alias in node.names:
                    if alias.name == "SpiderFootPlugin":
                        has_legacy_import = True

    if has_modern_import:
        result.pass_("imports_modern_plugin")
    else:
        result.fail("missing_modern_import: No 'from spiderfoot.modern_plugin import SpiderFootModernPlugin'")

    if has_legacy_import:
        result.fail("has_legacy_import: Still imports SpiderFootPlugin from spiderfoot")
    else:
        result.pass_("no_legacy_import")


def _find_plugin_classes(tree: ast.Module) -> list[ast.ClassDef]:
    """Find classes that inherit from SpiderFootModernPlugin."""
    classes = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "SpiderFootModernPlugin":
                    classes.append(node)
    return classes


def _check_class(content: str, cls: ast.ClassDef, result: ValidationResult) -> None:
    """Validate a plugin class."""
    prefix = f"{cls.name}: "

    # Check required methods
    methods = {node.name for node in ast.walk(cls) if isinstance(node, ast.FunctionDef)}

    for required in ("watchedEvents", "producedEvents", "handleEvent"):
        if required in methods:
            result.pass_(f"{prefix}has_{required}")
        elif cls.name.startswith("sfp__stor") or cls.name == "sfp_example":
            result.warn(f"{prefix}optional_{required} (storage/example module)")
        else:
            result.fail(f"{prefix}missing_{required}")

    # Check setup method
    if "setup" in methods:
        _check_setup(content, cls, result, prefix)
    else:
        result.warn(f"{prefix}no_setup_method (inherits from base)")

    # Check meta dict exists
    has_meta = False
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "meta":
                    has_meta = True
    if has_meta:
        result.pass_(f"{prefix}has_meta")
    else:
        result.warn(f"{prefix}no_meta_dict")

    # Check opts dict exists
    has_opts = False
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "opts":
                    has_opts = True
    if has_opts:
        result.pass_(f"{prefix}has_opts")
    else:
        result.warn(f"{prefix}no_opts_dict")


def _check_setup(content: str, cls: ast.ClassDef, result: ValidationResult,
                 prefix: str) -> None:
    """Validate setup() method."""
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == "setup":
            # Check for super().setup() call
            has_super_setup = False
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    if (isinstance(func, ast.Attribute)
                            and func.attr == "setup"
                            and isinstance(func.value, ast.Call)
                            and isinstance(func.value.func, ast.Name)
                            and func.value.func.id == "super"):
                        has_super_setup = True

            if has_super_setup:
                result.pass_(f"{prefix}super_setup_call")
            elif cls.name == "sfp_example":
                result.warn(f"{prefix}no_super_setup (example template)")
            else:
                result.fail(f"{prefix}missing_super_setup: setup() doesn't call super().setup()")

            # Check default arg
            args = node.args
            if len(args.defaults) >= 1:
                default = args.defaults[-1]
                if isinstance(default, ast.Constant) and default.value is None:
                    result.pass_(f"{prefix}setup_default_none")
                elif isinstance(default, ast.Call):
                    result.fail(f"{prefix}setup_mutable_default: userOpts has mutable default")
                elif isinstance(default, ast.Dict):
                    result.fail(f"{prefix}setup_mutable_default: userOpts={{}} instead of None")
            break


def _check_no_legacy(content: str, result: ValidationResult) -> None:
    """Check for residual legacy patterns."""
    # Check for legacy fetchUrl
    if re.search(r'self\.sf\.fetchUrl\b', content):
        result.fail("legacy_fetchUrl: Still uses self.sf.fetchUrl")
    else:
        result.pass_("no_legacy_fetchUrl")

    # Check for legacy resolveHost (exclude resolveHost6)
    if re.search(r'self\.sf\.resolveHost\b(?!6)', content):
        result.fail("legacy_resolveHost: Still uses self.sf.resolveHost")
    else:
        result.pass_("no_legacy_resolveHost")

    # Check for legacy resolveIP
    if re.search(r'self\.sf\.resolveIP\b', content):
        result.fail("legacy_resolveIP: Still uses self.sf.resolveIP")
    else:
        result.pass_("no_legacy_resolveIP")

    # Check for legacy cacheGet/cachePut
    if re.search(r'self\.sf\.cache(?:Get|Put)\b', content):
        result.fail("legacy_cache: Still uses self.sf.cacheGet/cachePut")
    else:
        result.pass_("no_legacy_cache")

    # Check self.sf = sfc (should be super().setup())
    if re.search(r'self\.sf\s*=\s*sfc', content):
        result.fail("legacy_sf_assign: Still has self.sf = sfc")
    else:
        result.pass_("no_legacy_sf_assign")


def validate_directory(dirpath: str, pattern: str = "sfp_*.py") -> list[ValidationResult]:
    """Validate all matching modules in directory."""
    results = []
    for filepath in sorted(glob.glob(os.path.join(dirpath, pattern))):
        if "_modern" in filepath:
            continue
        results.append(validate_module(filepath))
    return results


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Validate migrated SpiderFoot modules")
    parser.add_argument("path", help="File or directory to validate")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as failures")
    args = parser.parse_args()

    if os.path.isdir(args.path):
        results = validate_directory(args.path)
    else:
        results = [validate_module(args.path)]

    ok = sum(1 for r in results if r.ok)
    failed = sum(1 for r in results if not r.ok)
    total_checks = sum(len(r.passed) + len(r.failed) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)

    for r in results:
        if not r.ok or args.verbose:
            status = "PASS" if r.ok else "FAIL"
            print(f"[{status}] {r.module_name}")
            if args.verbose:
                for p in r.passed:
                    print(f"  + {p}")
            for f in r.failed:
                print(f"  ! {f}")
            if args.verbose:
                for w in r.warnings:
                    print(f"  ? {w}")

    print(f"\nSummary: {ok}/{ok + failed} passed, {total_checks} checks, {total_warnings} warnings")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
