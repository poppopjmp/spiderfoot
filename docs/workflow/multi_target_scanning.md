# Multi-Target Scanning

Multi-target scanning allows you to run assessments across multiple targets simultaneously within a workspace, providing efficient resource utilization and comprehensive coverage.

## Overview

Multi-target scanning provides:
- **Concurrent execution** across multiple targets
- **Resource management** to prevent system overload
- **Progress tracking** for all running scans
- **Unified results** in a single workspace

## Getting Started

### Basic Multi-Target Scan

```bash
# Scan all targets in workspace
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl,sfp_whois \
  --wait
```

### Advanced Configuration

```bash
# Comprehensive assessment with custom options
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl,sfp_portscan_tcp,sfp_threatcrowd \
  --options '{"_maxthreads": 3, "_timeout": 300}' \
  --wait
```

## Module Selection

### Passive Modules (Safe for Production)
```bash
PASSIVE="sfp_dnsresolve,sfp_whois,sfp_ssl,sfp_threatcrowd,sfp_virustotal"
python sfworkflow.py multi-scan ws_abc123 --modules $PASSIVE
```

### Active Modules (Use with Caution)
```bash
ACTIVE="sfp_portscan_tcp,sfp_spider,sfp_subdomain_enum"
python sfworkflow.py multi-scan ws_abc123 --modules $ACTIVE
```

## Monitoring Progress

### Real-time Status
```bash
# Check scan status
python sfworkflow.py scan-status ws_abc123

# List all scans in workspace
python sfworkflow.py list-scans ws_abc123
```

### Web Interface
- Navigate to workspace details
- View scan progress grid
- Monitor resource usage
- Real-time event discovery

## Best Practices

1. **Start with passive modules** for initial reconnaissance
2. **Monitor system resources** during large scans
3. **Use appropriate thread limits** based on target sensitivity
4. **Regular correlation analysis** after scan completion
5. **Generate reports** for stakeholder communication

Learn more about [Correlation Analysis](correlation_analysis.md) and [CTI Reports](cti_reports.md).
