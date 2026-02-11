#!/usr/bin/env python3
"""Remove backward-compatibility shims and update all imports.

This script:
1. Defines the mapping from shim import paths to new subpackage paths
2. Scans all .py files in the project
3. Rewrites imports to use subpackage paths
4. Deletes the shim files
"""

import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPIDERFOOT_DIR = os.path.join(PROJECT_ROOT, "spiderfoot")

# Mapping: old_module -> new_module (without 'spiderfoot.' prefix)
# e.g. "event" -> "events.event" means:
#   "from spiderfoot.event import X" -> "from spiderfoot.events.event import X"
#   "from spiderfoot import event" -> "from spiderfoot.events import event"
SHIM_MAP = {
    # events/ subpackage
    "event": "events.event",
    "event_relay": "events.event_relay",
    "event_dedup": "events.event_dedup",
    "event_filter": "events.event_filter",
    "event_pipeline": "events.event_pipeline",
    "event_taxonomy": "events.event_taxonomy",
    "event_indexer": "events.event_indexer",
    "event_registry": "events.event_registry",
    "event_store": "events.event_store",
    # scan/ subpackage
    "scan_state": "scan.scan_state",
    "scan_state_map": "scan.scan_state_map",
    "scan_coordinator": "scan.scan_coordinator",
    "scan_diff": "scan.scan_diff",
    "scan_delta": "scan.scan_delta",
    "scan_event_bridge": "scan.scan_event_bridge",
    "scan_hooks": "scan.scan_hooks",
    "scan_metadata_service": "scan.scan_metadata_service",
    "scan_orchestrator": "scan.scan_orchestrator",
    "scan_policy": "scan.scan_policy",
    "scan_profile": "scan.scan_profile",
    "scan_progress": "scan.scan_progress",
    "scan_queue": "scan.scan_queue",
    "scan_scheduler": "scan.scan_scheduler",
    "scan_service_facade": "scan.scan_service_facade",
    "scan_templates": "scan.scan_templates",
    "scan_workflow": "scan.scan_workflow",
    # plugins/ subpackage
    "plugin": "plugins.plugin",
    "modern_plugin": "plugins.modern_plugin",
    "async_plugin": "plugins.async_plugin",
    "plugin_registry": "plugins.plugin_registry",
    "plugin_test": "plugins.plugin_test",
    "module_loader": "plugins.module_loader",
    "module_caps": "plugins.module_caps",
    "module_comms": "plugins.module_comms",
    "module_contract": "plugins.module_contract",
    "module_deps": "plugins.module_deps",
    "module_graph": "plugins.module_graph",
    "module_health": "plugins.module_health",
    "module_metrics": "plugins.module_metrics",
    "module_output_validator": "plugins.module_output_validator",
    "module_profiler": "plugins.module_profiler",
    "module_registry": "plugins.module_registry",
    "module_resolver": "plugins.module_resolver",
    "module_sandbox": "plugins.module_sandbox",
    "module_timeout": "plugins.module_timeout",
    "module_versioning": "plugins.module_versioning",
    "module_api_client": "plugins.module_api_client",
    # config/ subpackage
    "constants": "config.constants",
    "app_config": "config.app_config",
    "config_schema": "config.config_schema",
    # security/ subpackage
    "auth": "security.auth",
    "csrf_protection": "security.csrf_protection",
    "security_compat": "security.security_compat",
    "security_integration": "security.security_integration",
    "security_logging": "security.security_logging",
    "security_middleware": "security.security_middleware",
    "service_auth": "security.service_auth",
    # observability/ subpackage
    "audit_log": "observability.audit_log",
    "health": "observability.health",
    "logger": "observability.logger",
    "metrics": "observability.metrics",
    "structured_logging": "observability.structured_logging",
    # services/ subpackage
    "cache_service": "services.cache_service",
    "cli_service": "services.cli_service",
    "config_service": "services.config_service",
    "correlation_service": "services.correlation_service",
    "dns_service": "services.dns_service",
    "embedding_service": "services.embedding_service",
    "grpc_service": "services.grpc_service",
    "http_service": "services.http_service",
    "notification_service": "services.notification_service",
    "reranker_service": "services.reranker_service",
    "websocket_service": "services.websocket_service",
    # reporting/ subpackage
    "export_service": "reporting.export_service",
    "report_formatter": "reporting.report_formatter",
    "report_generator": "reporting.report_generator",
    "report_preprocessor": "reporting.report_preprocessor",
    "report_storage": "reporting.report_storage",
    "visualization_service": "reporting.visualization_service",
}

