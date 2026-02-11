"""Convert root-level service files to re-export shims."""

from __future__ import annotations

import os

# Mapping of file to what it exports
FILE_EXPORTS = {
    "cache_service.py": [
        "CacheBackend",
        "CacheConfig",
        "CacheService",
        "MemoryCache",
        "FileCache",
        "RedisCache",
        "create_cache",
        "create_cache_from_config",
    ],
    "cli_service.py": [
        "cmd_version",
        "cmd_status",
        "cmd_metrics",
        "cmd_config_get",
        "cmd_config_set",
    ],
    "config_service.py": [
        "ConfigValidator",
        "ConfigService",
        "get_config_service",
        "reset_config_service",
    ],
    "correlation_service.py": [
        "CorrelationTrigger",
        "CorrelationServiceConfig",
        "CorrelationResult",
        "CorrelationService",
        "get_correlation_service",
    ],
    "dns_service.py": ["DnsServiceConfig", "DnsService"],
    "embedding_service.py": [
        "EmbeddingProvider",
        "EmbeddingConfig",
        "EmbeddingResult",
        "EmbeddingBackend",
        "MockEmbeddingBackend",
        "SentenceTransformerBackend",
        "OpenAIEmbeddingBackend",
        "HuggingFaceEmbeddingBackend",
        "EmbeddingService",
        "get_embedding_service",
    ],
    "grpc_service.py": [
        "ServiceClient",
        "ServiceCallError",
        "ServiceServer",
        "ServiceDirectory",
    ],
    "http_service.py": ["HttpServiceConfig", "HttpService"],
    "notification_service.py": [
        "Notification",
        "NotificationChannel",
        "SlackChannel",
        "WebhookChannel",
        "EmailChannel",
        "LogChannel",
        "NotificationService",
    ],
    "reranker_service.py": [
        "RerankerProvider",
        "ScoreNormalization",
        "RerankerConfig",
        "RerankItem",
        "RerankResult",
        "RerankResponse",
        "RerankerBackend",
        "MockRerankerBackend",
        "CrossEncoderBackend",
        "CohereRerankerBackend",
        "JinaRerankerBackend",
        "RerankerService",
        "normalize_scores",
        "reciprocal_rank_fusion",
    ],
    "websocket_service.py": [
        "ChannelType",
        "WebSocketMessage",
        "WebSocketClient",
        "WebSocketHub",
        "create_ws_router",
    ],
}


def make_shim(filename: str, exports: list[str]) -> str:
    """Generate shim content for a file."""
    base = filename.replace(".py", "")
    lines = [
        f'"""Backward-compatibility shim for {filename}.',
        "",
        f"This module re-exports from services/{filename} for backward compatibility.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        f"from .services.{base} import (",
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
