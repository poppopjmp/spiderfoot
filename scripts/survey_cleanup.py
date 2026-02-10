"""Survey remaining cleanup areas in the codebase."""
from __future__ import annotations

import ast
import os
import re


def main():
    # 1. Count broad except Exception (all patterns, not just pass)
    exc_broad = 0
    exc_locations = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', '.venv', 'test')]
        for f in files:
            if not f.endswith('.py'):
                continue
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                for i, line in enumerate(fh, 1):
                    if re.match(r'\s*except\s+Exception\b', line):
                        exc_broad += 1
                        exc_locations.append(f"{path}:{i}: {line.strip()}")
    print(f"Broad except Exception (all patterns): {exc_broad}")
    for loc in exc_locations[:20]:
        print(f"  {loc}")
    if len(exc_locations) > 20:
        print(f"  ... and {len(exc_locations) - 20} more")

    # 2. spiderfoot/ files without module docstring (excl __init__)
    no_moddoc = 0
    no_moddoc_files = []
    for root, dirs, files in os.walk('spiderfoot'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
        for f in files:
            if not f.endswith('.py') or f.startswith('__'):
                continue
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                content = fh.read()
            if not content.strip():
                continue
            # Check for module docstring after future imports and comments
            lines = content.split('\n')
            found_docstring = False
            for line in lines:
                stripped = line.strip()
                if stripped == '' or stripped.startswith('#') or stripped.startswith('from __future__'):
                    continue
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    found_docstring = True
                break
            if not found_docstring:
                no_moddoc += 1
                no_moddoc_files.append(path)
    print(f"\nspiderfoot/ files without module docstring (excl __init__): {no_moddoc}")
    for f in no_moddoc_files[:10]:
        print(f"  {f}")
    if len(no_moddoc_files) > 10:
        print(f"  ... and {len(no_moddoc_files) - 10} more")

    # 3. Functions without docstrings in spiderfoot/
    no_funcdoc = 0
    no_funcdoc_examples = []
    for root, dirs, files in os.walk('spiderfoot'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
        for f in files:
            if not f.endswith('.py') or f == 'spiderfoot_pb2_grpc.py':
                continue
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                content = fh.read()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    has_doc = (
                        node.body
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    )
                    if not has_doc:
                        no_funcdoc += 1
                        if len(no_funcdoc_examples) < 10:
                            no_funcdoc_examples.append(f"{path}:{node.lineno}: {node.name}")
    print(f"\nspiderfoot/ functions without docstrings: {no_funcdoc}")
    for ex in no_funcdoc_examples:
        print(f"  {ex}")
    if no_funcdoc > 10:
        print(f"  ... and {no_funcdoc - 10} more")

    # 4. print() in spiderfoot/ (not test)
    prints = 0
    print_locations = []
    for root, dirs, files in os.walk('spiderfoot'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
        for f in files:
            if not f.endswith('.py'):
                continue
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                for i, line in enumerate(fh, 1):
                    if re.match(r'\s*print\s*\(', line):
                        prints += 1
                        if len(print_locations) < 10:
                            print_locations.append(f"{path}:{i}: {line.strip()}")
    print(f"\nprint() in spiderfoot/: {prints}")
    for loc in print_locations:
        print(f"  {loc}")

    # 5. Magic numbers / hardcoded strings that could be constants
    # 6. Long functions (>50 lines)
    long_funcs = 0
    for root, dirs, files in os.walk('spiderfoot'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
        for f in files:
            if not f.endswith('.py') or f == 'spiderfoot_pb2_grpc.py':
                continue
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                content = fh.read()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, 'end_lineno', node.lineno)
                    length = end - node.lineno + 1
                    if length > 80:
                        long_funcs += 1
    print(f"\nFunctions >80 lines in spiderfoot/: {long_funcs}")

    # 7. TODO/FIXME/HACK comments in spiderfoot/
    todo_count = 0
    for root, dirs, files in os.walk('spiderfoot'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
        for f in files:
            if not f.endswith('.py'):
                continue
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                for line in fh:
                    if re.search(r'#\s*(TODO|FIXME|HACK|XXX)\b', line, re.IGNORECASE):
                        todo_count += 1
    print(f"\nTODO/FIXME/HACK comments in spiderfoot/: {todo_count}")


if __name__ == '__main__':
    main()
