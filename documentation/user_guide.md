# User Guide

*Author: poppopjmp*

This guide covers the main features, workflows, and best practices for SpiderFoot, including the web interface, CLI, workspaces, exporting data, automation, and troubleshooting.

---

## Core Concepts

- **Target**: The entity you want to investigate (domain, IP, email, etc.)
- **Module**: A plugin that gathers specific types of information
- **Event**: A piece of information discovered about a target
- **Scan**: A collection of modules run against one or more targets
- **Workspace**: A container for organizing related targets and scans

---

## Web Interface

SpiderFoot features a modern React SPA with a dark theme, real-time updates, and comprehensive scan management.

### Getting Started

**Docker Compose (Recommended):**
```bash
# Core only (5 services)
docker compose -f docker-compose-microservices.yml up --build -d

# Or full stack (all services except SSO)
docker compose -f docker-compose-microservices.yml --profile full up --build -d
```
Access the UI at [http://localhost:3000](http://localhost:3000) (core) or [https://localhost](https://localhost) (with proxy profile) and log in with your admin credentials.

![Login](images/login.png)

### Dashboard

The dashboard provides at-a-glance statistics — active scans, total events, risk distribution, and recent activity.

![Dashboard](images/dashboard.png)

### New Scan

Click **New Scan** to configure and launch an OSINT scan:
- Enter the target (domain, IP, email, etc.)
- Select the target type and choose module categories
- Click **Run Scan**

![New Scan](images/new_scan.png)

### Scans

View all scans with status, target, event counts, and duration. Filter, search, and manage scans from one place.

![Scans](images/scans.png)

### Scan Detail

Each scan has a detailed view with tabbed navigation:

- **Summary** — Key metrics, risk distribution, top modules, event type breakdown
- **Browse** — Filter results by event type, risk level, and source module
- **Graph** — Interactive force-directed graph of entity relationships
- **GeoMap** — World map plotting discovered IP address locations
- **Correlations** — Automated findings from the 94-rule YAML engine
- **AI Report** — LLM-generated Cyber Threat Intelligence report
- **Scan Settings** — Module configuration used for the scan
- **Log** — Execution logs and module output

![Scan Detail - Summary](images/scan_detail_summary.png)

![Scan Detail - Browse](images/scan_detail_browse.png)

![Scan Detail - Graph](images/scan_detail_graph.png)

![Scan Detail - GeoMap](images/scan_detail_geomap.png)

![Scan Detail - Correlations](images/scan_detail_correlations.png)

![Scan Detail - AI Report](images/scan_detail_ai_report.png)

### Workspaces

Organize related scans into **Workspaces** for multi-target campaigns. Each workspace groups scans, tracks notes, and provides workspace-level analytics and AI-generated reports.

![Workspaces](images/workspaces.png)

### Settings & Agents

Configure global settings, module API keys, and monitor the 6 AI-powered analysis agents.

![Settings](images/settings.png)

![Agents](images/agents.png)

---

## CLI Usage

- **List modules:**
  ```sh
  python sf.py -M
  ```
- **Help for a module:**
  ```sh
  python sf.py -M sfp_dnsresolve
  ```
- **Run scan:**
  ```sh
  python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl
  ```
- **Workspaces (CLI):**
  - Create, add targets, and run multi-target scans (see [Quick Start](quickstart.md)).
  - Use CLI workspaces for automation and scripting in large-scale assessments.

---

## Module Categories & Usage Patterns

SpiderFoot v5.3.3 includes 277 modules organized into enhanced categories:

### Core Investigation Modules
- **DNS/Network**: sfp_dnsresolve, sfp_whois, sfp_ssl, sfp_portscan_tcp, sfp_banner
- **Threat Intelligence**: sfp_threatcrowd, sfp_virustotal, sfp_alienvault, sfp_malware
- **Search Engines**: sfp_google, sfp_bing, sfp_duckduckgo, sfp_yandex
- **Social Media**: sfp_twitter, sfp_github, sfp_linkedin, sfp_instagram, **sfp_tiktok_osint**
- **Data Breach**: sfp_haveibeen, sfp_hunter, sfp_emailrep

### Enhanced Investigation Modules (New in v5.3.3)
- **Blockchain Analytics**: sfp_blockchain_analytics (Bitcoin, Ethereum, Litecoin analysis)
- **Advanced Correlation**: sfp_advanced_correlation (entity resolution, pattern detection)
- **Performance Optimization**: sfp_performance_optimizer (caching, rate limiting)

**Enhanced CLI Patterns:**
```bash
# Domain reconnaissance with performance optimization
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_subdomain_enum,sfp_ssl,sfp_whois,sfp_threatcrowd,sfp_performance_optimizer

# TikTok OSINT investigation
python sf.py -s @username -t SOCIAL_MEDIA -m sfp_tiktok_osint,sfp_advanced_correlation

# Cryptocurrency investigation
python sf.py -s 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa -t BITCOIN_ADDRESS -m sfp_blockchain_analytics,sfp_advanced_correlation

# Network block analysis
python sf.py -s 192.168.1.0/24 -t NETBLOCK -m sfp_portscan_tcp,sfp_banner,sfp_ssl

# Email investigation with enhanced correlation
python sf.py -s user@example.com -t EMAILADDR -m sfp_hunter,sfp_haveibeen,sfp_emailrep,sfp_advanced_correlation

# Multi-target investigation with performance optimization
python sf.py -s multiple_targets.txt -t FILE -m sfp_dnsresolve,sfp_ssl,sfp_blockchain_analytics,sfp_performance_optimizer
```

---

## Advanced CLI & Workflow

- **Workspace management, multi-target scanning, correlation, CTI reports, and automation:**
  - See [Quick Start](quickstart.md) and [Developer Guide](developer_guide.md) for scripting, batch operations, and CI/CD integration.
  - Use `sfworkflow.py` for advanced workspace and scan management.

---

## Result Interpretation

SpiderFoot v5.3.3 provides enhanced result analysis and interpretation:

### Event Types
- **Traditional Types**: IP_ADDRESS, DOMAIN_NAME, TCP_PORT_OPEN, SSL_CERTIFICATE_ISSUED, VULNERABILITY, MALICIOUS_DOMAIN, EMAILADDR, SOCIAL_MEDIA
- **Enhanced Types**: TIKTOK_PROFILE, BLOCKCHAIN_ADDRESS, CRYPTOCURRENCY_TRANSACTION, AI_THREAT_SUMMARY, CORRELATION_MATCH, PERFORMANCE_METRIC

### Risk Levels
- **HIGH (critical)**: Active threats, known vulnerabilities, sanctions matches
- **MEDIUM (important)**: Suspicious patterns, potential risks, correlation matches
- **LOW (informational)**: General information, metadata, social profiles
- **INFO (general)**: Performance metrics, cache statistics, correlation data

### Enhanced Findings
- **TikTok Intelligence**: Profile verification, follower analytics, content patterns
- **Blockchain Analysis**: Transaction flows, risk scores, exchange attribution
- **Correlation Results**: Cross-platform identity matches, behavioral patterns
- **Performance Insights**: Cache hit rates, optimization recommendations
- **AI Analysis**: Automated threat summaries, pattern recognition

### Common High-Risk Findings
- Open admin ports, expired SSL, known vulnerabilities
- Threat feed hits, breach exposures
- **Cryptocurrency sanctions matches**
- **High-risk blockchain transactions**
- **Cross-platform identity correlation**
- **Anomalous behavioral patterns**

---

## Best Practices

- Define scope and start with passive modules
- Escalate to active scanning only when necessary
- Document findings and keep records
- Configure API keys for maximum coverage
- Regularly update SpiderFoot and modules
- Use workspaces to keep projects organized
- Tune thread counts and timeouts for performance
- Respect authorization and legal boundaries

---

## Troubleshooting & Help

- For common issues, see the [Troubleshooting Guide](troubleshooting.md).
- For module-specific help, see the [Modules Guide](modules.md).
- For configuration and API keys, see the [Configuration Guide](configuration.md).
- Use `python sf.py --help` and `python sf.py -M` for command and module help.
- Community support: GitHub Issues, Discord, and Wiki.

---

## Automation & Integration

- Use CLI and `sfworkflow.py` for scripting, batch scans, and automation
- Integrate with CI/CD (see examples in the old CLI guide)
- Use environment variables for configuration and API keys

---

## Exporting Data

- Export results as CSV, Excel, or JSON from the web UI or CLI
- Use the API for programmatic access (see [API Reference](api_reference.md))
- Reports can be shared with stakeholders or imported into other tools

---

Next: [Modules](modules.md) for a list of available modules and their usage.
