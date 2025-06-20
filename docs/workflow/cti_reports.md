# CTI Report Generation

Generate comprehensive Cyber Threat Intelligence (CTI) reports using SpiderFoot's MCP (Model Context Protocol) integration for advanced analysis and presentation.

## Overview

CTI reports provide:
- **Threat assessment** with risk analysis
- **Infrastructure analysis** and security posture
- **Attack surface mapping** and exposure assessment
- **Executive summaries** for stakeholder communication

## Report Types

### Threat Assessment
Comprehensive threat landscape analysis including:
- Threat actor attribution
- Malware and campaign analysis
- Risk prioritization
- Mitigation recommendations

### Infrastructure Analysis
Security posture evaluation covering:
- Asset inventory and mapping
- Vulnerability assessment
- Configuration analysis
- Compliance reporting

### Attack Surface Analysis
External exposure mapping including:
- Internet-facing assets
- Service enumeration
- Security gaps identification
- Risk exposure calculation

## Generating Reports

### Basic Report Generation
```bash
# Generate threat assessment report
python sfworkflow.py generate-cti ws_abc123 \
  --type threat_assessment \
  --output threat_report.json
```

### Custom Analysis
```bash
# Generate with custom focus
python sfworkflow.py generate-cti ws_abc123 \
  --type threat_assessment \
  --prompt "Focus on APT indicators and nation-state threats" \
  --output custom_report.html
```

### Multiple Formats
```bash
# Generate in different formats
python sfworkflow.py generate-cti ws_abc123 \
  --type infrastructure_analysis \
  --format html \
  --output security_posture.html
```

## Report Management

### Listing Reports
```bash
# List all CTI reports for workspace
python sfworkflow.py list-cti ws_abc123
```

### Exporting Reports
```bash
# Export report in different format
python sfworkflow.py export-cti ws_abc123 report_abc123 \
  --format pdf \
  --output final_report.pdf
```

## Web Interface

### Report Dashboard
- Report generation interface
- Status tracking and progress
- Format selection and customization
- Download and sharing options

### Customization Options
- Report templates
- Custom prompts and focus areas
- Data filtering and selection
- Branding and formatting

## Configuration

### MCP Integration
```ini
[cti]
mcp_server_url = http://localhost:8000
mcp_api_key = your_mcp_api_key
mcp_timeout = 300
default_format = json
cache_reports = true
```

### Report Templates
- Standard threat assessment template
- Infrastructure analysis template
- Executive summary template
- Custom organization templates

## Best Practices

1. **Complete correlation analysis** before generating reports
2. **Use specific prompts** for targeted analysis
3. **Review generated content** for accuracy
4. **Customize for audience** (technical vs. executive)
5. **Regular report generation** for trend analysis

## Integration Examples

### Automated Reporting
```bash
#!/bin/bash
# Daily CTI report generation

WORKSPACE_ID="ws_daily_monitoring"
DATE=$(date +%Y%m%d)

# Generate threat assessment
python sfworkflow.py generate-cti $WORKSPACE_ID \
  --type threat_assessment \
  --output "threat_report_$DATE.json"

# Generate executive summary
python sfworkflow.py generate-cti $WORKSPACE_ID \
  --type executive_summary \
  --output "executive_summary_$DATE.pdf"
```

### SIEM Integration
```python
# Send reports to SIEM
import json
import requests

def send_to_siem(report_data):
    siem_endpoint = "https://siem.company.com/api/reports"
    headers = {"Authorization": "Bearer siem-token"}
    
    response = requests.post(
        siem_endpoint,
        json=report_data,
        headers=headers
    )
    return response.status_code == 200
```

Ready to explore more? Check out the [REST API](../api/rest_api.md) for programmatic access or [Advanced Topics](../advanced/performance_tuning.md) for optimization.
