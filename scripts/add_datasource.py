#!/usr/bin/env python3
"""
Add dataSource entries to modules that are missing them.
Tool modules get tool-specific dataSource; processing modules get local dataSource.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Tool modules → dataSource mappings
TOOL_DATASOURCES = {
    "sfp_httpx.py": {
        "website": "https://github.com/projectdiscovery/httpx",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/projectdiscovery/httpx"],
        "description": "Fast HTTP probing and technology detection tool by ProjectDiscovery.",
    },
    "sfp_subfinder.py": {
        "website": "https://github.com/projectdiscovery/subfinder",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/projectdiscovery/subfinder"],
        "description": "Passive subdomain enumeration tool by ProjectDiscovery.",
    },
    "sfp_tool_amass.py": {
        "website": "https://github.com/owasp-amass/amass",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/owasp-amass/amass"],
        "description": "OWASP attack surface mapping and subdomain enumeration.",
    },
    "sfp_tool_arjun.py": {
        "website": "https://github.com/s0md3v/Arjun",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/s0md3v/Arjun"],
        "description": "HTTP parameter discovery tool.",
    },
    "sfp_tool_dalfox.py": {
        "website": "https://github.com/hahwul/dalfox",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/hahwul/dalfox"],
        "description": "XSS vulnerability scanner and parameter analysis tool.",
    },
    "sfp_tool_dnsx.py": {
        "website": "https://github.com/projectdiscovery/dnsx",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/projectdiscovery/dnsx"],
        "description": "DNS resolution and record enumeration tool by ProjectDiscovery.",
    },
    "sfp_tool_ffuf.py": {
        "website": "https://github.com/ffuf/ffuf",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/ffuf/ffuf"],
        "description": "Fast web fuzzer for directory, file, and parameter discovery.",
    },
    "sfp_tool_gau.py": {
        "website": "https://github.com/lc/gau",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/lc/gau"],
        "description": "Get All URLs tool fetching known URLs from web archives.",
    },
    "sfp_tool_gitleaks.py": {
        "website": "https://github.com/gitleaks/gitleaks",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/gitleaks/gitleaks"],
        "description": "Secret detection tool for git repositories.",
    },
    "sfp_tool_gobuster.py": {
        "website": "https://github.com/OJ/gobuster",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/OJ/gobuster"],
        "description": "Directory/file brute-forcing and DNS subdomain enumeration tool.",
    },
    "sfp_tool_gospider.py": {
        "website": "https://github.com/jaeles-project/gospider",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/jaeles-project/gospider"],
        "description": "Fast web spider for link and JavaScript discovery.",
    },
    "sfp_tool_gowitness.py": {
        "website": "https://github.com/sensepost/gowitness",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/sensepost/gowitness"],
        "description": "Web screenshot tool for visual analysis of discovered hosts.",
    },
    "sfp_tool_hakrawler.py": {
        "website": "https://github.com/hakluke/hakrawler",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/hakluke/hakrawler"],
        "description": "Simple, fast web crawler for URL discovery.",
    },
    "sfp_tool_katana.py": {
        "website": "https://github.com/projectdiscovery/katana",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/projectdiscovery/katana"],
        "description": "Next-generation web crawler with headless browser support by ProjectDiscovery.",
    },
    "sfp_tool_linkfinder.py": {
        "website": "https://github.com/GerbenJav);avado/LinkFinder",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/GerbenJavado/LinkFinder"],
        "description": "JavaScript endpoint and API path extractor.",
    },
    "sfp_tool_masscan.py": {
        "website": "https://github.com/robertdavidgraham/masscan",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/robertdavidgraham/masscan"],
        "description": "Ultra-fast mass port scanner.",
    },
    "sfp_tool_massdns.py": {
        "website": "https://github.com/blechschmidt/massdns",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/blechschmidt/massdns"],
        "description": "High-performance DNS stub resolver for bulk lookups.",
    },
    "sfp_tool_naabu.py": {
        "website": "https://github.com/projectdiscovery/naabu",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/projectdiscovery/naabu"],
        "description": "High-speed port scanner by ProjectDiscovery.",
    },
    "sfp_tool_nikto.py": {
        "website": "https://github.com/sullo/nikto",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/sullo/nikto"],
        "description": "Web server vulnerability scanner.",
    },
    "sfp_tool_retirejs.py": {
        "website": "https://retirejs.github.io/retire.js/",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/RetireJS/retire.js"],
        "description": "Scanner for JavaScript libraries with known vulnerabilities.",
    },
    "sfp_tool_sslscan.py": {
        "website": "https://github.com/rbsec/sslscan",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/rbsec/sslscan"],
        "description": "SSL/TLS cipher suite enumeration tool.",
    },
    "sfp_tool_sslyze.py": {
        "website": "https://github.com/nabla-c0d3/sslyze",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/nabla-c0d3/sslyze"],
        "description": "Comprehensive SSL/TLS configuration analyzer.",
    },
    "sfp_tool_tlsx.py": {
        "website": "https://github.com/projectdiscovery/tlsx",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/projectdiscovery/tlsx"],
        "description": "Fast TLS certificate grabber by ProjectDiscovery.",
    },
    "sfp_tool_waybackurls.py": {
        "website": "https://github.com/tomnomnom/waybackurls",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/tomnomnom/waybackurls"],
        "description": "Fetch historical URLs from the Wayback Machine.",
    },
}

# OSINT/external source modules
OSINT_DATASOURCES = {
    "sfp_whois.py": {
        "website": "https://www.iana.org/whois",
        "model": "FREE_NOAUTH_LIMITED",
        "references": ["https://tools.ietf.org/html/rfc3912"],
        "description": "Domain and IP WHOIS registration data lookup.",
    },
    "sfp_pgp.py": {
        "website": "https://keys.openpgp.org/",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://keys.openpgp.org/"],
        "description": "PGP/GPG public key server lookups.",
    },
    "sfp_telegram.py": {
        "website": "https://telegram.org/",
        "model": "FREE_NOAUTH_LIMITED",
        "references": ["https://core.telegram.org/"],
        "description": "Telegram user and group discovery.",
    },
    "sfp_customfeed.py": {
        "website": None,
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": [],
        "description": "User-defined custom data feeds for threat intelligence.",
    },
    "sfp_webanalytics.py": {
        "website": None,
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": [],
        "description": "Extract web analytics and tracking IDs from web content.",
    },
    "sfp_subdomain_takeover.py": {
        "website": "https://github.com/EdOverflow/can-i-take-over-xyz",
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": ["https://github.com/EdOverflow/can-i-take-over-xyz"],
        "description": "Detect potential subdomain takeover vulnerabilities via dangling CNAME records.",
    },
    "sfp_sslcert.py": {
        "website": None,
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": [],
        "description": "Analyze SSL/TLS certificates for hostnames, expiry, and chain validation.",
    },
}

# Local processing modules — no external data source
LOCAL_MODULES = [
    "sfp_bitcoin.py",
    "sfp_company.py",
    "sfp_countryname.py",
    "sfp_crossref.py",
    "sfp_email.py",
    "sfp_hashes.py",
    "sfp_names.py",
    "sfp_phone.py",
]


def add_datasource(filepath: str, ds_dict: dict) -> bool:
    """Add dataSource entry to a module's meta dict."""
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    if 'dataSource' in content:
        return False

    # Build the dataSource string
    parts = ['        "dataSource": {']
    for key, val in ds_dict.items():
        if val is None:
            parts.append(f'            "{key}": None,')
        elif isinstance(val, str):
            parts.append(f'            "{key}": "{val}",')
        elif isinstance(val, list):
            if not val:
                parts.append(f'            "{key}": [],')
            else:
                items = ', '.join(f'"{v}"' for v in val)
                parts.append(f'            "{key}": [{items}],')
    parts.append('        },')
    ds_str = '\n'.join(parts)

    # Find the end of the meta dict and insert before the closing }
    # Look for the last entry before the closing brace of meta
    # Pattern: find "categories": [...], followed by eventual },
    # or find "toolDetails": {...}, followed by eventual },
    
    # Strategy: find the closing of meta dict
    # Insert before the last line that has just "    }" (end of meta)
    
    # Find meta = {  and its closing }
    meta_start = content.find('    meta = {')
    if meta_start == -1:
        print(f"  WARNING: Could not find meta dict in {filepath}")
        return False

    # Find matching closing brace
    brace_depth = 0
    meta_end = -1
    for i in range(meta_start, len(content)):
        if content[i] == '{':
            brace_depth += 1
        elif content[i] == '}':
            brace_depth -= 1
            if brace_depth == 0:
                meta_end = i
                break

    if meta_end == -1:
        print(f"  WARNING: Could not find end of meta dict in {filepath}")
        return False

    # Find the last comma before meta_end and insert after the last entry
    # Look backwards from meta_end for the last non-whitespace
    last_content_pos = meta_end - 1
    while last_content_pos > meta_start and content[last_content_pos] in ' \n\t':
        last_content_pos -= 1

    # Find end of last line before closing brace
    last_newline = content.rfind('\n', meta_start, meta_end)

    # Ensure there's a comma after the last entry
    line_before_close = content[last_newline:meta_end].strip()
    
    # Insert dataSource before the closing }
    insert_pos = last_newline + 1
    # Make sure previous line ends with comma
    prev_line_end = content.rfind('\n', meta_start, last_newline)
    prev_line = content[prev_line_end+1:last_newline+1] if prev_line_end >= 0 else ''
    
    # Add comma to last entry if needed
    if not prev_line.rstrip().endswith(',') and not prev_line.rstrip().endswith('{'):
        # Find the position just before the newline
        comma_pos = last_newline
        while comma_pos > 0 and content[comma_pos-1] in ' \t\n':
            comma_pos -= 1
        if content[comma_pos-1] not in ',{':
            content = content[:comma_pos] + ',' + content[comma_pos:]
            meta_end += 1
            last_newline += 1
    
    # Insert before closing brace line
    content = content[:last_newline+1] + ds_str + '\n' + content[last_newline+1:]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return True


