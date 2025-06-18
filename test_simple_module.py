#!/usr/bin/env python3

import sys
import os
import importlib.util

# Test custom module loading directly
def test_module_loading():
    mod_dir = "./modules"
    
    try:
        # Add modules directory to Python path
        if mod_dir not in sys.path:
            sys.path.insert(0, mod_dir)
        
        # Test loading one specific module
        module_file = "sfp_bingsharedip.py"
        module_name = module_file[:-3]
        module_path = os.path.join(mod_dir, module_file)
        
        print(f"Testing module: {module_name}")
        
        # Create module spec and load
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None:
            print(f"Could not create spec for {module_name}")
            return
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check if module has the expected class
        if hasattr(module, module_name):
            module_class = getattr(module, module_name)
            print(f"Module class found: {module_class}")
            
            # Check attributes
            print(f"Has meta: {hasattr(module_class, 'meta')}")
            print(f"Has opts: {hasattr(module_class, 'opts')}")
            
            if hasattr(module_class, 'meta'):
                meta = getattr(module_class, 'meta')
                print(f"Meta: {meta}")
                print(f"Use cases: {meta.get('useCases', [])}")
            
            if hasattr(module_class, 'opts'):
                opts = getattr(module_class, 'opts')
                print(f"Opts count: {len(opts)}")
              # Create the module info structure
            module_info = {
                'name': getattr(module_class, 'meta', {}).get('name', module_name),
                'descr': getattr(module_class, '__doc__', 'No description'),
                'cats': getattr(module_class, 'meta', {}).get('categories', []),
                'labels': getattr(module_class, 'meta', {}).get('flags', []),
                'provides': getattr(module_class, 'meta', {}).get('provides', []),
                'consumes': getattr(module_class, 'meta', {}).get('consumes', []),
                'opts': getattr(module_class, 'opts', {}),
                'optdescs': getattr(module_class, 'optdescs', {}),
                'meta': getattr(module_class, 'meta', {}),
                'group': getattr(module_class, 'meta', {}).get('useCases', [])            }
            
            print(f"\nModule info structure:")
            print(f"Name: {module_info['name']}")
            print(f"Categories: {module_info['cats']}")
            print(f"Labels: {module_info['labels']}")
            print(f"Group: {module_info['group']}")
            print(f"Opts count: {len(module_info['opts'])}")
            print(f"Optdescs count: {len(module_info['optdescs'])}")
            print(f"Has all expected fields: {all(key in module_info for key in ['name', 'descr', 'opts', 'group', 'cats', 'labels', 'optdescs', 'meta'])}")
            
            return module_info
        else:
            print(f"Module {module_name} doesn't have expected class")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_module_loading()
