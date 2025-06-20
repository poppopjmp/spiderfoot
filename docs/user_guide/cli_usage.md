# CLI Usage Guide

SpiderFoot provides powerful command-line interfaces for both traditional scanning and the new workflow functionality. This guide covers all CLI operations and usage patterns.

## Traditional CLI (sf.py)

### Basic Usage

```bash
# Basic syntax
python sf.py [options] -s <target> -t <target_type> -m <modules>

# Simple domain scan
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Multiple modules
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois
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
-f, --output-file <file>      Output file path
```

#### Advanced Options
```bash
-v, --verbose                 Verbose output
-q, --quiet                   Quiet mode
-c, --config <file>           Configuration file
-M, --list-modules            List all available modules
-T, --list-types              List all target types
-V, --version                 Show version information
```

### Target Types

```bash
# Domain scanning
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl

# IP address scanning
python sf.py -s 192.168.1.1 -t IP_ADDRESS -m sfp_portscan_tcp,sfp_banner

# Network block scanning
python sf.py -s 192.168.1.0/24 -t NETBLOCK -m sfp_portscan_tcp

# Email investigation
python sf.py -s user@example.com -t EMAILADDR -m sfp_hunter,sfp_haveibeen

# Username investigation
python sf.py -s johndoe123 -t USERNAME -m sfp_social

# Human name investigation
python sf.py -s "John Doe" -t HUMAN_NAME -m sfp_fullcontact
```

### Module Management

```bash
# List all modules
python sf.py -M

# List modules by category
python sf.py -M | grep "DNS"

# Get module information
python sf.py -M sfp_dnsresolve

# Test specific module
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -v
```

### Output Formats

```bash
# CSV output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -o csv -f results.csv

# JSON output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -o json -f results.json

# GEXF (graph) output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -o gexf -f graph.gexf

# All formats
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -o all -f results
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

# Clone workspace
python sfworkflow.py clone-workspace ws_abc123 --name "Cloned Assessment"
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

# Import targets from file
python sfworkflow.py import-targets ws_abc123 targets.csv
```

### Multi-Target Scanning

```bash
# Basic multi-scan
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl,sfp_whois

# Scan specific targets
python sfworkflow.py multi-scan ws_abc123 \
  --targets example.com,test.example.com \
  --modules sfp_dnsresolve,sfp_portscan_tcp

# Advanced scan with options
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl,sfp_portscan_tcp \
  --options '{"_maxthreads": 3, "_timeout": 300}' \
  --wait

# Background scan
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl \
  --background
```

### Scan Management

```bash
# List scans in workspace
python sfworkflow.py list-scans ws_abc123

# Show scan status
python sfworkflow.py scan-status ws_abc123 scan_def456

# Stop running scan
python sfworkflow.py stop-scan scan_def456

# Import existing scan
python sfworkflow.py import-scan ws_abc123 scan_12345

# Bulk import scans
python sfworkflow.py import-scans ws_abc123 scan_001 scan_002 scan_003
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

# Export correlations
python sfworkflow.py export-correlations ws_abc123 --output correlations.json
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

# List CTI reports
python sfworkflow.py list-cti ws_abc123

# Export CTI report
python sfworkflow.py export-cti ws_abc123 report_abc123 \
  --format html \
  --output final_report.html
```

### Data Export

```bash
# Export workspace data
python sfworkflow.py export ws_abc123 \
  --format json \
  --output workspace_data.json

# Export specific data types
python sfworkflow.py export ws_abc123 \
  --format csv \
  --events IP_ADDRESS,DOMAIN_NAME \
  --output network_data.csv

# Export with filtering
python sfworkflow.py export ws_abc123 \
  --format json \
  --risk-level HIGH,MEDIUM \
  --output high_risk_findings.json
```

## Advanced CLI Usage

### Configuration Management

```bash
# Validate configuration
python sf.py --validate-config

# Test database connection
python sf.py --test-database

# Test modules
python sf.py --test-modules

# Show configuration
python sf.py --show-config
```

### Batch Operations

```bash
# Batch scanning from file
while read target; do
  python sf.py -s "$target" -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl -o csv -f "${target}_results.csv"
done < targets.txt

# Batch workspace creation
for client in client1 client2 client3; do
  python sfworkflow.py create-workspace "$client Assessment" --description "Security assessment for $client"
done
```

### Scripting and Automation

#### Bash Script Example

```bash
#!/bin/bash
# automated_assessment.sh

WORKSPACE_NAME="Automated Assessment $(date +%Y%m%d)"
TARGETS_FILE="targets.txt"
MODULES="sfp_dnsresolve,sfp_ssl,sfp_portscan_tcp,sfp_threatcrowd"

# Create workspace
WORKSPACE_ID=$(python sfworkflow.py create-workspace "$WORKSPACE_NAME" | grep -o 'ws_[a-f0-9]*')
echo "Created workspace: $WORKSPACE_ID"

# Add targets
while read target; do
  python sfworkflow.py add-target "$WORKSPACE_ID" "$target" --type DOMAIN_NAME
done < "$TARGETS_FILE"

# Start multi-scan
python sfworkflow.py multi-scan "$WORKSPACE_ID" --modules "$MODULES" --wait

# Run correlation
python sfworkflow.py correlate "$WORKSPACE_ID"

# Generate report
python sfworkflow.py generate-cti "$WORKSPACE_ID" --type threat_assessment --output "report_$(date +%Y%m%d).json"

echo "Assessment complete for workspace: $WORKSPACE_ID"
```

