# Quick Start Guide

This guide will help you get up and running with SpiderFoot Enterprise quickly, covering both traditional single-target scanning and advanced enterprise features.

## Prerequisites

- SpiderFoot Enterprise installed (see [Installation Guide](installation.md))
- Python 3.9+ running
- Internet connection for external data sources
- Optional: PostgreSQL for enterprise database features

## Enterprise Features Overview

SpiderFoot Enterprise includes advanced capabilities:

- **🎯 Advanced Storage Engine**: High-performance data storage with compression and indexing
- **🤖 AI Threat Intelligence**: Machine learning-powered threat analysis and pattern recognition
- **🔒 Security Hardening**: Enhanced security controls and enterprise-grade configurations
- **📊 Advanced Analytics**: Comprehensive reporting and visualization capabilities
- **⚡ Performance Optimization**: Scalable architecture for enterprise workloads

## Starting SpiderFoot Enterprise

### Production Deployment (Recommended)

```bash
# Start with enterprise features enabled
python sf.py -l 0.0.0.0:5001 --enterprise

# Alternative: Use Docker production deployment
docker-compose -f docker-compose-prod.yml up -d
```

### Development Mode

```bash
# Start SpiderFoot web server (development)
python sf.py -l 127.0.0.1:5001

# Access in browser at http://127.0.0.1:5001
```

### Enterprise Configuration

Access the Settings page at http://127.0.0.1:5001/opts to configure enterprise modules:

- **Advanced Storage** (`sfp__stor_db_advanced`): Configure compression, indexing, and performance settings
- **AI Threat Intelligence** (`sfp__ai_threat_intel`): Set up machine learning models and threat analysis
- **Security Hardening** (`sfp__security_hardening`): Configure security policies and access controls

## Basic Scanning

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

### CLI Examples

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

# Enterprise scan with AI analysis
python sf.py -s example.com -t DOMAIN_NAME \
  -m sfp_dnsresolve,sfp_whois,sfp_sslcert,sfp__ai_threat_intel,sfp__stor_db_advanced
```

## Enterprise Features Usage

### Advanced Storage Configuration

1. **Navigate to Settings**: Go to http://127.0.0.1:5001/opts
2. **Find Advanced Storage Module**: Locate `sfp__stor_db_advanced`
3. **Configure Options**:
   - Enable compression for storage efficiency
   - Set up automatic indexing for faster queries
   - Configure data retention policies
   - Enable performance monitoring

### AI Threat Intelligence

1. **Access AI Module**: Find `sfp__ai_threat_intel` in settings
2. **Configure AI Features**:
   - Set confidence thresholds for threat detection
   - Enable pattern recognition algorithms
   - Configure predictive analytics
   - Set up automated threat classification

### Security Hardening

1. **Security Module**: Configure `sfp__security_hardening`
2. **Security Settings**:
   - Enable strict input validation
   - Configure audit logging
   - Set up access controls
   - Enable security monitoring

## Enterprise Database Setup

### PostgreSQL Configuration (Recommended for Production)

```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib
pip3 install psycopg2-binary

# Create enterprise database
sudo -u postgres createdb spiderfoot_enterprise
sudo -u postgres createuser spiderfootuser

# Grant permissions
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE spiderfoot_enterprise TO spiderfootuser;"

# Configure SpiderFoot
# Edit configuration to use PostgreSQL connection string
```

## Performance Monitoring

### Health Checks

```bash
# Check system health
python sf.py --health-check

# Monitor performance metrics
python sf.py --metrics

# Database performance check
python sf.py --db-health
```

### Viewing Performance Data

1. **Access Metrics Dashboard**: Available in web interface under "System"
2. **Storage Performance**: Monitor compression ratios and query speeds
3. **AI Processing**: View threat analysis performance metrics
4. **Security Events**: Review security audit logs and alerts

## Next Steps

### Production Deployment
- Review [Enterprise Deployment Guide](enterprise_deployment.md)
- Configure SSL/TLS certificates for production
- Set up backup and monitoring procedures
- Implement security best practices

### Advanced Configuration
- Explore [Advanced Storage](advanced/enterprise_storage.md) features
- Configure [AI Threat Intelligence](advanced/ai_threat_intelligence.md) models
- Review [Security Hardening](advanced/security_hardening.md) options
- Optimize [Performance Settings](advanced/performance_optimization.md)

### Integration
- Set up API access for automation
- Configure webhook notifications
- Integrate with SIEM platforms
- Implement CI/CD pipeline integration

For detailed information on any of these topics, refer to the comprehensive documentation in the respective sections.
