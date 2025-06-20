# Quick Start Guide

This guide will help you get up and running with SpiderFoot quickly, covering both traditional single-target scanning and the powerful new workspace-based multi-target workflows.

## Prerequisites

- SpiderFoot installed (see [Installation Guide](installation.md))
- Python 3.7+ running
- Internet connection for external data sources

## Starting SpiderFoot

### Web Interface (Recommended)

```bash
# Start SpiderFoot web server
python sf.py -l 127.0.0.1:5001

# Access in browser at http://127.0.0.1:5001
```

### Command Line Interface

```bash
# Basic domain scan
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois

# Scan with output file
python sf.py -s example.com -t DOMAIN_NAME -o csv -f results.csv

# List all available modules  
python sf.py -M
```

## Basic Scanning (Traditional Method)

### Single Target Scan

1. **Open Web Interface**: Navigate to http://127.0.0.1:5001
2. **Start New Scan**: Click "New Scan"
3. **Configure Scan**:
   - **Target**: Enter `example.com`
   - **Target Type**: Select "Domain Name"
   - **Modules**: Choose desired modules (start with "Passive" for first scan)
4. **Start Scan**: Click "Run Scan Now"
5. **Monitor Progress**: Watch real-time progress updates
6. **View Results**: Explore findings using Browse, Graph, and Export tabs

### CLI Single Scan Examples

```bash
# Basic domain reconnaissance (passive only)
python sf.py -s example.com -t DOMAIN_NAME \
  -m sfp_dnsresolve,sfp_whois,sfp_sslcert,sfp_threatcrowd

# IP address investigation
python sf.py -s 192.168.1.1 -t IP_ADDRESS \
  -m sfp_portscan_tcp,sfp_bgpview,sfp_arin

# Email address investigation
python sf.py -s user@example.com -t EMAILADDR \
  -m sfp_hunter,sfp_haveibeenpwned,sfp_emailrep

# Comprehensive scan with threat intelligence
python sf.py -s example.com -t DOMAIN_NAME \
  -m sfp_dnsresolve,sfp_whois,sfp_sslcert,sfp_virustotal,sfp_shodan,sfp_threatcrowd
```

## Workspace-Based Scanning (Advanced Multi-Target)

### Creating Your First Workspace

#### Web Interface
1. Navigate to **Workspaces** section
2. Click **Create New Workspace**
3. Enter name: "Security Assessment 2025"
4. Add description: "Multi-target security assessment"
5. Click **Create Workspace**

#### CLI Method
```bash
# Create workspace
python sfworkflow.py create-workspace "Security Assessment 2025"
# Note the workspace ID returned (e.g., ws_abc123456)

# List all workspaces
python sfworkflow.py list-workspaces
```

### Adding Targets to Workspace

#### Multiple Target Types
```bash
# Add primary domain and subdomains
python sfworkflow.py add-target ws_abc123456 example.com --type DOMAIN_NAME
python sfworkflow.py add-target ws_abc123456 www.example.com --type INTERNET_NAME
python sfworkflow.py add-target ws_abc123456 mail.example.com --type INTERNET_NAME

# Add infrastructure targets
python sfworkflow.py add-target ws_abc123456 192.168.1.1 --type IP_ADDRESS  
python sfworkflow.py add-target ws_abc123456 192.168.1.0/24 --type NETBLOCK

# Add email and personnel targets
python sfworkflow.py add-target ws_abc123456 admin@example.com --type EMAILADDR

# Add with metadata for organization
python sfworkflow.py add-target ws_abc123456 staging.example.com \
  --type INTERNET_NAME \
  --metadata '{"priority": "high", "environment": "staging", "criticality": "production"}'
```

#### Bulk Target Management
```bash
# List targets in workspace
python sfworkflow.py list-targets ws_abc123456

# Import from file (if supported)
# Create targets.csv with: target,type,metadata
echo "api.example.com,INTERNET_NAME,{\"service\": \"api\"}" >> targets.csv
user@example.com,EMAILADDR
EOF

# Bulk import (feature coming soon)
python sfworkflow.py import-targets ws_abc123 targets.txt
```

### Running Multi-Target Scans

#### Basic Multi-Target Scan
```bash
# Scan all targets in workspace
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl,sfp_whois \
  --wait

# Scan specific targets
python sfworkflow.py multi-scan ws_abc123 \
  --targets example.com,test.example.com \
  --modules sfp_dnsresolve,sfp_portscan_tcp
```

#### Advanced Scan Configuration
```bash
# Comprehensive assessment
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_ssl,sfp_portscan_tcp,sfp_whois,sfp_threatcrowd,sfp_virustotal \
  --options '{"_maxthreads": 3, "_timeout": 300}' \
  --wait

# Passive reconnaissance only
python sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_whois,sfp_ssl,sfp_threatcrowd \
  --wait
```

## Analyzing Results

### Cross-Correlation Analysis

After completing multi-target scans, run correlation analysis:

```bash
# Analyze patterns across all scans
python sfworkflow.py correlate ws_abc123

# View correlation results
python sfworkflow.py show-correlations ws_abc123
```

### CTI Report Generation

Generate comprehensive threat intelligence reports:

```bash
# Generate threat assessment report
python sfworkflow.py generate-cti ws_abc123 \
  --type threat_assessment \
  --output assessment_report.json

# Generate with custom focus
python sfworkflow.py generate-cti ws_abc123 \
  --type threat_assessment \
  --prompt "Focus on critical vulnerabilities and threat actors" \
  --output custom_report.html
```

## Common Scan Scenarios

### Scenario 1: Domain Reconnaissance

