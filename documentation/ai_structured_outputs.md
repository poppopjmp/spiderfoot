# AI Structured Outputs Guide

This guide covers using Pydantic-validated structured outputs for LLM responses in SpiderFoot's AI pipeline.

---

## Overview

SpiderFoot v6.0.0 introduces a typed AI output pipeline that forces LLMs to return JSON conforming to predefined Pydantic schemas. This eliminates brittle regex/string parsing of LLM responses and provides compile-time type safety.

### How It Works

1. A Pydantic model defines the expected response shape
2. `chat_structured()` converts the model to a JSON Schema
3. The schema is sent as `response_format: { type: "json_schema", json_schema: { ... } }` to the LLM
4. The LLM response is parsed and validated via `model_validate()`
5. You get a fully typed Python object — or a validation error

---

## Available Schemas

All schemas are in `spiderfoot/ai/schemas.py`:

### Enums

| Enum | Values |
|------|--------|
| `SeverityLevel` | `critical`, `high`, `medium`, `low`, `informational` |
| `ConfidenceLevel` | `high`, `medium`, `low` |

### Nested Models (reusable building blocks)

| Model | Fields | Purpose |
|-------|--------|---------|
| `Finding` | `title`, `description`, `severity`, `confidence`, `evidence`, `recommendations` | Individual finding |
| `ThreatIndicator` | `type`, `value`, `context`, `severity`, `first_seen`, `last_seen` | IOC/threat indicator |
| `Recommendation` | `title`, `description`, `priority`, `effort` | Actionable recommendation |
| `Attribution` | `threat_actor`, `confidence`, `evidence`, `ttps` | Threat attribution |

### Top-Level Response Models

| Model | Key Fields | Use Case |
|-------|-----------|----------|
| `ScanReportOutput` | `title`, `sections: list[ReportSectionOutput]`, `summary`, `metadata` | Full scan report generation |
| `ExecutiveSummaryOutput` | `summary`, `key_findings: list[Finding]`, `risk_level`, `recommendations` | Executive briefing |
| `RiskAssessmentOutput` | `overall_risk`, `risk_factors`, `findings`, `mitigations` | Risk scoring |
| `ThreatAssessmentOutput` | `threat_level`, `indicators: list[ThreatIndicator]`, `attribution`, `recommendations` | Threat intelligence |
| `CorrelationOutput` | `correlations`, `confidence`, `supporting_evidence`, `narrative` | Cross-scan correlation |
| `FindingValidationOutput` | `validated_findings`, `false_positives`, `uncertain`, `validation_notes` | Finding triage |
| `TextSummaryOutput` | `summary`, `key_points`, `entities_mentioned` | Generic text summarization |

---

## Usage

### With `LLMClient`

```python
from spiderfoot.llm_client import LLMClient
from spiderfoot.ai.schemas import RiskAssessmentOutput

client = LLMClient(config)

messages = [
    {"role": "system", "content": "You are a security analyst."},
    {"role": "user", "content": f"Assess the risk for this scan data: {scan_data}"},
]

# Returns a validated RiskAssessmentOutput instance
result = client.chat_structured(
    messages=messages,
    response_model=RiskAssessmentOutput,
    strict=True,  # Enforce strict schema compliance (default)
)

print(result.overall_risk)        # SeverityLevel enum
print(result.findings[0].title)   # str — fully typed
print(result.recommendations)     # list[Recommendation]
```

### With `AgentBase`

```python
from spiderfoot.agents.base import AgentBase
from spiderfoot.ai.schemas import ExecutiveSummaryOutput

class ReportAgent(AgentBase):
    async def generate_summary(self, scan_data: dict) -> ExecutiveSummaryOutput:
        messages = [
            {"role": "system", "content": "Generate an executive summary."},
            {"role": "user", "content": str(scan_data)},
        ]
        return await self.call_llm_structured(
            messages=messages,
            response_model=ExecutiveSummaryOutput,
        )
```

---

## How `chat_structured()` Works Internally

```python
def chat_structured(self, messages, response_model, strict=True):
    # 1. Generate JSON Schema from Pydantic model
    schema = response_model.model_json_schema()

    # 2. Build response_format payload
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": response_model.__name__,
            "schema": schema,
            "strict": strict,
        }
    }

    # 3. Inject format hint into system message
    # "Respond with valid JSON matching the provided schema."

    # 4. Send request with response_format
    raw = self._send_request(messages, response_format=response_format)

    # 5. Parse and validate
    return response_model.model_validate(json.loads(raw))
```

---

## Mock Support for Testing

The `_MockGenerator` class produces schema-conformant mock data:

```python
# In test mode, chat_structured() returns valid mock objects
client = LLMClient(config, mock=True)
result = client.chat_structured(messages, RiskAssessmentOutput)
# result is a valid RiskAssessmentOutput with generated mock data
```

The mock generator uses `_mock_from_schema()` to traverse the JSON Schema and produce conformant values for each field type.

---

## Creating Custom Schemas

Add new schemas to `spiderfoot/ai/schemas.py`:

```python
from pydantic import BaseModel, Field
from spiderfoot.ai.schemas import SeverityLevel, Finding

class CustomAnalysisOutput(BaseModel):
    """Custom analysis output for a specific use case."""
    analysis_type: str = Field(description="Type of analysis performed")
    findings: list[Finding] = Field(description="List of findings")
    risk_score: float = Field(ge=0.0, le=10.0, description="Risk score 0-10")
    severity: SeverityLevel = Field(description="Overall severity")
    raw_data: dict = Field(default_factory=dict, description="Raw analysis data")
```

Then use it:

```python
result = client.chat_structured(messages, CustomAnalysisOutput)
```

---

## Provider Compatibility

The `response_format: json_schema` mode is supported by:

| Provider | Support |
|----------|---------|
| OpenAI (GPT-4o, GPT-4o-mini) | Full `json_schema` mode |
| Anthropic (via LiteLLM) | JSON mode (schema hint in prompt) |
| Ollama (local models) | JSON mode (schema hint in prompt) |

SpiderFoot's LiteLLM gateway normalizes provider differences — the `chat_structured()` API is the same regardless of backend.
