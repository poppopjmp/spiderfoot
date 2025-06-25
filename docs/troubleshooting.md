# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with SpiderFoot across installation, configuration, scanning, and workflow functionality.

## Installation Issues

### Python Version Problems
```bash
# Check Python version (requires 3.7+)
python3 --version
python --version

# Check which Python is being used
which python3
which python

# Verify pip version
pip3 --version
```

**Solutions:**
- Install Python 3.9+ for best compatibility
- Use `python3` explicitly instead of `python`
- Consider using `pyenv` for Python version management

### Dependency Installation Failures

#### Pip Issues
```bash
# Upgrade pip to latest version
python3 -m pip install --upgrade pip

# Clear pip cache
pip3 cache purge

# Install with user permissions
pip3 install --user -r requirements.txt

# Use virtual environment (recommended)
python3 -m venv spiderfoot-env
source spiderfoot-env/bin/activate  # Linux/macOS
spiderfoot-env\Scripts\activate     # Windows
pip install -r requirements.txt
```

#### Common Package Errors
```bash
# SSL certificate issues
pip3 install --trusted-host pypi.org --trusted-host pypi.python.org certifi

# Network/proxy issues
pip3 install --proxy http://proxy.company.com:8080 -r requirements.txt

# Specific package failures
pip3 install --force-reinstall requests cherrypy mako
```

### Permission Issues

#### Linux/macOS
```bash
# Install to user directory
pip3 install --user -r requirements.txt

# Fix file permissions
chmod +x sf.py sfworkflow.py

# Database permission issues
chmod 755 data/
chmod 644 data/spiderfoot.db
```

#### Windows
```cmd
# Run as administrator if needed
# Or use user installation
pip install --user -r requirements.txt

# Ensure Python is in PATH
echo %PATH%
```

### Port Binding Issues
```bash
# Check what's using port 5001
netstat -tlnp | grep 5001     # Linux
netstat -ano | findstr 5001   # Windows
lsof -i :5001                 # macOS

# Use different port
python sf.py -l 127.0.0.1:5002

# Kill process using port
sudo kill -9 $(lsof -ti:5001) # Linux/macOS
```

## Runtime Issues

### Web Interface Problems

#### Cannot Access Web Interface
```bash
# Check if SpiderFoot is running
ps aux | grep sf.py           # Linux/macOS
tasklist | findstr python    # Windows

# Verify port binding
netstat -tlnp | grep 5001

# Check firewall settings
sudo ufw allow 5001           # Ubuntu
# Windows: Check Windows Firewall settings
```

#### Web Interface Loads but Shows Errors
- **Check browser console** for JavaScript errors
- **Clear browser cache** and cookies
- **Try different browser** (Chrome, Firefox, Edge)
- **Check database permissions** and connectivity

#### Template or Static File Errors
```bash
# Verify directory structure
ls -la spiderfoot/templates/
ls -la spiderfoot/static/

# Check file permissions
find spiderfoot/ -name "*.tmpl" -exec chmod 644 {} \;
find spiderfoot/static/ -type f -exec chmod 644 {} \;
```

### Database Issues

#### Database Connection Errors
```bash
# Check database file exists and is writable
ls -la data/spiderfoot.db
ls -la spiderfoot.db

# Database locked errors
lsof data/spiderfoot.db            # Check what's accessing DB
pkill -f sf.py                # Kill any hanging processes

# Backup and recreate database
cp data/spiderfoot.db data/spiderfoot.db.backup
rm data/spiderfoot.db
python sf.py --create-db      # If option exists
```

#### Database Corruption
```bash
# Check database integrity
sqlite3 data/spiderfoot.db "PRAGMA integrity_check;"

# Repair database
sqlite3 data/spiderfoot.db "VACUUM;"
sqlite3 data/spiderfoot.db "REINDEX;"

# Restore from backup
cp data/spiderfoot.db.backup data/spiderfoot.db
```

### Scanning Issues

#### Scans Not Starting
1. **Check module configuration**:
   ```bash
   python sf.py -M                    # List all modules
   python sf.py -M sfp_dnsresolve     # Test specific module
   ```

2. **Verify target format**:
   ```bash
   python sf.py -T                    # List target types
   ```

3. **Check logs**:
   ```bash
   tail -f logs/spiderfoot.log        # Monitor logs
   python sf.py -v -s example.com -t DOMAIN_NAME -m sfp_dnsresolve
   ```

#### Scans Hanging or Slow
```bash
# Reduce thread count
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --max-threads 1

# Set timeout
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --timeout 60

# Check system resources
top                               # Linux/macOS
taskmgr                          # Windows

# Monitor database activity
lsof data/spiderfoot.db
```

#### Module-Specific Errors

