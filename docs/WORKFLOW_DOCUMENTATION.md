# SpiderFoot Workflow Functionality Documentation

## Overview

This document provides comprehensive documentation for the SpiderFoot Workflow functionality, which enables multi-target scanning, cross-correlation analysis, workspace management, and CTI report generation using Model Context Protocol (MCP) integration.

## Architecture

### Core Components

1. **Workspace Management** (`workspace.py`)
   - Multi-target, multi-scan organization
   - Persistent storage of scan relationships
   - Single scan import functionality
   - Workspace cloning and merging

2. **Workflow Engine** (`workflow.py`)
   - Multi-target concurrent scanning
   - Cross-correlation analysis
   - Scan lifecycle management
   - Progress tracking and reporting

3. **MCP Integration** (`mcp_integration.py`)
   - Model Context Protocol client
   - CTI report generation
   - Multiple report formats (JSON, HTML, PDF, DOCX)
   - Template-based analysis

4. **API Interface** (`workflow_api.py`)
   - RESTful API endpoints
   - Workspace and scan management
   - Correlation and CTI operations
   - Export and search functionality

5. **CLI Interface** (`sfworkflow.py`)
   - Command-line interface
   - Batch operations
   - Automation support
   - Interactive workflows

6. **Configuration Management** (`workflow_config.py`)
   - Centralized configuration
   - Environment-specific settings
   - Validation and defaults

## Features

### Workspace Management

#### Creating Workspaces
```python
from spiderfoot.workspace import SpiderFootWorkspace

# Create new workspace
workspace = SpiderFootWorkspace(config, name="Security Assessment 2024")
workspace.description = "Q1 security assessment targets"
workspace.save_workspace()
```

#### Adding Targets
```python
# Add single target
target_id = workspace.add_target("example.com", "DOMAIN_NAME")

# Add multiple targets with metadata
targets = [
    {"value": "192.168.1.1", "type": "IP_ADDRESS", "metadata": {"priority": "high"}},
    {"value": "test.example.com", "type": "INTERNET_NAME", "metadata": {"env": "staging"}}
]

for target in targets:
    workspace.add_target(target["value"], target["type"], target["metadata"])
```

#### Importing Existing Scans
```python
# Import single scan
success = workspace.import_single_scan("scan_12345", {"source": "previous_assessment"})

# Bulk import
scan_ids = ["scan_001", "scan_002", "scan_003"]
results = workspace.bulk_import_scans(scan_ids)
print(f"Imported {sum(results.values())} of {len(results)} scans")
```

### Multi-Target Scanning

#### Starting Concurrent Scans
```python
from spiderfoot.workflow import SpiderFootWorkflow

# Create workflow
workflow = workspace.create_workflow()

# Define targets and modules
targets = [
    {"value": "example.com", "type": "DOMAIN_NAME"},
    {"value": "test.example.com", "type": "INTERNET_NAME"}
]

modules = ["sfp_dnsresolve", "sfp_portscan_tcp", "sfp_ssl"]

# Start multi-target scan
scan_ids = workflow.start_multi_target_scan(targets, modules)

# Wait for completion
statuses = workflow.wait_for_scans_completion(scan_ids, timeout=3600)
```

#### Progress Monitoring
```python
def progress_callback(message):
    print(f"Progress: {message}")

# Start with progress monitoring
scan_ids = workflow.start_multi_target_scan(
    targets, modules, 
    progress_callback=progress_callback
)
```

### Cross-Correlation Analysis

#### Running Correlations
```python
# Run all correlation rules
results = workflow.run_cross_correlation()

# Run specific rules
specific_rules = ["cross_scan_shared_infrastructure", "cross_scan_threat_indicators"]
results = workflow.run_cross_correlation(correlation_rules=specific_rules)

# Process results
for result in results:
    print(f"Rule: {result['rule_name']}")
    print(f"Type: {result['type']}")
    print(f"Affected scans: {result['scan_ids']}")
    print(f"Risk: {result['risk']}")
```

