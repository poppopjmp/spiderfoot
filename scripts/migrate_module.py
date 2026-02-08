"""Automated migration tool: SpiderFootPlugin -> SpiderFootModernPlugin.

Mechanically transforms legacy modules to use the modern plugin base
class while preserving all existing functionality.

Transformations applied:
1. Import swap: SpiderFootPlugin -> SpiderFootModernPlugin
2. Base class swap in class declaration
3. setup() refactoring: manual opts merge -> super().setup()
4. self.sf.fetchUrl() -> self.fetch_url()
5. self.sf.resolveHost() -> self.resolve_host()
6. self.sf.resolveHost6() -> self.resolve_host6()
7. self.sf.resolveIP() -> self.reverse_resolve()
8. Mutable default argument fix: dict() -> None

Usage::

    python scripts/migrate_module.py modules/sfp_example.py
    python scripts/migrate_module.py modules/  # batch all
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple


class MigrationResult:
    """Tracks changes made to a single module."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.changes: List[str] = []
        self.warnings: List[str] = []
        self.error: str = ""
        self.original_lines: int = 0
        self.migrated: bool = False

    def add_change(self, desc: str) -> None:
        self.changes.append(desc)

    def add_warning(self, desc: str) -> None:
        self.warnings.append(desc)

    def __repr__(self) -> str:
        status = "OK" if self.migrated else "SKIP"
        return f"MigrationResult({self.filepath}, {status}, {len(self.changes)} changes)"


def _is_legacy_module(content: str) -> bool:
    """Check if file uses legacy SpiderFootPlugin."""
    return bool(
        re.search(r'from\s+spiderfoot\s+import\s+.*SpiderFootPlugin', content)
        or re.search(r'class\s+\w+\(SpiderFootPlugin\)', content)
    )


def _is_already_modern(content: str) -> bool:
    """Check if file already uses SpiderFootModernPlugin."""
    return bool(
        re.search(r'SpiderFootModernPlugin', content)
    )


def migrate_content(content: str, result: MigrationResult) -> str:
    """Apply all migration transformations to file content.

    Returns the transformed content.
    """
    original = content

    # 1. Import swap
    content, n = re.subn(
        r'from\s+spiderfoot\s+import\s+(.*?)SpiderFootPlugin(.*?)$',
        _replace_import,
        content,
        flags=re.MULTILINE,
    )
    if n > 0:
        result.add_change(f"Import: SpiderFootPlugin -> SpiderFootModernPlugin ({n} lines)")

    # Also handle: from spiderfoot import SpiderFootEvent, SpiderFootPlugin
    # where SpiderFootPlugin is one of several imports
    content, n = re.subn(
        r'from\s+spiderfoot\s+import\s+([^#\n]*?)SpiderFootPlugin([^#\n]*)',
        _replace_import_inline,
        content,
        flags=re.MULTILINE,
    )
    if n > 0:
        result.add_change(f"Import (inline): added modern plugin import ({n} lines)")

    # 2. Base class swap
    content, n = re.subn(
        r'class\s+(\w+)\(SpiderFootPlugin\)',
        r'class \1(SpiderFootModernPlugin)',
        content,
    )
    if n > 0:
        result.add_change(f"Base class: -> SpiderFootModernPlugin ({n} classes)")

    # 3. setup() refactoring
    content = _migrate_setup(content, result)

    # 4. self.sf.fetchUrl -> self.fetch_url
    content, n = re.subn(
        r'self\.sf\.fetchUrl\b',
        'self.fetch_url',
        content,
    )
    if n > 0:
        result.add_change(f"fetchUrl -> fetch_url ({n} calls)")

    # 5. self.sf.resolveHost( -> self.resolve_host(
    content, n = re.subn(
        r'self\.sf\.resolveHost\b(?!6)',
        'self.resolve_host',
        content,
    )
    if n > 0:
        result.add_change(f"resolveHost -> resolve_host ({n} calls)")

    # 6. self.sf.resolveHost6 -> self.resolve_host6
    content, n = re.subn(
        r'self\.sf\.resolveHost6\b',
        'self.resolve_host6',
        content,
    )
    if n > 0:
        result.add_change(f"resolveHost6 -> resolve_host6 ({n} calls)")

    # 7. self.sf.resolveIP -> self.reverse_resolve
    content, n = re.subn(
        r'self\.sf\.resolveIP\b',
        'self.reverse_resolve',
        content,
    )
    if n > 0:
        result.add_change(f"resolveIP -> reverse_resolve ({n} calls)")

    result.migrated = content != original
    return content


def _replace_import(m: re.Match) -> str:
    """Replace standalone SpiderFootPlugin import."""
    before = m.group(1).strip().rstrip(',').strip()
    after = m.group(2).strip().lstrip(',').strip()

    parts = []
    if before:
        parts.append(f"from spiderfoot import {before}")
    if after:
        parts.append(f"from spiderfoot import {after}")

    parts.append("from spiderfoot.modern_plugin import SpiderFootModernPlugin")
    return "\n".join(parts)


