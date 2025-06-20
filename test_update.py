#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from update_version import set_version, main

# Test setting version 5.2.2 and updating all references
set_version("5.2.2")
print("Version set, now updating all references...")

# Import the functions we need
from update_version import update_readme, update_docs, update_docker_configs, update_code_fallback, check_version_consistency

update_readme()
update_docs()
update_docker_configs() 
update_code_fallback()
check_version_consistency()
