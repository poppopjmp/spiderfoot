# CLI Usage Guide

SpiderFoot provides powerful command-line interfaces for both traditional scanning and advanced workflow functionality.

## Traditional CLI (sf.py)

### Basic Usage

```bash
# Basic syntax
python sf.py [options] -s <target> -t <target_type> -m <modules>

# Simple domain scan
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Multiple modules
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois

# Start web interface
python sf.py -l 127.0.0.1:5001
```

### Command Line Options

#### Core Options
```bash
-s, --scan <target>           Target to scan
-t, --target-type <type>      Target type (DOMAIN_NAME, IP_ADDRESS, etc.)
-m, --modules <modules>       Comma-separated list of modules
-l, --listen <host:port>      Start web server on host:port
-d, --database <path>         Database file path
-o, --output <format>         Output format (csv, json, gexf)
-f, --output-file <path>      Output file path
```

#### Advanced Options
```bash
-v, --verbose                 Verbose output
-q, --quiet                   Quiet mode
-c, --config <file>           Configuration file path
-M, --list-modules [filter]   List available modules (optionally filtered)
-T, --list-types              List all target types
-V, --version                 Show version information
-k, --correlate               Run correlation rules post-scan
-r, --recurse <depth>         Maximum recursion depth
-n, --name <scan_name>        Custom scan name
```

### Module Management

```bash
# List all modules
python sf.py -M

# List modules by category
python sf.py -M | grep "DNS"

# Get help for specific module
python sf.py -M sfp_dnsresolve

# List all target types
python sf.py -T
```

### Output Formats

```bash
# CSV output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -o csv -f results.csv

# JSON output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -o json -f results.json

# GEXF (Graph) output for visualization
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -o gexf -f results.gexf
```

### Advanced Scanning Examples

```bash
# Comprehensive domain scan
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois,sfp_portscan_tcp,sfp_cert

# IP address investigation
python sf.py -s 192.168.1.1 -t IP_ADDRESS -m sfp_shodan,sfp_portscan_tcp,sfp_bgpview

# Email investigation
python sf.py -s john@example.com -t EMAILADDR -m sfp_hunter,sfp_hibp,sfp_emailformat

# Company investigation
python sf.py -s "Example Corp" -t COMPANY_NAME -m sfp_googlesearch,sfp_bing,sfp_clearbit

# Scan with correlation analysis
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl -k

# Custom scan name and output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -n "Daily Domain Scan" -o json -f daily_scan.json
```

## Workflow CLI (sfworkflow.py)

*Advanced multi-target scanning and workspace management*

### Workspace Management

```bash
# List all workspaces
python sfworkflow.py list-workspaces

# Create new workspace
python sfworkflow.py create-workspace "Security Assessment 2024" --description "Q1 security targets"

# Show workspace details
python sfworkflow.py show-workspace ws_abc123

# Clone workspace
python sfworkflow.py clone-workspace ws_abc123 --name "Assessment Copy"

# Delete workspace (with confirmation)
python sfworkflow.py delete-workspace ws_abc123

# Force delete without confirmation
python sfworkflow.py delete-workspace ws_abc123 --force

# Merge workspaces
python sfworkflow.py merge-workspaces ws_target ws_source
```

### Target Management

```bash
# Add single target
python sfworkflow.py add-target ws_abc123 example.com --type DOMAIN_NAME

# Add target with metadata
python sfworkflow.py add-target ws_abc123 example.com --type DOMAIN_NAME --metadata '{"priority": "high", "env": "production"}'

# List workspace targets
python sfworkflow.py list-targets ws_abc123

# Remove target
python sfworkflow.py remove-target ws_abc123 tgt_def456
```

### Scan Operations

```bash
# Import existing scan into workspace
python sfworkflow.py import-scan ws_abc123 scan_12345

# Import multiple scans
python sfworkflow.py import-scans ws_abc123 scan_001 scan_002 scan_003

# List workspace scans
python sfworkflow.py list-scans ws_abc123

# Multi-target scanning
python sfworkflow.py multi-scan ws_abc123 \
  --targets example.com test.example.com \
  --modules sfp_dnsresolve sfp_ssl sfp_portscan_tcp \
  --wait

# Multi-scan with targets from file
python sfworkflow.py multi-scan ws_abc123 \
  --targets-file targets.json \
  --modules sfp_dnsresolve sfp_ssl \
  --options '{"timeout": 300}' \
  --wait
```

