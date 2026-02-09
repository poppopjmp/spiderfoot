"""
SpiderFoot Module Management — loading, registry, dependency resolution, and testing.

This sub-package groups module lifecycle management modules.

Usage::

    from spiderfoot.module_mgmt import module_loader, module_registry
"""

__all__ = [
    "module_caps",
    "module_comms",
    "module_deps",
    "module_graph",
    "module_health",
    "module_loader",
    "module_metrics",
    "module_profiler",
    "module_registry",
    "module_resolver",
    "module_sandbox",
    "module_versioning",
    "modern_plugin",
    "plugin",
    "plugin_registry",
    "plugin_test",
    "async_plugin",
    "hot_reload",
]