##### API Key Issues
1. **Configure API keys** in web interface: Settings → Module Settings
2. **Test API connectivity**:
   ```bash
   curl -H "X-API-KEY: your-key" https://api.service.com/test
   ```
3. **Check API quotas** and rate limits

##### Network/DNS Issues
```bash
# Test DNS resolution
nslookup example.com
dig example.com

# Test connectivity
ping example.com
curl -I https://example.com

# Check proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

##### SSL/Certificate Issues
```bash
# Test SSL connection
openssl s_client -connect example.com:443

# Update certificates
pip3 install --upgrade certifi

# Skip SSL verification (testing only)
export PYTHONHTTPSVERIFY=0
```

## Workflow Issues

### Workspace Problems

#### Workspace Creation Fails
```bash
# Check workflow configuration
python -c "from spiderfoot.workflow_config import WorkflowConfig; print(WorkflowConfig().config)"

# Verify database schema
sqlite3 data/spiderfoot.db ".schema tbl_workspaces"

# Check permissions
ls -la data/
chmod 755 data/
```

#### Workspace Data Missing
```bash
# List workspaces
python sfworkflow.py list-workspaces

# Show workspace details
python sfworkflow.py show-workspace ws_abc123

# Check database entries
sqlite3 data/spiderfoot.db "SELECT * FROM tbl_workspaces;"
```

### Multi-Target Scanning Issues

#### Scans Not Starting
1. **Check target validation**:
   ```bash
   python sfworkflow.py list-targets ws_abc123
   ```

2. **Verify module availability**:
   ```bash
   python sf.py -M | grep -E "(sfp_dnsresolve|sfp_ssl)"
   ```

3. **Check resource limits**:
   ```bash
   # Monitor system resources during scanning
   htop  # or top
   ```

#### Memory Issues
```bash
# Reduce concurrent scans
python sfworkflow.py multi-scan ws_abc123 --max-concurrent 2

# Monitor memory usage
free -h                          # Linux
vm_stat                          # macOS
wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /format:list  # Windows

# Check Python memory usage
python -c "import psutil; print(f'Memory: {psutil.virtual_memory().percent}%')"
```

### Correlation Issues

#### Correlation Analysis Fails
```bash
# Check correlation rules
python -c "from spiderfoot.workflow_config import WorkflowConfig; print(WorkflowConfig().get('correlation.rules_enabled'))"

# Test with single rule
python sfworkflow.py correlate ws_abc123 --rules cross_scan_shared_infrastructure

# Check scan completion
python sfworkflow.py list-scans ws_abc123
```

#### CTI Report Generation Issues
```bash
# Test MCP connection
python sfworkflow.py test-mcp

# Check MCP configuration
grep -A 10 '"mcp"' workflow_config.json

# Verify Python async support
python -c "import asyncio; print('Asyncio available')"
```

## Performance Issues

### General Performance Optimization

#### Database Performance
```bash
# Optimize database
sqlite3 data/spiderfoot.db "VACUUM;"
sqlite3 data/spiderfoot.db "ANALYZE;"

# Check database size
du -sh data/spiderfoot.db

# Clean old scans
sqlite3 data/spiderfoot.db "DELETE FROM tbl_scan_instance WHERE created < datetime('now', '-30 days');"
```

#### Memory Optimization
```bash
# Reduce thread count
python sf.py --max-threads 1

# Use memory-efficient modules
python sf.py -m sfp_dnsresolve,sfp_ssl  # Instead of all modules

# Monitor memory usage
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB')
"
```

#### Network Optimization
```bash
# Adjust timeouts
python sf.py --timeout 30

# Use CDN/cache for module data
export SF_CACHE_ENABLED=true

# Configure proxy for better routing
export HTTP_PROXY=http://proxy.company.com:8080
```

### Large-Scale Scanning

#### Batch Processing
```bash
# Process targets in smaller batches
split -l 100 large_targets.txt batch_

# Use workspace for organization
python sfworkflow.py create-workspace "Large Assessment"
python sfworkflow.py multi-scan ws_abc123 --targets-file batch_aa --wait
```

#### Resource Monitoring
```bash
# Monitor during scans
watch -n 5 'free -m && echo "=== Processes ===" && ps aux | grep python | head -5'

# Log resource usage
while true; do
    echo "$(date): $(free -m | grep Mem:)" >> resource_usage.log
    sleep 60
done &
```

## Configuration Issues

### Module Configuration

#### API Key Problems
1. **Web Interface Method**:
   - Go to Settings → Module Settings
   - Configure API keys for each service
   - Test connectivity

2. **Configuration File Method**:
   ```bash
   # Edit configuration file
   vim spiderfoot.conf
   
   [sfp_virustotal]
   api_key = your-api-key-here
   ```

3. **Environment Variables**:
   ```bash
   export VIRUSTOTAL_API_KEY=your-key
   export SHODAN_API_KEY=your-key
   ```

#### Module Dependencies
```bash
# Install module-specific dependencies
pip3 install requests beautifulsoup4 dnspython

