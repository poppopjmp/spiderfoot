#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

# Test individual module setup
def test_module_setup():
    try:
        # Import required components
        from sflib import SpiderFoot
        from spiderfoot import SpiderFootDb
        
        # Import a specific module
        from sfp_bingsharedip import sfp_bingsharedip
        
        print("Module imported successfully")
        
        # Create a minimal config
        config = {
            '__logging': True,
            '__outputfilter': None,
            '_debug': False,
            '_useragent': 'SpiderFoot',
            '_dnsserver': '',
            '_fetchtimeout': 5,
            '_internettlds': '',
            '_internettlds_cache': None,
            '_tor_proxies': []
        }
        
        # Create SpiderFoot instance
        sf = SpiderFoot(config)
        
        # Create module instance
        mod = sfp_bingsharedip()
        print(f"Module instance created: {mod}")
        
        # Setup module with minimal opts
        user_opts = {
            'cohostsamedomain': False,
            'pages': 20,
            'verify': True,
            'maxcohost': 100,
            'api_key': ''
        }
        
        mod.setup(sf, user_opts)
        print("Module setup completed successfully")
        
        print(f"Module opts: {mod.opts}")
        print(f"Module errorState: {mod.errorState}")
        
        return True
        
    except Exception as e:
        print(f"Error during module setup: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_module_setup()
