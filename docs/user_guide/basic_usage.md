# Basic Usage Guide

This guide covers the fundamental concepts and basic usage patterns of SpiderFoot for both new and experienced users.

## Core Concepts

### What is SpiderFoot?

SpiderFoot is an open source intelligence (OSINT) automation tool that:
- **Discovers**: Finds information about targets across the internet
- **Correlates**: Identifies relationships between discovered data
- **Analyzes**: Provides insights into security posture and threats
- **Reports**: Generates comprehensive assessment reports

### Key Terms

- **Target**: The entity you want to investigate (domain, IP, email, etc.)
- **Module**: A plugin that gathers specific types of information
- **Event**: A piece of information discovered about a target
- **Scan**: A collection of modules run against one or more targets
- **Workspace**: A container for organizing related targets and scans

## Target Types

SpiderFoot supports various target types for investigation:

### Network Targets
- **IP Address**: `192.168.1.1`
- **Network Block**: `192.168.1.0/24`
- **Domain Name**: `example.com`
- **Subdomain**: `mail.example.com`
- **ASN**: `AS15169` (Autonomous System Number)

### Personal Targets
- **Email Address**: `user@example.com`
- **Phone Number**: `+1-555-123-4567`
- **Human Name**: `John Doe`
- **Username**: `johndoe123`

### Digital Assets
- **Bitcoin Address**: `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`
- **Ethereum Address**: `0x742d35Cc6634C0532925a3b8D6Ac6cb`

## Basic Scanning Workflow

### 1. Choose Your Target

Start with a clear understanding of what you want to investigate:

```bash
# Domain investigation
python sf.py -s example.com -t DOMAIN_NAME

# IP address investigation  
python sf.py -s 192.168.1.1 -t IP_ADDRESS

# Email investigation
python sf.py -s user@example.com -t EMAILADDR
```

### 2. Select Appropriate Modules

Choose modules based on your investigation goals:

#### Passive Reconnaissance (Safe)
```bash
# DNS and certificate information
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois

# Threat intelligence lookup
python sf.py -s example.com -t DOMAIN_NAME -m sfp_threatcrowd,sfp_virustotal
```

#### Active Reconnaissance (Use with Caution)
```bash
# Port scanning
python sf.py -s 192.168.1.1 -t IP_ADDRESS -m sfp_portscan_tcp

# Web crawling
python sf.py -s example.com -t DOMAIN_NAME -m sfp_spider
```

### 3. Monitor and Analyze Results

#### Command Line Output
```bash
# Run with verbose output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -v

# Save results to file
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -o csv -f results.csv
```

#### Web Interface
1. Access http://127.0.0.1:5001
2. Navigate to scan results
3. Browse events by type
4. View relationship graphs
5. Export findings

## Module Categories

### DNS and Network Modules
- **sfp_dnsresolve**: DNS resolution and reverse DNS
- **sfp_whois**: WHOIS information lookup
- **sfp_ssl**: SSL certificate analysis
- **sfp_portscan_tcp**: TCP port scanning
- **sfp_banner**: Service banner grabbing

### Threat Intelligence Modules
- **sfp_threatcrowd**: ThreatCrowd API queries
- **sfp_virustotal**: VirusTotal API integration
- **sfp_alienvault**: AlienVault OTX integration
- **sfp_malware**: Malware analysis platforms

### Search Engine Modules
- **sfp_google**: Google search results
- **sfp_bing**: Bing search results
- **sfp_duckduckgo**: DuckDuckGo search
- **sfp_yandex**: Yandex search engine

### Social Media Modules
- **sfp_twitter**: Twitter account enumeration
- **sfp_github**: GitHub repository discovery
- **sfp_linkedin**: LinkedIn profile discovery
- **sfp_instagram**: Instagram account lookup

### Data Breach Modules
- **sfp_haveibeen**: HaveIBeenPwned integration
- **sfp_hunter**: Hunter.io email discovery
- **sfp_emailrep**: Email reputation checking

## Common Usage Patterns

### Domain Reconnaissance

```bash
# Comprehensive domain analysis
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_subdomain_enum,sfp_ssl,sfp_whois,sfp_threatcrowd

# Focus on subdomains
python sf.py -s example.com -t DOMAIN_NAME -m sfp_subdomain_enum,sfp_dnsresolve,sfp_ssl
```

### Infrastructure Assessment

```bash
# Network block analysis
python sf.py -s 192.168.1.0/24 -t NETBLOCK -m sfp_portscan_tcp,sfp_banner,sfp_ssl

# Individual host assessment
python sf.py -s 192.168.1.1 -t IP_ADDRESS -m sfp_portscan_tcp,sfp_banner,sfp_whois,sfp_threatcrowd
```