def main():
    modules_dir = Path(__file__).resolve().parent.parent / 'modules'
    dry_run = '--dry-run' in sys.argv
    
    count = 0

    # Tool modules
    for fn, ds in TOOL_DATASOURCES.items():
        path = modules_dir / fn
        if not path.exists():
            print(f"  SKIP: {fn} not found")
            continue
        if dry_run:
            print(f"  [DRY] Would add dataSource to {fn}")
            count += 1
        else:
            if add_datasource(str(path), ds):
                print(f"  Added dataSource to {fn}")
                count += 1
            else:
                print(f"  SKIP: {fn} (already has dataSource)")

    # OSINT modules
    for fn, ds in OSINT_DATASOURCES.items():
        path = modules_dir / fn
        if not path.exists():
            print(f"  SKIP: {fn} not found")
            continue
        if dry_run:
            print(f"  [DRY] Would add dataSource to {fn}")
            count += 1
        else:
            if add_datasource(str(path), ds):
                print(f"  Added dataSource to {fn}")
                count += 1
            else:
                print(f"  SKIP: {fn} (already has dataSource)")

    # Local processing modules
    local_ds = {
        "website": None,
        "model": "FREE_NOAUTH_UNLIMITED",
        "references": [],
        "description": "Local data processing and extraction (no external API).",
    }
    for fn in LOCAL_MODULES:
        path = modules_dir / fn
        if not path.exists():
            print(f"  SKIP: {fn} not found")
            continue
        if dry_run:
            print(f"  [DRY] Would add dataSource to {fn}")
            count += 1
        else:
            if add_datasource(str(path), local_ds):
                print(f"  Added dataSource to {fn}")
                count += 1
            else:
                print(f"  SKIP: {fn} (already has dataSource)")

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Added dataSource to {count} modules")


if __name__ == '__main__':
    main()
