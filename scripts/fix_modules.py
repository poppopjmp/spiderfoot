#!/usr/bin/env python3
"""
Module compliance fixer for SpiderFoot.

Fixes:
1. Tool modules: old-style setup → super().setup() + from __future__
2. Double-merge: removes redundant self.opts.update(userOpts) after super().setup()
3. Missing self.errorState = False in setup()
4. Missing self.results = self.tempStorage() for modules that use self.results
5. ValueError raises in setup → errorState pattern
6. Missing from __future__ import annotations
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def fix_tool_module_setup(content: str, filename: str) -> tuple[str, list[str]]:
    """Fix old-style self.sf = sfc setup in tool modules."""
    changes = []

    # Pattern: self.sf = sfc followed by manual opts loop
    old_setup = re.search(
        r'(    def setup\(self, sfc, userOpts=None\):\n)'
        r'(        self\.sf = sfc\n)'
        r'(        self\.results = self\.tempStorage\(\)\n)'
        r'(        if userOpts:\n)'
        r'(            for opt in list\(self\.opts\.keys\(\)\):\n)'
        r'(                self\.opts\[opt\] = userOpts\.get\(opt, self\.opts\[opt\]\))',
        content,
    )

    if old_setup:
        old_text = old_setup.group(0)
        new_text = (
            '    def setup(self, sfc, userOpts=None):\n'
            '        super().setup(sfc, userOpts or {})\n'
            '        self.errorState = False\n'
            '        self.results = self.tempStorage()'
        )
        content = content.replace(old_text, new_text)
        changes.append(f"  Fixed old-style setup -> super().setup()")

    return content, changes


def fix_double_merge(content: str, filename: str) -> tuple[str, list[str]]:
    """Remove redundant self.opts.update(userOpts) after super().setup()."""
    changes = []

    # Pattern: super().setup(sfc, userOpts or {}) followed by self.opts.update(userOpts)
    pattern = r'(        super\(\)\.setup\(sfc, userOpts or \{\}\)\n)        self\.opts\.update\(userOpts\)\n'
    if re.search(pattern, content):
        content = re.sub(pattern, r'\1', content)
        changes.append("  Removed redundant self.opts.update(userOpts)")

    return content, changes


def fix_errorstate_reset(content: str, filename: str) -> tuple[str, list[str]]:
    """Add self.errorState = False after super().setup() if missing."""
    changes = []

    # Skip storage and internal modules
    if filename.startswith('sfp__'):
        return content, changes

    # Check if setup exists and calls super().setup()
    has_super_setup = 'super().setup(sfc' in content
    has_errorstate_reset = re.search(r'self\.errorState\s*=\s*False', content)

    # Only for modules that have setup and use errorState but don't reset it
    if has_super_setup and not has_errorstate_reset and 'self.errorState' in content:
        # Insert after super().setup() line
        content = re.sub(
            r'(        super\(\)\.setup\(sfc, userOpts or \{\}\))\n',
            r'\1\n        self.errorState = False\n',
            content,
            count=1,
        )
        changes.append("  Added self.errorState = False reset in setup()")

    return content, changes


def fix_results_init(content: str, filename: str) -> tuple[str, list[str]]:
    """Add self.results = self.tempStorage() if module uses self.results but doesn't init."""
    changes = []

    if filename.startswith('sfp__'):
        return content, changes

    # Check if module uses self.results outside of setup
    uses_results = bool(re.search(r'self\.results\[', content)) or \
                   bool(re.search(r'in self\.results', content))

    if not uses_results:
        return content, changes

    # Check if setup already inits self.results
    setup_match = re.search(
        r'def setup\(self.*?\n(.*?)(?=\n    def |\nclass |\Z)',
        content, re.DOTALL,
    )
    if setup_match and 'self.results' in setup_match.group(1):
        return content, changes

    # Need to add self.results init
    # Insert after errorState or after super().setup()
    if 'self.errorState = False' in content:
        content = re.sub(
            r'(        self\.errorState = False)\n',
            r'\1\n        self.results = self.tempStorage()\n',
            content,
            count=1,
        )
    elif 'super().setup(sfc' in content:
        content = re.sub(
            r'(        super\(\)\.setup\(sfc, userOpts or \{\}\))\n',
            r'\1\n        self.results = self.tempStorage()\n',
            content,
            count=1,
        )
    else:
        return content, changes

    changes.append("  Added self.results = self.tempStorage() in setup()")
    return content, changes