### Email Investigation

```bash
# Email address investigation
python sf.py -s user@example.com -t EMAILADDR -m sfp_hunter,sfp_haveibeen,sfp_emailrep

# Domain email enumeration
python sf.py -s example.com -t DOMAIN_NAME -m sfp_hunter,sfp_emailformat
```

### Social Media Intelligence

```bash
# Username investigation
python sf.py -s johndoe123 -t USERNAME -m sfp_twitter,sfp_github,sfp_instagram

# Human name investigation
python sf.py -s "John Doe" -t HUMAN_NAME -m sfp_fullcontact,sfp_pipl
```

## Result Interpretation

### Event Types and Meanings

#### Network Events
- **IP_ADDRESS**: IP addresses associated with target
- **DOMAIN_NAME**: Domain names and subdomains discovered
- **TCP_PORT_OPEN**: Open ports found during scanning
- **SSL_CERTIFICATE_ISSUED**: SSL certificate information

#### Security Events
- **VULNERABILITY**: Security vulnerabilities identified
- **MALICIOUS_DOMAIN**: Domains flagged as malicious
- **THREAT_INTEL**: Threat intelligence indicators
- **BLACKLISTED**: Entries found in blacklists

#### Personal Information
- **EMAILADDR**: Email addresses discovered
- **PHONE_NUMBER**: Phone numbers found
- **SOCIAL_MEDIA**: Social media profiles
- **HUMAN_NAME**: Human names associated with target

### Risk Assessment

#### Risk Levels
- **HIGH**: Critical security issues requiring immediate attention
- **MEDIUM**: Important findings that warrant investigation
- **LOW**: Informational findings for situational awareness
- **INFO**: General information about targets

#### Common High-Risk Findings
- Open administrative ports (SSH, RDP, etc.)
- Expired or weak SSL certificates
- Known vulnerabilities in exposed services
- Presence in threat intelligence feeds
- Data breach exposures

## Best Practices

### Reconnaissance Planning

1. **Define Scope**: Clearly identify what you're authorized to investigate
2. **Start Passive**: Begin with passive reconnaissance modules
3. **Escalate Gradually**: Move to active scanning only when necessary
4. **Document Findings**: Keep detailed records of discoveries

### Module Selection

1. **Understand Module Behavior**: Know which modules are passive vs. active
2. **Respect Rate Limits**: Use delays between requests for external APIs
3. **API Key Management**: Configure API keys for enhanced functionality
4. **Regular Updates**: Keep modules updated for latest capabilities

### Ethical Considerations

1. **Authorization**: Only scan targets you own or have permission to test
2. **Respect Boundaries**: Don't exceed authorized scope
3. **Be Considerate**: Avoid overwhelming target systems
4. **Legal Compliance**: Follow applicable laws and regulations

### Performance Optimization

1. **Thread Management**: Adjust thread count based on system capabilities
2. **Timeout Settings**: Set appropriate timeouts for network operations
3. **Storage Management**: Regularly clean up old scan data
4. **Resource Monitoring**: Monitor CPU and memory usage during scans

## Troubleshooting Common Issues

### Module Not Found
```bash
# Check available modules
python sf.py -M

# Verify module name
python sf.py -M | grep dnsresolve
```

### API Key Issues
```bash
# Verify API key configuration
python sf.py --test-modules

# Check module-specific settings
python sf.py -s example.com -t DOMAIN_NAME -m sfp_virustotal -v
```

### Network Connectivity
```bash
# Test basic connectivity
python sf.py -s google.com -t DOMAIN_NAME -m sfp_dnsresolve

# Check proxy settings
export HTTP_PROXY=http://proxy.example.com:8080
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve
```

### Performance Issues
```bash
# Reduce thread count
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --options '{"_maxthreads": 1}'

# Increase timeouts
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --options '{"_timeout": 60}'
```

## Getting Help

### Documentation Resources
- **Module Help**: `python sf.py -M` for module list and descriptions
- **Command Help**: `python sf.py --help` for command-line options
- **Configuration**: Check `spiderfoot.conf` for available settings

### Community Support
- **GitHub Issues**: Report bugs and feature requests
- **Discord Community**: Get help from other users
- **Wiki**: Comprehensive documentation and guides

### Advanced Features
Once comfortable with basic usage, explore:
- **Workspace Management**: Organize complex assessments
- **Multi-Target Scanning**: Concurrent scanning across multiple targets
- **Correlation Analysis**: Identify patterns across scan results
- **CTI Reports**: Generate threat intelligence reports

Ready to dive deeper? Check out the [Web Interface Guide](web_interface.md) or explore [Workspace Management](../WORKSPACE_INTEGRATION_COMPLETE.md).