```bash
# Create workspace
WORKSPACE=$(python sfworkflow.py create-workspace "Domain Recon" | grep -o 'ws_[a-f0-9]*')

# Add primary domain and subdomains
python sfworkflow.py add-target $WORKSPACE example.com --type DOMAIN_NAME
python sfworkflow.py add-target $WORKSPACE www.example.com --type INTERNET_NAME
python sfworkflow.py add-target $WORKSPACE mail.example.com --type INTERNET_NAME

# Run passive reconnaissance
python sfworkflow.py multi-scan $WORKSPACE \
  --modules sfp_dnsresolve,sfp_whois,sfp_ssl,sfp_subdomain_enum,sfp_threatcrowd \
  --wait

# Generate report
python sfworkflow.py generate-cti $WORKSPACE --type infrastructure_analysis
```

### Scenario 2: Network Assessment

```bash
# Create workspace
WORKSPACE=$(python sfworkflow.py create-workspace "Network Assessment" | grep -o 'ws_[a-f0-9]*')

# Add network ranges and individual IPs
python sfworkflow.py add-target $WORKSPACE 192.168.1.0/24 --type NETBLOCK
python sfworkflow.py add-target $WORKSPACE 192.168.1.1 --type IP_ADDRESS

# Run network scanning
python sfworkflow.py multi-scan $WORKSPACE \
  --modules sfp_portscan_tcp,sfp_banner,sfp_ssl,sfp_whois \
  --options '{"_maxthreads": 2}' \
  --wait

# Correlate findings
python sfworkflow.py correlate $WORKSPACE
```

### Scenario 3: Threat Hunting

```bash
# Create workspace
WORKSPACE=$(python sfworkflow.py create-workspace "Threat Hunt" | grep -o 'ws_[a-f0-9]*')

# Add indicators
python sfworkflow.py add-target $WORKSPACE suspicious.example.com --type DOMAIN_NAME
python sfworkflow.py add-target $WORKSPACE attacker@evil.com --type EMAILADDR
python sfworkflow.py add-target $WORKSPACE 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --type BITCOIN_ADDRESS

# Run threat intelligence modules
python sfworkflow.py multi-scan $WORKSPACE \
  --modules sfp_threatcrowd,sfp_virustotal,sfp_alienvault,sfp_malware \
  --wait

# Generate threat assessment
python sfworkflow.py generate-cti $WORKSPACE --type threat_assessment
```

## Understanding Results

### Event Types

SpiderFoot discovers various event types:
- **IP_ADDRESS**: IP addresses associated with targets
- **DOMAIN_NAME**: Domain names and subdomains
- **SSL_CERTIFICATE_ISSUED**: SSL certificate information
- **TCP_PORT_OPEN**: Open TCP ports
- **VULNERABILITY**: Security vulnerabilities
- **THREAT_INTEL**: Threat intelligence indicators

### Risk Levels

- **HIGH**: Critical security issues requiring immediate attention
- **MEDIUM**: Important findings that should be investigated
- **LOW**: Informational findings for awareness
- **INFO**: General information about targets

### Web Interface Navigation

1. **Scans Tab**: View all scan results and status
2. **Browse Tab**: Explore findings by event type
3. **Graph Tab**: Visualize relationships between findings
4. **Export Tab**: Download results in various formats

## Next Steps

### Explore Advanced Features

1. **Module Configuration**: Learn about [individual modules](modules/index.md)
2. **API Integration**: Explore the [REST API](api/rest_api.md)
3. **Custom Correlation**: Create [custom correlation rules](workflow/correlation_analysis.md)
4. **Performance Tuning**: Optimize for [large assessments](advanced/performance_tuning.md)

### Best Practices

1. **Start Small**: Begin with passive modules for initial reconnaissance
2. **Use Workspaces**: Organize related targets in workspaces for better analysis
3. **Monitor Resources**: Watch CPU and memory usage during large scans
4. **Regular Updates**: Keep SpiderFoot updated for latest modules and features
5. **API Keys**: Configure API keys for enhanced module functionality

### Common Module Combinations

```bash
# Passive reconnaissance
PASSIVE_MODULES="sfp_dnsresolve,sfp_whois,sfp_ssl,sfp_threatcrowd"

# Active scanning (use with caution)
ACTIVE_MODULES="sfp_portscan_tcp,sfp_webheader,sfp_subdomain_enum"

# Threat intelligence
THREAT_MODULES="sfp_virustotal,sfp_alienvault,sfp_malware,sfp_botnet"

# Comprehensive assessment
COMPREHENSIVE_MODULES="$PASSIVE_MODULES,$ACTIVE_MODULES,$THREAT_MODULES"
```

## Getting Help

- **Module Help**: `python sf.py -M` lists all modules
- **CLI Help**: `python sfworkflow.py --help` for workflow commands
- **Documentation**: Browse the complete [documentation](index.md)
- **Community**: Join our [Discord server](https://discord.gg/vyvztrG)

## Troubleshooting Quick Fixes

### Common Issues

```bash
# Module not found
pip install -r requirements.txt

# Permission denied
chmod +x sf.py sfworkflow.py

# Port in use
python sf.py -l 127.0.0.1:5002

# Database locked
rm spiderfoot.db
```

### Performance Issues

```bash
# Reduce concurrent threads
python sfworkflow.py multi-scan ws_abc123 --options '{"_maxthreads": 1}'

# Limit scan scope
python sfworkflow.py multi-scan ws_abc123 --modules sfp_dnsresolve,sfp_ssl
```

Ready to dive deeper? Check out the [complete documentation](index.md) or explore specific features in the user guides!
