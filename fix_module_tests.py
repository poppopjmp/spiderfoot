#!/usr/bin/env python3
"""
Script to fix NameError issues in module tests where 'self' is not defined.
This script searches for function definitions that are missing 'self' parameter
and fixes them.
"""

import os
import re
import glob

# List of test files that need to be fixed based on the error output
TEST_FILES_WITH_SELF_ERRORS = [
    "test/unit/modules/test_sfp_names.py",
    "test/unit/modules/test_sfp_networksdb.py", 
    "test/unit/modules/test_sfp_neutrinoapi.py",
    "test/unit/modules/test_sfp_onioncity.py",
    "test/unit/modules/test_sfp_onyphe.py",
    "test/unit/modules/test_sfp_pastebin.py",
    "test/unit/modules/test_sfp_pgp.py",
    "test/unit/modules/test_sfp_phone.py",
    "test/unit/modules/test_sfp_projectdiscovery.py",
    "test/unit/modules/test_sfp_pulsedive.py",
    "test/unit/modules/test_sfp_riskiq.py",
    "test/unit/modules/test_sfp_securitytrails.py",
    "test/unit/modules/test_sfp_seon.py",
    "test/unit/modules/test_sfp_shodan.py",
    "test/unit/modules/test_sfp_slideshare.py",
    "test/unit/modules/test_sfp_snov.py",
    "test/unit/modules/test_sfp_social.py",
    "test/unit/modules/test_sfp_sociallinks.py",
    "test/unit/modules/test_sfp_socialprofiles.py",
    "test/unit/modules/test_sfp_spur.py",
    "test/unit/modules/test_sfp_spyonweb.py",
    "test/unit/modules/test_sfp_strangeheaders.py",
    "test/unit/modules/test_sfp_textmagic.py",
    "test/unit/modules/test_sfp_tool_cmseek.py",
    "test/unit/modules/test_sfp_tool_nbtscan.py",
    "test/unit/modules/test_sfp_tool_nmap.py",
    "test/unit/modules/test_sfp_tool_nuclei.py",
    "test/unit/modules/test_sfp_tool_onesixtyone.py",
    "test/unit/modules/test_sfp_tool_snallygaster.py",
    "test/unit/modules/test_sfp_tool_testsslsh.py",
    "test/unit/modules/test_sfp_tool_trufflehog.py",
    "test/unit/modules/test_sfp_tool_wafw00f.py",
    "test/unit/modules/test_sfp_tool_wappalyzer.py",
    "test/unit/modules/test_sfp_tool_whatweb.py",
    "test/unit/modules/test_sfp_trashpanda.py",
    "test/unit/modules/test_sfp_twilio.py",
    "test/unit/modules/test_sfp_twitter.py",
    "test/unit/modules/test_sfp_viewdns.py",
    "test/unit/modules/test_sfp_virustotal.py",
    "test/unit/modules/test_sfp_webanalytics.py",
    "test/unit/modules/test_sfp_webframework.py",
    "test/unit/modules/test_sfp_whatcms.py",
    "test/unit/modules/test_sfp_whoisology.py",
    "test/unit/modules/test_sfp_whoxy.py",
    "test/unit/modules/test_sfp_wigle.py",
    "test/unit/modules/test_sfp_xforce.py",
    "test/unit/modules/test_sfp_zetalytics.py",
]

def fix_self_parameter_issues(file_path):
    """Fix function definitions that are missing self parameter."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to find function definitions that are missing self parameter
    # Look for test functions in classes that don't have self parameter
    pattern = r'(\s+def\s+test_\w+)\(\):'
    
    def replacement(match):
        return match.group(1) + '(self):'
    
    content = re.sub(pattern, replacement, content)
    
    # Fix decorators that might have corrupted function signatures
    # Pattern: @decorator\n    def func(...depth=0): -> @decorator\n    def func(self):
    pattern = r'(@\w+(?:\([^)]*\))?)\s*\n\s+(def\s+test_\w+)\([^)]*depth=0\):'
    
    def decorator_replacement(match):
        decorator = match.group(1)
        func_def = match.group(2)
        return f"{decorator}\n    {func_def}(self):"
    
    content = re.sub(pattern, decorator_replacement, content)
    
    # Fix corrupted function signatures like selfdepth=0
    pattern = r'(\s+def\s+test_\w+)\([^)]*selfdepth[^)]*\):'
    content = re.sub(pattern, r'\1(self):', content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Main function to fix all test files."""
    base_dir = os.path.dirname(__file__)
    fixed_files = []
    
    for test_file in TEST_FILES_WITH_SELF_ERRORS:
        file_path = os.path.join(base_dir, test_file)
        if os.path.exists(file_path):
            if fix_self_parameter_issues(file_path):
                fixed_files.append(test_file)
                print(f"Fixed: {test_file}")
            else:
                print(f"No changes needed: {test_file}")
        else:
            print(f"File not found: {test_file}")
    
    print(f"\nFixed {len(fixed_files)} files:")
    for file in fixed_files:
        print(f"  - {file}")

if __name__ == "__main__":
    main()