### Correlation Analysis

```bash
# Run correlation analysis on all scans
python sfworkflow.py correlate ws_abc123

# Run specific correlation rules
python sfworkflow.py correlate ws_abc123 \
  --rules cross_scan_shared_infrastructure cross_scan_threat_indicators

# Run correlation on specific scans
python sfworkflow.py correlate ws_abc123 \
  --scan-ids scan_001 scan_002

# Show correlation results
python sfworkflow.py show-correlations ws_abc123
```

### CTI Report Generation

*Requires MCP (Model Context Protocol) integration*

```bash
# Generate threat assessment report
python sfworkflow.py generate-cti ws_abc123 \
  --type threat_assessment \
  --output threat_report.json

# Generate executive summary
python sfworkflow.py generate-cti ws_abc123 \
  --type executive_summary \
  --output executive_report.html

# List CTI reports
python sfworkflow.py list-cti ws_abc123

# Export CTI report to different format
python sfworkflow.py export-cti ws_abc123 report_abc123 \
  --format html \
  --output final_report.html
```

### Data Operations

```bash
# Search events across workspace
python sfworkflow.py search ws_abc123 "malware" \
  --types MALICIOUS_IPADDR MALICIOUS_DOMAIN \
  --limit 50

# Search specific scans
python sfworkflow.py search ws_abc123 "certificate" \
  --scans scan_001 scan_002 \
  --limit 100

# Export workspace data
python sfworkflow.py export ws_abc123 \
  --format json \
  --output workspace_data.json

# Test MCP connection (if CTI features enabled)
python sfworkflow.py test-mcp
```

### Example Workflows

#### Complete Assessment Workflow
```bash
#!/bin/bash

# Variables
WORKSPACE_NAME="Monthly Security Assessment"
TARGETS="example.com test.example.com api.example.com"
MODULES="sfp_dnsresolve sfp_ssl sfp_portscan_tcp sfp_whois sfp_cert"

# Create workspace
WORKSPACE_ID=$(python sfworkflow.py create-workspace "$WORKSPACE_NAME" | grep -o 'ws_[a-f0-9]*')
echo "Created workspace: $WORKSPACE_ID"

# Add targets
for target in $TARGETS; do
    python sfworkflow.py add-target "$WORKSPACE_ID" "$target" --type DOMAIN_NAME
done

# Start multi-target scan
python sfworkflow.py multi-scan "$WORKSPACE_ID" \
  --targets $TARGETS \
  --modules $MODULES \
  --wait

# Run correlation analysis
python sfworkflow.py correlate "$WORKSPACE_ID"

# Generate CTI report
python sfworkflow.py generate-cti "$WORKSPACE_ID" \
  --type threat_assessment \
  --output "assessment_$(date +%Y%m%d).json"

echo "Assessment complete for workspace: $WORKSPACE_ID"
```

#### Target File Format (targets.json)
```json
[
  {
    "value": "example.com",
    "type": "DOMAIN_NAME",
    "metadata": {
      "priority": "high",
      "environment": "production"
    }
  },
  {
    "value": "192.168.1.1",
    "type": "IP_ADDRESS", 
    "metadata": {
      "priority": "medium",
      "location": "datacenter-1"
    }
  }
]
```

## Configuration CLI

### Configuration File Management

```bash
# Create sample configuration
python -m spiderfoot.workflow_config create-sample workflow_config.json

# View current configuration
python sf.py --show-config

# Use custom configuration file
python sf.py -c custom_config.conf -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Validate configuration
python sf.py --validate-config
```

## Integration Examples

### Automation Scripts

#### Python Integration
```python
#!/usr/bin/env python3
import subprocess
import json

def run_spiderfoot_scan(target, modules):
    """Run SpiderFoot scan and return results."""
    cmd = [
        'python', 'sf.py',
        '-s', target,
        '-t', 'DOMAIN_NAME',
        '-m', ','.join(modules),
        '-o', 'json',
        '-f', 'results.json'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        with open('results.json', 'r') as f:
            return json.load(f)
    else:
        print(f"Error: {result.stderr}")
        return None

# Usage
modules = ['sfp_dnsresolve', 'sfp_ssl', 'sfp_whois']
results = run_spiderfoot_scan('example.com', modules)
```