#### Custom Correlation Rules
The system supports custom correlation rules defined in YAML format:

```yaml
id: custom_shared_certificates
name: Shared SSL Certificates
description: Identifies shared SSL certificates across different targets
fields:
  - SSL_CERTIFICATE_ISSUED
confidence: 85
risk: INFO
```

### CTI Report Generation

#### Basic Report Generation
```python
# Generate threat assessment report
report = await workspace.generate_cti_report("threat_assessment")

# Generate with custom prompt
custom_prompt = "Focus on APT indicators and nation-state threats"
report = await workspace.generate_cti_report(
    "threat_assessment", 
    custom_prompt=custom_prompt
)
```

#### Available Report Types
1. **Threat Assessment** - Comprehensive threat analysis
2. **Infrastructure Analysis** - Security posture evaluation
3. **Attack Surface** - External exposure mapping

#### Exporting Reports
```python
from spiderfoot.mcp_integration import CTIReportExporter

exporter = CTIReportExporter()

# Export as HTML
html_file = exporter.export_report(report, "html", "threat_report.html")

# Export as JSON
json_file = exporter.export_report(report, "json", "threat_report.json")
```

## API Usage

### REST API Endpoints

#### Workspace Management
```bash
# List workspaces
GET /api/workspaces

# Create workspace
POST /api/workspaces
{
  "name": "Security Assessment",
  "description": "Q1 assessment targets"
}

# Get workspace details
GET /api/workspaces/{workspace_id}

# Delete workspace
DELETE /api/workspaces/{workspace_id}
```

#### Target Management
```bash
# Add target
POST /api/workspaces/{workspace_id}/targets
{
  "target": "example.com",
  "target_type": "DOMAIN_NAME",
  "metadata": {"priority": "high"}
}

# List targets
GET /api/workspaces/{workspace_id}/targets
```

#### Multi-Target Scanning
```bash
# Start multi-target scan
POST /api/workspaces/{workspace_id}/multi-scan
{
  "targets": [
    {"value": "example.com", "type": "DOMAIN_NAME"},
    {"value": "test.example.com", "type": "INTERNET_NAME"}
  ],
  "modules": ["sfp_dnsresolve", "sfp_portscan_tcp"],
  "scan_options": {"_maxthreads": 3}
}
```

#### CTI Report Generation
```bash
# Generate CTI report
POST /api/workspaces/{workspace_id}/cti-reports
{
  "report_type": "threat_assessment",
  "custom_prompt": "Focus on critical vulnerabilities"
}

# List reports
GET /api/workspaces/{workspace_id}/cti-reports

# Export report
POST /api/workspaces/{workspace_id}/cti-reports/{report_id}/export
{
  "format": "html",
  "output_path": "/path/to/report.html"
}
```

## CLI Usage

### Workspace Operations
```bash
# List workspaces
python sfworkflow.py list-workspaces

# Create workspace
python sfworkflow.py create-workspace "Security Assessment" --description "Q1 targets"

# Show workspace details
python sfworkflow.py show-workspace ws_abc123

# Clone workspace
python sfworkflow.py clone-workspace ws_abc123 --name "Security Assessment Copy"
```

### Target Management
```bash
# Add target
python sfworkflow.py add-target ws_abc123 example.com --type DOMAIN_NAME

# List targets
python sfworkflow.py list-targets ws_abc123

# Remove target
python sfworkflow.py remove-target ws_abc123 tgt_def456
```

### Scan Operations
```bash
# Import single scan
python sfworkflow.py import-scan ws_abc123 scan_12345

# Import multiple scans
python sfworkflow.py import-scans ws_abc123 scan_001 scan_002 scan_003

# Multi-target scanning
python sfworkflow.py multi-scan ws_abc123 \
  --targets example.com test.example.com \
  --modules sfp_dnsresolve sfp_portscan_tcp \
  --wait
```