# Files/dirs to skip
SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    "scripts",  # Don't modify our own scripts
}

# Shim files to delete (relative to spiderfoot/)
SHIM_FILES = list(SHIM_MAP.keys())


def should_process(filepath: str) -> bool:
    """Check if file should be processed."""
    if not filepath.endswith(".py"):
        return False
    parts = filepath.replace("\\", "/").split("/")
    for skip in SKIP_DIRS:
        if skip in parts:
            return False
    # Don't modify the shim files themselves
    rel = os.path.relpath(filepath, SPIDERFOOT_DIR).replace("\\", "/")
    if rel in [f"{s}.py" for s in SHIM_FILES]:
        return False
    return True


def rewrite_imports(content: str, filepath: str) -> str:
    """Rewrite imports from shim paths to subpackage paths."""
    lines = content.split("\n")
    new_lines = []
    changed = False

    for line in lines:
        new_line = line

        # Handle: from spiderfoot.OLD_MODULE import ...
        for old_mod, new_mod in SHIM_MAP.items():
            # Pattern: from spiderfoot.old_module import ...
            pattern = rf'^(\s*from\s+)spiderfoot\.{re.escape(old_mod)}(\s+import\s+.*)$'
            match = re.match(pattern, line)
            if match:
                new_line = f"{match.group(1)}spiderfoot.{new_mod}{match.group(2)}"
                changed = True
                break

            # Pattern: import spiderfoot.old_module
            pattern2 = rf'^(\s*import\s+)spiderfoot\.{re.escape(old_mod)}\s*$'
            match2 = re.match(pattern2, line)
            if match2:
                new_line = f"{match2.group(1)}spiderfoot.{new_mod}"
                changed = True
                break

        # Handle relative imports within spiderfoot/ package
        # from .old_module import ... -> from .subpackage.old_module import ...
        rel = os.path.relpath(filepath, SPIDERFOOT_DIR).replace("\\", "/")
        # Only for files directly in spiderfoot/ (not in subdirectories)
        if "/" not in rel and rel.endswith(".py"):
            for old_mod, new_mod in SHIM_MAP.items():
                pattern_rel = rf'^(\s*from\s+)\.{re.escape(old_mod)}(\s+import\s+.*)$'
                match_rel = re.match(pattern_rel, new_line)
                if match_rel:
                    new_line = f"{match_rel.group(1)}.{new_mod}{match_rel.group(2)}"
                    changed = True
                    break

        new_lines.append(new_line)

    if changed:
        return "\n".join(new_lines)
    return None


def find_py_files(root: str):
    """Find all Python files to process."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out skip dirs
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            if should_process(fpath):
                files.append(fpath)
    return files


def main():
    dry_run = "--dry-run" in sys.argv
    delete = "--delete" in sys.argv

    print(f"SpiderFoot Shim Removal Tool")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Delete shims: {delete}")
    print(f"Shim mappings: {len(SHIM_MAP)}")
    print()

    # Step 1: Update all imports
    files = find_py_files(PROJECT_ROOT)
    print(f"Found {len(files)} Python files to scan")

    updated = 0
    for fpath in sorted(files):
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        result = rewrite_imports(content, fpath)
        if result is not None:
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            if dry_run:
                print(f"  WOULD UPDATE: {rel}")
            else:
                with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                    f.write(result)
                print(f"  UPDATED: {rel}")
            updated += 1

    print(f"\n{'Would update' if dry_run else 'Updated'} {updated} files")

    # Step 2: Delete shim files
    if delete:
        print("\nDeleting shim files:")
        deleted = 0
        for mod in SHIM_FILES:
            shim_path = os.path.join(SPIDERFOOT_DIR, f"{mod}.py")
            if os.path.exists(shim_path):
                rel = os.path.relpath(shim_path, PROJECT_ROOT)
                if dry_run:
                    print(f"  WOULD DELETE: {rel}")
                else:
                    os.remove(shim_path)
                    print(f"  DELETED: {rel}")
                deleted += 1
        print(f"\n{'Would delete' if dry_run else 'Deleted'} {deleted} shim files")


if __name__ == "__main__":
    main()
