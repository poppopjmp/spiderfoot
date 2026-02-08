"""Module configuration schema validation for SpiderFoot.

Provides JSON Schema-like validation for module options, enabling:
- Type checking of option values against declared schemas
- Range/pattern/enum constraints
- Validation of user-provided config before module init
- Schema generation for documentation and UI
- Detection of common config errors

Usage::

    from spiderfoot.config_schema import ConfigSchema, validate_module_config

    schema = ConfigSchema()
    schema.add_field("api_key", type="str", required=True,
                     description="API key for the service")
    schema.add_field("max_pages", type="int", default=10,
                     min_value=1, max_value=100)

    errors = schema.validate({"api_key": "abc", "max_pages": 50})
    # errors == []

    errors = schema.validate({"max_pages": "not_a_number"})
    # errors == ["api_key: required field missing", "max_pages: ..."]
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

log = logging.getLogger("spiderfoot.config_schema")


@dataclass
class FieldSchema:
    """Schema for a single configuration field."""
    name: str
    type: str = "str"  # str, int, float, bool, list
    description: str = ""
    required: bool = False
    default: Any = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    enum: Optional[List[Any]] = None
    sensitive: bool = False  # True for passwords/API keys

    _TYPE_MAP = {
        "str": str,
        "string": str,
        "int": int,
        "integer": int,
        "float": float,
        "number": (int, float),
        "bool": bool,
        "boolean": bool,
        "list": list,
    }

    def validate(self, value: Any) -> List[str]:
        """Validate a value against this field's schema.

        Returns a list of error messages (empty if valid).
        """
        errors = []

        if value is None:
            if self.required:
                errors.append(f"{self.name}: required field missing")
            return errors

        # Type check
        expected = self._TYPE_MAP.get(self.type)
        if expected and not isinstance(value, expected):
            # Allow int for float fields
            if self.type in ("float", "number") and isinstance(value, int):
                pass
            else:
                errors.append(
                    f"{self.name}: expected type '{self.type}', "
                    f"got '{type(value).__name__}'"
                )
                return errors  # Skip further checks if wrong type

        # Numeric range
        if self.min_value is not None and isinstance(value, (int, float)):
            if value < self.min_value:
                errors.append(
                    f"{self.name}: value {value} below minimum {self.min_value}"
                )
        if self.max_value is not None and isinstance(value, (int, float)):
            if value > self.max_value:
                errors.append(
                    f"{self.name}: value {value} above maximum {self.max_value}"
                )

        # String length
        if isinstance(value, str):
            if self.min_length is not None and len(value) < self.min_length:
                errors.append(
                    f"{self.name}: length {len(value)} below minimum "
                    f"{self.min_length}"
                )
            if self.max_length is not None and len(value) > self.max_length:
                errors.append(
                    f"{self.name}: length {len(value)} above maximum "
                    f"{self.max_length}"
                )

        # Pattern match
        if self.pattern and isinstance(value, str):
            if not re.match(self.pattern, value):
                errors.append(
                    f"{self.name}: value does not match pattern '{self.pattern}'"
                )

        # Enum
        if self.enum is not None and value not in self.enum:
            errors.append(
                f"{self.name}: value '{value}' not in allowed values "
                f"{self.enum}"
            )

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Export as a dict for documentation/JSON Schema."""
        d: Dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            d["default"] = self.default
        if self.min_value is not None:
            d["min_value"] = self.min_value
        if self.max_value is not None:
            d["max_value"] = self.max_value
        if self.min_length is not None:
            d["min_length"] = self.min_length
        if self.max_length is not None:
            d["max_length"] = self.max_length
        if self.pattern:
            d["pattern"] = self.pattern
        if self.enum:
            d["enum"] = self.enum
        if self.sensitive:
            d["sensitive"] = True
        return d


