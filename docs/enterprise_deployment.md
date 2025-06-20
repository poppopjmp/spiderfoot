# SpiderFoot Enterprise Deployment Guide

This guide covers deploying SpiderFoot Enterprise in production environments with all enterprise features enabled.

## Overview

SpiderFoot Enterprise provides advanced capabilities for production OSINT automation including:

- **Advanced Storage Engine**: High-performance data storage with compression and indexing
- **AI Threat Intelligence**: ML-powered threat analysis and pattern recognition
- **Security Hardening**: Enhanced security controls and enterprise-grade configurations
- **Scalable Architecture**: Support for high-volume scanning and enterprise workloads
- **Comprehensive Analytics**: Advanced reporting and visualization capabilities

## Prerequisites

### System Requirements

**Minimum Requirements:**
- CPU: 4+ cores
- RAM: 8GB+ 
- Storage: 100GB+ available space
- OS: Linux, macOS, or Windows
- Python: 3.9 or higher

**Recommended Production Requirements:**
- CPU: 8+ cores
- RAM: 16GB+
- Storage: 500GB+ SSD storage
- Network: High-bandwidth internet connection
- Database: PostgreSQL for enterprise scalability

### Dependencies

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Optional: PostgreSQL for enterprise database
sudo apt-get install postgresql postgresql-contrib
pip3 install psycopg2-binary
```

## Deployment Options

### 1. Standard Production Deployment

```bash
# Clone repository
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot

# Install dependencies
pip3 install -r requirements.txt

# Initialize with production configuration
python3 ./sf.py --init-prod

# Start with enterprise features
python3 ./sf.py -l 0.0.0.0:5001 --enterprise
```

### 2. Docker Production Deployment

```bash
# Production deployment with optimized configuration
docker-compose -f docker-compose-prod.yml up -d

# Monitor deployment
docker-compose -f docker-compose-prod.yml logs -f
```

### 3. Enterprise Database Setup

#### PostgreSQL Configuration

```bash
# Create enterprise database
sudo -u postgres psql
CREATE DATABASE spiderfoot_enterprise;
CREATE USER spiderfootuser WITH PASSWORD 'secure_enterprise_password';
GRANT ALL PRIVILEGES ON DATABASE spiderfoot_enterprise TO spiderfootuser;
\q

# Configure SpiderFoot
python3 ./sf.py --init-db postgresql://spiderfootuser:secure_enterprise_password@localhost/spiderfoot_enterprise
```

## Enterprise Module Configuration

### Advanced Storage Engine

The advanced storage module (`sfp__stor_db_advanced`) provides:

- **Data Compression**: Automatic compression reduces storage requirements by 60-80%
- **Optimized Indexing**: Enhanced database indexes for faster query performance
- **Partitioning**: Automatic data partitioning for large datasets
- **Performance Monitoring**: Real-time storage performance metrics

**Configuration Options:**
```python
# In module configuration
{
    "compression_level": 6,        # 1-9, higher = better compression
    "enable_indexing": True,       # Enable advanced indexing
    "partition_threshold": 1000000, # Records per partition
    "cleanup_days": 90            # Data retention period
}
```

### AI Threat Intelligence

The AI threat intelligence module (`sfp__ai_threat_intel`) includes:

- **Pattern Recognition**: ML algorithms identify threat patterns
- **Automated Analysis**: AI-powered threat classification
- **Predictive Analytics**: Threat trend analysis and predictions
- **Intelligence Correlation**: Cross-reference threat indicators

**Configuration Options:**
```python
# In module configuration  
{
    "ai_confidence_threshold": 0.7,  # AI confidence level (0.0-1.0)
    "enable_predictions": True,      # Enable threat predictions
    "correlation_depth": 3,          # Correlation analysis depth
    "learning_mode": "adaptive"      # AI learning mode
}
```

### Security Hardening

The security hardening module (`sfp__security_hardening`) provides:

- **Input Validation**: Comprehensive input sanitization
- **Security Headers**: Enhanced HTTP security headers
- **Access Controls**: Role-based access control
- **Audit Logging**: Comprehensive security audit trails

**Configuration Options:**
```python
# In module configuration
{
    "strict_validation": True,       # Enable strict input validation
    "audit_all_actions": True,      # Log all user actions
    "session_timeout": 3600,        # Session timeout (seconds)
    "password_complexity": "high"   # Password complexity requirements
}
```

## Performance Optimization

### Threading Configuration

```python
# In sf.py or configuration
{
    "max_threads": 50,              # Maximum concurrent threads
    "thread_pool_size": 20,         # Thread pool size
    "queue_timeout": 300,           # Queue timeout (seconds)
    "memory_limit": "8GB"           # Memory usage limit
}
```

### Database Optimization

```sql
-- PostgreSQL optimization settings
ALTER SYSTEM SET shared_buffers = '2GB';
ALTER SYSTEM SET effective_cache_size = '6GB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
SELECT pg_reload_conf();
```

## Monitoring and Maintenance

### Health Checks

SpiderFoot Enterprise includes built-in health monitoring:

```bash
# Check system health
python3 ./sf.py --health-check

