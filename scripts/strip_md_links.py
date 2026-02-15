#!/usr/bin/env python3
"""
strip_md_links.py

This script recursively scans all Markdown (.md) files in a directory and replaces Markdown links to other .md files
with links that omit the .md extension (for GitHub Wiki compatibility).

Example:
  [Configuration](configuration.md)  -->  [Configuration](configuration)
  [Guide](docs/guide.md)             -->  [Guide](docs/guide)

Usage:
  python strip_md_links.py <directory>
"""
import os
import re
import sys

MD_LINK_RE = re.compile(r'(\[[^\]]+\]\([^\)]+?)\.md(#[^\)]*)?\)')

def strip_md_links_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = MD_LINK_RE.sub(lambda m: f"{m.group(1)}{m.group(2) or ''})", content)
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated: {filepath}")


def main(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith('.md'):
                strip_md_links_in_file(os.path.join(dirpath, fname))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python strip_md_links.py <directory>")
        sys.exit(1)
    main(sys.argv[1])
