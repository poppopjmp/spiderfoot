"""
Report Generator Agent
========================
Generates comprehensive Cyber Threat Intelligence (CTI) reports by
aggregating findings, correlations, and enriched context from the
Qdrant vector database.

Produces structured Markdown reports with:
  1. Executive Summary
  2. Key Findings
  3. Technical Analysis
  4. Risk Assessment
  5. Conclusions & Recommendations

Uses Qdrant to retrieve ALL indexed scan events (scrolled) plus
semantic similarity and infrastructure queries, ensuring every
report is rich, evidence-driven, and data-complete.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .base import AgentConfig, AgentResult, BaseAgent

logger = logging.getLogger("sf.agents.report_generator")

# ---------------------------------------------------------------------------
# System Prompt — Detailed CTI Report Instructions
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert Cyber Threat Intelligence (CTI) analyst and professional report writer with deep expertise in OSINT (Open Source Intelligence) reconnaissance methodology.

Your task is to produce a comprehensive, structured Cyber Threat Intelligence Report based on scan data collected by SpiderFoot, an automated OSINT reconnaissance platform. The data has been enriched with semantic analysis from a vector database (Qdrant) that indexes all scan events with embeddings for intelligent retrieval.

You will receive:
- Full event data from the vector database (all indexed scan events grouped by type)
- Event type statistics and risk breakdowns (info/low/medium/high/critical)
- Pre-computed attack surface metrics (domains, hosts, emails, open ports, technologies, services)
- Semantic similarity search results (most relevant events ranked by cosine similarity)
- Infrastructure-focused search results (network, ports, services)
- Geographic intelligence data (countries, coordinates, physical addresses)
- Correlation findings from cross-scan and rule-based analysis
- Summary statistics from the scan engine

═══════════════════════════════════════════════════════════════════
REPORT FORMAT: Write the report in clean, professional Markdown.
═══════════════════════════════════════════════════════════════════

Use the EXACT structure below. Every section is MANDATORY — do not skip or merge sections.

---

# Cyber Threat Intelligence Report: {Target Name}

**Report Date:** {current date}
**Classification:** TLP:AMBER — For authorized recipients only
**Prepared by:** SpiderFoot Automated CTI Engine
**Scan ID(s):** {scan identifiers}

---

## 1. Executive Summary

Write 3–5 substantive paragraphs providing a high-level strategic overview suitable for senior leadership, CISOs, and non-technical stakeholders.

Paragraph 1 — SCOPE & OBJECTIVE:
- State the assessment target (domain, organisation, IP range)
- Describe what was assessed: full OSINT reconnaissance covering DNS, WHOIS, web applications, email addresses, data breaches, network infrastructure, SSL/TLS certificates, social media, dark web exposure, etc.
- Mention the number of scans conducted and total events collected

Paragraph 2 — CRITICAL FINDINGS SUMMARY:
- Summarize the 3–5 most significant findings in business-impact language
- Quantify the attack surface: X domains discovered, Y hosts enumerated, Z email addresses exposed, N open ports identified
- Highlight any data breaches, leaked credentials, or sensitive data exposure
- Reference specific evidence (e.g., "14 email addresses were found in known data breaches")

Paragraph 3 — OVERALL RISK ASSESSMENT:
- State the overall risk rating: **Critical**, **High**, **Medium**, or **Low**
- Justify the rating based on the evidence (e.g., "The presence of 3 critical vulnerabilities and exposed administrative interfaces elevates the risk to High")
- Describe the potential business impact if findings are exploited

Paragraph 4 — KEY RECOMMENDATIONS (brief):
- List the top 3–5 immediate actions required
- Keep these at executive level; detailed recommendations go in Section 5

Paragraph 5 (optional) — CONTEXT:
- Any relevant organisational, industry, or threat landscape context
- Comparison with typical findings for similar targets

---

## 2. Key Findings

Present every significant finding as a numbered subsection. Order by severity (Critical → High → Medium → Low → Informational). Include ALL meaningful findings from the scan data — do not omit low-severity items; group similar findings of the same type if there are many.

For EACH finding, use this exact format:

### 2.X {Descriptive Finding Title}

| Attribute | Detail |
|-----------|--------|
| **Severity** | Critical / High / Medium / Low / Informational |
| **Category** | (e.g., Data Leak, Exposed Service, Misconfiguration, Vulnerable Software, Information Disclosure, DNS Issue, SSL/TLS Weakness, Email Security, Credential Exposure) |
| **Affected Asset(s)** | Specific domains, IPs, URLs, or email addresses affected |

**Description:**
Provide a detailed, technical explanation of what was discovered. Reference the specific event types and data from the scan. Explain WHY this is a finding and what it means technically.

**Evidence:**
Quote or reference specific scan data: IP addresses, HTTP headers, DNS records, SSL certificate details, open port banners, leaked data snippets, WHOIS records, etc. Use code blocks for technical evidence:
```
[paste relevant raw evidence from scan data]
```

**Impact:**
Explain the real-world security impact. What could an attacker do with this information? What is the business risk? Consider: data theft, unauthorised access, lateral movement, reputation damage, regulatory penalties (GDPR, PCI-DSS, etc.).

**Recommendation:**
Provide specific, actionable remediation steps. Be precise: "Disable TLS 1.0 and 1.1 on web server at 192.168.1.1" not just "Improve encryption."

---

## 3. Technical Analysis

Provide deep technical analysis in the following subsections. Use specific evidence from the scan data throughout. Include tables, lists, and code blocks where appropriate.

### 3.1 Attack Surface Overview

Quantify and describe the full attack surface:
- Total domains and subdomains discovered (list the key ones)
- IP addresses and netblock ownership
- Email addresses found (and where they were found — WHOIS, web scraping, breach databases)
- Open ports and services detected
- Web technologies and frameworks identified
- Certificates and SSL/TLS configuration

Present attack surface metrics in a summary table:
| Metric | Count |
|--------|-------|
| Domains | X |
| Hosts/IPs | X |
| Email Addresses | X |
| Open Ports | X |
| Technologies | X |
| Exposed Services | X |

### 3.2 Infrastructure Analysis

Analyse the network infrastructure:
- IP address ranges and ASN ownership
- Hosting providers and cloud platforms identified
- CDN and proxy usage (Cloudflare, Akamai, etc.)
- DNS configuration analysis (MX records, SPF, DKIM, DMARC)
- Mail server infrastructure
- Network topology observations

### 3.3 Technology Stack

Detail all web technologies, frameworks, CMS platforms, server software, and JavaScript libraries identified. Note version information where available and flag any outdated/vulnerable versions.

### 3.4 Email & Identity Exposure

Analyse email-related findings:
- Email addresses discovered and their sources
- Presence in known data breaches (HaveIBeenPwned, breach compilations)
- WHOIS privacy and registrant exposure
- Social media and public profile connections
- Credential exposure in paste sites or dark web

### 3.5 SSL/TLS & Certificate Analysis

Evaluate certificate security:
- Certificate validity, issuer, and expiry dates
- Protocol versions supported (TLS 1.0/1.1/1.2/1.3)
- Cipher suite strength
- Certificate chain issues
- HSTS configuration

### 3.6 DNS & Domain Intelligence

Analyse DNS findings:
- DNS zone configuration
- Subdomain enumeration results
- Similar/typosquatting domains detected
- Domain registration patterns
- Affiliated domains discovered
- Domain age and WHOIS history

---

## 4. Risk Assessment

Provide a comprehensive risk assessment using the following structure:

### 4.1 Risk Rating Matrix

Create a risk summary table:

| Risk Level | Count | Key Examples |
|------------|-------|--------------|
| Critical | X | Brief list of critical findings |
| High | X | Brief list of high findings |
| Medium | X | Brief list of medium findings |
| Low | X | Brief list of low findings |
| Informational | X | Brief list of informational findings |

### 4.2 Threat Scenario Analysis

Describe 2–3 realistic attack scenarios that could leverage the discovered findings. For each scenario:
- **Attack vector**: How would an adversary exploit these findings?
- **Attack chain**: What sequence of steps would they follow?
- **Potential impact**: What damage could be caused?
- **Likelihood**: How likely is this scenario?

### 4.3 Geographic Risk Analysis

Analyse the geographic distribution of the target's infrastructure:
- Countries where infrastructure is hosted
- Jurisdictional and regulatory implications (GDPR, data sovereignty)
- Geographic concentration risk
- Observations from geo-located endpoints

---

## 5. Conclusions & Recommendations

### 5.1 Summary of Findings

Provide a concise summary paragraph restating the most important findings and the overall security posture of the target.

### 5.2 Prioritised Recommendations

Present recommendations in a prioritised action table:

| Priority | Action | Rationale | Effort |
|----------|--------|-----------|--------|
| Immediate | Specific action | Why this matters | Low/Medium/High |
| Short-term (30 days) | Specific action | Why this matters | Low/Medium/High |
| Medium-term (90 days) | Specific action | Why this matters | Low/Medium/High |
| Long-term | Specific action | Why this matters | Low/Medium/High |

Include at least 5–10 specific, actionable recommendations covering:
- Immediate security fixes (critical/high findings)
- Configuration hardening
- Monitoring and detection improvements
- Policy and process improvements
- Ongoing OSINT monitoring recommendations

### 5.3 Next Steps

Recommend specific follow-up activities:
- Deeper penetration testing on identified attack vectors
- Continuous monitoring setup
- Vendor risk assessment (if third-party services identified)
- Employee awareness training (if email/identity exposure found)

---

*This report was generated by the SpiderFoot Automated CTI Engine using AI-powered analysis. All findings are based on passive OSINT reconnaissance and do not involve active exploitation or intrusive testing. Verify findings with authorised security assessments before taking remediation action.*

═══════════════════════════════════════════════════════════════════
IMPORTANT INSTRUCTIONS:
═══════════════════════════════════════════════════════════════════

1. Use EVERY piece of evidence provided in the scan data. Do not fabricate or assume data not present.
2. Reference specific event types, IP addresses, domains, and data points from the scan evidence.
3. If the scan data is limited, say so — but still analyse every piece of available data thoroughly.
4. Write in a professional, objective tone appropriate for a formal security report.
5. Use tables, lists, and code blocks to present technical data clearly.
6. Every finding MUST have specific evidence from the scan data — no generic statements without backing data.
7. The report should be thorough — aim for detailed, comprehensive coverage. Do not abbreviate or truncate sections.
8. Do NOT wrap the output in ```markdown``` fences — output raw Markdown directly.
"""


