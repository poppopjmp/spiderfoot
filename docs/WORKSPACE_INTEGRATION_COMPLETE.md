# SpiderFoot Workspace Integration Guide

## Overview

SpiderFoot workspaces provide a powerful way to organize, manage, and analyze security assessments across multiple targets and scans. This comprehensive guide covers all aspects of workspace integration with the SpiderFoot platform.

## Table of Contents

1. [Workspace Concepts](#workspace-concepts)
2. [Creating and Managing Workspaces](#creating-and-managing-workspaces)
3. [Target Management](#target-management)
4. [Multi-Target Scanning](#multi-target-scanning)
5. [Scan Import and Export](#scan-import-and-export)
6. [Cross-Correlation Analysis](#cross-correlation-analysis)
7. [Report Generation](#report-generation)
8. [API Integration](#api-integration)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

## Workspace Concepts

### What is a Workspace?

A workspace is a logical container that groups related targets, scans, and analysis results for a specific security assessment or project. Workspaces enable:

- **Organization**: Group related targets by project, client, or assessment period
- **Collaboration**: Share scan results and analysis across team members
- **Correlation**: Identify patterns and relationships across multiple scans
- **Reporting**: Generate comprehensive reports spanning multiple targets
- **Workflow**: Manage complex assessment lifecycles

### Key Components

1. **Targets**: Domain names, IP addresses, networks, or other entities to assess
2. **Scans**: Individual SpiderFoot scan instances within the workspace
3. **Correlations**: Cross-scan pattern analysis and threat intelligence
4. **Metadata**: Assessment context, timing, and configuration
5. **Reports**: Generated analysis and findings documentation

## Creating and Managing Workspaces

### Creating a New Workspace

#### Web UI Method

1. Navigate to the **Workspaces** section in the SpiderFoot web interface
2. Click **Create Workspace**
3. Provide:
   - **Name**: Descriptive workspace name (e.g., "Q1 2024 Security Assessment")
   - **Description**: Optional detailed description
4. Click **Create Workspace**

#### CLI Method

```bash
python sfworkflow.py create-workspace "Security Assessment 2024" \
  --description "Quarterly security assessment targets"
```

#### API Method

```bash
curl -X POST http://localhost:5001/api/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Security Assessment 2024",
    "description": "Quarterly security assessment targets"
  }'
```

### Workspace Configuration

#### Basic Settings

- **Name**: Human-readable workspace identifier
- **Description**: Detailed workspace purpose and scope
- **Created Time**: Automatic timestamp of workspace creation
- **Modified Time**: Last modification timestamp

#### Advanced Settings

- **Retention Policy**: Data retention period (default: 90 days)
- **Auto-scheduling**: Automatic scan scheduling configuration
- **Business Hours**: Scan timing restrictions
- **Throttling**: Resource usage limits

### Editing Workspaces

#### Updating Workspace Information

```python
# Python API
workspace = SpiderFootWorkspace.load_workspace(config, workspace_id)
workspace.name = "Updated Assessment Name"
workspace.description = "Updated description"
workspace.save_workspace()
```

#### Web UI Editing

1. Navigate to **Workspaces** → Select workspace → **Edit**
2. Modify name or description
3. Click **Update Workspace**

## Target Management

### Adding Targets

Targets are the entities you want to assess within a workspace. SpiderFoot supports multiple target types:

#### Supported Target Types

- **DOMAIN_NAME**: example.com
- **INTERNET_NAME**: subdomain.example.com
- **IP_ADDRESS**: 192.168.1.1
- **NETBLOCK**: 192.168.1.0/24
- **ASN**: AS12345
- **EMAILADDR**: user@example.com
- **PHONE_NUMBER**: +1-555-123-4567
- **HUMAN_NAME**: John Doe
- **BITCOIN_ADDRESS**: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa

#### Adding Single Target

**Web UI:**
1. Select workspace → **Add Target**
2. Enter target value and select type
3. Click **Add Target**

**CLI:**
```bash
python sfworkflow.py add-target ws_abc123 example.com --type DOMAIN_NAME
```

**API:**
```bash
curl -X POST http://localhost:5001/api/workspaces/ws_abc123/targets \
  -H "Content-Type: application/json" \
  -d '{
    "target": "example.com",
    "target_type": "DOMAIN_NAME",
    "metadata": {"priority": "high", "environment": "production"}
  }'
```

#### Bulk Target Import

**JSON Format:**
```json
{
  "targets": [
    {"value": "example.com", "type": "DOMAIN_NAME", "metadata": {"priority": "high"}},
    {"value": "test.example.com", "type": "INTERNET_NAME", "metadata": {"environment": "staging"}},
    {"value": "192.168.1.1", "type": "IP_ADDRESS", "metadata": {"location": "datacenter"}}
  ]
}
```

**Python Implementation:**
```python
targets = [
    {"value": "example.com", "type": "DOMAIN_NAME"},
    {"value": "test.example.com", "type": "INTERNET_NAME"},
    {"value": "192.168.1.1", "type": "IP_ADDRESS"}
]

for target in targets:
    workspace.add_target(target["value"], target["type"], target.get("metadata", {}))
```

### Target Metadata

Target metadata provides additional context for assessment:

```python
metadata = {
    "priority": "high|medium|low",
    "environment": "production|staging|development",
    "owner": "team-name",
    "criticality": "critical|important|normal",
    "location": "datacenter|cloud|remote",
    "notes": "Additional context information"
}
```

### Removing Targets

**Web UI:** Select workspace → Target list → **Remove** button

**CLI:**
```bash
python sfworkflow.py remove-target ws_abc123 tgt_def456
```

**API:**
```bash
curl -X DELETE http://localhost:5001/api/workspaces/ws_abc123/targets/tgt_def456
```

## Multi-Target Scanning

### Starting Multi-Target Scans

Multi-target scanning allows you to run assessments across all targets in a workspace simultaneously.

#### Scan Configuration

**Module Selection:**
- **Passive Modules**: DNS, WHOIS, certificate analysis
- **Active Modules**: Port scanning, web crawling
- **Threat Intelligence**: ThreatCrowd, VirusTotal, Shodan
- **Custom Selection**: Choose specific modules for your assessment

**Example Module Sets:**

```python
# Basic reconnaissance
basic_modules = [
    "sfp_dnsresolve", "sfp_whois", "sfp_sslcert", 
    "sfp_subdomain_enum", "sfp_threatcrowd"
]

# Comprehensive assessment
comprehensive_modules = [
    "sfp_dnsresolve", "sfp_whois", "sfp_sslcert",
    "sfp_portscan_tcp", "sfp_webheader", "sfp_subdomain_enum",
    "sfp_threatcrowd", "sfp_virustotal", "sfp_shodan"
]

# Stealth assessment (passive only)
stealth_modules = [
    "sfp_dnsresolve", "sfp_whois", "sfp_sslcert",
    "sfp_threatcrowd", "sfp_virustotal"
]
```

#### Starting Scans

**Web UI Method:**
1. Select workspace → **Multi-Target Scan**
2. Select targets to scan
3. Choose modules
4. Configure scan options
5. Click **Start Scan**

**CLI Method:**
```bash
python sfworkflow.py multi-scan ws_abc123 \
  --modules "sfp_dnsresolve,sfp_portscan_tcp,sfp_ssl" \
  --options '{"_maxthreads": 3, "_timeout": 300}' \
  --wait
```

**Python API:**
```python
from spiderfoot.workflow import SpiderFootWorkflow

workspace = SpiderFootWorkspace.load_workspace(config, "ws_abc123")
workflow = workspace.create_workflow()

targets = workspace.get_targets()
modules = ["sfp_dnsresolve", "sfp_portscan_tcp", "sfp_ssl"]
scan_options = {"_maxthreads": 3, "_timeout": 300}

scan_ids = workflow.start_multi_target_scan(targets, modules, scan_options)
```

### Scan Monitoring

#### Real-time Progress Tracking

```python
# Monitor scan progress
statuses = workflow.get_scan_statuses(scan_ids)
for scan_id, status in statuses.items():
    print(f"Scan {scan_id}: {status['status']} - {status['progress']}%")

# Wait for completion
completed_scans = workflow.wait_for_scans_completion(scan_ids, timeout=3600)
```

#### Web UI Monitoring

The workspace details page provides real-time updates on:
- Scan status (STARTING, RUNNING, FINISHED, FAILED)
- Progress percentage
- Events discovered
- Estimated completion time

### Scan Results Access

#### Programmatic Access

```python
# Get scan results
results = workspace.get_scan_results(scan_id)

# Get all workspace results
all_results = workspace.export_data()
```

#### Web UI Access

1. Navigate to workspace details
2. Select **Scans** tab
3. Click on individual scan for detailed results
4. Use **Results** tab for aggregated findings

## Scan Import and Export

### Importing Existing Scans

Import previously completed SpiderFoot scans into a workspace:

#### Single Scan Import

**Web UI:**
1. Workspace → **Import Scans**
2. Enter scan ID
3. Click **Import**

**CLI:**
```bash
python sfworkflow.py import-scan ws_abc123 scan_12345
```

**Python:**
```python
success = workspace.import_single_scan("scan_12345", {"source": "external_assessment"})
```

#### Bulk Import

```python
scan_ids = ["scan_001", "scan_002", "scan_003"]
results = workspace.bulk_import_scans(scan_ids)
print(f"Imported {sum(results.values())} of {len(results)} scans")
```

### Export Options

#### Data Export Formats

- **JSON**: Structured data for programmatic processing
- **CSV**: Tabular data for analysis in spreadsheets
- **GEXF**: Graph data for visualization tools
- **XML**: Standard markup format

#### Export Scopes

- **All Data**: Complete scan results and metadata
- **Events Only**: Specific event types and findings
- **Correlations**: Cross-scan pattern analysis results
- **Summary**: High-level findings and statistics

#### Export Methods

**Web UI:**
1. Workspace → **Generate Report**
2. Select format and scope
3. Click **Generate Report**

**CLI:**
```bash
python sfworkflow.py export ws_abc123 --format json --output assessment_results.json
```

**API:**
```bash
curl -X POST http://localhost:5001/api/workspaces/ws_abc123/export \
  -H "Content-Type: application/json" \
  -d '{"format": "json", "scope": "all"}' \
  --output assessment_results.json
```

## Cross-Correlation Analysis

### Overview

Cross-correlation analysis identifies patterns, relationships, and shared indicators across multiple scans within a workspace.

### Correlation Types

#### Infrastructure Correlations
- Shared IP addresses across domains
- Common hosting providers
- Similar SSL certificate patterns
- Overlapping network ranges

#### Technology Correlations
- Common web technologies
- Shared software versions
- Similar security configurations
- Consistent vulnerability patterns

#### Threat Intelligence Correlations
- Shared threat indicators
- Common attack patterns
- Related malware families
- Linked threat actor indicators

### Running Correlation Analysis

#### Automatic Correlation

```python
# Enable auto-correlation in workspace
workspace.enable_auto_correlation()

# Correlations run automatically after each scan completion
```

#### Manual Correlation

**Web UI:**
1. Workspace details → **Correlations** tab
2. Click **Run Correlation Analysis**

**CLI:**
```bash
python sfworkflow.py correlate ws_abc123
```

**Python:**
```python
correlation_results = workflow.run_cross_correlation()
```

### Correlation Results

#### Result Structure

```python
{
    "cross_scan_patterns": [
        {
            "pattern_type": "shared_infrastructure",
            "confidence": 95,
            "scans_involved": ["scan_001", "scan_002"],
            "shared_entities": ["192.168.1.1", "shared-hosting.com"],
            "risk_assessment": "medium"
        }
    ],
    "threat_indicators": [
        {
            "indicator_type": "suspicious_ssl_cert",
            "indicator_value": "self-signed certificate",
            "affected_targets": ["example.com", "test.example.com"],
            "risk_level": "high"
        }
    ]
}
```

#### Accessing Results

**Web UI:** Workspace → **Correlations** tab shows:
- Cross-scan pattern count
- Threat indicator summary
- Detailed correlation findings
- Risk assessment matrix

**Programmatic:**
```python
correlations = workspace.get_correlations()
for correlation in correlations:
    print(f"Pattern: {correlation['pattern_type']}")
    print(f"Confidence: {correlation['confidence']}%")
    print(f"Risk: {correlation['risk_assessment']}")
```

## Report Generation

### Standard Reports

#### Workspace Summary Report

Comprehensive overview including:
- Target inventory
- Scan statistics
- Key findings summary
- Risk assessment
- Correlation highlights

#### Detailed Technical Report

In-depth technical analysis:
- Complete scan results
- Vulnerability details
- Infrastructure mapping
- Threat intelligence context

#### Executive Summary

High-level business-focused report:
- Risk overview
- Business impact assessment
- Remediation priorities
- Strategic recommendations

### CTI (Cyber Threat Intelligence) Reports

#### MCP Integration

SpiderFoot integrates with Model Context Protocol (MCP) for advanced CTI report generation:

```python
# Generate CTI report
report = await workspace.generate_cti_report(
    report_type="threat_assessment",
    custom_prompt="Focus on critical vulnerabilities and threat actor attribution"
)
```

#### Report Types

- **Threat Assessment**: Comprehensive threat landscape analysis
- **Vulnerability Analysis**: Security weakness prioritization
- **Attribution Analysis**: Threat actor and campaign attribution
- **Incident Response**: Security incident investigation support

#### Report Formats

- **JSON**: Structured data for integration
- **HTML**: Web-based interactive reports
- **PDF**: Printable documentation
- **Markdown**: Human-readable text format

### Custom Report Generation

#### Template-Based Reports

```python
# Custom report template
template = {
    "title": "Custom Security Assessment",
    "sections": [
        {"type": "executive_summary", "data_source": "correlations"},
        {"type": "technical_findings", "data_source": "scan_results"},
        {"type": "recommendations", "data_source": "threat_intelligence"}
    ],
    "format": "html"
}

report = workspace.generate_custom_report(template)
```

#### Report Automation

```bash
# Scheduled report generation
python sfworkflow.py generate-report ws_abc123 \
  --type executive_summary \
  --schedule daily \
  --output "/reports/daily_assessment.pdf"
```

## API Integration

### REST API Endpoints

The SpiderFoot Workflow API provides programmatic access to all workspace functionality:

#### Authentication

```python
import requests

# API authentication (if enabled)
headers = {
    "Authorization": "Bearer your-api-token",
    "Content-Type": "application/json"
}
```

#### Workspace Operations

```python
# List workspaces
response = requests.get("http://localhost:5001/api/workspaces", headers=headers)
workspaces = response.json()

# Create workspace
workspace_data = {
    "name": "API Test Workspace",
    "description": "Created via API"
}
response = requests.post("http://localhost:5001/api/workspaces", 
                        json=workspace_data, headers=headers)
workspace = response.json()

# Get workspace details
response = requests.get(f"http://localhost:5001/api/workspaces/{workspace_id}", 
                       headers=headers)
details = response.json()
```

#### Target Management

```python
# Add target
target_data = {
    "target": "api-test.example.com",
    "target_type": "DOMAIN_NAME",
    "metadata": {"source": "api", "priority": "high"}
}
response = requests.post(f"http://localhost:5001/api/workspaces/{workspace_id}/targets",
                        json=target_data, headers=headers)

# List targets
response = requests.get(f"http://localhost:5001/api/workspaces/{workspace_id}/targets",
                       headers=headers)
targets = response.json()
```

#### Scan Management

```python
# Start multi-target scan
scan_config = {
    "targets": ["example.com", "test.example.com"],
    "modules": ["sfp_dnsresolve", "sfp_portscan_tcp"],
    "scan_options": {"_maxthreads": 3}
}
response = requests.post(f"http://localhost:5001/api/workspaces/{workspace_id}/multi-scan",
                        json=scan_config, headers=headers)
scan_result = response.json()

# Get scan status
response = requests.get(f"http://localhost:5001/api/scans/{scan_id}/status",
                       headers=headers)
status = response.json()
```

### WebSocket Integration

Real-time updates via WebSocket connections:

```javascript
// JavaScript WebSocket client
const ws = new WebSocket('ws://localhost:5001/ws/workspace/{workspace_id}');

ws.onmessage = function(event) {
    const update = JSON.parse(event.data);
    switch(update.type) {
        case 'scan_progress':
            updateScanProgress(update.scan_id, update.progress);
            break;
        case 'scan_complete':
            handleScanCompletion(update.scan_id);
            break;
        case 'correlation_result':
            displayCorrelation(update.correlation);
            break;
    }
};
```

### Integration Examples

#### CI/CD Integration

```yaml
# GitHub Actions example
name: Security Assessment
on:
  schedule:
    - cron: '0 2 * * 1'  # Weekly Monday 2 AM

jobs:
  security_scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v2
      
      - name: Run SpiderFoot Assessment
        run: |
          # Create workspace
          WORKSPACE_ID=$(curl -X POST http://spiderfoot:5001/api/workspaces \
            -H "Content-Type: application/json" \
            -d '{"name": "CI Security Scan"}' | jq -r '.workspace_id')
          
          # Add targets from config
          for target in $(cat targets.txt); do
            curl -X POST http://spiderfoot:5001/api/workspaces/$WORKSPACE_ID/targets \
              -H "Content-Type: application/json" \
              -d "{\"target\": \"$target\", \"target_type\": \"DOMAIN_NAME\"}"
          done
          
          # Start scan
          curl -X POST http://spiderfoot:5001/api/workspaces/$WORKSPACE_ID/multi-scan \
            -H "Content-Type: application/json" \
            -d '{"modules": ["sfp_dnsresolve", "sfp_ssl", "sfp_threatcrowd"]}'
```

#### SIEM Integration

```python
# Splunk integration example
import splunklib.client as client

def send_to_splunk(workspace_results):
    service = client.connect(
        host='splunk-server',
        port=8089,
        username='admin',
        password='password'
    )
    
    index = service.indexes['security']
    
    for result in workspace_results:
        event_data = {
            "timestamp": result['timestamp'],
            "workspace_id": result['workspace_id'],
            "target": result['target'],
            "event_type": result['event_type'],
            "data": result['data'],
            "risk_level": result.get('risk_level', 'info')
        }
        
        index.submit(json.dumps(event_data), sourcetype='spiderfoot:workspace')
```

## Best Practices

### Workspace Organization

#### Naming Conventions

- **Project-based**: `2024-Q1-External-Assessment`
- **Client-based**: `ClientName-Security-Audit-2024`
- **Type-based**: `Internal-Infrastructure-Scan`
- **Time-based**: `Weekly-Monitoring-CW23-2024`

#### Workspace Scope

- **Single Project**: One workspace per security assessment
- **Target Grouping**: Group related targets (same network, same application)
- **Time-bound**: Define clear start and end dates
- **Team Access**: Organize by team or department responsibilities

### Target Management

#### Target Validation

```python
def validate_target(target_value, target_type):
    """Validate target before adding to workspace."""
    if target_type == "DOMAIN_NAME":
        import re
        domain_pattern = re.compile(
            r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
            r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        )
        return bool(domain_pattern.match(target_value))
    
    elif target_type == "IP_ADDRESS":
        import ipaddress
        try:
            ipaddress.ip_address(target_value)
            return True
        except ValueError:
            return False
    
    return True
```

#### Metadata Best Practices

```python
# Comprehensive target metadata
target_metadata = {
    "priority": "high",           # high, medium, low
    "environment": "production",  # production, staging, development
    "owner": "security-team",     # responsible team/person
    "criticality": "critical",    # critical, important, normal
    "location": "datacenter-1",   # physical/logical location
    "compliance": ["PCI", "SOX"], # compliance requirements
    "notes": "Customer-facing application",
    "scan_frequency": "weekly",   # preferred scan schedule
    "business_hours": "09:00-17:00 EST"
}
```

### Scan Configuration

#### Module Selection Guidelines

```python
# Passive reconnaissance (safe for production)
passive_modules = [
    "sfp_dnsresolve",      # DNS resolution
    "sfp_whois",           # WHOIS lookups
    "sfp_sslcert",         # SSL certificate analysis
    "sfp_threatcrowd",     # Threat intelligence
    "sfp_virustotal",      # VirusTotal queries
    "sfp_shodan_api"       # Shodan API (passive)
]

# Active scanning (use with caution)
active_modules = [
    "sfp_portscan_tcp",    # TCP port scanning
    "sfp_webheader",       # HTTP header analysis
    "sfp_subdomain_enum",  # Active subdomain enumeration
    "sfp_dnstake",         # DNS takeover detection
]

# Comprehensive assessment
comprehensive_modules = passive_modules + active_modules
```

#### Performance Optimization

```python
# Scan options for performance tuning
scan_options = {
    "_maxthreads": 3,        # Concurrent threads (adjust based on target tolerance)
    "_timeout": 300,         # Module timeout in seconds
    "_netblocklookup": True, # Enable netblock lookup
    "_maxnetblock": 24,      # Maximum netblock size
    "_dnsserver": "",        # Custom DNS server
    "_fetchtimeout": 30,     # HTTP fetch timeout
    "_internettlds": "all",  # TLD list to use
    "_maxpages": 100,        # Maximum pages to crawl
    "_useragent": "Mozilla/5.0 (compatible; SpiderFoot)"
}
```

### Security Considerations

#### Access Control

```python
# Workspace access control (planned feature)
workspace_acl = {
    "owner": "security-team-lead",
    "read_access": ["security-team", "management"],
    "write_access": ["security-team"],
    "admin_access": ["security-team-lead"],
    "sharing": "internal"  # internal, external, public
}
```

#### Data Protection

- **Encryption**: Encrypt sensitive workspace data at rest
- **Access Logging**: Log all workspace access and modifications
- **Data Retention**: Implement data retention policies
- **Backup**: Regular backup of critical workspace data

#### API Security

```python
# API authentication configuration
api_config = {
    "authentication": {
        "enabled": True,
        "method": "bearer_token",  # bearer_token, api_key, basic_auth
        "token_expiry": 3600,      # Token expiry in seconds
        "rate_limiting": {
            "enabled": True,
            "requests_per_minute": 100,
            "burst_limit": 20
        }
    },
    "authorization": {
        "role_based": True,
        "workspace_isolation": True
    }
}
```

### Performance Best Practices

#### Resource Management

```python
# Workspace resource limits
resource_limits = {
    "max_concurrent_scans": 5,      # Per workspace
    "max_targets_per_workspace": 100,
    "max_scan_duration": 7200,      # 2 hours
    "max_results_per_scan": 50000,
    "max_workspace_size": "1GB"
}
```

#### Monitoring and Alerting

```python
# Workspace monitoring configuration
monitoring_config = {
    "alerts": {
        "scan_failure": True,
        "high_risk_findings": True,
        "resource_exhaustion": True,
        "correlation_anomalies": True
    },
    "notifications": {
        "email": ["security-team@company.com"],
        "slack": "#security-alerts",
        "webhook": "https://company.com/webhook/spiderfoot"
    }
}
```

## Troubleshooting

### Common Issues

#### Workspace Creation Failures

**Problem**: Workspace creation fails with "Invalid name" error
**Solution**: 
- Use alphanumeric characters and spaces only
- Avoid special characters in workspace names
- Ensure name is between 3-100 characters

```python
# Validate workspace name
import re

def validate_workspace_name(name):
    if len(name) < 3 or len(name) > 100:
        return False, "Name must be 3-100 characters"
    
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', name):
        return False, "Name contains invalid characters"
    
    return True, "Valid name"
```

#### Target Addition Issues

**Problem**: Target validation fails
**Solution**:
- Verify target format matches type (domain name format for DOMAIN_NAME)
- Check for typos in domain names or IP addresses
- Ensure target type is correctly selected

#### Scan Failures

**Problem**: Multi-target scans fail to start
**Solution**:
- Check target accessibility from SpiderFoot server
- Verify module selection is appropriate for target types
- Review scan options for compatibility
- Check system resources (CPU, memory, disk space)

#### Performance Issues

**Problem**: Slow workspace operations
**Solution**:
- Reduce concurrent scan count
- Optimize module selection
- Implement result archiving for old workspaces
- Monitor database performance

### Logging and Debugging

#### Enable Debug Logging

```python
import logging

# Configure logging for workspace operations
logging.basicConfig(level=logging.DEBUG)

# Specific loggers
workspace_logger = logging.getLogger("spiderfoot.workspace")
workflow_logger = logging.getLogger("spiderfoot.workflow")
api_logger = logging.getLogger("spiderfoot.api")

# Set log levels
workspace_logger.setLevel(logging.DEBUG)
workflow_logger.setLevel(logging.INFO)
api_logger.setLevel(logging.WARNING)
```

#### Diagnostic Commands

```bash
# Check workspace health
python sfworkflow.py diagnose ws_abc123

# Validate workspace data integrity
python sfworkflow.py validate ws_abc123

# Export workspace logs
python sfworkflow.py export-logs ws_abc123 --output workspace_logs.json
```

### Database Maintenance

#### Workspace Cleanup

```python
# Clean up old workspaces
from spiderfoot.workspace import SpiderFootWorkspace

def cleanup_old_workspaces(config, days_old=90):
    """Remove workspaces older than specified days."""
    import time
    
    cutoff_time = time.time() - (days_old * 24 * 3600)
    old_workspaces = SpiderFootWorkspace.list_workspaces(
        config, 
        filter_criteria={"created_before": cutoff_time}
    )
    
    for workspace_info in old_workspaces:
        workspace = SpiderFootWorkspace.load_workspace(
            config, 
            workspace_info['workspace_id']
        )
        workspace.delete_workspace()
        print(f"Deleted workspace: {workspace_info['name']}")
```

#### Database Optimization

```sql
-- Optimize workspace database
VACUUM;
REINDEX;
ANALYZE;

-- Check workspace table statistics
SELECT 
    COUNT(*) as total_workspaces,
    AVG(LENGTH(targets)) as avg_targets_size,
    AVG(LENGTH(scans)) as avg_scans_size,
    AVG(LENGTH(metadata)) as avg_metadata_size
FROM tbl_workspaces;
```

### Error Recovery

#### Corrupted Workspace Recovery

```python
def recover_corrupted_workspace(config, workspace_id):
    """Attempt to recover a corrupted workspace."""
    try:
        # Try to load workspace
        workspace = SpiderFootWorkspace.load_workspace(config, workspace_id)
        
        # Validate data integrity
        validation_result = workspace.validate_data_integrity()
        
        if not validation_result['valid']:
            # Attempt repair
            repair_result = workspace.repair_data(validation_result['issues'])
            
            if repair_result['success']:
                workspace.save_workspace()
                return True, "Workspace repaired successfully"
            else:
                return False, f"Repair failed: {repair_result['error']}"
        
        return True, "Workspace is valid"
        
    except Exception as e:
        return False, f"Recovery failed: {str(e)}"
```

### Contact and Support

For additional support with workspace integration:

- **Documentation**: [SpiderFoot Wiki](https://github.com/smicallef/spiderfoot/wiki)
- **Issues**: [GitHub Issues](https://github.com/smicallef/spiderfoot/issues)
- **Community**: [Discord Server](https://discord.gg/vyvztrG)
- **Twitter**: [@spiderfoot](https://twitter.com/spiderfoot)

---

*Last updated: June 2025*
*Version: SpiderFoot 5.0.3*
