"""Survey script to find next cleanup targets."""
from __future__ import annotations

import ast
import os
import re

SKIP_FILES = {'spiderfoot_pb2_grpc.py', 'spiderfoot_pb2.py', '__version__.py'}
SKIP_DIRS = {'__pycache__', '.git', '.venv', '.tox'}


def walk_py(root: str = 'spiderfoot'):
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith('.py') and f not in SKIP_FILES:
                yield os.path.join(dirpath, f)


def check_open_no_encoding():
    count = 0
    for fp in walk_py():
        for i, line in enumerate(open(fp, encoding='utf-8'), 1):
            if 'open(' in line and 'encoding' not in line:
                s = line.strip()
                if s.startswith('#') or s.startswith('from') or s.startswith('import'):
                    continue
                if "'rb'" in line or '"rb"' in line or "'wb'" in line or '"wb"' in line:
                    continue
                if "'ab'" in line or '"ab"' in line:
                    continue
                if 'mock' in line.lower() or 'builtin' in line:
                    continue
                count += 1
    return count


def check_trailing_newline():
    count = 0
    for fp in walk_py():
        content = open(fp, 'rb').read()
        if content and not content.endswith(b'\n'):
            count += 1
            print(f'  No trailing newline: {fp}')
    return count


def check_type_ignore():
    count = 0
    for fp in walk_py():
        for line in open(fp, encoding='utf-8'):
            if '# type: ignore' in line:
                count += 1
    return count


def check_star_imports():
    count = 0
    for fp in walk_py():
        for i, line in enumerate(open(fp, encoding='utf-8'), 1):
            s = line.strip()
            if re.match(r'^from\s+\S+\s+import\s+\*', s):
                count += 1
                print(f'  Star import: {fp}:{i}: {s}')
    return count


def check_bare_except():
    count = 0
    for fp in walk_py():
        for i, line in enumerate(open(fp, encoding='utf-8'), 1):
            if re.search(r'except\s*:', line) and 'except Exception' not in line:
                s = line.strip()
                if s == 'except:':
                    count += 1
                    print(f'  Bare except: {fp}:{i}')
    return count


def check_long_lines():
    count = 0
    for fp in walk_py():
        for i, line in enumerate(open(fp, encoding='utf-8'), 1):
            if len(line.rstrip()) > 120:
                count += 1
    return count


def check_duplicate_blank_lines():
    count = 0
    for fp in walk_py():
        lines = open(fp, encoding='utf-8').readlines()
        prev_blank = False
        for line in lines:
            is_blank = line.strip() == ''
            if is_blank and prev_blank:
                count += 1
            prev_blank = is_blank
    return count


if __name__ == '__main__':
    print(f'1. open() without encoding: {check_open_no_encoding()}')
    print(f'2. Files without trailing newline: {check_trailing_newline()}')
    print(f'3. type: ignore comments: {check_type_ignore()}')
    print(f'4. Star imports: {check_star_imports()}')
    print(f'5. Bare except (no type): {check_bare_except()}')
    print(f'6. Lines > 120 chars: {check_long_lines()}')
    print(f'7. Consecutive blank lines: {check_duplicate_blank_lines()}')