def fix_future_annotations(content: str, filename: str) -> tuple[str, list[str]]:
    """Add from __future__ import annotations if missing."""
    changes = []

    if 'from __future__ import annotations' in content:
        return content, changes

    # Add after docstring if present, or at very top
    # Find the end of the module docstring
    docstring_match = re.match(r'(""".*?""")\n', content, re.DOTALL)
    if docstring_match:
        insert_pos = docstring_match.end()
        content = (
            content[:insert_pos]
            + '\nfrom __future__ import annotations\n'
            + content[insert_pos:]
        )
    else:
        content = 'from __future__ import annotations\n\n' + content

    changes.append("  Added from __future__ import annotations")
    return content, changes


def fix_valueerror_in_setup(content: str, filename: str) -> tuple[str, list[str]]:
    """Replace ValueError raises in setup() with errorState pattern."""
    changes = []

    # Find setup method
    setup_match = re.search(
        r'(    def setup\(self.*?\n)(.*?)(?=\n    def )',
        content, re.DOTALL,
    )
    if not setup_match:
        return content, changes

    setup_body = setup_match.group(2)
    if 'raise ValueError' not in setup_body:
        return content, changes

    # Replace raise ValueError patterns with self.errorState = True; return
    new_body = re.sub(
        r'(\s+)raise ValueError\(["\'](.+?)["\']\)',
        r'\1self.errorState = True\n\1return',
        setup_body,
    )

    if new_body != setup_body:
        content = content.replace(setup_body, new_body)
        changes.append("  Replaced raise ValueError with errorState pattern in setup()")

    return content, changes


def fix_setup_signature(content: str, filename: str) -> tuple[str, list[str]]:
    """Standardize setup() signature to use type hints."""
    changes = []

    # Only fix if using old-style without type hints and it's already been
    # converted to super().setup()
    old_sig = '    def setup(self, sfc, userOpts=None):\n'
    new_sig = '    def setup(self, sfc, userOpts=None):\n'  # Keep simple for compatibility

    return content, changes


def main():
    modules_dir = Path(__file__).resolve().parent.parent / 'modules'
    if not modules_dir.exists():
        print(f"ERROR: modules directory not found at {modules_dir}")
        sys.exit(1)

    dry_run = '--dry-run' in sys.argv
    verbose = '--verbose' in sys.argv or '-v' in sys.argv

    fixers = [
        fix_tool_module_setup,
        fix_double_merge,
        fix_future_annotations,
        fix_errorstate_reset,
        fix_results_init,
        fix_valueerror_in_setup,
    ]

    total_changes = 0
    files_changed = 0

    for fn in sorted(os.listdir(modules_dir)):
        if not fn.startswith('sfp_') or not fn.endswith('.py'):
            continue

        path = modules_dir / fn
        with open(path, encoding='utf-8') as f:
            original = f.read()

        content = original
        all_changes = []

        for fixer in fixers:
            content, changes = fixer(content, fn)
            all_changes.extend(changes)

        if content != original:
            files_changed += 1
            total_changes += len(all_changes)

            if verbose or dry_run:
                print(f"\n{'[DRY RUN] ' if dry_run else ''}Fixing {fn}:")
                for c in all_changes:
                    print(c)

            if not dry_run:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Summary: {total_changes} fixes across {files_changed} files")


if __name__ == '__main__':
    main()