### Correlation Analysis
```bash
# Run correlation analysis
python sfworkflow.py correlate ws_abc123

# Run specific rules
python sfworkflow.py correlate ws_abc123 \
  --rules cross_scan_shared_infrastructure cross_scan_threat_indicators

# Show correlation results
python sfworkflow.py show-correlations ws_abc123
```

### CTI Report Generation
```bash
# Generate CTI report
python sfworkflow.py generate-cti ws_abc123 \
  --type threat_assessment \
  --output threat_report.json

# List reports
python sfworkflow.py list-cti ws_abc123

# Export report
python sfworkflow.py export-cti ws_abc123 report_abc123 \
  --format html \
  --output report.html
```

## Configuration

### Configuration File Structure
```json
{
  "workflow": {
    "max_concurrent_scans": 5,
    "scan_timeout": 3600,
    "correlation_enabled": true,
    "auto_correlation": true
  },
  "mcp": {
    "enabled": true,
    "server_url": "http://localhost:8000",
    "api_key": "your-api-key",
    "timeout": 300
  },
  "correlation": {
    "rules_enabled": [
      "cross_scan_shared_infrastructure",
      "cross_scan_similar_technologies",
      "cross_scan_threat_indicators"
    ],
    "confidence_threshold": 75
  },
  "api": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 5001
  }
}
```

### Environment Variables
```bash
# MCP Configuration
export SPIDERFOOT_MCP_URL="http://localhost:8000"
export SPIDERFOOT_MCP_API_KEY="your-api-key"

# Workflow Configuration
export SPIDERFOOT_MAX_CONCURRENT_SCANS="5"
export SPIDERFOOT_SCAN_TIMEOUT="3600"

# API Configuration
export SPIDERFOOT_API_HOST="127.0.0.1"
export SPIDERFOOT_API_PORT="5001"
```

## Database Schema

### Workspace Table
```sql
CREATE TABLE tbl_workspaces (
    workspace_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_time REAL,
    modified_time REAL,
    targets TEXT,
    scans TEXT,
    metadata TEXT,
    correlations TEXT,
    workflows TEXT
);
```

### Workspace Metadata Structure
```json
{
  "correlations": [
    {
      "timestamp": 1640995200,
      "scan_ids": ["scan_001", "scan_002"],
      "results_count": 5,
      "results": [...]
    }
  ],
  "cti_reports": [
    {
      "report_id": "report_abc123",
      "report_type": "threat_assessment",
      "generated_time": "2024-01-01T00:00:00Z",
      "risk_rating": "HIGH"
    }
  ]
}
```

## Integration Examples

### Python Integration
```python
import asyncio
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot.workflow import SpiderFootWorkflow

async def automated_assessment(config, targets, modules):
    """Automated security assessment workflow."""
    
    # Create workspace
    workspace = SpiderFootWorkspace(config, name="Automated Assessment")
    
    # Add targets
    for target in targets:
        workspace.add_target(target["value"], target["type"])
    
    # Create and run workflow
    workflow = workspace.create_workflow()
    scan_ids = workflow.start_multi_target_scan(targets, modules)
    
    # Wait for completion
    statuses = workflow.wait_for_scans_completion(scan_ids)
    
    # Run correlation
    correlations = workflow.run_cross_correlation()
    
    # Generate CTI report
    report = await workspace.generate_cti_report("threat_assessment")
    
    return {
        "workspace_id": workspace.workspace_id,
        "scan_results": statuses,
        "correlations": correlations,
        "cti_report": report
    }

# Usage
targets = [
    {"value": "example.com", "type": "DOMAIN_NAME"},
    {"value": "192.168.1.1", "type": "IP_ADDRESS"}
]
modules = ["sfp_dnsresolve", "sfp_portscan_tcp", "sfp_ssl"]

result = asyncio.run(automated_assessment(config, targets, modules))
```

