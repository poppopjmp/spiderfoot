#!/usr/bin/env python

import sys
import os

# Add the project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_correlation_rules():
    print("Testing correlation rule loading...")
    
    try:
        # Load correlation rules like sf.py does
        import yaml
        script_dir = os.path.dirname(os.path.abspath(__file__))
        correlations_dir = os.path.join(script_dir, 'correlations')
        correlation_rules = []
        
        if os.path.exists(correlations_dir):
            print(f"Correlations directory found: {correlations_dir}")
            files = [f for f in os.listdir(correlations_dir) if f.endswith('.yaml') and f != 'template.yaml']
            print(f"Found {len(files)} correlation rule files")
            
            for filename in files[:3]:  # Test first 3 files
                filepath = os.path.join(correlations_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        raw_yaml = f.read()
                        rule = yaml.safe_load(raw_yaml)
                        if rule and isinstance(rule, dict):
                            rule['id'] = filename[:-5]  # Remove .yaml extension
                            rule['rawYaml'] = raw_yaml  # Store raw YAML content
                            correlation_rules.append(rule)
                            print(f"✓ Loaded rule: {rule['id']}")
                            print(f"  Has rawYaml: {'rawYaml' in rule}")
                            print(f"  rawYaml length: {len(rule.get('rawYaml', ''))}")
                except Exception as e:
                    print(f"✗ Failed to load {filename}: {e}")
        
        print(f"Successfully loaded {len(correlation_rules)} correlation rules")
        
        # Test that we can create the ruleset like sfscan.py does
        ruleset = dict()
        for rule in correlation_rules:
            try:
                ruleset[rule['id']] = rule['rawYaml']
                print(f"✓ Added {rule['id']} to ruleset")
            except KeyError as e:
                print(f"✗ Missing key in rule {rule.get('id', 'unknown')}: {e}")
        
        print(f"Ruleset contains {len(ruleset)} rules")
        print("Correlation rules test completed successfully!")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_correlation_rules()
