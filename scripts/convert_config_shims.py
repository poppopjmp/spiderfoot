"""Convert root-level config files to re-export shims."""

from __future__ import annotations

import os

# Mapping of file to what it exports
FILE_EXPORTS = {
    "app_config.py": [
        "ProxyType",
        "CacheBackend",
        "EventBusBackend",
        "WorkerStrategy",
        "LogLevel",
        "CoreConfig",
        "NetworkConfig",
        "DatabaseConfig",
        "WebConfig",
        "ApiConfig",
        "CacheSettings",
        "EventBusSettings",
        "VectorConfig",
        "WorkerConfig",
        "RedisConfig",
        "ElasticsearchConfig",
        "ValidationError",
        "AppConfig",
    ],
    "config_schema.py": [
        "FieldSchema",
        "ConfigSchema",
        "infer_schema_from_module",
        "validate_module_config",
    ],
    "constants.py": [
        "DEFAULT_TTL_ONE_HOUR",
        "MODULE_TIMEOUT_SECONDS",
        "SHORT_CACHE_TTL_SECONDS",
        "SESSION_IDLE_TIMEOUT",
        "DEFAULT_RESULT_LIMIT",
        "DEFAULT_BATCH_SIZE",
        "DEFAULT_MAX_RETRIES",
        "DB_RETRY_BACKOFF_BASE",
        "DEFAULT_API_PORT",
        "DEFAULT_WEB_PORT",
        "DEFAULT_VECTOR_PORT",
        "MAX_BODY_BYTES",
        "DEFAULT_MAX_TOKENS",
        "DEFAULT_OPENAI_BASE_URL",
        "DEFAULT_OLLAMA_BASE_URL",
        "DEFAULT_VLLM_BASE_URL",
        "DEFAULT_DOH_URL",
        "DEFAULT_DATABASE_NAME",
    ],
}


def make_shim(filename: str, exports: list[str]) -> str:
    """Generate shim content for a file."""
    base = filename.replace(".py", "")
    lines = [
        f'"""Backward-compatibility shim for {filename}.',
        "",
        f"This module re-exports from config/{filename} for backward compatibility.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        f"from .config.{base} import (",
    ]
    for exp in exports:
        lines.append(f"    {exp},")
    lines.append(")")
    lines.append("")
    lines.append("__all__ = [")
    for exp in exports:
        lines.append(f'    "{exp}",')
    lines.append("]")
    lines.append("")
    return "\n".join(lines)


# Convert all files
os.chdir("d:/github/spiderfoot/spiderfoot")
for filename, exports in FILE_EXPORTS.items():
    shim = make_shim(filename, exports)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(shim)
    print(f"Converted {filename} to shim ({len(exports)} exports)")

print(f"\nConverted {len(FILE_EXPORTS)} files to shims")