#### Python Script Example

```python
#!/usr/bin/env python3
# automated_workflow.py

import subprocess
import json
import sys

def run_command(cmd):
    """Execute command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    return result.stdout.strip()

def create_workspace(name, description=""):
    """Create a new workspace."""
    cmd = f'python sfworkflow.py create-workspace "{name}"'
    if description:
        cmd += f' --description "{description}"'
    
    output = run_command(cmd)
    if output and 'ws_' in output:
        # Extract workspace ID
        import re
        match = re.search(r'ws_[a-f0-9]+', output)
        return match.group(0) if match else None
    return None

def add_targets(workspace_id, targets):
    """Add multiple targets to workspace."""
    for target in targets:
        cmd = f'python sfworkflow.py add-target {workspace_id} {target["value"]} --type {target["type"]}'
        if 'metadata' in target:
            metadata = json.dumps(target['metadata'])
            cmd += f' --metadata \'{metadata}\''
        run_command(cmd)

def main():
    # Configuration
    workspace_name = "Automated Security Assessment"
    targets = [
        {"value": "example.com", "type": "DOMAIN_NAME"},
        {"value": "192.168.1.1", "type": "IP_ADDRESS"},
    ]
    modules = ["sfp_dnsresolve", "sfp_ssl", "sfp_threatcrowd"]
    
    # Create workspace
    workspace_id = create_workspace(workspace_name)
    if not workspace_id:
        print("Failed to create workspace")
        sys.exit(1)
    
    print(f"Created workspace: {workspace_id}")
    
    # Add targets
    add_targets(workspace_id, targets)
    
    # Start scan
    modules_str = ",".join(modules)
    run_command(f'python sfworkflow.py multi-scan {workspace_id} --modules {modules_str} --wait')
    
    # Generate report
    run_command(f'python sfworkflow.py generate-cti {workspace_id} --type threat_assessment --output assessment_report.json')
    
    print("Assessment completed successfully")

if __name__ == "__main__":
    main()
```

## Environment Variables

```bash
# SpiderFoot configuration
export SPIDERFOOT_WEB_ADDR="0.0.0.0"
export SPIDERFOOT_WEB_PORT="5001"
export SPIDERFOOT_DATABASE="/path/to/database.db"

# API keys
export SPIDERFOOT_VIRUSTOTAL_API_KEY="your_key"
export SPIDERFOOT_SHODAN_API_KEY="your_key"
export SPIDERFOOT_HUNTER_API_KEY="your_key"

# Workflow settings
export SPIDERFOOT_MAX_CONCURRENT_SCANS="3"
export SPIDERFOOT_SCAN_TIMEOUT="7200"

# Network settings
export HTTP_PROXY="http://proxy.example.com:8080"
export HTTPS_PROXY="http://proxy.example.com:8080"
```

## Performance Tuning

### Resource Management

```bash
# Limit concurrent operations
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl \
  --options '{"_maxthreads": 2}'

# Increase timeouts for slow networks
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve \
  --options '{"_timeout": 120}'

# Memory optimization
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve \
  --options '{"_maxpages": 50, "_maxdirs": 25}'
```

### Monitoring and Logging

```bash
# Verbose output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -v

# Debug logging
export SPIDERFOOT_LOG_LEVEL=DEBUG
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Log to file
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --logfile scan.log
```

## Error Handling and Troubleshooting

### Common CLI Issues

```bash
# Module not found
python sf.py -M | grep <module_name>

# Permission issues
chmod +x sf.py sfworkflow.py

# Database issues
python sf.py --test-database

# Configuration validation
python sf.py --validate-config
```

### Debugging Commands

```bash
# Test single module
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -v

# Check module status
python sf.py -M sfp_dnsresolve

# Validate target type
python sf.py -T

# Test network connectivity
python sf.py -s google.com -t DOMAIN_NAME -m sfp_dnsresolve
```

## Integration Examples

### Cron Jobs

```bash
# Daily automated scan
0 2 * * * /path/to/automated_assessment.sh >> /var/log/spiderfoot_daily.log 2>&1

# Weekly comprehensive assessment
0 2 * * 1 python sfworkflow.py multi-scan ws_weekly --modules comprehensive --wait
```

### CI/CD Integration

```yaml
# GitHub Actions
- name: Security Scan
  run: |
    python sfworkflow.py create-workspace "CI Scan ${{ github.run_number }}"
    python sfworkflow.py add-target $WORKSPACE_ID ${{ env.TARGET_DOMAIN }} --type DOMAIN_NAME
    python sfworkflow.py multi-scan $WORKSPACE_ID --modules sfp_dnsresolve,sfp_ssl --wait
```

### Log Analysis

```bash
# Parse scan results
python sfworkflow.py export ws_abc123 --format json | jq '.events[] | select(.risk == "HIGH")'

# Count events by type
python sfworkflow.py export ws_abc123 --format json | jq '.events[].event_type' | sort | uniq -c
```

Ready to explore more? Check out the [Module Guide](modules_guide.md) or learn about [Advanced Topics](../advanced/performance_tuning.md).
