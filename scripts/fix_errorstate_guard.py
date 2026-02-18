#!/usr/bin/env python3
"""
Fix P0 issue: modules that set self.errorState = True but never check it in handleEvent().
Adds `if self.errorState: return` guard at the top of handleEvent().
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def fix_missing_errorstate_guard(filepath: str) -> bool:
    """Add errorState guard to handleEvent if missing."""
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # Skip if no errorState usage at all
    if 'self.errorState' not in content:
        return False

    # Check if handleEvent already has the guard
    handle_match = re.search(
        r'(    def handleEvent\(self.*?\).*?:\n)(.*?)(?=\n    def |\nclass |\Z)',
        content, re.DOTALL,
    )
    if not handle_match:
        return False

    handle_body = handle_match.group(2)

    # Already has errorState check early in handleEvent
    # Look for it in first 10 lines
    body_lines = handle_body.split('\n')[:10]
    for line in body_lines:
        if 'self.errorState' in line:
            return False

    # Add the guard after the method signature
    # Find the right insertion point — after docstring if present
    old_header = handle_match.group(1)

    # Check for docstring
    stripped = handle_body.lstrip('\n')
    if stripped.lstrip().startswith('"""') or stripped.lstrip().startswith("'''"):
        # Find end of docstring
        q = '"""' if '"""' in stripped[:10] else "'''"
        first_q = stripped.find(q)
        second_q = stripped.find(q, first_q + 3)
        if second_q >= 0:
            docstring_end = second_q + 3
            # Find end of docstring line
            nl_after = stripped.find('\n', docstring_end)
            if nl_after >= 0:
                before_doc = handle_body[:len(handle_body) - len(stripped)]
                doc_part = stripped[:nl_after + 1]
                rest = stripped[nl_after + 1:]
                new_body = before_doc + doc_part + '\n        if self.errorState:\n            return\n\n' + rest
                content = content.replace(
                    old_header + handle_body,
                    old_header + new_body,
                )
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                return True

    # No docstring — insert right after method def line
    # Find first non-blank line after def
    content = content.replace(
        old_header,
        old_header + '        if self.errorState:\n            return\n\n',
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return True


def main():
    modules_dir = Path(__file__).resolve().parent.parent / 'modules'
    dry_run = '--dry-run' in sys.argv

    # P0 modules — errorState set but never checked in handleEvent
    targets = [
        'sfp_abstractapi.py',
        'sfp_abuseipdb.py',
        'sfp_arbitrum.py',
        'sfp_bluesky.py',
        'sfp_criminalip.py',
        'sfp_discord.py',
        'sfp_dnsdumpster.py',
        'sfp_ethereum.py',
        'sfp_fofa.py',
        'sfp_mastodon.py',
        'sfp_matrix.py',
        'sfp_mattermost.py',
        'sfp_netlas.py',
        'sfp_openwifimap.py',
        'sfp_punkspider.py',
        'sfp_rocketchat.py',
        'sfp_spamhaus.py',
        'sfp_tron.py',
        'sfp_unwiredlabs.py',
        'sfp_wificafespots.py',
        'sfp_wifimapio.py',
    ]

    count = 0
    for fn in targets:
        path = modules_dir / fn
        if not path.exists():
            print(f'  SKIP: {fn} not found')
            continue
        if dry_run:
            print(f'  [DRY] Would add errorState guard to {fn}')
            count += 1
        else:
            if fix_missing_errorstate_guard(str(path)):
                print(f'  Fixed: {fn}')
                count += 1
            else:
                print(f'  SKIP: {fn} (already guarded or no handleEvent)')

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Fixed {count} modules")


if __name__ == '__main__':
    main()
