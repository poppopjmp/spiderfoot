# SpiderFoot Production Deployment

This directory contains a comprehensive production-ready Docker Compose configuration for SpiderFoot with PostgreSQL, Elasticsearch, Redis, Nginx, and monitoring stack.

## Quick Start

1. **Copy and configure environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Deploy with the automated script:**
   ```bash
   # Linux/macOS
   chmod +x deploy-production.sh
   ./deploy-production.sh --monitoring
   
   # Windows (PowerShell)
   .\deploy-production.ps1 -Monitoring
   ```

3. **Access your SpiderFoot instance:**
   - Main application: `https://your-domain.com`
   - Grafana monitoring: `https://grafana.your-domain.com`
   - Kibana analytics: `https://kibana.your-domain.com`

## Architecture Overview

The production deployment includes:

### Core Services
- **SpiderFoot Application**: Main OSINT reconnaissance platform
- **PostgreSQL 15**: Primary database with performance optimizations
- **Elasticsearch 8.11**: Advanced search and data analytics
- **Redis 7**: Caching and session management
- **Nginx**: Reverse proxy with SSL termination, rate limiting, and security headers

### Monitoring Stack (Optional)
- **Prometheus**: Metrics collection and storage
- **Grafana**: Monitoring dashboards and alerting
- **Kibana**: Elasticsearch data visualization
- **Various Exporters**: PostgreSQL, Redis, Nginx, Node metrics

### Support Services
- **Automated Backups**: PostgreSQL database backups with retention
- **Health Checks**: Comprehensive service health monitoring
- **Security**: Rate limiting, SSL/TLS, security headers

## Configuration Files

### Environment Configuration
- `.env`: Main configuration file (copy from `.env.example`)
- Contains all passwords, paths, and service settings

### Nginx Configuration
- `docker-compose-production-files/nginx.conf`: Main Nginx configuration
- `docker-compose-production-files/nginx/conf.d/`: Site-specific configurations
- Advanced features: SSL/TLS, rate limiting, caching, security headers

### Database Configuration
- `docker-compose-production-files/postgres-init/init.sh`: Database initialization
- Creates monitoring users, extensions, and performance optimizations

### Monitoring Configuration
- `docker-compose-production-files/prometheus/prometheus.yml`: Prometheus config
- `docker-compose-production-files/grafana/`: Grafana dashboards and datasources

### Backup Configuration
- `docker-compose-production-files/backup-scripts/`: Database backup and restore scripts
- Automated retention and optional S3 upload

## Deployment Profiles

### Core Profile (Default)
```bash
docker-compose -f docker-compose-prod.yml up -d
```
Includes: SpiderFoot, PostgreSQL, Elasticsearch, Redis, Nginx

### Monitoring Profile
```bash
docker-compose -f docker-compose-prod.yml --profile monitoring up -d
```
Adds: Prometheus, Grafana, Kibana, Exporters

### Backup Profile
```bash
docker-compose -f docker-compose-prod.yml --profile backup run --rm postgres-backup
```
Runs: Database backup service

## Security Features

### Network Security
- Isolated networks: frontend, backend, monitoring
- Backend network is internal-only
- No direct external access to databases

### SSL/TLS Configuration
- Modern TLS 1.2/1.3 only
- Strong cipher suites
- HSTS headers
- OCSP stapling ready

### Rate Limiting
- API endpoints: 10 requests/second
- Login endpoints: 5 requests/minute
- General endpoints: 50 requests/second
- Connection limiting per IP

### Security Headers
- Content Security Policy
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection
- Referrer-Policy

## Performance Optimizations

### PostgreSQL
- Optimized shared_buffers, work_mem, etc.
- Connection pooling
- Performance extensions (pg_stat_statements)
- Monitoring and read-only users

### Elasticsearch
- 2GB heap size (configurable)
- Memory lock enabled
- Optimized for single-node deployment
- Index auto-creation enabled

### Redis
- Persistent storage with AOF
- Memory optimization (LRU eviction)
- Connection keep-alive

### Nginx
- HTTP/2 support
- Gzip compression
- Static file caching
- Upstream connection pooling

## Monitoring and Observability

### Metrics Collection
- Application metrics via Prometheus
- Database metrics via postgres_exporter
- Cache metrics via redis_exporter
- Reverse proxy metrics via nginx_exporter
- System metrics via node_exporter

### Dashboards
- Pre-configured Grafana dashboards
- Real-time performance monitoring
- Alert conditions ready

### Logging
- Structured logging to files
- Nginx access/error logs
- Application logs with timestamps

## Backup and Recovery

### Automated Backups
- Daily PostgreSQL backups
- Multiple formats (SQL and custom)
- Configurable retention (30 days default)
- Optional S3 upload

### Manual Backup
```bash
docker-compose -f docker-compose-prod.yml --profile backup run --rm postgres-backup
```

### Restore Process
```bash
# Use the restore script
docker-compose -f docker-compose-prod.yml exec postgres /scripts/restore.sh backup_file.sql
```

## Maintenance Operations

### View Logs
```bash
# All services
docker-compose -f docker-compose-prod.yml logs -f

# Specific service
docker-compose -f docker-compose-prod.yml logs -f spiderfoot
```

### Scale Services
```bash
# Scale SpiderFoot application
docker-compose -f docker-compose-prod.yml up -d --scale spiderfoot=2
```

### Update Services
```bash
# Pull latest images
docker-compose -f docker-compose-prod.yml pull

# Restart with new images
docker-compose -f docker-compose-prod.yml up -d
```

### Health Checks
```bash
# Check service health
docker-compose -f docker-compose-prod.yml ps

# Check specific service health
curl -k https://your-domain.com/health
```

## Troubleshooting

### Common Issues

1. **SSL Certificate Errors**
   - Check certificate files in `${CERTS_PATH}`
   - Verify certificate validity: `openssl x509 -in cert.crt -text -noout`

2. **Database Connection Issues**
   - Check PostgreSQL health: `docker-compose -f docker-compose-prod.yml exec postgres pg_isready`
   - Verify credentials in `.env`

3. **Elasticsearch Issues**
   - Check cluster health: `curl http://localhost:9200/_cluster/health`
   - Verify heap size and memory limits

4. **Performance Issues**
   - Monitor with Grafana dashboards
   - Check resource usage: `docker stats`
   - Review logs for errors

### Debug Commands
```bash
# Enter container shell
docker-compose -f docker-compose-prod.yml exec spiderfoot bash

# Check container logs
docker-compose -f docker-compose-prod.yml logs --tail=100 spiderfoot

# Monitor resource usage
docker stats $(docker-compose -f docker-compose-prod.yml ps -q)
```

## Security Considerations

### Production Checklist
- [ ] Change all default passwords in `.env`
- [ ] Use trusted SSL certificates (not self-signed)
- [ ] Configure firewall rules
- [ ] Set up log monitoring
- [ ] Configure backup encryption
- [ ] Review and adjust rate limits
- [ ] Set up intrusion detection
- [ ] Regular security updates

### Access Control
- Configure basic auth for monitoring interfaces
- Use VPN for administrative access
- Implement IP whitelisting for sensitive endpoints
- Regular audit of user accounts

### Data Protection
- Encrypt backups
- Secure backup storage
- Regular backup testing
- Data retention policies

## Support and Documentation

### Additional Resources
- [SpiderFoot Documentation](../docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

### Getting Help
1. Check the troubleshooting section above
2. Review service logs for error messages
3. Consult the official SpiderFoot documentation
4. Open an issue on the SpiderFoot GitHub repository

## License

This production deployment configuration is provided under the same license as SpiderFoot.