# ---------------------------------------------------------------------------
# Qdrant Context Retrieval (supports multiple scan IDs for workspace reports)
# ---------------------------------------------------------------------------

def _get_qdrant_context(
    scan_ids: List[str],
    target: str,
    max_events_per_scan: int = 500,
) -> dict:
    """Retrieve enriched context from Qdrant vector DB for one or more scans.

    Aggregates events across all provided scan IDs, builds statistics,
    runs semantic and infrastructure similarity searches, and returns
    a comprehensive context dict for the LLM prompt.
    """
    context: Dict[str, Any] = {
        "scan_events": {},
        "semantic_hits": [],
        "infra_hits": [],
        "event_stats": {},
        "attack_surface": {},
        "available": False,
    }

    if not scan_ids:
        return context

    try:
        from spiderfoot.qdrant_client import get_qdrant_client, Filter
        from spiderfoot.services.embedding_service import get_embedding_service
        from spiderfoot.vector_correlation import (
            VectorCorrelationEngine, VectorCorrelationConfig,
            CorrelationStrategy,
        )

        qdrant = get_qdrant_client()
        embeddings = get_embedding_service()
        config = VectorCorrelationConfig()

        all_events: list = []
        type_counts: Dict[str, int] = {}
        risk_counts: Dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}

        # ── 1. Scroll ALL events across all linked scans ──
        for sid in scan_ids:
            scan_filter = Filter(must=[Filter.match("scan_id", sid)])
            offset = None
            batch_limit = 100
            scan_event_count = 0

            while scan_event_count < max_events_per_scan:
                remaining = max_events_per_scan - scan_event_count
                fetch = min(batch_limit, remaining)
                points, next_offset = qdrant.scroll(
                    config.collection_name,
                    limit=fetch,
                    offset=offset,
                    filter_=scan_filter,
                )
                if not points:
                    break
                all_events.extend(points)
                scan_event_count += len(points)
                offset = next_offset
                if not next_offset:
                    break

        # Build type statistics and risk breakdown
        for pt in all_events:
            et = pt.payload.get("event_type", "UNKNOWN")
            type_counts[et] = type_counts.get(et, 0) + 1
            r = pt.payload.get("risk", 0)
            if isinstance(r, int) and 0 <= r <= 4:
                risk_counts[r] = risk_counts.get(r, 0) + 1

        # ── Pre-compute attack surface counts ──
        domain_types: Set[str] = {
            "INTERNET_NAME", "DOMAIN_NAME", "DOMAIN_WHOIS",
            "SIMILARDOMAIN", "AFFILIATE_DOMAIN",
        }
        host_types: Set[str] = {
            "IP_ADDRESS", "IPV6_ADDRESS", "NETBLOCK_MEMBER",
            "NETBLOCK_OWNER", "CO_HOSTED_SITE",
        }
        email_types: Set[str] = {
            "EMAIL_ADDRESS", "EMAILADDR", "EMAILADDR_GENERIC",
        }
        port_types: Set[str] = {
            "TCP_PORT_OPEN", "UDP_PORT_OPEN", "OPEN_TCP_PORT",
            "TCP_PORT_OPEN_BANNER",
        }
        tech_types: Set[str] = {
            "WEBSERVER_TECHNOLOGY", "SOFTWARE_USED",
            "WEBSERVER_HTTPHEADERS", "URL_WEB_FRAMEWORK",
            "WEBSERVER_STRANGEHEADER",
        }
        service_types: Set[str] = {
            "WEBSERVER_BANNER", "OPERATING_SYSTEM",
            "TCP_PORT_OPEN_BANNER", "URL_JAVASCRIPT_FRAMEWORK",
        }

        attack_surface: Dict[str, Any] = {
            "domains": sum(type_counts.get(t, 0) for t in domain_types),
            "hosts": sum(type_counts.get(t, 0) for t in host_types),
            "emails": sum(type_counts.get(t, 0) for t in email_types),
            "open_ports": sum(type_counts.get(t, 0) for t in port_types),
        }

        technologies: Set[str] = set()
        exposed_services: Set[str] = set()
        for pt in all_events:
            et = pt.payload.get("event_type", "")
            data = str(pt.payload.get("data", ""))[:200]
            if et in tech_types and data:
                technologies.add(data.split("\n")[0].strip()[:80])
            if et in service_types and data:
                exposed_services.add(data.split("\n")[0].strip()[:80])

        attack_surface["technologies"] = sorted(technologies)[:50]
        attack_surface["exposed_services"] = sorted(exposed_services)[:50]
        context["attack_surface"] = attack_surface

        context["event_stats"] = {
            "total_indexed": len(all_events),
            "scans_queried": len(scan_ids),
            "type_breakdown": dict(
                sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            ),
            "risk_breakdown": {
                "info": risk_counts.get(0, 0),
                "low": risk_counts.get(1, 0),
                "medium": risk_counts.get(2, 0),
                "high": risk_counts.get(3, 0),
                "critical": risk_counts.get(4, 0),
            },
        }

        # ── Group events by type (up to 25 per type for richer context) ──
        by_type: Dict[str, list] = {}
        for pt in all_events:
            et = pt.payload.get("event_type", "UNKNOWN")
            if et not in by_type:
                by_type[et] = []
            if len(by_type[et]) < 25:
                by_type[et].append({
                    "data": str(pt.payload.get("data", ""))[:800],
                    "source": pt.payload.get("source_module", ""),
                    "risk": pt.payload.get("risk", 0),
                    "confidence": pt.payload.get("confidence", 100),
                    "scan_id": pt.payload.get("scan_id", ""),
                })
        context["scan_events"] = by_type

        # ── 2. Semantic similarity search ──
        engine = VectorCorrelationEngine(
            qdrant=qdrant,
            embeddings=embeddings,
            config=config,
        )

        for sid in scan_ids:
            try:
                sim_result = engine.correlate(
                    f"security vulnerabilities threats exposure for {target}",
                    strategy=CorrelationStrategy.SIMILARITY,
                    scan_id=sid,
                )
                for h in sim_result.hits[:30]:
                    context["semantic_hits"].append({
                        "type": h.event.event_type,
                        "data": h.event.data[:500],
                        "source": h.event.source_module,
                        "risk": h.event.risk,
                        "score": round(h.score, 3),
                        "scan_id": sid,
                    })
            except Exception as e:
                logger.warning("Semantic search failed for scan %s: %s", sid, e)

        # Sort by score descending, take top 50
        context["semantic_hits"].sort(key=lambda x: x["score"], reverse=True)
        context["semantic_hits"] = context["semantic_hits"][:50]

        # ── 3. Infrastructure search ──
        for sid in scan_ids:
            try:
                infra_result = engine.correlate(
                    f"infrastructure network services ports DNS hosting for {target}",
                    strategy=CorrelationStrategy.INFRASTRUCTURE,
                    scan_id=sid,
                )
                for h in infra_result.hits[:20]:
                    context["infra_hits"].append({
                        "type": h.event.event_type,
                        "data": h.event.data[:500],
                        "source": h.event.source_module,
                        "score": round(h.score, 3),
                        "scan_id": sid,
                    })
            except Exception as e:
                logger.warning("Infra search failed for scan %s: %s", sid, e)

        context["infra_hits"].sort(key=lambda x: x["score"], reverse=True)
        context["infra_hits"] = context["infra_hits"][:40]

        context["available"] = True
        logger.info(
            "Qdrant context: %d scans queried, %d events, %d types, "
            "%d semantic hits, %d infra hits",
            len(scan_ids), len(all_events), len(type_counts),
            len(context["semantic_hits"]), len(context["infra_hits"]),
        )

    except ImportError as e:
        logger.warning("Qdrant/embedding dependencies not available: %s", e)
    except Exception as e:
        logger.warning("Failed to retrieve Qdrant context: %s", e)

    return context


