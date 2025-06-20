#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from update_version import set_version, update_readme, update_docs, update_docker_configs, update_code_fallback, check_version_consistency

# Restore to original version
set_version("5.2.1")
print("Version restored, now updating all references...")

update_readme()
update_docs()
update_docker_configs() 
update_code_fallback()
check_version_consistency()
