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

- **Start the server:**
  ```sh
  python sf.py -l 127.0.0.1:5001
  ```
- **Access via browser:** [http://127.0.0.1:5001](http://127.0.0.1:5001)
- **Log in:** Use your admin account (created on first launch).
- **New Scan:**
  - Click **New Scan** to scan a single target.
  - Enter the target, select type and modules, and run.
  - Use the module search to quickly find and enable/disable modules.
- **Workspaces:**
  - Use **Workspaces** to manage multiple targets and scans.
  - Organize scans, view history, and collaborate with team members.
  - Workspaces are ideal for large projects, recurring assessments, or team-based investigations.
- **Results:**
  - View results in real time, filter by event type, and export data.
  - Use the graph view to visualize relationships between entities.
  - Export results as CSV, Excel, or JSON for further analysis.

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

- **DNS/Network**: sfp_dnsresolve, sfp_whois, sfp_ssl, sfp_portscan_tcp, sfp_banner
- **Threat Intelligence**: sfp_threatcrowd, sfp_virustotal, sfp_alienvault, sfp_malware
- **Search Engines**: sfp_google, sfp_bing, sfp_duckduckgo, sfp_yandex
- **Social Media**: sfp_twitter, sfp_github, sfp_linkedin, sfp_instagram
- **Data Breach**: sfp_haveibeen, sfp_hunter, sfp_emailrep

**Common CLI Patterns:**
```bash
# Domain reconnaissance
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_subdomain_enum,sfp_ssl,sfp_whois,sfp_threatcrowd
# Network block analysis
python sf.py -s 192.168.1.0/24 -t NETBLOCK -m sfp_portscan_tcp,sfp_banner,sfp_ssl
# Email investigation
python sf.py -s user@example.com -t EMAILADDR -m sfp_hunter,sfp_haveibeen,sfp_emailrep
```

---

## Advanced CLI & Workflow

- **Workspace management, multi-target scanning, correlation, CTI reports, and automation:**
  - See [Quick Start](quickstart.md) and [Developer Guide](developer_guide.md) for scripting, batch operations, and CI/CD integration.
  - Use `sfworkflow.py` for advanced workspace and scan management.

---

## Result Interpretation

- **Event Types:** IP_ADDRESS, DOMAIN_NAME, TCP_PORT_OPEN, SSL_CERTIFICATE_ISSUED, VULNERABILITY, MALICIOUS_DOMAIN, EMAILADDR, SOCIAL_MEDIA, etc.
- **Risk Levels:** HIGH (critical), MEDIUM (important), LOW (informational), INFO (general)
- **Common High-Risk Findings:** Open admin ports, expired SSL, known vulnerabilities, threat feed hits, breach exposures

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
