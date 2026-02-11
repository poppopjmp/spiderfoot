"""Backward-compatibility shim for scan_workflow.py.

This module re-exports from scan/scan_workflow.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_workflow import (
    StepType,
    StepStatus,
    StepResult,
    WorkflowStep,
    ModuleStep,
    SequenceStep,
    ParallelStep,
    ConditionalStep,
    DelayStep,
    CheckpointStep,
    ScanWorkflow,
)

__all__ = [
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
]
