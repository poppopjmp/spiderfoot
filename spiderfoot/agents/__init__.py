"""
SpiderFoot Agents Service
==========================
AI-powered analysis agents that process scan data from the data lake.

Modeled after the Nemesis agent architecture, these agents consume events
from the event bus and produce enriched findings via LLM analysis.

Agents:
    - FindingValidator: Validates and deduplicates high-risk findings
    - CredentialAnalyzer: Analyzes exposed credentials for risk scoring
    - TextSummarizer: Summarizes large text content from scan results
    - ReportGenerator: Generates comprehensive scan reports
    - ThreatIntelAnalyzer: Cross-references findings with threat intel
    - DocumentAnalyzer: Analyzes uploaded documents for OSINT relevance
"""

__version__ = "0.1.0"