class ConfigSchema:
    """Schema for a module's configuration options.

    Provides validation, defaults, and documentation for module config.
    """

    def __init__(self, module_name: str = "") -> None:
        self.module_name = module_name
        self._fields: Dict[str, FieldSchema] = {}

    def add_field(self, name: str, **kwargs) -> "ConfigSchema":
        """Add a field to the schema. Returns self for chaining.

        Args:
            name: Field name (matches option key)
            **kwargs: FieldSchema parameters (type, required, default, etc.)
        """
        self._fields[name] = FieldSchema(name=name, **kwargs)
        return self

    def get_field(self, name: str) -> Optional[FieldSchema]:
        """Get a field schema by name."""
        return self._fields.get(name)

    @property
    def fields(self) -> Dict[str, FieldSchema]:
        return dict(self._fields)

    @property
    def required_fields(self) -> List[str]:
        return [n for n, f in self._fields.items() if f.required]

    @property
    def sensitive_fields(self) -> List[str]:
        return [n for n, f in self._fields.items() if f.sensitive]

    def validate(self, config: Dict[str, Any]) -> List[str]:
        """Validate a config dict against the schema.

        Args:
            config: Dict of option_name -> value

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check each declared field
        for name, field_schema in self._fields.items():
            value = config.get(name)
            if value is None and name not in config:
                if field_schema.required:
                    errors.append(f"{name}: required field missing")
                continue
            errors.extend(field_schema.validate(value))

        return errors

    def get_defaults(self) -> Dict[str, Any]:
        """Get a dict of default values for all fields."""
        return {
            name: fs.default
            for name, fs in self._fields.items()
            if fs.default is not None
        }

    def find_unknown_keys(self, config: Dict[str, Any]) -> List[str]:
        """Find config keys not declared in the schema."""
        return sorted(k for k in config if k not in self._fields)

    def to_dict(self) -> Dict[str, Any]:
        """Export schema as a dict."""
        return {
            "module_name": self.module_name,
            "fields": {
                name: fs.to_dict()
                for name, fs in self._fields.items()
            },
            "required": self.required_fields,
            "sensitive": self.sensitive_fields,
        }

    def __len__(self) -> int:
        return len(self._fields)

    def __contains__(self, name: str) -> bool:
        return name in self._fields


def infer_schema_from_module(opts: Dict[str, Any],
                              optdescs: Dict[str, str],
                              module_name: str = "") -> ConfigSchema:
    """Infer a ConfigSchema from a module's opts and optdescs dicts.

    Auto-detects types from default values.

    Args:
        opts: Module's opts dict (option_name -> default_value)
        optdescs: Module's optdescs dict (option_name -> description)
        module_name: Module name for the schema

    Returns:
        ConfigSchema instance
    """
    schema = ConfigSchema(module_name=module_name)

    for name, default in opts.items():
        desc = optdescs.get(name, "")

        # Infer type from default value
        if isinstance(default, bool):
            field_type = "bool"
        elif isinstance(default, int):
            field_type = "int"
        elif isinstance(default, float):
            field_type = "float"
        elif isinstance(default, list):
            field_type = "list"
        else:
            field_type = "str"

        # Detect sensitive fields by name patterns
        sensitive = bool(re.match(
            r".*(?:api[_-]?key|password|secret|token).*",
            name, re.IGNORECASE
        ))

        # Required if it's a sensitive/API key field with empty default
        required = sensitive and default == ""

        schema.add_field(
            name,
            type=field_type,
            description=desc,
            default=default,
            sensitive=sensitive,
            required=required,
        )

    return schema


def validate_module_config(module_name: str, config: Dict[str, Any],
                           opts: Dict[str, Any],
                           optdescs: Dict[str, str]) -> List[str]:
    """Convenience function to validate a module's config.

    Args:
        module_name: Module name
        config: User-provided config dict
        opts: Module's default opts
        optdescs: Module's option descriptions

    Returns:
        List of validation errors
    """
    schema = infer_schema_from_module(opts, optdescs, module_name)
    return schema.validate(config)
