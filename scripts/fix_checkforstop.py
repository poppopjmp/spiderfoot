#!/usr/bin/env python3
"""Add self.checkForStop() guards to loops with API calls in handleEvent().

Targets the top-14 worst offenders — modules with loops making external
API calls that never check for scan cancellation.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


# (filename, loop_header_pattern, indent_level, exit_action)
# indent_level: number of spaces for the loop body
# exit_action: "return" or "break"
TARGETS = [
    # Tier 1 — Critical
    ("sfp_accounts.py", "for puser in permutations:", 20, "return"),
    ("sfp_hunter.py", "while rescount <= maxgoal:", 8, "return"),
    ("sfp_skymem.py", "for page in range(1, 21):", 8, "return"),
    ("sfp_4chan.py", "for board in boards:", 8, "return"),
    ("sfp_4chan.py", "for thread in threads[:max_threads]:", 12, "return"),
    ("sfp_subdomain_takeover.py", "for data in self.fingerprints:", 12, "return"),
    # Tier 2 — High
    ("sfp_opencorporates.py", "for c in companies:", 8, "return"),
    ("sfp_gleif.py", "for lei in set(leis):", 8, "return"),
    ("sfp_hybrid_analysis.py", "for file_hash in hashes:", 8, "break"),
    ("sfp_arin.py", "for p in ref:", 24, "break"),  # first loop at deeper indent
    ("sfp_threatminer.py", "for qry in qrylist:", 8, "break"),
    ("sfp_github.py", "for item in ret['items']:", 12, "break"),  # both loops
    ("sfp_onioncity.py", "for link in darknet_links:", 8, "return"),
]


def add_checkforstop(filepath: str, loop_header: str, indent: int, exit_action: str) -> bool:
    """Add checkForStop guard as first statement in a loop body."""
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # Build the search pattern: find the loop header line
    indent_str = ' ' * indent
    loop_line = f"{indent_str}{loop_header}\n"

    # Check if this loop already has checkForStop
    pos = content.find(loop_line)
    if pos == -1:
        # Try with less indent
        for try_indent in range(indent - 4, indent + 8, 4):
            indent_str = ' ' * try_indent
            loop_line = f"{indent_str}{loop_header}\n"
            pos = content.find(loop_line)
            if pos != -1:
                indent = try_indent
                break

    if pos == -1:
        print(f"  WARNING: Could not find loop '{loop_header}' in {filepath}")
        return False

    # Find the next line after the loop header
    next_line_start = pos + len(loop_line)

    # Check if checkForStop already exists in the next few lines
    next_chunk = content[next_line_start:next_line_start + 200]
    if 'checkForStop' in next_chunk.split('\n')[0] or 'checkForStop' in next_chunk.split('\n')[1] if len(next_chunk.split('\n')) > 1 else False:
        print(f"  SKIP: '{loop_header}' in {filepath} already has checkForStop")
        return False

    # Build the guard with proper indent (loop body = indent + 4)
    body_indent = ' ' * (indent + 4)
    guard = f"{body_indent}if self.checkForStop():\n{body_indent}    {exit_action}\n"

    # Insert the guard right after the loop header
    new_content = content[:next_line_start] + guard + content[next_line_start:]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True


def main():
    modules_dir = Path(__file__).resolve().parent.parent / 'modules'
    dry_run = '--dry-run' in sys.argv

    count = 0
    for fn, loop_header, indent, exit_action in TARGETS:
        path = modules_dir / fn
        if not path.exists():
            print(f"  SKIP: {fn} not found")
            continue

        if dry_run:
            print(f"  [DRY] {fn}: would add checkForStop to '{loop_header}'")
            count += 1
            continue

        if add_checkforstop(str(path), loop_header, indent, exit_action):
            print(f"  FIXED: {fn} — added checkForStop to '{loop_header}'")
            count += 1
        else:
            print(f"  SKIP: {fn} — '{loop_header}'")

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Fixed {count} loop(s)")


if __name__ == '__main__':
    main()
