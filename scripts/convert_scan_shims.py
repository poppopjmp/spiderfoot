"""Convert root-level scan_*.py files to re-export shims."""

from __future__ import annotations

import os

# Mapping of file to what it exports
FILE_EXPORTS = {
    "scan_coordinator.py": [
        "NodeState",
        "WorkState",
        "DistributionStrategy",
        "ScannerNode",
        "ScanWork",
        "WorkAssignment",
        "ScanCoordinator",
        "get_coordinator",
    ],
    "scan_delta.py": [
        "DeltaKind",
        "Finding",
        "Delta",
        "TrendPoint",
        "ScanDeltaAnalyzer",
        "DeltaResult",
    ],
    "scan_diff.py": [
        "ChangeType",
        "Finding",
        "Change",
        "ScanSnapshot",
        "DiffResult",
        "ScanDiff",
    ],
    "scan_event_bridge.py": [
        "ScanEventBridge",
        "create_scan_bridge",
        "get_scan_bridge",
        "teardown_scan_bridge",
        "list_active_bridges",
        "reset_bridges",
    ],
    "scan_hooks.py": [
        "ScanEvent",
        "ScanLifecycleEvent",
        "ScanLifecycleHooks",
        "get_scan_hooks",
    ],
    "scan_metadata_service.py": ["ScanMetadataService"],
    "scan_orchestrator.py": [
        "ScanPhase",
        "PhaseResult",
        "ModuleSchedule",
        "ScanOrchestrator",
    ],
    "scan_policy.py": [
        "PolicyAction",
        "ViolationSeverity",
        "PolicyViolation",
        "PolicyCheckResult",
        "ScanPolicy",
        "PolicyEngine",
    ],
    "scan_profile.py": [
        "ProfileCategory",
        "ScanProfile",
        "ProfileManager",
        "get_profile_manager",
    ],
    "scan_progress.py": [
        "ModuleStatus",
        "ModuleProgress",
        "ProgressSnapshot",
        "ScanProgressTracker",
    ],
    "scan_queue.py": [
        "Priority",
        "BackpressureAction",
        "PressureLevel",
        "QueueItem",
        "QueueStats",
        "ScanQueue",
    ],
    "scan_scheduler.py": [
        "ScanPriority",
        "ScanRequest",
        "ScanStatus",
        "SchedulerConfig",
        "ScanScheduler",
    ],
    "scan_service_facade.py": ["ScanServiceError", "ScanService"],
    "scan_state.py": [
        "ScanState",
        "StateTransition",
        "InvalidTransitionError",
        "ScanStateMachine",
    ],
    "scan_state_map.py": [
        "db_status_to_state",
        "state_to_db_status",
        "proto_to_state",
        "state_to_proto",
        "db_status_to_proto",
    ],
    "scan_templates.py": ["TemplateCategory", "ScanTemplate", "TemplateRegistry"],
    "scan_workflow.py": [
        "StepType",
        "StepStatus",
        "StepResult",
        "WorkflowStep",
        "ModuleStep",
        "SequenceStep",
        "ParallelStep",
        "ConditionalStep",
        "DelayStep",
        "CheckpointStep",
        "ScanWorkflow",
    ],
}


def make_shim(filename: str, exports: list[str]) -> str:
    """Generate shim content for a file."""
    base = filename.replace(".py", "")
    lines = [
        f'"""Backward-compatibility shim for {filename}.',
        "",
        f"This module re-exports from scan/{filename} for backward compatibility.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        f"from .scan.{base} import (",
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
