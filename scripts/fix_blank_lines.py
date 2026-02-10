"""Remove consecutive blank lines in Python files.

Reduces multiple consecutive blank lines to at most 2 (PEP 8 allows
2 blank lines between top-level definitions, 1 inside functions).
"""
from __future__ import annotations

import os
import sys


SKIP_FILES = {'spiderfoot_pb2_grpc.py', 'spiderfoot_pb2.py'}
SKIP_DIRS = {'__pycache__', '.git', '.venv', '.tox'}


def fix_file(filepath: str) -> int:
    """Fix consecutive blank lines in a file. Returns number of lines removed."""
    with open(filepath, encoding='utf-8') as f:
        lines = f.readlines()

    new_lines: list[str] = []
    blank_count = 0
    removed = 0

    for line in lines:
        if line.strip() == '':
            blank_count += 1
            if blank_count <= 2:
                new_lines.append(line)
            else:
                removed += 1
        else:
            blank_count = 0
            new_lines.append(line)

    # Also strip trailing blank lines at end of file (keep at most 1)
    while len(new_lines) > 1 and new_lines[-1].strip() == '' and new_lines[-2].strip() == '':
        new_lines.pop()
        removed += 1

    if removed > 0:
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.writelines(new_lines)

    return removed


def main() -> None:
    root = sys.argv[1] if len(sys.argv) > 1 else 'spiderfoot'
    total_removed = 0
    files_fixed = 0

    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith('.py') or f in SKIP_FILES:
                continue
            fp = os.path.join(dirpath, f)
            removed = fix_file(fp)
            if removed > 0:
                total_removed += removed
                files_fixed += 1
                print(f'  {fp}: removed {removed} blank lines')

    print(f'\nTotal: removed {total_removed} blank lines from {files_fixed} files')


if __name__ == '__main__':
    main()
