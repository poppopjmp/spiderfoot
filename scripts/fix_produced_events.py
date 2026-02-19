#!/usr/bin/env python3
"""
Fix undeclared producedEvents: add missing event types to producedEvents() declarations.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Mapping: filename -> list of event types to add to producedEvents()
FIXES = {
    "sfp_builtwith.py": ["AFFILIATE_DOMAIN_NAME", "AFFILIATE_INTERNET_NAME"],
    "sfp_censys.py": ["IPV6_ADDRESS", "IP_ADDRESS"],
    "sfp_dnscommonsrv.py": ["DNS_SRV"],
    "sfp_flickr.py": ["INTERNET_NAME_UNRESOLVED"],
    "sfp_fraudguard.py": ["AFFILIATE_IPADDR", "AFFILIATE_IPV6_ADDRESS", "IPV6_ADDRESS", "IP_ADDRESS"],
    "sfp_hybrid_analysis.py": ["INTERNET_NAME_UNRESOLVED"],
    "sfp_ipapicom.py": ["PHYSICAL_COORDINATES"],
    "sfp_jsonwhoiscom.py": ["AFFILIATE_DOMAIN_WHOIS", "AFFILIATE_EMAILADDR"],
    "sfp_leakix.py": ["INTERNET_NAME_UNRESOLVED", "IP_ADDRESS"],
    "sfp_mnemonic.py": ["INTERNET_NAME_UNRESOLVED"],
    "sfp_networksdb.py": ["DOMAIN_NAME", "NETBLOCKV6_MEMBER"],
    "sfp_searchcode.py": ["INTERNET_NAME", "INTERNET_NAME_UNRESOLVED"],
    "sfp_seon.py": ["EMAILADDR_DISPOSABLE", "PHYSICAL_COORDINATES"],
    "sfp_shodan.py": ["BGP_AS_MEMBER", "SOFTWARE_USED"],
    "sfp_snov.py": ["RAW_RIR_DATA"],
    "sfp_sociallinks.py": ["USERNAME"],
    "sfp_template.py": ["AFFILIATE_IPADDR", "IP_ADDRESS"],
    "sfp_threatminer.py": ["INTERNET_NAME_UNRESOLVED"],
    "sfp_virustotal.py": ["AFFILIATE_DOMAIN_NAME"],
}

# Fix typos: sfp_stackoverflow.py uses AFFILIATE_IP_ADDRESS which should be AFFILIATE_IPADDR
TYPO_FIXES = {
    "sfp_stackoverflow.py": ("AFFILIATE_IP_ADDRESS", "AFFILIATE_IPADDR"),
}


def add_produced_events(filepath: str, event_types: list[str]) -> bool:
    """Add missing event types to producedEvents() return list.

    Handles formats:
      def producedEvents(self) -> list:
          \"\"\"docstring.\"\"\"
          return ["EVT1", "EVT2", ...]
    """
    import ast

    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # Flexible regex: match producedEvents with optional return annotation,
    # optional docstring, then `return [...]`
    match = re.search(
        r'(def producedEvents\(self\).*?return\s+)(\[.*?\])',
        content, re.DOTALL,
    )
    if not match:
        print(f"  WARNING: Could not find producedEvents in {filepath}")
        return False

    list_str = match.group(2)

    # Parse existing list with ast.literal_eval for safety
    try:
        existing = ast.literal_eval(list_str)
    except Exception:
        print(f"  WARNING: Could not parse list in {filepath}: {list_str[:80]}")
        return False

    # Filter to only add types not already declared
    to_add = [t for t in event_types if t not in existing]
    if not to_add:
        return False

    # Build new list
    new_list = existing + to_add
    items = ',\n            '.join(f'"{t}"' for t in new_list)
    new_list_str = f'[\n            {items},\n        ]'

    # Replace old list with new
    content = content.replace(match.group(0), match.group(1) + new_list_str)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return True


def fix_typo(filepath: str, old_type: str, new_type: str) -> bool:
    """Fix event type typo in a module."""
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    new_content = content.replace(f'"{old_type}"', f'"{new_type}"')
    if new_content == content:
        return False

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True


def main():
    modules_dir = Path(__file__).resolve().parent.parent / 'modules'
    dry_run = '--dry-run' in sys.argv

    count = 0

    # Fix typos first
    for fn, (old_type, new_type) in TYPO_FIXES.items():
        path = modules_dir / fn
        if not path.exists():
            print(f'  SKIP: {fn} not found')
            continue
        if dry_run:
            print(f'  [DRY] Would fix typo in {fn}: {old_type} -> {new_type}')
            count += 1
        else:
            if fix_typo(str(path), old_type, new_type):
                print(f'  Fixed typo in {fn}: {old_type} -> {new_type}')
                count += 1
                # Also add to producedEvents if needed
                if new_type not in open(str(path)).read().split('producedEvents')[1].split(']')[0] if 'producedEvents' in open(str(path)).read() else '':
                    FIXES.setdefault(fn, []).append(new_type)

    # Fix undeclared producedEvents
    for fn, event_types in FIXES.items():
        path = modules_dir / fn
        if not path.exists():
            print(f'  SKIP: {fn} not found')
            continue
        if dry_run:
            print(f'  [DRY] Would add to {fn}: {event_types}')
            count += 1
        else:
            if add_produced_events(str(path), event_types):
                print(f'  Updated producedEvents in {fn}: +{event_types}')
                count += 1
            else:
                print(f'  SKIP: {fn} (events already declared)')

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Fixed {count} modules")


if __name__ == '__main__':
    main()
