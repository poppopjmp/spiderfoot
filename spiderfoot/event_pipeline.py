"""Backward compatibility shim for spiderfoot.event_pipeline.

Please import from spiderfoot.events.event_pipeline instead.
"""

from __future__ import annotations

from .events.event_pipeline import StageResult, PipelineEvent, StageStats, PipelineStage, FunctionStage, ValidatorStage, TransformStage, TaggingStage, RouterStage, EventPipeline

__all__ = ['StageResult', 'PipelineEvent', 'StageStats', 'PipelineStage', 'FunctionStage', 'ValidatorStage', 'TransformStage', 'TaggingStage', 'RouterStage', 'EventPipeline']
