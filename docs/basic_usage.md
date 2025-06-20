# Basic Usage Guide

This guide covers the fundamental concepts and basic usage patterns of SpiderFoot for both new and experienced users.

## Core Concepts

### What is SpiderFoot?

SpiderFoot is an open source intelligence (OSINT) automation tool that:
- **Discovers**: Finds information about targets across the internet using 240+ modules
- **Correlates**: Identifies relationships between discovered data through advanced correlation
- **Analyzes**: Provides insights into security posture and threat landscape
- **Reports**: Generates comprehensive assessment reports in multiple formats

### Key Terms

- **Target**: The entity you want to investigate (domain, IP, email, etc.)
- **Module**: A plugin that gathers specific types of information from various sources
- **Event**: A piece of information discovered about a target with metadata and relationships
- **Scan**: A collection of modules run against one or more targets with progress tracking
- **Workspace**: A container for organizing related targets and scans with cross-correlation
- **Correlation**: Automated analysis that identifies patterns across multiple scans

## Target Types

SpiderFoot supports comprehensive target types for investigation:

### Network Infrastructure
- **IP Address**: `192.168.1.1` - Individual IP addresses
- **Network Block**: `192.168.1.0/24` - IP ranges and subnets
- **Domain Name**: `example.com` - Primary domains
- **Internet Name**: `mail.example.com` - Subdomains and hostnames
- **ASN**: `AS15169` - Autonomous System Numbers for BGP analysis

### Personal Intelligence
- **Email Address**: `user@example.com` - Email addresses for breach data and social media
- **Phone Number**: `+1-555-123-4567` - Phone numbers for OSINT
- **Human Name**: `John Doe` - Person names for background checks
- **Username**: `johndoe123` - Usernames for social media enumeration

### Digital Assets & Finance
- **Bitcoin Address**: `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa` - Bitcoin transaction analysis
- **Ethereum Address**: `0x742d35Cc6634C0532925a3b8D6Ac6cb` - Ethereum blockchain analysis

## Basic Scanning Workflow

### 1. Choose Your Target and Scope

Start with a clear understanding of what you want to investigate and your authorization:

```bash
# Examples of target selection
TARGET_DOMAIN="example.com"        # Primary domain investigation
TARGET_IP="192.168.1.1"           # Infrastructure analysis
TARGET_EMAIL="admin@example.com"   # Personnel investigation
TARGET_SUBNET="192.168.1.0/24"    # Network range analysis
```
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

For more advanced features, check out [Workspace Management](WORKSPACE_INTEGRATION_COMPLETE.md) and [Multi-Target Scanning](workflow/multi_target_scanning.md).
