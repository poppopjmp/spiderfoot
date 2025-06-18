#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Test module loading
try:
    from spiderfoot import SpiderFootHelpers
    
    mod_dir = "./modules"
    print("Testing standard module loader...")
    modules = SpiderFootHelpers.loadModulesAsDict(mod_dir, [])
    
    if modules:
        print(f"Successfully loaded {len(modules)} modules with standard loader")
        # Check structure of first module
        first_mod = next(iter(modules))
        mod_data = modules[first_mod]
        print(f"\nFirst module: {first_mod}")
        print(f"Structure: {list(mod_data.keys())}")
        print(f"Name: {mod_data.get('name', 'N/A')}")
        print(f"Group (use cases): {mod_data.get('group', [])}")
        print(f"Has opts: {'opts' in mod_data}")
        if 'opts' in mod_data:
            print(f"Opts count: {len(mod_data['opts'])}")
    else:
        print("Standard loader failed, trying custom loader...")
        from sf import load_modules_custom
        import logging
        logging.basicConfig(level=logging.INFO)
        log = logging.getLogger()
        modules = load_modules_custom(mod_dir, log)
        
        if modules:
            print(f"Successfully loaded {len(modules)} modules with custom loader")
            # Check structure of first module
            first_mod = next(iter(modules))
            mod_data = modules[first_mod]
            print(f"\nFirst module: {first_mod}")
            print(f"Structure: {list(mod_data.keys())}")
            print(f"Name: {mod_data.get('name', 'N/A')}")
            print(f"Group (use cases): {mod_data.get('group', [])}")
            print(f"Has opts: {'opts' in mod_data}")
            if 'opts' in mod_data:
                print(f"Opts count: {len(mod_data['opts'])}")
        else:
            print("Both loaders failed!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