def _replace_import_inline(m: re.Match) -> str:
    """Handle SpiderFootPlugin mixed with other imports."""
    before = m.group(1).strip().rstrip(',').strip()
    after = m.group(2).strip().lstrip(',').strip()

    remaining = []
    if before:
        remaining.append(before.rstrip(',').strip())
    if after:
        remaining.append(after.lstrip(',').strip())

    parts = []
    remaining_str = ", ".join(r for r in remaining if r)
    if remaining_str:
        parts.append(f"from spiderfoot import {remaining_str}")
    parts.append("from spiderfoot.modern_plugin import SpiderFootModernPlugin")
    return "\n".join(parts)


def _migrate_setup(content: str, result: MigrationResult) -> str:
    """Refactor setup() method to use super().setup()."""
    # Pattern: def setup(self, sfc, userOpts=dict()):
    # Replace default arg
    content, n = re.subn(
        r'def\s+setup\s*\(\s*self\s*,\s*sfc\s*,\s*userOpts\s*=\s*dict\(\)\s*\)',
        'def setup(self, sfc, userOpts=None)',
        content,
    )
    if n > 0:
        result.add_change(f"setup() default arg: dict() -> None ({n})")

    # Also handle: userOpts={}
    content, n = re.subn(
        r'def\s+setup\s*\(\s*self\s*,\s*sfc\s*,\s*userOpts\s*=\s*\{\}\s*\)',
        'def setup(self, sfc, userOpts=None)',
        content,
    )
    if n > 0:
        result.add_change(f"setup() default arg: {{}} -> None ({n})")

    # Replace `self.sf = sfc` (typically the first line in setup)
    # and manual opts merge with super().setup()
    # Pattern: self.sf = sfc followed by optional __dataSource__ and opts loop
    setup_body_pattern = re.compile(
        r'(def setup\(self, sfc, userOpts=None\):.*?\n)'
        r'(\s+)self\.sf\s*=\s*sfc\s*\n'
        r'(?:(\s+)self\.__dataSource__\s*=\s*["\']([^"\']*?)["\']\s*\n)?'
        r'(?:\s+self\.results\s*=\s*self\.tempStorage\(\)\s*\n)?'
        r'(?:\s+(?:for\s+opt\s+in\s+(?:list\()?userOpts(?:\.keys\(\))?(?:\))?:\s*\n\s+self\.opts\[opt\]\s*=\s*userOpts\[opt\]\s*\n))?',
        re.DOTALL,
    )

    def _rewrite_setup(m: re.Match) -> str:
        sig = m.group(1)
        indent = m.group(2)
        data_source = m.group(4) if m.group(4) else None

        lines = [sig]
        lines.append(f"{indent}super().setup(sfc, userOpts or {{}})")
        lines.append(f"{indent}self.results = self.tempStorage()")
        if data_source:
            lines.append(f'{indent}self.__dataSource__ = "{data_source}"')
        lines.append("")
        return "\n".join(lines)

    new_content = setup_body_pattern.sub(_rewrite_setup, content)
    if new_content != content:
        result.add_change("setup() body: replaced manual init with super().setup()")
        content = new_content

    return content


def migrate_file(filepath: str, dry_run: bool = False) -> MigrationResult:
    """Migrate a single module file.

    Parameters
    ----------
    filepath : str
        Path to the .py file.
    dry_run : bool
        If True, don't write changes.

    Returns
    -------
    MigrationResult
    """
    result = MigrationResult(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        result.error = f"Read error: {exc}"
        return result

    result.original_lines = content.count("\n")

    if _is_already_modern(content):
        result.add_warning("Already uses SpiderFootModernPlugin")
        return result

    if not _is_legacy_module(content):
        result.add_warning("Not a legacy SpiderFootPlugin module")
        return result

    migrated = migrate_content(content, result)

    if not result.migrated:
        result.add_warning("No changes needed")
        return result

    if not dry_run:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(migrated)
        except Exception as exc:
            result.error = f"Write error: {exc}"
            result.migrated = False

    return result


def migrate_directory(dirpath: str, dry_run: bool = False,
                      pattern: str = "sfp_*.py") -> List[MigrationResult]:
    """Migrate all matching modules in a directory."""
    import glob
    results = []
    for filepath in sorted(glob.glob(os.path.join(dirpath, pattern))):
        # Skip already-modern modules
        if "_modern" in filepath:
            continue
        result = migrate_file(filepath, dry_run=dry_run)
        results.append(result)
    return results


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Migrate SpiderFoot modules to SpiderFootModernPlugin")
    parser.add_argument("path", help="File or directory to migrate")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't write changes, just report")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if os.path.isdir(args.path):
        results = migrate_directory(args.path, dry_run=args.dry_run)
    else:
        results = [migrate_file(args.path, dry_run=args.dry_run)]

    migrated = sum(1 for r in results if r.migrated)
    skipped = sum(1 for r in results if not r.migrated)
    errors = sum(1 for r in results if r.error)

    for r in results:
        if args.verbose or r.migrated or r.error:
            status = "[OK]" if r.migrated else "[WARN]" if r.warnings else "[ERR]"
            print(f"{status} {r.filepath}")
            for c in r.changes:
                print(f"    + {c}")
            for w in r.warnings:
                print(f"    ? {w}")
            if r.error:
                print(f"    ! {r.error}")

    print(f"\nSummary: {migrated} migrated, {skipped} skipped, {errors} errors")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