### Shell Script Integration
```bash
#!/bin/bash

# Automated workflow script
WORKSPACE_NAME="Daily Security Scan"
TARGETS_FILE="targets.json"
MODULES="sfp_dnsresolve sfp_portscan_tcp sfp_ssl"

# Create workspace
WORKSPACE_ID=$(python sfworkflow.py create-workspace "$WORKSPACE_NAME" | grep -o 'ws_[a-f0-9]*')

echo "Created workspace: $WORKSPACE_ID"

# Start multi-target scan
python sfworkflow.py multi-scan "$WORKSPACE_ID" \
  --targets-file "$TARGETS_FILE" \
  --modules $MODULES \
  --wait

# Run correlation
python sfworkflow.py correlate "$WORKSPACE_ID"

# Generate CTI report
python sfworkflow.py generate-cti "$WORKSPACE_ID" \
  --type threat_assessment \
  --output "daily_threat_report_$(date +%Y%m%d).json"

echo "Assessment complete for workspace: $WORKSPACE_ID"
```

## Troubleshooting

### Common Issues

#### MCP Connection Issues
```python
# Test MCP connection
import asyncio
from spiderfoot.mcp_integration import SpiderFootMCPClient

async def test_mcp():
    mcp_client = SpiderFootMCPClient(config)
    success = await mcp_client.test_mcp_connection()
    print(f"MCP Connection: {'Success' if success else 'Failed'}")

asyncio.run(test_mcp())
```

#### Scan Timeout Issues
- Increase `scan_timeout` in configuration
- Reduce `max_concurrent_scans` to prevent resource exhaustion
- Check module-specific timeout settings

#### Correlation Performance
- Enable `parallel_processing` in correlation settings
- Adjust `confidence_threshold` to filter results
- Limit `max_results_per_rule` for large datasets

### Logging and Debugging
```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Workflow-specific logging
workflow_logger = logging.getLogger("spiderfoot.workflow")
workspace_logger = logging.getLogger("spiderfoot.workspace")
mcp_logger = logging.getLogger("spiderfoot.mcp")
```

### Performance Optimization

#### Scan Performance
- Adjust `max_concurrent_scans` based on system resources
- Use scan options to limit module execution time
- Implement progress callbacks for monitoring

#### Correlation Performance
- Enable parallel processing for large datasets
- Use specific correlation rules instead of running all rules
- Implement result caching for repeated analyses

#### Memory Management
- Regular workspace cleanup using retention policies
- Limit export data size using configuration settings
- Use streaming for large data exports

## Security Considerations

### API Security
- Enable authentication for production deployments
- Use HTTPS for all API communications
- Implement rate limiting to prevent abuse
- Validate all input parameters

### MCP Security
- Use secure connections (HTTPS) for MCP communication
- Implement API key rotation
- Validate MCP server certificates
- Sanitize data before sending to MCP servers

### Data Protection
- Encrypt sensitive workspace metadata
- Implement data retention policies
- Use secure file permissions for exports
- Regular backup of critical workspace data

### Access Control
- Implement user-based workspace access
- Use role-based permissions for API endpoints
- Audit log all workspace modifications
- Secure database connections

## Best Practices

### Workflow Design
1. **Organize by project or assessment period**
2. **Use descriptive workspace names and descriptions**
3. **Group related targets in single workspaces**
4. **Regular correlation analysis after scan completion**
5. **Generate CTI reports for stakeholder communication**

### Performance
1. **Limit concurrent scans based on system capacity**
2. **Use appropriate scan timeouts for target types**
3. **Monitor resource usage during large assessments**
4. **Implement cleanup procedures for completed assessments**

### Data Management
1. **Regular export of important workspace data**
2. **Use metadata to track assessment context**
3. **Implement retention policies for old data**
4. **Backup critical correlation results and CTI reports**

## Future Enhancements

### Planned Features
1. **Advanced correlation rule engine**
2. **Real-time scan monitoring dashboard**
3. **Integration with external SIEM systems**
4. **Automated threat hunting workflows**
5. **Machine learning-based anomaly detection**

### Integration Roadmap
1. **STIX/TAXII integration for threat intelligence**
2. **Webhook support for external notifications**
3. **Plugin architecture for custom report formats**
4. **Cloud deployment automation**
5. **Kubernetes orchestration support**
