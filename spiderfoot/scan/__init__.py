"""SpiderFoot scan subpackage.

This subpackage contains scan lifecycle, scheduling, coordination,
and state management components.

Usage::

    from spiderfoot.scan import ScanStateMachine, ScanState
    from spiderfoot.scan import ScanCoordinator, ScanOrchestrator
"""

from __future__ import annotations

# Scan state
from .scan_state import (
    InvalidTransitionError,
    ScanState,
    ScanStateMachine,
    StateTransition,
)

# Scan state mapping
from .scan_state_map import (
    db_status_to_proto,
    db_status_to_state,
    proto_to_state,
    state_to_db_status,
    state_to_proto,
)

# Scan coordinator
from .scan_coordinator import (
    DistributionStrategy,
    NodeState,
    ScanCoordinator,
    ScannerNode,
    ScanWork,
    WorkAssignment,
    WorkState,
    get_coordinator,
)

# Scan delta analysis
from .scan_delta import (
    Delta,
    DeltaKind,
    DeltaResult,
    Finding as DeltaFinding,
    ScanDeltaAnalyzer,
    TrendPoint,
)

# Scan diff
from .scan_diff import (
    Change,
    ChangeType,
    DiffResult,
    Finding as DiffFinding,
    ScanDiff,
    ScanSnapshot,
)

# Scan event bridge
from .scan_event_bridge import (
    ScanEventBridge,
    create_scan_bridge,
    get_scan_bridge,
    list_active_bridges,
    reset_bridges,
    teardown_scan_bridge,
)

# Scan hooks
from .scan_hooks import (
    ScanEvent,
    ScanLifecycleEvent,
    ScanLifecycleHooks,
    get_scan_hooks,
)

# Scan metadata service
from .scan_metadata_service import ScanMetadataService

# Scan orchestrator
from .scan_orchestrator import (
    ModuleSchedule,
    PhaseResult,
    ScanOrchestrator,
    ScanPhase,
)

# Scan policy
from .scan_policy import (
    PolicyAction,
    PolicyCheckResult,
    PolicyEngine,
    PolicyViolation,
    ScanPolicy,
    ViolationSeverity,
)

# Scan profile
from .scan_profile import (
    ProfileCategory,
    ProfileManager,
    ScanProfile,
    get_profile_manager,
)

# Scan progress
from .scan_progress import (
    ModuleProgress,
    ModuleStatus,
    ProgressSnapshot,
    ScanProgressTracker,
)

# Scan queue
from .scan_queue import (
    BackpressureAction,
    PressureLevel,
    Priority,
    QueueItem,
    QueueStats,
    ScanQueue,
)

# Scan scheduler
from .scan_scheduler import (
    SchedulerConfig,
    ScanPriority,
    ScanRequest,
    ScanScheduler,
    ScanStatus,
)

# Scan service facade
from .scan_service_facade import ScanService, ScanServiceError

# Scan templates
from .scan_templates import ScanTemplate, TemplateCategory, TemplateRegistry

# Scan workflow
from .scan_workflow import (
    CheckpointStep,
    ConditionalStep,
    DelayStep,
    ModuleStep,
    ParallelStep,
    ScanWorkflow,
    SequenceStep,
    StepResult,
    StepStatus,
    StepType,
    WorkflowStep,
)

__all__ = [
    # Scan state
    "InvalidTransitionError",
    "ScanState",
    "ScanStateMachine",
    "StateTransition",
    # Scan state mapping
    "db_status_to_proto",
    "db_status_to_state",
    "proto_to_state",
    "state_to_db_status",
    "state_to_proto",
    # Scan coordinator
    "DistributionStrategy",
    "NodeState",
    "ScanCoordinator",
    "ScannerNode",
    "ScanWork",
    "WorkAssignment",
    "WorkState",
    "get_coordinator",
    # Scan delta
    "Delta",
    "DeltaKind",
    "DeltaResult",
    "DeltaFinding",
    "ScanDeltaAnalyzer",
    "TrendPoint",
    # Scan diff
    "Change",
    "ChangeType",
    "DiffResult",
    "DiffFinding",
    "ScanDiff",
    "ScanSnapshot",
    # Scan event bridge
    "ScanEventBridge",
    "create_scan_bridge",
    "get_scan_bridge",
    "list_active_bridges",
    "reset_bridges",
    "teardown_scan_bridge",
    # Scan hooks
    "ScanEvent",
    "ScanLifecycleEvent",
    "ScanLifecycleHooks",
    "get_scan_hooks",
    # Scan metadata service
    "ScanMetadataService",
    # Scan orchestrator
    "ModuleSchedule",
    "PhaseResult",
    "ScanOrchestrator",
    "ScanPhase",
    # Scan policy
    "PolicyAction",
    "PolicyCheckResult",
    "PolicyEngine",
    "PolicyViolation",
    "ScanPolicy",
    "ViolationSeverity",
    # Scan profile
    "ProfileCategory",
    "ProfileManager",
    "ScanProfile",
    "get_profile_manager",
    # Scan progress
    "ModuleProgress",
    "ModuleStatus",
    "ProgressSnapshot",
    "ScanProgressTracker",
    # Scan queue
    "BackpressureAction",
    "PressureLevel",
    "Priority",
    "QueueItem",
    "QueueStats",
    "ScanQueue",
    # Scan scheduler
    "SchedulerConfig",
    "ScanPriority",
    "ScanRequest",
    "ScanScheduler",
    "ScanStatus",
    # Scan service facade
    "ScanService",
    "ScanServiceError",
    # Scan templates
    "ScanTemplate",
    "TemplateCategory",
    "TemplateRegistry",
    # Scan workflow
    "CheckpointStep",
    "ConditionalStep",
    "DelayStep",
    "ModuleStep",
    "ParallelStep",
    "ScanWorkflow",
    "SequenceStep",
    "StepResult",
    "StepStatus",
    "StepType",
    "WorkflowStep",
]