# Check module requirements
python sf.py -M sfp_shodan  # Shows dependencies
```

### Workflow Configuration

#### Configuration File Issues
```bash
# Create sample configuration
python -m spiderfoot.workflow_config create-sample config.json

# Validate configuration
python -c "
from spiderfoot.workflow_config import WorkflowConfig
try:
    config = WorkflowConfig('config.json')
    print('Configuration valid')
except Exception as e:
    print(f'Configuration error: {e}')
"
```

#### MCP Integration Issues
```bash
# Test MCP server
curl -X POST http://localhost:8000/api/test

# Check MCP configuration
python -c "
from spiderfoot.workflow_config import WorkflowConfig
config = WorkflowConfig()
print('MCP enabled:', config.get('mcp.enabled'))
print('MCP URL:', config.get('mcp.server_url'))
"
```

## Logging and Debugging

### Enable Debug Logging
```bash
# Verbose output
python sf.py -v -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Debug logging in Python
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Your SpiderFoot code here
"

# Log to file
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve > scan.log 2>&1
```

### Log Analysis
```bash
# Monitor logs in real-time
tail -f logs/spiderfoot.log

# Search for errors
grep -i error logs/spiderfoot.log
grep -i exception logs/spiderfoot.log

# Analyze module performance
grep "Module.*took" logs/spiderfoot.log | sort -k4 -n
```

### Debug Specific Components
```bash
# Debug database operations
sqlite3 data/spiderfoot.db ".log debug.log"

# Debug web interface
python sf.py -l 127.0.0.1:5001 --debug

# Debug workflow operations
python sfworkflow.py --verbose list-workspaces
```

## Getting Help

### Information Gathering
Before seeking help, gather this information:

```bash
# System information
echo "OS: $(uname -a)"
echo "Python: $(python3 --version)"
echo "SpiderFoot: $(python sf.py --version)"
echo "Working directory: $(pwd)"

# Configuration
echo "Database: $(ls -la data/spiderfoot.db 2>/dev/null || echo 'Not found')"
echo "Modules: $(python sf.py -M | wc -l) available"

# Recent errors
echo "Recent errors:"
tail -20 logs/spiderfoot.log | grep -i error
```

### Community Resources

#### GitHub Issues
- **Search existing issues**: https://github.com/poppopjmp/spiderfoot/issues
- **Create new issue**: Include system info, logs, and reproduction steps

#### Discord Community
- **Real-time help**: https://discord.gg/vyvztrG
- **Share logs and screenshots**

#### Documentation
- **Official documentation**: Available in web interface
- **Module documentation**: `python sf.py -M module_name`
- **API documentation**: Check `/docs` endpoint in web interface

### Professional Support
For enterprise deployments or complex issues:
- Consider professional consulting
- Review enterprise support options
- Engage with SpiderFoot community experts

## Emergency Procedures

### Complete Reset
```bash
# Backup current state
cp -r spiderfoot/ spiderfoot_backup/
cp data/spiderfoot.db data/spiderfoot.db.backup

# Clean installation
rm -rf spiderfoot/
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot/
pip3 install -r requirements.txt

# Restore database if needed
cp ../data/spiderfoot.db.backup ./data/spiderfoot.db
```

### Data Recovery
```bash
# Recover scan data from database
sqlite3 data/spiderfoot.db "
SELECT scan_id, scan_name, scan_target 
FROM tbl_scan_instance 
ORDER BY created DESC LIMIT 10;
"

# Export important scan results
sqlite3 data/spiderfoot.db "
.mode csv
.output important_scans.csv
SELECT * FROM tbl_scan_results WHERE scan_id = 'your_scan_id';
.quit
"
```

### Performance Recovery
```bash
# Kill all SpiderFoot processes
pkill -f sf.py
pkill -f sfworkflow.py