# ---------------------------------------------------------------------------
# Report Generator Agent
# ---------------------------------------------------------------------------

class ReportGeneratorAgent(BaseAgent):
    """Generates structured CTI reports using Qdrant vector context + LLM."""

    @property
    def event_types(self) -> List[str]:
        return ["SCAN_COMPLETE", "REPORT_REQUEST"]

    async def process_event(self, event: Dict[str, Any]) -> AgentResult:
        scan_id = event.get("scan_id", "")
        scan_ids: List[str] = event.get("scan_ids", [])
        target = event.get("target", "")
        scan_name = event.get("scan_name", "")
        findings = event.get("findings", [])
        correlations = event.get("correlations", [])
        stats = event.get("stats", {})
        agent_results = event.get("agent_results", [])
        geo_data = event.get("geo_data", {})

        # Use scan_ids list if provided (workspace reports), else single scan_id
        if not scan_ids and scan_id:
            scan_ids = [scan_id]

        # ── Retrieve rich context from Qdrant ──
        qdrant_ctx = _get_qdrant_context(scan_ids, target)

        # ── Build the comprehensive user prompt ──
        qdrant_section = self._format_qdrant_context(qdrant_ctx)
        findings_text = self._format_findings(findings[:100])
        correlations_text = self._format_correlations(correlations[:30])
        geo_section = self._format_geo_data(geo_data)

        title_hint = scan_name or target or "Target"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        user_prompt = f"""Generate a comprehensive Cyber Threat Intelligence Report for the following target.

══════════════════════════════════════════════════
TARGET INFORMATION
══════════════════════════════════════════════════

**Target:** {target}
**Report Title:** {title_hint}
**Scan ID(s):** {', '.join(scan_ids) if scan_ids else scan_id}
**Report Date:** {now}
**Number of Scans:** {len(scan_ids)}

══════════════════════════════════════════════════
SCAN STATISTICS
══════════════════════════════════════════════════

- Total events collected: {stats.get('total_events', qdrant_ctx.get('event_stats', {}).get('total_indexed', 'N/A'))}
- Unique domains: {stats.get('domains', 'N/A')}
- Unique IPs: {stats.get('ips', 'N/A')}
- Emails found: {stats.get('emails', 'N/A')}
- High-risk findings: {stats.get('high_risk', 'N/A')}

{qdrant_section}

══════════════════════════════════════════════════
SCAN ENGINE FINDINGS
══════════════════════════════════════════════════

{findings_text}

══════════════════════════════════════════════════
CORRELATION ANALYSIS RESULTS
══════════════════════════════════════════════════

{correlations_text}

══════════════════════════════════════════════════
AGENT ANALYSIS
══════════════════════════════════════════════════

{json.dumps(agent_results[:10], indent=2) if agent_results else 'No agent analysis results available.'}

{geo_section}

══════════════════════════════════════════════════
INSTRUCTIONS
══════════════════════════════════════════════════

Using ALL the evidence above, generate a complete Cyber Threat Intelligence Report
following the exact structure specified in your system instructions.

- Analyse EVERY event type and its data — do not skip any category of findings.
- Reference specific IPs, domains, headers, banners, and data points as evidence.
- The Vector Database Context section is the PRIMARY source of intelligence — use it extensively.
- If certain sections have limited data, note the limitation but still analyse what is available.
- Produce the full report — do not truncate or abbreviate any section.
"""

        # ── Call LLM with retries ──
        last_error = None
        for attempt in range(3):
            try:
                response = await self.call_llm(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=self.config.llm_model,
                    temperature=0.3,
                    max_tokens=65536,
                )

                # Strip markdown fences if the model wraps output
                report_md = self._clean_markdown(response)

                return AgentResult(
                    agent_name=self.config.name,
                    event_id=event.get("id", ""),
                    scan_id=scan_id or (scan_ids[0] if scan_ids else ""),
                    result_type="scan_report",
                    data={
                        "report": report_md,
                        "model": self.config.llm_model,
                        "generated_at": now,
                        "scan_ids": scan_ids,
                        "target": target,
                        "events_analysed": qdrant_ctx.get("event_stats", {}).get(
                            "total_indexed", 0
                        ),
                        "qdrant_available": qdrant_ctx["available"],
                    },
                    confidence=0.9 if qdrant_ctx["available"] else 0.6,
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    "Report generation attempt %d/3 failed: %s", attempt + 1, e
                )
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(2 ** (attempt + 1))

        return AgentResult(
            agent_name=self.config.name,
            event_id=event.get("id", ""),
            scan_id=scan_id or (scan_ids[0] if scan_ids else ""),
            result_type="error",
            data={},
            confidence=0,
            error=str(last_error) if last_error else "Unknown error after 3 attempts",
        )

    # ── Formatting helpers ──

    def _format_qdrant_context(self, ctx: dict) -> str:
        """Format Qdrant vector DB context into a rich prompt section."""
        if not ctx.get("available"):
            return (
                "══════════════════════════════════════════════════\n"
                "VECTOR DATABASE CONTEXT\n"
                "══════════════════════════════════════════════════\n\n"
                "Vector DB context not available — report will use summary data only.\n"
            )

        lines = [
            "══════════════════════════════════════════════════",
            "VECTOR DATABASE CONTEXT (Qdrant — Full Scan Intelligence)",
            "══════════════════════════════════════════════════",
        ]

        # Event statistics
        stats = ctx.get("event_stats", {})
        lines.append(
            f"\n[INDEXED EVENTS] Total: {stats.get('total_indexed', 0)} "
            f"across {stats.get('scans_queried', 1)} scan(s)"
        )

        risk = stats.get("risk_breakdown", {})
        if risk:
            lines.append(
                f"  Risk distribution: "
                f"Critical={risk.get('critical', 0)}, "
                f"High={risk.get('high', 0)}, "
                f"Medium={risk.get('medium', 0)}, "
                f"Low={risk.get('low', 0)}, "
                f"Info={risk.get('info', 0)}"
            )

        # Attack surface
        atk = ctx.get("attack_surface", {})
        if atk:
            lines.append("\n[ATTACK SURFACE METRICS]")
            lines.append(f"  Domains: {atk.get('domains', 0)}")
            lines.append(f"  Hosts/IPs: {atk.get('hosts', 0)}")
            lines.append(f"  Email addresses: {atk.get('emails', 0)}")
            lines.append(f"  Open ports: {atk.get('open_ports', 0)}")
            techs = atk.get("technologies", [])
            if techs:
                lines.append(f"  Technologies: {', '.join(techs)}")
            svcs = atk.get("exposed_services", [])
            if svcs:
                lines.append(f"  Exposed services: {', '.join(svcs)}")

        # Type breakdown
        types = stats.get("type_breakdown", {})
        if types:
            lines.append(f"\n[EVENT TYPE DISTRIBUTION] ({len(types)} unique types)")
            for et, count in list(types.items())[:40]:
                lines.append(f"  {et}: {count}")

        # Detailed scan events
        scan_events = ctx.get("scan_events", {})
        if scan_events:
            total_items = sum(len(v) for v in scan_events.values())
            lines.append(
                f"\n[DETAILED SCAN EVENTS] ({total_items} items across "
                f"{len(scan_events)} event types)"
            )
            risk_labels = {0: "INFO", 1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}
            for event_type, events in scan_events.items():
                lines.append(f"\n  --- {event_type} ({len(events)} events) ---")
                for e in events:
                    rl = risk_labels.get(e.get("risk", 0), "?")
                    lines.append(
                        f"  [{rl}] {e['data'][:600]}  "
                        f"(source: {e['source']})"
                    )

        # Semantic hits
        semantic = ctx.get("semantic_hits", [])
        if semantic:
            lines.append(
                f"\n[SEMANTIC SIMILARITY MATCHES] "
                f"(Top {len(semantic)} most relevant events)"
            )
            for h in semantic:
                lines.append(
                    f"  [{h['type']}] score={h['score']} risk={h['risk']} | "
                    f"{h['data'][:400]}"
                )

        # Infrastructure hits
        infra = ctx.get("infra_hits", [])
        if infra:
            lines.append(
                f"\n[INFRASTRUCTURE INTELLIGENCE] ({len(infra)} matches)"
            )
            for h in infra:
                lines.append(
                    f"  [{h['type']}] score={h['score']} | {h['data'][:400]}"
                )

        return "\n".join(lines)

    def _format_findings(self, findings: List[Dict]) -> str:
        if not findings:
            return "No pre-processed findings available."
        lines = []
        for f in findings:
            risk = f.get("risk", 0)
            risk_label = {0: "INFO", 1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}.get(
                risk, "?"
            )
            lines.append(
                f"- [{risk_label}] [{f.get('event_type', f.get('type', '?'))}] "
                f"{str(f.get('data', f.get('description', '')))[:300]}"
            )
        return "\n".join(lines) if lines else "No findings available."

    def _format_correlations(self, correlations: List[Dict]) -> str:
        if not correlations:
            return "No correlations found."
        lines = []
        for c in correlations:
            lines.append(
                f"- {c.get('type', c.get('rule_name', '?'))}: "
                f"{c.get('description', c.get('rule_descr', ''))[:300]}"
            )
        return "\n".join(lines)

    def _format_geo_data(self, geo_data: Dict[str, Any]) -> str:
        if not geo_data:
            return ""
        countries = geo_data.get("countries", [])
        coordinates = geo_data.get("coordinates", [])
        addresses = geo_data.get("addresses", [])
        if not countries and not coordinates and not addresses:
            return ""

        lines = [
            "══════════════════════════════════════════════════",
            "GEOGRAPHIC INTELLIGENCE",
            "══════════════════════════════════════════════════",
        ]
        if countries:
            lines.append(f"\nCountries ({len(countries)}):")
            for c in countries[:30]:
                city = f", city: {c['city']}" if c.get("city") else ""
                lines.append(
                    f"  - {c.get('name', c.get('code', '?'))} "
                    f"({c.get('code', '??')}): {c.get('count', 0)} events{city}"
                )
        if coordinates:
            lines.append(f"\nGeo-located endpoints ({len(coordinates)}):")
            for coord in coordinates[:30]:
                lines.append(
                    f"  - ({coord.get('lat', 0)}, {coord.get('lon', 0)}) "
                    f"{coord.get('label', '')}"
                )
        if addresses:
            lines.append(f"\nPhysical addresses ({len(addresses)}):")
            for addr in addresses[:20]:
                lines.append(f"  - {addr}")
        return "\n".join(lines)

    def _clean_markdown(self, text: str) -> str:
        """Strip markdown code fences if the LLM wrapped the output."""
        t = text.strip()
        if t.startswith("```markdown"):
            t = t[len("```markdown"):].strip()
        elif t.startswith("```md"):
            t = t[len("```md"):].strip()
        elif t.startswith("```"):
            t = t[3:].strip()
        if t.endswith("```"):
            t = t[:-3].strip()
        return t

    @classmethod
    def create(cls) -> "ReportGeneratorAgent":
        """Create a report generator configured for CTI reports."""
        config = AgentConfig.from_env("report_generator")
        config.llm_model = "gemma3-27b"
        config.timeout_seconds = 600  # 10 min for large reports
        config.event_types = cls(config).event_types
        return cls(config)