#### Bash Automation
```bash
#!/bin/bash

# Batch scanning script
TARGETS_FILE="targets.txt"
OUTPUT_DIR="scan_results"
MODULES="sfp_dnsresolve,sfp_ssl,sfp_portscan_tcp"

mkdir -p "$OUTPUT_DIR"

while IFS= read -r target; do
    echo "Scanning: $target"
    
    python sf.py \
        -s "$target" \
        -t DOMAIN_NAME \
        -m "$MODULES" \
        -o json \
        -f "$OUTPUT_DIR/${target}_results.json" \
        -n "Batch Scan: $target"
        
    echo "Completed: $target"
done < "$TARGETS_FILE"

echo "All scans completed. Results in: $OUTPUT_DIR"
```

## Performance and Troubleshooting

### Performance Optimization

```bash
# Adjust thread count for faster scanning
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --max-threads 10

# Use timeout for faster completion
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --timeout 60

# Limit recursion depth
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -r 2
```

### Debugging and Logging

```bash
# Verbose output for debugging
python sf.py -v -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Quiet mode (minimal output)
python sf.py -q -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Log to file
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --log-file scan.log
```

### Common Issues

```bash
# Check if modules are working
python sf.py -M sfp_dnsresolve

# Test with single module
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Check database connectivity
python sf.py --test-db

# Verify target type
python sf.py -T | grep DOMAIN

# Check API configuration
python sf.py --test-apis
```

# GEXF (graph) output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -o gexf -f graph.gexf
```

## Workflow CLI (sfworkflow.py)

### Workspace Management

```bash
# Create workspace
python sfworkflow.py create-workspace "Assessment Name" \
  --description "Description of the assessment"

# List workspaces
python sfworkflow.py list-workspaces

# Show workspace details
python sfworkflow.py show-workspace ws_abc123

# Delete workspace
python sfworkflow.py delete-workspace ws_abc123
```

### Target Management

```bash
# Add single target
python sfworkflow.py add-target ws_abc123 example.com --type DOMAIN_NAME

# Add target with metadata
python sfworkflow.py add-target ws_abc123 example.com --type DOMAIN_NAME \
  --metadata '{"priority": "high", "environment": "production"}'

# List targets
python sfworkflow.py list-targets ws_abc123

# Remove target
python sfworkflow.py remove-target ws_abc123 tgt_def456
```

### Multi-Target Scanning

```bash
# Basic multi-scan
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl,sfp_whois

# Advanced scan with options
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl,sfp_portscan_tcp \
  --options '{"_maxthreads": 3, "_timeout": 300}' \
  --wait
```

### Correlation Analysis

```bash
# Run all correlations
python sfworkflow.py correlate ws_abc123

# Run specific correlation rules
python sfworkflow.py correlate ws_abc123 \
  --rules cross_scan_shared_infrastructure,cross_scan_threat_indicators

# Show correlation results
python sfworkflow.py show-correlations ws_abc123
```

### CTI Report Generation

```bash
# Generate threat assessment report
python sfworkflow.py generate-cti ws_abc123 \
  --type threat_assessment \
  --output threat_report.json

# Generate with custom prompt
python sfworkflow.py generate-cti ws_abc123 \
  --type threat_assessment \
  --prompt "Focus on APT indicators and nation-state threats" \
  --output custom_report.html
```

## Advanced Usage

### Batch Operations

```bash
# Batch scanning from file
while read target; do
  python sf.py -s "$target" -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl -o csv -f "${target}_results.csv"
done < targets.txt
```

### Environment Variables

```bash
# SpiderFoot configuration
export SPIDERFOOT_WEB_ADDR="0.0.0.0"
export SPIDERFOOT_WEB_PORT="5001"
export SPIDERFOOT_DATABASE="/path/to/database.db"

# API keys
export SPIDERFOOT_VIRUSTOTAL_API_KEY="your_key"
export SPIDERFOOT_SHODAN_API_KEY="your_key"
```

## Troubleshooting

### Common Issues

```bash
# Module not found
python sf.py -M | grep <module_name>

# Permission issues
chmod +x sf.py sfworkflow.py

# Configuration validation
python sf.py --validate-config
```

For more detailed examples and advanced usage, see the [User Guide](user_guide/basic_usage.md) and [Workflow Documentation](WORKFLOW_DOCUMENTATION.md).
