#!/usr/bin/env python3
"""Add 'from __future__ import annotations' to files that use typing generics."""

import re
import glob

files = glob.glob('spiderfoot/**/*.py', recursive=True) + glob.glob('modules/**/*.py', recursive=True) + glob.glob('*.py')
files = [f for f in files if '_pb2' not in f and 'test_' not in f]

count = 0
for fpath in sorted(files):
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
        content = fh.read()
    if 'from __future__ import annotations' in content:
        continue
    if not re.search(r'\b(Dict|List|Tuple|Set|Optional|Union)\[', content):
        continue

    lines = content.split('\n')
    i = 0

    # Skip shebang
    if lines and lines[0].startswith('#!'):
        i = 1
    # Skip comment block header (e.g. # -*- coding ... or # Name: ...)
    while i < len(lines) and lines[i].startswith('#'):
        i += 1
    # Check for module docstring
    if i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote = stripped[:3]
            if stripped.count(quote) >= 2 and len(stripped) > 3:
                # Single-line docstring
                i += 1
            else:
                i += 1
                while i < len(lines) and quote not in lines[i]:
                    i += 1
                if i < len(lines):
                    i += 1

    # Skip blank lines after docstring/headers
    while i < len(lines) and lines[i].strip() == '':
        i += 1

    insert_idx = i
    lines.insert(insert_idx, 'from __future__ import annotations')
    lines.insert(insert_idx + 1, '')

    new_content = '\n'.join(lines)
    with open(fpath, 'w', encoding='utf-8', newline='') as fh:
        fh.write(new_content)
    count += 1
    print(f"  Added: {fpath}")

print(f'\nTotal: Added from __future__ import annotations to {count} files')
