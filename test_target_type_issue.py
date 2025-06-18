#!/usr/bin/env python3
"""Test target type handling in web UI scan creation."""

import sys
import os

# Add the spiderfoot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from spiderfoot.helpers import SpiderFootHelpers

def test_target_type_detection():
    """Test various target types."""
    
    test_cases = [
        ("google.com", "INTERNET_NAME"),
        ("192.168.1.1", "IP_ADDRESS"),
        ("192.168.1.0/24", "NETBLOCK_OWNER"),
        ("test@example.com", "EMAILADDR"),
        ("John Doe", "HUMAN_NAME"),
        ("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2", "BITCOIN_ADDRESS"),
        ("+1-555-123-4567", "PHONE_NUMBER"),
        ("", None),
        ("   ", None),
        ("invalid_target_12345", None),
    ]
    
    for target, expected in test_cases:
        result = SpiderFootHelpers.targetTypeFromString(target)
        print(f"Target: '{target}' -> Type: {result} (Expected: {expected})")
        
        if result != expected:
            print(f"ERROR: Expected {expected}, got {result}")
            return False
    
    print("All target type detection tests passed!")
    return True

def test_web_ui_target_processing():
    """Test the exact target processing as done in web UI."""
    
    # Test the cleanUserInput method simulation
    def cleanUserInput(inputs):
        """Simulate the cleanUserInput method."""
        import html
        cleaned = []
        for inp in inputs:
            if inp is None:
                cleaned.append("")
            else:
                # Remove HTML tags and decode entities
                clean = html.unescape(str(inp).strip())
                cleaned.append(clean)
        return cleaned
    
    test_targets = [
        "google.com",
        "  google.com  ",
        "192.168.1.1",
        "test@example.com",
        "John Doe",
        "&lt;script&gt;alert()&lt;/script&gt;google.com",
        "",
        None,
    ]
    
    for target in test_targets:
        print(f"\nTesting target: {repr(target)}")
        
        # Simulate web UI processing
        try:
            cleaned = cleanUserInput([target])[0] if target is not None else ""
            print(f"  After cleanUserInput: {repr(cleaned)}")
            
            if not cleaned:
                print(f"  ERROR: Target is empty after cleaning")
                continue
                
            targetType = SpiderFootHelpers.targetTypeFromString(cleaned)
            print(f"  Target type: {targetType}")
            
            if targetType is None:
                print(f"  ERROR: Target type is None for cleaned target: {repr(cleaned)}")
            
        except Exception as e:
            print(f"  ERROR: Exception during processing: {e}")

if __name__ == "__main__":
    print("Testing target type detection...")
    test_target_type_detection()
    
    print("\n" + "="*50)
    print("Testing web UI target processing...")
    test_web_ui_target_processing()
