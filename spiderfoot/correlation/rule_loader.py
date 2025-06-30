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
import yaml
import os
import jsonschema

RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "meta": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "risk": {"type": "string"},
                "author": {"type": "string"},
                "url": {"type": "string"},
                "version": {"type": "string"},
                "scope": {"type": "string", "enum": ["scan", "workspace", "global"]}
            },
            "required": ["name", "description", "risk"]
        },
        "collections": {"type": "object"},
        "headline": {"type": "string"},
        "enabled": {"type": "boolean"},
        "id": {"type": "string"},
        "version": {"type": "string"}
    },
    "required": ["meta", "collections", "headline"]
}

class RuleLoader:
    def __init__(self, rule_dir):
        self.rule_dir = rule_dir
        self.rules = []
        self.errors = []

    def load_rules(self):
        for fname in os.listdir(self.rule_dir):
            if not fname.endswith('.yaml'):
                continue
            path = os.path.join(self.rule_dir, fname)
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    rule = yaml.safe_load(f)
                    jsonschema.validate(instance=rule, schema=RULE_SCHEMA)
                    rule['rawYaml'] = open(path, 'r', encoding='utf-8').read()
                    rule['filename'] = fname
                    self.rules.append(rule)
                except Exception as e:
                    self.errors.append((fname, str(e)))
        return self.rules

    def get_errors(self):
        return self.errors

    def get_rules(self):
        return self.rules
