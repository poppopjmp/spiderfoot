#!/usr/bin/env python3
"""
SpiderFoot Documentation Builder
Builds the documentation and checks for common issues
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def install_dependencies():
    """Install documentation dependencies"""
    print("Installing documentation dependencies...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
    ], cwd="docs", check=True)

def clean_build():
    """Clean previous builds"""
    print("Cleaning previous builds...")
    build_dir = Path("docs/_build")
    if build_dir.exists():
        import shutil
        shutil.rmtree(build_dir)

def build_docs(format_type="html"):
    """Build documentation"""
    print(f"Building documentation in {format_type} format...")
    
    if os.name == 'nt':  # Windows
        cmd = ["docs\\make.bat", format_type]
    else:  # Unix/Linux/macOS
        cmd = ["make", "-C", "docs", format_type]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Documentation build failed:")
        print(result.stdout)
        print(result.stderr)
        return False
    
    print(f"Documentation built successfully!")
    print(f"Output location: docs/_build/{format_type}/")
    return True

def check_links():
    """Check for broken links in documentation"""
    print("Checking for broken links...")
    
    if os.name == 'nt':  # Windows
        cmd = ["docs\\make.bat", "linkcheck"]
    else:  # Unix/Linux/macOS
        cmd = ["make", "-C", "docs", "linkcheck"]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Link check completed with warnings:")
        print(result.stdout)
    else:
        print("All links are valid!")

def serve_docs():
    """Serve documentation locally for preview"""
    print("Starting local documentation server...")
    print("Open http://localhost:8000 in your browser")
    
    try:
        subprocess.run([
            sys.executable, "-m", "http.server", "8000"
        ], cwd="docs/_build/html", check=True)
    except KeyboardInterrupt:
        print("\nDocumentation server stopped.")

def main():
    parser = argparse.ArgumentParser(description="Build SpiderFoot documentation")
    parser.add_argument("--install-deps", action="store_true", help="Install documentation dependencies")
    parser.add_argument("--clean", action="store_true", help="Clean previous builds")
    parser.add_argument("--format", default="html", choices=["html", "pdf", "epub"], help="Output format")
    parser.add_argument("--check-links", action="store_true", help="Check for broken links")
    parser.add_argument("--serve", action="store_true", help="Serve documentation locally")
    parser.add_argument("--all", action="store_true", help="Run complete build process")
    
    args = parser.parse_args()
    
    if args.all or args.install_deps:
        install_dependencies()
    
    if args.all or args.clean:
        clean_build()
    
    if args.all or not any([args.install_deps, args.clean, args.check_links, args.serve]):
        success = build_docs(args.format)
        if not success:
            sys.exit(1)
    
    if args.all or args.check_links:
        check_links()
    
    if args.serve:
        serve_docs()

if __name__ == "__main__":
    main()
