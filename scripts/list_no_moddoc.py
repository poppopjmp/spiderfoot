"""List spiderfoot/ files missing module docstrings."""
from __future__ import annotations

import os


def main():
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
                no_moddoc_files.append(path)

    for f in no_moddoc_files:
        print(f)
    print(f"\nTotal: {len(no_moddoc_files)}")


if __name__ == '__main__':
    main()
