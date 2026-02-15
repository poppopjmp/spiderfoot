"""Find open() calls without encoding= parameter in spiderfoot/."""
from __future__ import annotations

import os
import re


def main():
    bare_opens = 0
    locations = []
    for root, dirs, files in os.walk('spiderfoot'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
        for f in files:
            if not f.endswith('.py') or f == 'spiderfoot_pb2_grpc.py':
                continue
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                for i, line in enumerate(fh, 1):
                    if re.search(r'\bopen\s*\(', line) and 'encoding' not in line:
                        # Exclude binary mode opens
                        if any(mode in line for mode in ["'rb'", '"rb"', "'wb'", '"wb"', "'ab'", '"ab"']):
                            continue
                        if 'import' in line:
                            continue
                        bare_opens += 1
                        if len(locations) < 20:
                            locations.append(f"{path}:{i}: {line.strip()[:100]}")

    print(f"open() without encoding= (text mode) in spiderfoot/: {bare_opens}")
    for loc in locations:
        print(f"  {loc}")
    if bare_opens > 20:
        print(f"  ... and {bare_opens - 20} more")


if __name__ == '__main__':
    main()
