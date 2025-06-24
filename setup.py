#!/usr/bin/env python3
"""Setup script for SpiderFoot."""

import os
import pathlib
from setuptools import setup, find_packages

# Read version from VERSION file
version_file = pathlib.Path(__file__).parent / "VERSION"
with open(version_file, 'r', encoding='utf-8') as f:
    version = f.read().strip()

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip()
        for line in fh
        if line.strip() and not line.startswith("#") and not line.startswith("-")
    ]

setup(
    name="spiderfoot",
    version=version,
    author="Steve Micallef, Agostino Panico",
    author_email="steve@binarypool.com, van1sh@van1shland.io",
    description="SpiderFoot - Open Source Intelligence Automation Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/poppopjmp/spiderfoot",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: System :: Networking :: Monitoring",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "spiderfoot=sf:main",
            "spiderfoot-cli=sfcli:main",
            "spiderfoot-api=sfapi:main",
        ],
    },
    include_package_data=True,
    package_data={
        "spiderfoot": ["data/*", "static/*", "templates/*"],
    },
)
