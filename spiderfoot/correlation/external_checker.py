# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot Correlation Engine
# Purpose:      Common functions for enriching events with contextual information.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
import argparse
import sys
from rule_loader import RuleLoader

def main():
    parser = argparse.ArgumentParser(description="SpiderFoot Correlation Rule Checker")
    parser.add_argument('rule_dir', help='Directory containing correlation YAML rules')
    args = parser.parse_args()

    loader = RuleLoader(args.rule_dir)
    rules = loader.load_rules()
    errors = loader.get_errors()

    if errors:
        print("Rule validation errors:")
        for fname, err in errors:
            print(f"  {fname}: {err}")
        sys.exit(1)
    else:
        print(f"All {len(rules)} rules validated successfully.")
        for rule in rules:
            print(f"- {rule['meta']['name']} (id: {rule.get('id', 'N/A')})")

if __name__ == '__main__':
    main()
