#!/usr/bin/env python3
"""Test target type validation"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from spiderfoot.helpers import SpiderFootHelpers

def test_target_type_validation():
    """Test target type validation with various inputs."""
    print("Testing target type validation...")
    
    test_cases = [
        ("127.0.0.1", "IP_ADDRESS"),
        ("example.com", "INTERNET_NAME"),
        ("test@example.com", "EMAILADDR"),
        ("John Doe", "HUMAN_NAME"),
        ("", None),
        (None, None),
        ("invalid_target_@#$%", None),
        ("192.168.1.0/24", "NETBLOCK_OWNER"),
    ]
    
    for target, expected in test_cases:
        try:
            result = SpiderFootHelpers.targetTypeFromString(target) if target is not None else None
            print(f"Target: '{target}' -> Type: {result} (expected: {expected})")
            
            if result != expected:
                print(f"  ⚠️  Mismatch! Expected {expected}, got {result}")
            else:
                print(f"  ✅  Correct")
                
        except Exception as e:
            print(f"  ❌  Error for target '{target}': {e}")
    
    print("\nTarget type validation test completed")
    return True

if __name__ == "__main__":
    success = test_target_type_validation()
    sys.exit(0 if success else 1)
