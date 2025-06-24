#!/usr/bin/env python3
"""
Comprehensive version management utility for SpiderFoot.
This script updates ALL version references across the entire repository.

Usage:
    python update_version.py                    # Update all version references
    python update_version.py --check            # Just display current version
    python update_version.py --set 5.3.0        # Set a new version
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict

def get_version():
    """Get version from VERSION file."""
    version_file = Path(__file__).parent / "VERSION"
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"ERROR: VERSION file not found at {version_file}")
        sys.exit(1)

def set_version(new_version: str):
    """Set a new version in the VERSION file."""
    # Validate version format
    if not re.match(r'^\d+\.\d+\.\d+$', new_version):
        print(f"ERROR: Invalid version format '{new_version}'. Expected format: X.Y.Z")
        sys.exit(1)
    
    version_file = Path(__file__).parent / "VERSION"
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(new_version + '\n')
    
    print(f"Set version to {new_version} in VERSION file")

def update_readme():
    """Update version references in README.md."""
    readme_path = Path(__file__).parent / "README.md"
    version = get_version()
    
    if not readme_path.exists():
        print(f"WARNING: README.md not found at {readme_path}")
        return
    
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    updated = False
    
    # Update badge version
    new_content = re.sub(
        r'version-\d+\.\d+\.\d+--Enterprise',
        f'version-{version}--Enterprise',
        content
    )
    if new_content != content:
        updated = True
        content = new_content
    
    # Update release tag
    new_content = re.sub(
        r'/releases/tag/v\d+\.\d+\.\d+',
        f'/releases/tag/v{version}',
        content
    )
    if new_content != content:
        updated = True
        content = new_content
    
    if updated:
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Updated README.md with version {version}")
    else:
        print(f"[OK] README.md already has correct version {version}")

def update_docs():
    """Update version references in documentation files."""
    version = get_version()
    docs_dir = Path(__file__).parent / "docs"
    
    # Files to update
    files_to_update = [
        docs_dir / "index.rst",
        docs_dir / "configuration.md", 
        docs_dir / "conf.py",
    ]
    
    for file_path in files_to_update:
        if not file_path.exists():
            print(f"WARNING: {file_path} not found")
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Update version patterns
        content = re.sub(r'Version \d+\.\d+\.\d+', f'Version {version}', content)
        content = re.sub(r'SpiderFoot \d+\.\d+\.\d+', f'SpiderFoot {version}', content)
        content = re.sub(r"version = '\d+\.\d+\.\d+'", f"version = '{version}'", content)
        content = re.sub(r'release = \'\d+\.\d+\.\d+\'', f"release = '{version}'", content)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[OK] Updated {file_path.name} with version {version}")
        else:
            print(f"[OK] {file_path.name} already has correct version {version}")

def update_docker_configs():
    """Update version references in Docker configuration files."""
    version = get_version()
    
    # Update docker-compose files and GitHub workflows
    docker_files = [
        "docker-compose-prod.yml",
        "docker-compose.yml",
        ".github/workflows/docker-image.yml",
        ".github/workflows/acceptance_test.yml"
    ]
    
    for file_name in docker_files:
        file_path = Path(__file__).parent / file_name
        if not file_path.exists():
            print(f"WARNING: {file_name} not found")
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Update Docker image versions
        content = re.sub(
            r'spiderfoot:v\d+\.\d+\.\d+',
            f'spiderfoot:v{version}',
            content
        )
        
        # Update any other version tags
        content = re.sub(
            r'poppopjmp/spiderfoot:v\d+\.\d+\.\d+',
            f'poppopjmp/spiderfoot:v{version}',
            content
        )
        
        content = re.sub(
            r'ghcr\.io/poppopjmp/spiderfoot:v\d+\.\d+\.\d+',
            f'ghcr.io/poppopjmp/spiderfoot:v{version}',
            content
        )
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[OK] Updated {file_name} with version {version}")
        else:
            print(f"[OK] {file_name} already has correct version {version}")

def update_code_fallback():
    """Update fallback version in __version__.py."""
    version = get_version()
    version_file = Path(__file__).parent / "spiderfoot" / "__version__.py"
    
    if not version_file.exists():
        print(f"WARNING: {version_file} not found")
        return
    
    with open(version_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Update fallback version
    content = re.sub(
        r'return "\d+\.\d+\.\d+"',
        f'return "{version}"',
        content
    )
    
    if content != original_content:
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Updated __version__.py fallback with version {version}")
    else:
        print(f"[OK] __version__.py already has correct fallback version {version}")

def update_debian_control():
    """Update version in debian/control if present."""
    version = get_version()
    control_path = Path(__file__).parent / "debian" / "control"
    if not control_path.exists():
        print(f"WARNING: {control_path} not found")
        return
    with open(control_path, 'r', encoding='utf-8') as f:
        content = f.read()
    original_content = content
    # Optionally update a Version: field if present (not required for all controls)
    content = re.sub(r'^(Version: )\d+\.\d+\.\d+', f'\\1{version}', content, flags=re.MULTILINE)
    if content != original_content:
        with open(control_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Updated debian/control with version {version}")
    else:
        print(f"[OK] debian/control already has correct version {version} or no version field present")

def update_github_workflows():
    """Update artifact names in build-artifacts.yaml with the new version."""
    version = get_version()
    workflow_path = Path(__file__).parent / ".github" / "workflows" / "build-artifacts.yaml"
    if not workflow_path.exists():
        print(f"WARNING: {workflow_path} not found")
        return
    with open(workflow_path, 'r', encoding='utf-8') as f:
        content = f.read()
    original_content = content
    # Update artifact names with version
    content = re.sub(r'spiderfoot-(\$\{[^}]+\})-(dist|sdist|wheel)', f'spiderfoot-\\1-{version}-\\2', content)
    content = re.sub(r'spiderfoot-(\$\{ steps.get_version.outputs.version \})-deb', f'spiderfoot-{version}-deb', content)
    if content != original_content:
        with open(workflow_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Updated build-artifacts.yaml with version {version}")
    else:
        print(f"[OK] build-artifacts.yaml already has correct version {version}")

def update_snapcraft():
    version = get_version()
    snap_path = Path(__file__).parent / "snapcraft.yaml"
    if not snap_path.exists():
        print(f"WARNING: {snap_path} not found")
        return
    with open(snap_path, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = re.sub(r"version: '([\d\.]+)'", f"version: '{version}'", content)
    if new_content != content:
        with open(snap_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"[OK] Updated snapcraft.yaml with version {version}")
    else:
        print(f"[OK] snapcraft.yaml already has correct version {version}")

def update_spec():
    version = get_version()
    spec_path = Path(__file__).parent / "spiderfoot.spec"
    if not spec_path.exists():
        print(f"WARNING: {spec_path} not found")
        return
    with open(spec_path, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = re.sub(r"Version: *[\d\.]+", f"Version:        {version}", content)
    if new_content != content:
        with open(spec_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"[OK] Updated spiderfoot.spec with version {version}")
    else:
        print(f"[OK] spiderfoot.spec already has correct version {version}")

def update_homebrew_formula():
    version = get_version()
    rb_path = Path(__file__).parent / "spiderfoot.rb"
    if not rb_path.exists():
        print(f"WARNING: {rb_path} not found")
        return
    with open(rb_path, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = re.sub(r'version "[\d\.]+"', f'version "{version}"', content)
    new_content = re.sub(r'v[\d\.]+.tar.gz', f'v{version}.tar.gz', new_content)
    if new_content != content:
        with open(rb_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"[OK] Updated spiderfoot.rb with version {version}")
    else:
        print(f"[OK] spiderfoot.rb already has correct version {version}")

def check_version_consistency():
    """Check that all version references are consistent."""
    version = get_version()
    print(f"\nChecking version consistency across repository...")
    print(f"Expected version: {version}")
    
    # Check patterns in different files
    patterns = [
        ("README.md", [
            r'version-(\d+\.\d+\.\d+)--Enterprise',
            r'/releases/tag/v(\d+\.\d+\.\d+)'
        ]),
        ("docs/index.rst", [
            r'Version (\d+\.\d+\.\d+)',
            r'SpiderFoot (\d+\.\d+\.\d+)'
        ]),
        ("docs/conf.py", [
            r"version = '(\d+\.\d+\.\d+)'",
            r"release = '(\d+\.\d+\.\d+)'"
        ]),
        ("docker-compose-prod.yml", [
            r'spiderfoot:v(\d+\.\d+\.\d+)'
        ]),
        ("spiderfoot/__version__.py", [
            r'return "(\d+\.\d+\.\d+)"'
        ])
    ]
    
    inconsistent = False
    
    for file_name, file_patterns in patterns:
        file_path = Path(__file__).parent / file_name
        if not file_path.exists():
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for pattern in file_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if match != version:
                    print(f"[ERROR] {file_name}: Found version {match}, expected {version}")
                    inconsistent = True
    
    if not inconsistent:
        print("[SUCCESS] All version references are consistent")
    else:
        print("\n[WARNING] Found inconsistent version references. Run without --check to fix them.")

def list_all_version_files():
    """List all files that contain version references."""
    print("\nFiles managed by this version utility:")
    print("=====================================")
    
    managed_files = [
        "VERSION (master version file)",
        "README.md",
        "docs/index.rst", 
        "docs/configuration.md",
        "docs/conf.py",
        "docker-compose-prod.yml",
        "docker-compose.yml", 
        ".github/workflows/docker-image.yml",
        ".github/workflows/acceptance_test.yml",
        "spiderfoot/__version__.py (fallback version)",
    ]
    
    for file_name in managed_files:
        file_path = Path(__file__).parent / file_name.split(' ')[0]
        status = "[OK]" if file_path.exists() else "[MISSING]"
        print(f"  {status} {file_name}")
    
    print("\nFiles that automatically read from VERSION:")
    print("==========================================")
    auto_files = [
        "setup.py",
        "spiderfoot/__version__.py",
        "All Python modules importing __version__",
    ]
    
    for file_name in auto_files:
        print(f"  [OK] {file_name}")

def main():
    """Main function to update all version references."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            version = get_version()
            print(f"Current version: {version}")
            check_version_consistency()
            return
        elif sys.argv[1] == "--list":
            list_all_version_files()
            return
        elif sys.argv[1] == "--set" and len(sys.argv) > 2:
            new_version = sys.argv[2]
            set_version(new_version)
            # Fall through to update all references
        elif sys.argv[1] == "--help":
            print(__doc__)
            return
        else:
            print("Usage: update_version.py [--check|--list|--set VERSION|--help]")
            return
    
    print("Updating all version references...")
    print("==================================")
    
    update_readme()
    update_docs()
    update_docker_configs()
    update_code_fallback()
    update_debian_control()
    update_github_workflows()
    update_snapcraft()
    update_spec()
    update_homebrew_formula()
    
    version = get_version()
    print(f"\n[SUCCESS] All version references updated to {version}")
    print("[SUCCESS] Remember to commit these changes!")
    
    # Run consistency check
    check_version_consistency()

if __name__ == "__main__":
    main()
