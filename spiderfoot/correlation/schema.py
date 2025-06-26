# JSON Schema for correlation rules
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