# Monitor performance metrics
python3 ./sf.py --metrics

# Database health check
python3 ./sf.py --db-health
```

### Backup and Recovery

```bash
# Backup enterprise database
python3 ./sf.py --backup --output /path/to/backup

# Restore from backup
python3 ./sf.py --restore --input /path/to/backup

# Automated backup (add to crontab)
0 2 * * * cd /path/to/spiderfoot && python3 ./sf.py --backup --output /backups/spiderfoot-$(date +\%Y\%m\%d).backup
```

### Log Management

```bash
# Configure log rotation
echo "
/path/to/spiderfoot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        systemctl reload spiderfoot
    endscript
}" >> /etc/logrotate.d/spiderfoot
```

## Security Considerations

### Network Security

- **Firewall Configuration**: Only expose necessary ports (5001 for web interface)
- **HTTPS/TLS**: Use SSL certificates for production deployments
- **Network Segmentation**: Deploy in secure network segments
- **VPN Access**: Restrict access through VPN when possible

### Authentication and Authorization

```python
# Configure authentication
{
    "auth_method": "ldap",          # ldap, oauth2, or local
    "require_2fa": True,            # Require two-factor authentication
    "session_encryption": True,     # Encrypt session data
    "password_policy": {
        "min_length": 12,
        "require_special": True,
        "require_numbers": True,
        "require_uppercase": True
    }
}
```

### Data Protection

- **Encryption at Rest**: Enable database encryption
- **Encryption in Transit**: Use HTTPS/TLS for all communications
- **Data Classification**: Implement data classification policies
- **Access Logging**: Comprehensive audit trails for compliance

## Troubleshooting

### Common Issues

1. **High Memory Usage**
   ```bash
   # Reduce thread count and memory limits
   python3 ./sf.py --max-threads 20 --memory-limit 4GB
   ```

2. **Database Performance**
   ```sql
   -- Analyze and optimize database
   ANALYZE;
   VACUUM FULL;
   REINDEX DATABASE spiderfoot_enterprise;
   ```

3. **Module Loading Errors**
   ```bash
   # Check module dependencies
   python3 ./sf.py --check-modules
   
   # Reinstall requirements
   pip3 install -r requirements.txt --force-reinstall
   ```

### Performance Tuning

1. **Database Tuning**
   - Increase shared_buffers for PostgreSQL
   - Optimize checkpoint settings
   - Configure appropriate work_mem values

2. **Application Tuning**
   - Adjust thread pool sizes based on CPU cores
   - Configure memory limits appropriately
   - Enable connection pooling for database

3. **System Tuning**
   - Increase file descriptor limits
   - Optimize network buffer sizes
   - Configure appropriate swap settings

## Support and Documentation

### Resources

- **Documentation**: [docs/](.)
- **API Reference**: [api/](api/)
- **Module Guide**: [modules_guide.md](modules_guide.md)
- **Security Guide**: [security_considerations.md](security_considerations.md)

### Community Support

- **Discord**: [SpiderFoot Community](https://discord.gg/vyvztrG)
- **GitHub Issues**: [Issue Tracker](https://github.com/poppopjmp/spiderfoot/issues)
- **Contributing**: [contributing.md](contributing.md)

## Conclusion

SpiderFoot Enterprise provides a comprehensive, production-ready OSINT automation platform with advanced capabilities for enterprise environments. This deployment guide covers the essential aspects of deploying and managing SpiderFoot Enterprise in production.

For additional support or custom deployment requirements, please refer to the community resources or consider professional support options.
