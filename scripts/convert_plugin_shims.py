"""Convert root-level plugin/module files to re-export shims."""

from __future__ import annotations

import ast
import os

# Mapping of file to what it exports
FILE_EXPORTS = {
    "plugin.py": ["SpiderFootPlugin", "SpiderFootPluginLogger"],
    "modern_plugin.py": ["SpiderFootModernPlugin"],
    "async_plugin.py": [
        "AsyncResult",
        "SpiderFootAsyncPlugin",
        "get_event_loop",
        "shutdown_event_loop",
    ],
    "plugin_registry.py": [
        "InstalledPlugin",
        "PluginManifest",
        "PluginRegistry",
        "PluginStatus",
    ],
    "plugin_test.py": [
        "EventCapture",
        "FakeSpiderFoot",
        "FakeTarget",
        "PluginTestHarness",
        "make_event",
        "make_root_event",
    ],
    "module_api_client.py": [
        "ApiResponse",
        "HttpMethod",
        "ModuleApiClient",
        "RateLimiter",
        "RequestConfig",
        "RequestRecord",
        "ResponseFormat",
    ],
    "module_caps.py": [
        "Capability",
        "CapabilityCategory",
        "CapabilityRegistry",
        "ModuleCapabilityDeclaration",
        "Requirement",
        "get_capability_registry",
    ],
    "module_comms.py": [
        "ChannelStats",
        "Message",
        "MessageBus",
        "MessagePriority",
        "get_message_bus",
    ],
    "module_contract.py": [
        "DataSourceModel",
        "ModuleMeta",
        "ModuleValidationResult",
        "SpiderFootModuleProtocol",
        "validate_module",
        "validate_module_batch",
    ],
    "module_deps.py": [
        "DepEdge",
        "DepStatus",
        "ModuleDependencyResolver",
        "ModuleNode",
        "ResolutionResult",
    ],
    "module_graph.py": ["ModuleGraph", "ModuleInfo"],
    "module_health.py": [
        "HealthStatus",
        "ModuleHealth",
        "ModuleHealthMonitor",
        "get_health_monitor",
    ],
    "module_loader.py": [
        "LoadResult",
        "ModuleLoader",
        "get_module_loader",
        "init_module_loader",
        "reset_module_loader",
    ],
    "module_metrics.py": [
        "MetricsCollector",
        "MetricType",
        "MetricValue",
        "ModuleMetrics",
        "TimerContext",
    ],
    "module_output_validator.py": [
        "ModuleOutputValidator",
        "UndeclaredEventError",
        "ValidationStats",
        "get_output_validator",
    ],
    "module_profiler.py": [
        "MethodProfile",
        "ModuleProfile",
        "ModuleProfiler",
        "get_module_profiler",
    ],
    "module_registry.py": [
        "DiscoveryResult",
        "ModuleDescriptor",
        "ModuleRegistry",
        "ModuleStatus",
    ],
    "module_resolver.py": [
        "Dependency",
        "DepKind",
        "ModuleDescriptor",
        "ModuleResolver",
        "ResolutionResult",
        "ResolveStatus",
    ],
    "module_sandbox.py": [
        "ModuleSandbox",
        "ResourceLimits",
        "ResourceTracker",
        "SandboxManager",
        "SandboxResult",
        "SandboxState",
    ],
    "module_timeout.py": [
        "ModuleTimeoutGuard",
        "TimeoutRecord",
        "get_timeout_guard",
    ],
    "module_versioning.py": [
        "ChangelogEntry",
        "ModuleVersionInfo",
        "ModuleVersionRegistry",
        "SemanticVersion",
        "VersionBump",
        "VersionConstraint",
    ],
}

# Generate shim content
def make_shim(filename: str, exports: list[str]) -> str:
    base = filename.replace(".py", "")
    lines = [
        f'"""Backward-compatibility shim for {filename}.',
        "",
        f"This module re-exports from plugins/{filename} for backward compatibility.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        f"from .plugins.{base} import (",
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
