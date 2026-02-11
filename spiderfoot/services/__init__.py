"""SpiderFoot services subpackage.

This subpackage contains various service components for caching,
configuration, DNS, embedding, gRPC, HTTP, notifications, and more.

Usage::

    from spiderfoot.services import CacheService, ConfigService
    from spiderfoot.services import DnsService, EmbeddingService
"""

from __future__ import annotations

# Cache service
from .cache_service import (
    CacheBackend,
    CacheConfig,
    CacheService,
    create_cache,
    create_cache_from_config,
    FileCache,
    MemoryCache,
    RedisCache,
)

# CLI service
from .cli_service import (
    cmd_config_get,
    cmd_config_set,
    cmd_metrics,
    cmd_status,
    cmd_version,
)

# Config service
from .config_service import (
    ConfigService,
    ConfigValidator,
    get_config_service,
    reset_config_service,
)

# Correlation service
from .correlation_service import (
    CorrelationResult,
    CorrelationService,
    CorrelationServiceConfig,
    CorrelationTrigger,
    get_correlation_service,
)

# DNS service
from .dns_service import DnsService, DnsServiceConfig

# Embedding service
from .embedding_service import (
    EmbeddingBackend,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    EmbeddingService,
    get_embedding_service,
    HuggingFaceEmbeddingBackend,
    MockEmbeddingBackend,
    OpenAIEmbeddingBackend,
    SentenceTransformerBackend,
)

# gRPC service
from .grpc_service import (
    ServiceCallError,
    ServiceClient,
    ServiceDirectory,
    ServiceServer,
)

# HTTP service
from .http_service import HttpService, HttpServiceConfig

# Notification service
from .notification_service import (
    EmailChannel,
    LogChannel,
    Notification,
    NotificationChannel,
    NotificationService,
    SlackChannel,
    WebhookChannel,
)

# Reranker service
from .reranker_service import (
    CohereRerankerBackend,
    CrossEncoderBackend,
    JinaRerankerBackend,
    MockRerankerBackend,
    normalize_scores,
    reciprocal_rank_fusion,
    RerankerBackend,
    RerankerConfig,
    RerankerProvider,
    RerankerService,
    RerankItem,
    RerankResponse,
    RerankResult,
    ScoreNormalization,
)

# WebSocket service
from .websocket_service import (
    ChannelType,
    create_ws_router,
    WebSocketClient,
    WebSocketHub,
    WebSocketMessage,
)

__all__ = [
    # Cache service
    "CacheBackend",
    "CacheConfig",
    "CacheService",
    "create_cache",
    "create_cache_from_config",
    "FileCache",
    "MemoryCache",
    "RedisCache",
    # CLI service
    "cmd_config_get",
    "cmd_config_set",
    "cmd_metrics",
    "cmd_status",
    "cmd_version",
    # Config service
    "ConfigService",
    "ConfigValidator",
    "get_config_service",
    "reset_config_service",
    # Correlation service
    "CorrelationResult",
    "CorrelationService",
    "CorrelationServiceConfig",
    "CorrelationTrigger",
    "get_correlation_service",
    # DNS service
    "DnsService",
    "DnsServiceConfig",
    # Embedding service
    "EmbeddingBackend",
    "EmbeddingConfig",
    "EmbeddingProvider",
    "EmbeddingResult",
    "EmbeddingService",
    "get_embedding_service",
    "HuggingFaceEmbeddingBackend",
    "MockEmbeddingBackend",
    "OpenAIEmbeddingBackend",
    "SentenceTransformerBackend",
    # gRPC service
    "ServiceCallError",
    "ServiceClient",
    "ServiceDirectory",
    "ServiceServer",
    # HTTP service
    "HttpService",
    "HttpServiceConfig",
    # Notification service
    "EmailChannel",
    "LogChannel",
    "Notification",
    "NotificationChannel",
    "NotificationService",
    "SlackChannel",
    "WebhookChannel",
    # Reranker service
    "CohereRerankerBackend",
    "CrossEncoderBackend",
    "JinaRerankerBackend",
    "MockRerankerBackend",
    "normalize_scores",
    "reciprocal_rank_fusion",
    "RerankerBackend",
    "RerankerConfig",
    "RerankerProvider",
    "RerankerService",
    "RerankItem",
    "RerankResponse",
    "RerankResult",
    "ScoreNormalization",
    # WebSocket service
    "ChannelType",
    "create_ws_router",
    "WebSocketClient",
    "WebSocketHub",
    "WebSocketMessage",
]
