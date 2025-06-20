# SpiderFoot Documentation

SpiderFoot is an open source intelligence (OSINT) automation tool that integrates with just about every data source available and utilizes a range of methods for data analysis, making that data easy to navigate.

## What is SpiderFoot?

SpiderFoot automates the process of gathering intelligence about a given target, which may be an:
- IP address
- Domain/sub-domain name  
- Hostname
- Network subnet (CIDR)
- ASN
- E-mail address
- Phone number
- Username
- Person's name
- Bitcoin address

## Key Features

### Intelligence Gathering
- **240+ Modules**: Comprehensive data collection from various sources including passive and active reconnaissance
- **Multiple Target Types**: Support for domains, IPs, emails, Bitcoin addresses, and more
- **Automated Discovery**: Intelligent enumeration and reconnaissance with correlation
- **Threat Intelligence**: Integration with major TI platforms (VirusTotal, Shodan, etc.)

### Workflow Management  
- **Workspaces**: Organize multi-target assessments with persistent storage
- **Multi-Target Scanning**: Concurrent assessment across multiple targets with progress tracking
- **Cross-Correlation**: Identify patterns and relationships between scan results
- **CTI Reports**: Generate comprehensive threat intelligence reports with MCP integration

### Integration & Automation
- **REST API**: Full programmatic access to all functionality
- **Webhook Support**: Real-time notifications and integrations
- **Export Options**: Multiple output formats (CSV, JSON, GEXF, HTML, PDF)
- **CI/CD Integration**: Automated security assessments and monitoring

## Getting Started

### Quick Installation
```bash
# Clone repository
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot

# Install dependencies
pip3 install -r requirements.txt

# Start web interface
python3 sf.py -l 127.0.0.1:5001
```

### First Scan
1. **Open Web Interface**: Navigate to http://127.0.0.1:5001
2. **Start New Scan**: Click "New Scan"  
3. **Configure Target**: Enter target (e.g., "example.com")
4. **Select Target Type**: Choose "Domain Name"
5. **Choose Modules**: Select desired modules or use "All" for comprehensive scan
6. **Run Scan**: Click "Run Scan Now"

### Workspace Assessment
```bash
# Create workspace for multi-target assessment
python3 sfworkflow.py create-workspace "Security Assessment"

# Add multiple targets
python3 sfworkflow.py add-target ws_abc123 example.com --type DOMAIN_NAME
python3 sfworkflow.py add-target ws_abc123 test.example.com --type INTERNET_NAME
python3 sfworkflow.py add-target ws_abc123 192.168.1.1 --type IP_ADDRESS

# Run multi-target scan with comprehensive modules
python3 sfworkflow.py multi-scan ws_abc123 \
  --modules sfp_dnsresolve,sfp_portscan_tcp,sfp_ssl,sfp_whois,sfp_threatcrowd \
  --wait

# Run correlation analysis to find patterns
python3 sfworkflow.py correlate ws_abc123

# Generate comprehensive threat intelligence report  
python3 sfworkflow.py generate-cti ws_abc123 \
  --type threat_assessment \
  --output assessment_report.json
```

## Documentation Structure

### Getting Started
- [Installation Guide](installation.md) - Detailed setup instructions
- [Quick Start Guide](quickstart.md) - Get scanning quickly
- [Configuration](configuration.md) - System configuration options

### Workflow & Workspaces
- [Workflow Engine](WORKFLOW_DOCUMENTATION.md) - Complete workflow documentation
- [Workspace Management](WORKSPACE_INTEGRATION_COMPLETE.md) - Multi-target organization
- [Multi-Target Scanning](workflow/multi_target_scanning.md) - Concurrent scanning
- [Correlation Analysis](workflow/correlation_analysis.md) - Pattern identification
- [CTI Reports](workflow/cti_reports.md) - Intelligence report generation

### User Guide
- [Basic Usage](basic_usage.md) - Fundamental concepts and usage
- [Web Interface](web_interface.md) - Browser-based interface guide
- [CLI Usage](cli_usage.md) - Command-line interface reference
- [Modules Guide](modules_guide.md) - Understanding and using modules

### Module Documentation
- [Module Index](modules/index.md) - Complete module reference
- [Custom Modules](modules/custom_modules.md) - Creating your own modules
- [Recorded Future](modules/sfp_recordedfuture.md) - Recorded Future integration

### API Reference
- [REST API](api/rest_api.md) - HTTP API documentation
- [Python API](python_api.md) - Python integration guide
- [Webhook Integration](webhook_integration.md) - Real-time notifications

### Advanced Topics
- [Docker Deployment](docker_deployment.md) - Container deployment
- [Performance Tuning](performance_tuning.md) - Optimization guide
- [Security Considerations](security_considerations.md) - Production security
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

### Developer Guide
- [Contributing](contributing.md) - How to contribute to SpiderFoot
- [Module Development](developer/module_development.md) - Creating modules
- [API Development](developer/api_development.md) - Extending the API

## Use Cases

### Security Assessments
- **External reconnaissance** for penetration testing
- **Attack surface mapping** for organizations
- **Vulnerability assessment** and exposure analysis
- **Digital footprint analysis** for risk evaluation

### Threat Intelligence
- **IOC enrichment** with additional context
- **Threat actor attribution** and campaign analysis
- **Malware infrastructure** mapping
- **Dark web monitoring** and analysis

### Compliance & Governance
- **Data exposure monitoring** for compliance
- **Brand protection** and monitoring
- **Employee security awareness** training
- **Third-party risk assessment**

### Investigation & Research
- **OSINT investigations** for various purposes
- **Academic research** and analysis
- **Journalism** and fact-checking
- **Law enforcement** support

## Architecture

### Core Components
- **SpiderFoot Engine**: Core scanning and module management
- **Web Interface**: User-friendly browser-based interface
- **Database**: SQLite backend for storing results
- **Modules**: Plugin system for data collection
- **API**: RESTful interface for automation

### Workflow Engine
- **Workspace Management**: Multi-target organization
- **Correlation Engine**: Pattern identification across scans
- **MCP Integration**: Advanced CTI report generation
- **Progress Tracking**: Real-time scan monitoring

## Community & Support

### Getting Help
- **Documentation**: Comprehensive guides and tutorials
- **Discord Community**: Active user community for support
- **GitHub Issues**: Bug reports and feature requests
- **Wiki**: Additional documentation and examples

### Contributing
- **Open Source**: MIT licensed and community-driven
- **Module Development**: Easy plugin creation
- **Feature Requests**: Community-driven roadmap
- **Code Contributions**: Welcome from all skill levels

## License

SpiderFoot is licensed under the MIT License. See the LICENSE file for details.

## Acknowledgments

SpiderFoot is maintained by Steve Micallef and the open source community. Special thanks to all contributors who have helped make SpiderFoot what it is today.

For more information, visit the [SpiderFoot GitHub repository](https://github.com/poppopjmp/spiderfoot).
