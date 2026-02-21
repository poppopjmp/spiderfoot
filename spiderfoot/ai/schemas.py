# -------------------------------------------------------------------------------
# Name:         ai/schemas
# Purpose:      Pydantic models for LLM structured outputs.
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2025-07-01
# Copyright:    (c) Agostino Panico 2025
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Pydantic models for LLM structured outputs.

These models are designed to be used with the OpenAI ``response_format``
parameter (``json_schema`` mode) so the LLM is forced to return valid,
schema-conformant JSON instead of free-form Markdown.

Each model can be passed to :meth:`~spiderfoot.llm_client.LLMClient.chat_structured`
or :meth:`~spiderfoot.agents.base.BaseAgent.call_llm_structured` to get a
typed, validated response object back.

Naming convention
-----------------
Suffix ``Output`` denotes a top-level structured response model.
Nested models (e.g. ``Finding``, ``Recommendation``) are reusable across
multiple output schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SeverityLevel(str, Enum):
    """Severity/risk rating scale."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ConfidenceLevel(str, Enum):
    """Confidence in an AI-generated assessment."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Reusable nested models
# ---------------------------------------------------------------------------

class Finding(BaseModel):
    """A single OSINT finding surfaced by the LLM."""
    title: str = Field(..., description="Short title (< 120 chars)")
    description: str = Field(..., description="Detailed description")
    severity: SeverityLevel = Field(
        default=SeverityLevel.INFO,
        description="Severity rating",
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.MEDIUM,
        description="How confident the LLM is in this finding",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Supporting evidence / data points",
    )
    affected_assets: list[str] = Field(
        default_factory=list,
        description="Assets (domains, IPs, emails) affected",
    )
    mitre_techniques: list[str] = Field(
        default_factory=list,
        description="Relevant MITRE ATT&CK technique IDs (e.g. T1595)",
    )


class ThreatIndicator(BaseModel):
    """A threat indicator identified during analysis."""
    indicator_type: str = Field(
        ...,
        description="Type: ip, domain, email, hash, url, etc.",
    )
    value: str = Field(..., description="The indicator value")
    context: str = Field(default="", description="Why this is significant")
    severity: SeverityLevel = Field(default=SeverityLevel.MEDIUM)
    source_module: str = Field(
        default="",
        description="SpiderFoot module that produced the raw data",
    )


class Recommendation(BaseModel):
    """An actionable recommendation."""
    title: str = Field(..., description="Short action title")
    description: str = Field(..., description="Detailed steps")
    priority: SeverityLevel = Field(
        default=SeverityLevel.MEDIUM,
        description="Urgency of this recommendation",
    )
    category: str = Field(
        default="general",
        description="Category: remediation, monitoring, hardening, process",
    )
    estimated_effort: str = Field(
        default="unknown",
        description="Effort estimate: low, medium, high",
    )


class Attribution(BaseModel):
    """Threat attribution analysis."""
    threat_actor: str = Field(
        default="unknown",
        description="Name or identifier of threat actor/group",
    )
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.LOW)
    motivation: str = Field(default="", description="Assessed motivation")
    techniques: list[str] = Field(
        default_factory=list,
        description="TTPs observed",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence supporting attribution",
    )


# ---------------------------------------------------------------------------
# Top-level structured output models
# ---------------------------------------------------------------------------

class RiskAssessmentOutput(BaseModel):
    """Structured risk assessment from LLM analysis."""
    overall_risk: SeverityLevel = Field(
        ..., description="Overall risk rating"
    )
    risk_score: int = Field(
        ..., ge=0, le=100,
        description="Numeric risk score (0-100)",
    )
    summary: str = Field(
        ..., description="2-3 sentence risk summary"
    )
    key_risks: list[str] = Field(
        default_factory=list,
        description="Top risk factors (bullet-point style)",
    )
    findings: list[Finding] = Field(
        default_factory=list,
        description="Detailed findings",
    )


