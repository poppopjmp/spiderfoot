#!/usr/bin/env python3
"""List modules missing dataSource in meta."""
import os
import re

modules_dir = os.path.join(os.path.dirname(__file__), '..', 'modules')

for fn in sorted(os.listdir(modules_dir)):
    if not fn.startswith('sfp_') or not fn.endswith('.py'):
        continue
    if fn.startswith('sfp__') or fn == 'sfp_example.py':
        continue
    path = os.path.join(modules_dir, fn)
    with open(path, encoding='utf-8') as f:
        content = f.read()
    if 'dataSource' not in content:
        name_m = re.search(r'"name":\s*"(.*?)"', content)
        summ_m = re.search(r'"summary":\s*"(.*?)"', content)
        name = name_m.group(1) if name_m else fn
        summ = summ_m.group(1) if summ_m else ''
        print(f'{fn}: {name} | {summ}')
