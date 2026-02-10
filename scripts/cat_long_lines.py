"""Categorize long lines (>120 chars) in spiderfoot/ files."""
from __future__ import annotations
import os

SKIP = {'spiderfoot_pb2_grpc.py', 'spiderfoot_pb2.py', '__pycache__'}
cats = {'sql': 0, 'string': 0, 'comment': 0, 'code': 0, 'url': 0}

for root, dirs, files in os.walk('spiderfoot'):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if not f.endswith('.py') or f in SKIP:
            continue
        fp = os.path.join(root, f)
        for i, line in enumerate(open(fp, encoding='utf-8'), 1):
            if len(line.rstrip()) > 120:
                s = line.strip()
                if 'http://' in s or 'https://' in s:
                    cats['url'] += 1
                elif s.startswith('#'):
                    cats['comment'] += 1
                elif any(kw in s for kw in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE TABLE')):
                    cats['sql'] += 1
                elif '"""' in s or "'''" in s or 'description' in s.lower():
                    cats['string'] += 1
                else:
                    cats['code'] += 1

for cat, cnt in sorted(cats.items(), key=lambda x: -x[1]):
    print(f'  {cat}: {cnt}')
print(f'Total: {sum(cats.values())}')