# Clean temporary files
rm -rf __pycache__/
rm -rf logs/*.log.old
rm -rf cache/*

# Restart with minimal configuration
python sf.py -l 127.0.0.1:5001 --max-threads 1
```

This comprehensive troubleshooting guide should help resolve most common issues with SpiderFoot installation, configuration, and operation.

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

### Database Issues
```bash
# Check database file exists and is writable
ls -la data/spiderfoot.db
ls -la spiderfoot.db

# Database locked errors
lsof data/spiderfoot.db            # Check what's accessing DB
pkill -f sf.py                # Kill any hanging processes

# Backup and recreate database
cp data/spiderfoot.db data/spiderfoot.db.backup
rm data/spiderfoot.db
python sf.py --create-db      # If option exists
```

## Performance Issues

### Slow Scans
```bash
# Reduce concurrent threads
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --options '{"_maxthreads": 1}'

# Increase timeouts
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --options '{"_timeout": 60}'
```

### High Memory Usage
```bash
# Monitor memory usage
ps aux | grep sf.py

# Limit module execution
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve --options '{"_maxpages": 50}'
```

### Network Connectivity
```bash
# Test basic connectivity
python sf.py -s google.com -t DOMAIN_NAME -m sfp_dnsresolve

# Check proxy settings
export HTTP_PROXY=http://proxy.example.com:8080
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve
```

## Web Interface Issues

### Cannot Access Web Interface
1. **Check if SpiderFoot is running**
2. **Verify port and address**: Default is 127.0.0.1:5001
3. **Check firewall settings**
4. **Try different browser**

### Authentication Issues
```bash
# Reset authentication
# Edit spiderfoot.conf and set:
__authentication = false

# Or change default credentials
__username = admin
__password = newpassword
```

### Browser Compatibility
- **Chrome/Chromium**: Fully supported
- **Firefox**: Fully supported  
- **Safari**: Mostly supported
- **Edge**: Mostly supported
- **Internet Explorer**: Not supported

## Workflow Issues

### Workspace Creation Fails
```bash
# Check workspace name validation
python sfworkflow.py create-workspace "Valid Name Without Special Chars"

# Verify database permissions
ls -la data/spiderfoot.db
```

### Multi-Target Scan Issues
```bash
# Check target format
python sfworkflow.py add-target ws_123 example.com --type DOMAIN_NAME

# Verify module compatibility
python sf.py -M sfp_module_name
```

### Correlation Analysis Problems
```bash
# Ensure scans are complete
python sfworkflow.py list-scans ws_123

# Check correlation rules
python sfworkflow.py correlate ws_123 --rules cross_scan_shared_infrastructure
```

## Docker Issues

### Container Won't Start
```bash
# Check container logs
docker logs <container_id>

# Verify port mapping
docker run -p 5001:5001 spiderfoot/spiderfoot

# Check Docker version
docker --version
```

### Volume Mounting Issues
```bash
# Correct volume syntax
docker run -p 5001:5001 -v $(pwd)/data:/var/lib/spiderfoot spiderfoot/spiderfoot

# Check permissions
ls -la data/
```

## Debugging Tools

### Enable Debug Logging
```bash
# Set debug level
export SPIDERFOOT_LOG_LEVEL=DEBUG

# Run with verbose output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve -v
```

### Configuration Validation
```bash
# Validate configuration
python sf.py --validate-config

# Test database connection
python sf.py --test-database

# Check module status
python sf.py --test-modules
```

### Network Debugging
```bash
# Test DNS resolution
nslookup example.com

# Check connectivity
curl -I https://example.com

# Test with specific DNS server
dig @8.8.8.8 example.com
```

## Getting Help

### Documentation Resources
- **Installation Guide**: Detailed setup instructions
- **Configuration Guide**: All configuration options
- **Module Documentation**: Individual module help
- **API Reference**: Programming interfaces

### Community Support
- **GitHub Issues**: Bug reports and feature requests
- **Discord Community**: Real-time community support
- **Wiki**: Additional documentation
- **Stack Overflow**: Tag questions with 'spiderfoot'

### Professional Support
For commercial support and consulting:
- Contact the SpiderFoot team
- Professional services available
- Custom module development
- Enterprise deployment assistance

## Error Reference

### Common Error Messages

#### "Module not found"
**Cause**: Module name misspelled or doesn't exist
**Solution**: Check available modules with `python sf.py -M`

#### "Target validation failed"
**Cause**: Invalid target format for selected type
**Solution**: Verify target matches expected format (domain.com for DOMAIN_NAME)

#### "Database locked"
**Cause**: Another SpiderFoot instance using same database
**Solution**: Stop other instances or use different database file

#### "Connection timeout"
**Cause**: Network connectivity issues or firewall blocking
**Solution**: Check network connection and proxy settings

#### "API key invalid"
**Cause**: Incorrect or expired API key
**Solution**: Verify API key in module configuration

### HTTP Error Codes

#### 404 Not Found
**Web Interface**: Page or resource doesn't exist
**API**: Endpoint or resource not found

#### 500 Internal Server Error
**Cause**: Server-side error in SpiderFoot
**Solution**: Check logs for specific error details

#### 403 Forbidden
**Cause**: Authentication required or insufficient permissions
**Solution**: Check authentication settings

For additional help, join our [Discord community](https://discord.gg/vyvztrG) or check the [GitHub issues](https://github.com/smicallef/spiderfoot/issues).
