#!/usr/bin/env python3
"""List all SpiderFoot modules with display names and categories."""
import os
import re

modules = []
for fn in sorted(os.listdir('modules')):
    if not (fn.startswith('sfp_') and fn.endswith('.py')):
        continue
    name = fn[4:-3]
    with open(f'modules/{fn}', encoding='utf-8') as f:
        src = f.read()
    m_name = re.search(r"'name'\s*:\s*[\"'](.+?)[\"']", src)
    m_cat = re.search(r"'categories'\s*:\s*\[([^\]]+)\]", src)
    display = m_name.group(1) if m_name else name
    cat = m_cat.group(1).strip().strip("\"'") if m_cat else "?"
    modules.append((name, display, cat))

print(f"Total: {len(modules)} modules\n")
for name, display, cat in modules:
    print(f"{name:40s} {display:40s} {cat}")
