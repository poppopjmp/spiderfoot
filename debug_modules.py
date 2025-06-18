#!/usr/bin/env python3

import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

# Try to load modules and print their structure
try:
    from spiderfoot import SpiderFootHelpers
    print("Loading modules using standard loader...")
    
    mod_dir = os.path.join(os.path.dirname(__file__), 'modules')
    modules = SpiderFootHelpers.loadModulesAsDict(mod_dir)
    
    print(f"Loaded {len(modules)} modules using standard loader")
    
    # Check first few modules
    for i, (mod_name, mod_info) in enumerate(modules.items()):
        if i >= 3:  # Only show first 3
            break
        print(f"\nModule: {mod_name}")
        print(f"  Keys: {list(mod_info.keys())}")
        print(f"  Has opts: {'opts' in mod_info}")
        if 'opts' in mod_info:
            print(f"  Opts type: {type(mod_info['opts'])}")
            print(f"  Opts keys: {list(mod_info['opts'].keys())[:5]}...")  # First 5 opts
        print(f"  Description: {mod_info.get('descr', 'None')[:50]}...")
        
except Exception as e:
    print(f"Standard loader failed: {e}")
    import traceback
    traceback.print_exc()

# Also try custom loader
try:
    print("\n\nTrying custom loader...")
    from sf import load_modules_custom
    import logging
    
    # Create a simple logger
    log = logging.getLogger()
    log.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    log.addHandler(handler)
    
    modules = load_modules_custom(mod_dir, log)
    print(f"Loaded {len(modules)} modules using custom loader")
    
    # Check first few modules
    for i, (mod_name, mod_info) in enumerate(modules.items()):
        if i >= 3:  # Only show first 3
            break
        print(f"\nModule: {mod_name}")
        print(f"  Keys: {list(mod_info.keys())}")
        print(f"  Has opts: {'opts' in mod_info}")
        if 'opts' in mod_info:
            print(f"  Opts type: {type(mod_info['opts'])}")
            print(f"  Opts keys: {list(mod_info['opts'].keys())[:5]}...")  # First 5 opts
        print(f"  Description: {mod_info.get('descr', 'None')[:50]}...")

except Exception as e:
    print(f"Custom loader failed: {e}")
    import traceback
    traceback.print_exc()
