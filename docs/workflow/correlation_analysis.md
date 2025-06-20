# Correlation Analysis

Cross-correlation analysis identifies patterns, relationships, and shared indicators across multiple scans within a workspace, providing deeper insights into your security posture.

## Overview

Correlation analysis discovers:
- **Shared infrastructure** across different targets
- **Common technologies** and configurations
- **Threat intelligence patterns** and indicators
- **Attack surface relationships** and dependencies

## Types of Correlations

### Infrastructure Correlations
- Shared IP addresses across domains
- Common hosting providers
- Similar SSL certificate patterns
- Overlapping network ranges

### Technology Correlations
- Common web technologies
- Shared software versions
- Similar security configurations
- Consistent vulnerability patterns

### Threat Intelligence Correlations
- Shared threat indicators
- Common attack patterns
- Related malware families
- Linked threat actor indicators

## Running Correlation Analysis

### Automatic Correlation
```bash
# Run all correlation rules
python sfworkflow.py correlate ws_abc123
```

### Specific Rules
```bash
# Run specific correlation rules
python sfworkflow.py correlate ws_abc123 \
  --rules cross_scan_shared_infrastructure,cross_scan_threat_indicators
```

### Viewing Results
```bash
# Show correlation results
python sfworkflow.py show-correlations ws_abc123

# Export correlations
python sfworkflow.py export-correlations ws_abc123 --output correlations.json
```

## Correlation Rules

### Built-in Rules
- **cross_scan_shared_infrastructure**: Identifies shared hosting and infrastructure
- **cross_scan_similar_technologies**: Finds common technology stacks
- **cross_scan_threat_indicators**: Matches threat intelligence across scans
- **cross_scan_vulnerability_patterns**: Identifies common vulnerabilities

### Custom Rules
Create custom correlation rules in YAML format:

```yaml
id: custom_shared_certificates
name: Shared SSL Certificates
description: Identifies shared SSL certificates across different targets
fields:
  - SSL_CERTIFICATE_ISSUED
confidence: 85
risk: INFO
```

## Web Interface

### Correlation Dashboard
- Pattern summary and statistics
- Risk assessment matrix
- Detailed correlation findings
- Interactive result exploration

### Visualization
- Relationship graphs
- Pattern clustering
- Risk heat maps
- Timeline analysis

## Best Practices

1. **Complete all scans** before running correlation
2. **Regular analysis** as new data becomes available
3. **Review patterns** for false positives
4. **Document findings** for future reference
5. **Share results** with relevant teams

Ready to generate reports? Learn about [CTI Reports](cti_reports.md).
