"""SpiderFoot plugins subpackage.

This subpackage contains plugin and module management components:
- Base plugin classes and async support
- Module loading, registration, and discovery
- Health monitoring, metrics, and profiling
- API client and communication infrastructure
- Sandboxing and timeout management
"""

from __future__ import annotations

# Base plugin classes
from .plugin import SpiderFootPlugin, SpiderFootPluginLogger
from .modern_plugin import SpiderFootModernPlugin
from .async_plugin import (
    AsyncResult,
    SpiderFootAsyncPlugin,
    get_event_loop,
    shutdown_event_loop,
)

# Plugin registry
from .plugin_registry import (
    InstalledPlugin,
    PluginManifest,
    PluginRegistry,
    PluginStatus,
)

# Plugin testing
from .plugin_test import (
    EventCapture,
    FakeSpiderFoot,
    FakeTarget,
    PluginTestHarness,
    make_event,
    make_root_event,
)

# Module API client
from .module_api_client import (
    ApiResponse,
    HttpMethod,
    ModuleApiClient,
    RateLimiter,
    RequestConfig,
    RequestRecord,
    ResponseFormat,
)

# Module capabilities
from .module_caps import (
    Capability,
    CapabilityCategory,
    CapabilityRegistry,
    ModuleCapabilityDeclaration,
    Requirement,
    get_capability_registry,
)

# Module communication
from .module_comms import (
    ChannelStats,
    Message,
    MessageBus,
    MessagePriority,
    get_message_bus,
)

# Module contract
from .module_contract import (
    DataSourceModel,
    ModuleMeta,
    ModuleValidationResult,
    SpiderFootModuleProtocol,
    validate_module,
    validate_module_batch,
)

# Module dependencies
from .module_deps import (
    DepEdge,
    DepStatus,
    ModuleDependencyResolver,
    ModuleNode,
    ResolutionResult as DepsResolutionResult,
)

# Module graph
from .module_graph import ModuleGraph, ModuleInfo

# Module health
from .module_health import (
    HealthStatus,
    ModuleHealth,
    ModuleHealthMonitor,
    get_health_monitor,
)

# Module loader
from .module_loader import (
    LoadResult,
    ModuleLoader,
    get_module_loader,
    init_module_loader,
    reset_module_loader,
)

# Module metrics
from .module_metrics import (
    MetricsCollector,
    MetricType,
    MetricValue,
    ModuleMetrics,
    TimerContext,
)

# Module output validator
from .module_output_validator import (
    ModuleOutputValidator,
    UndeclaredEventError,
    ValidationStats,
    get_output_validator,
)

# Module profiler
from .module_profiler import (
    MethodProfile,
    ModuleProfile,
    ModuleProfiler,
    get_module_profiler,
)

# Module registry
from .module_registry import (
    DiscoveryResult,
    ModuleDescriptor,
    ModuleRegistry,
    ModuleStatus,
)

# Module resolver
from .module_resolver import (
    Dependency,
    DepKind,
    ModuleDescriptor as ResolverModuleDescriptor,
    ModuleResolver,
    ResolutionResult as ResolverResolutionResult,
    ResolveStatus,
)

# Module sandbox
from .module_sandbox import (
    ModuleSandbox,
    ResourceLimits,
    ResourceTracker,
    SandboxManager,
    SandboxResult,
    SandboxState,
)

# Module timeout
from .module_timeout import (
    ModuleTimeoutGuard,
    TimeoutRecord,
    get_timeout_guard,
)

# Module versioning
from .module_versioning import (
    ChangelogEntry,
    ModuleVersionInfo,
    ModuleVersionRegistry,
    SemanticVersion,
    VersionBump,
    VersionConstraint,
)

__all__ = [
    # Base plugins
    "SpiderFootPlugin",
    "SpiderFootPluginLogger",
    "SpiderFootModernPlugin",
    "AsyncResult",
    "SpiderFootAsyncPlugin",
    "get_event_loop",
    "shutdown_event_loop",
    # Plugin registry
    "InstalledPlugin",
    "PluginManifest",
    "PluginRegistry",
    "PluginStatus",
    # Plugin testing
    "EventCapture",
    "FakeSpiderFoot",
    "FakeTarget",
    "PluginTestHarness",
    "make_event",
    "make_root_event",
    # Module API client
    "ApiResponse",
    "HttpMethod",
    "ModuleApiClient",
    "RateLimiter",
    "RequestConfig",
    "RequestRecord",
    "ResponseFormat",
    # Module capabilities
    "Capability",
    "CapabilityCategory",
    "CapabilityRegistry",
    "ModuleCapabilityDeclaration",
    "Requirement",
    "get_capability_registry",
    # Module communication
    "ChannelStats",
    "Message",
    "MessageBus",
    "MessagePriority",
    "get_message_bus",
    # Module contract
    "DataSourceModel",
    "ModuleMeta",
    "ModuleValidationResult",
    "SpiderFootModuleProtocol",
    "validate_module",
    "validate_module_batch",
    # Module dependencies
    "DepEdge",
    "DepStatus",
    "ModuleDependencyResolver",
    "ModuleNode",
    "DepsResolutionResult",
    # Module graph
    "ModuleGraph",
    "ModuleInfo",
    # Module health
    "HealthStatus",
    "ModuleHealth",
    "ModuleHealthMonitor",
    "get_health_monitor",
    # Module loader
    "LoadResult",
    "ModuleLoader",
    "get_module_loader",
    "init_module_loader",
    "reset_module_loader",
    # Module metrics
    "MetricsCollector",
    "MetricType",
    "MetricValue",
    "ModuleMetrics",
    "TimerContext",
    # Module output validator
    "ModuleOutputValidator",
    "UndeclaredEventError",
    "ValidationStats",
    "get_output_validator",
    # Module profiler
    "MethodProfile",
    "ModuleProfile",
    "ModuleProfiler",
    "get_module_profiler",
    # Module registry
    "DiscoveryResult",
    "ModuleDescriptor",
    "ModuleRegistry",
    "ModuleStatus",
    # Module resolver
    "Dependency",
    "DepKind",
    "ResolverModuleDescriptor",
    "ModuleResolver",
    "ResolverResolutionResult",
    "ResolveStatus",
    # Module sandbox
    "ModuleSandbox",
    "ResourceLimits",
    "ResourceTracker",
    "SandboxManager",
    "SandboxResult",
    "SandboxState",
    # Module timeout
    "ModuleTimeoutGuard",
    "TimeoutRecord",
    "get_timeout_guard",
    # Module versioning
    "ChangelogEntry",
    "ModuleVersionInfo",
    "ModuleVersionRegistry",
    "SemanticVersion",
    "VersionBump",
    "VersionConstraint",
]
