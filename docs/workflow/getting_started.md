# Workflow Getting Started

This guide introduces SpiderFoot's powerful workflow functionality, including workspaces, multi-target scanning, and correlation analysis.

## What are Workflows?

SpiderFoot workflows enable:
- **Multi-target management** in organized workspaces
- **Concurrent scanning** across multiple targets
- **Cross-correlation analysis** to identify patterns
- **CTI report generation** for comprehensive intelligence

## Core Concepts

### Workspaces
Logical containers that group related targets, scans, and analysis results for a specific security assessment or project.

### Multi-Target Scanning
Run scans across multiple targets simultaneously with intelligent resource management and progress tracking.

### Correlation Analysis
Identify patterns, relationships, and shared indicators across multiple scans within a workspace.

### CTI Reports
Generate comprehensive threat intelligence reports using Model Context Protocol (MCP) integration.

## Quick Start

### 1. Create Your First Workspace

```bash
# Create workspace
python sfworkflow.py create-workspace "My First Assessment"
# Returns: Created workspace: ws_abc123
```

### 2. Add Targets

```bash
# Add multiple targets
python sfworkflow.py add-target ws_abc123 example.com --type DOMAIN_NAME
python sfworkflow.py add-target ws_abc123 192.168.1.1 --type IP_ADDRESS
python sfworkflow.py add-target ws_abc123 user@example.com --type EMAILADDR
```

### 3. Start Multi-Target Scan

```bash
# Run passive reconnaissance
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl,sfp_whois,sfp_threatcrowd \
  --wait
```

### 4. Analyze Results

```bash
# Run correlation analysis
python sfworkflow.py correlate ws_abc123

# Generate CTI report
python sfworkflow.py generate-cti ws_abc123 \
  --type threat_assessment \
  --output assessment_report.json
```

## Next Steps

- Learn about [Multi-Target Scanning](multi_target_scanning.md)
- Explore [Correlation Analysis](correlation_analysis.md)
- Generate [CTI Reports](cti_reports.md)