class ExecutiveSummaryOutput(BaseModel):
    """Structured executive summary for a scan report."""
    title: str = Field(
        ..., description="Report title"
    )
    executive_summary: str = Field(
        ..., description="2-4 paragraph executive summary"
    )
    risk_rating: SeverityLevel = Field(
        default=SeverityLevel.MEDIUM,
        description="Overall risk rating",
    )
    risk_score: int = Field(
        default=50, ge=0, le=100,
        description="Numeric risk score (0-100)",
    )
    key_findings: list[str] = Field(
        default_factory=list,
        description="Top 5-10 key findings as bullet points",
    )
    scope: str = Field(
        default="",
        description="Scope of the assessment (target, modules used)",
    )


class ReportSectionOutput(BaseModel):
    """A single section of an AI-generated report."""
    section_title: str = Field(..., description="Section heading")
    content: str = Field(
        ..., description="Section body (Markdown)"
    )
    findings: list[Finding] = Field(
        default_factory=list,
        description="Findings in this section",
    )
    threat_indicators: list[ThreatIndicator] = Field(
        default_factory=list,
        description="Indicators found in this section",
    )


class ScanReportOutput(BaseModel):
    """Full structured scan report from LLM analysis."""
    title: str = Field(..., description="Report title")
    executive_summary: str = Field(
        ..., description="Executive summary (2-4 paragraphs)"
    )
    risk_rating: SeverityLevel = Field(default=SeverityLevel.MEDIUM)
    risk_score: int = Field(default=50, ge=0, le=100)
    key_findings: list[Finding] = Field(
        default_factory=list,
        description="All key findings",
    )
    threat_indicators: list[ThreatIndicator] = Field(
        default_factory=list,
        description="Notable threat indicators",
    )
    sections: list[ReportSectionOutput] = Field(
        default_factory=list,
        description="Report body sections",
    )
    recommendations: list[Recommendation] = Field(
        default_factory=list,
        description="Actionable recommendations",
    )
    attribution: Attribution | None = Field(
        default=None,
        description="Optional threat attribution",
    )
    methodology: str = Field(
        default="",
        description="Methodology / approach used",
    )


class ThreatAssessmentOutput(BaseModel):
    """Structured threat assessment for a single entity."""
    entity: str = Field(..., description="The assessed entity (domain, IP, etc.)")
    entity_type: str = Field(..., description="Type of entity")
    threat_level: SeverityLevel = Field(default=SeverityLevel.LOW)
    threat_score: int = Field(default=0, ge=0, le=100)
    summary: str = Field(..., description="Assessment summary")
    indicators: list[ThreatIndicator] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)


class CorrelationOutput(BaseModel):
    """Structured output for RAG-based correlation analysis."""
    correlation_type: str = Field(
        ..., description="Type of correlation found"
    )
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    summary: str = Field(..., description="Correlation summary")
    entities: list[str] = Field(
        default_factory=list,
        description="Entities involved in the correlation",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence supporting the correlation",
    )
    implications: list[str] = Field(
        default_factory=list,
        description="Security implications",
    )


class FindingValidationOutput(BaseModel):
    """Structured output for AI-based finding validation."""
    finding_id: str = Field(..., description="ID of the finding being validated")
    is_valid: bool = Field(..., description="Whether the finding is valid")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    reasoning: str = Field(..., description="Why the finding is/isn't valid")
    severity_override: SeverityLevel | None = Field(
        default=None,
        description="Adjusted severity if different from original",
    )
    additional_context: str = Field(
        default="",
        description="Extra context discovered during validation",
    )


class TextSummaryOutput(BaseModel):
    """Structured output for text summarisation."""
    summary: str = Field(..., description="Concise summary")
    key_points: list[str] = Field(
        default_factory=list,
        description="Key points extracted",
    )
    entities_mentioned: list[str] = Field(
        default_factory=list,
        description="Named entities found in the text",
    )
    sentiment: str = Field(
        default="neutral",
        description="Overall sentiment: positive, negative, neutral",
    )
