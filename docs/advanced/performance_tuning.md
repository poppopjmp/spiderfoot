# Performance Tuning

Optimize SpiderFoot for maximum performance and efficiency in your environment.

## System Optimization

### Hardware Requirements

#### Minimum Configuration
- **CPU**: 2 cores
- **RAM**: 4 GB
- **Storage**: 10 GB SSD
- **Network**: 10 Mbps

#### Recommended Configuration
- **CPU**: 8+ cores
- **RAM**: 16+ GB
- **Storage**: 100+ GB NVMe SSD
- **Network**: 100+ Mbps

#### High-Performance Configuration
- **CPU**: 16+ cores
- **RAM**: 32+ GB
- **Storage**: 500+ GB NVMe SSD
- **Network**: 1+ Gbps

### Operating System Tuning

```bash
# Increase file descriptor limits
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Optimize network settings
echo "net.core.rmem_max = 16777216" >> /etc/sysctl.conf
echo "net.core.wmem_max = 16777216" >> /etc/sysctl.conf
echo "net.ipv4.tcp_rmem = 4096 65536 16777216" >> /etc/sysctl.conf

# Apply changes
sysctl -p
```

## SpiderFoot Configuration

### Thread Management

```ini
[performance]
# Global thread limits
max_threads = 20
max_concurrent_modules = 100

# Scan-specific threads
scan_max_threads = 10
module_timeout = 300

# Queue management
max_queue_size = 10000
queue_timeout = 60
```

### Memory Optimization

```ini
[performance]
# Memory limits
max_memory_usage = 4096  # MB
memory_check_interval = 300  # seconds

# Garbage collection
gc_threshold = 1000
gc_interval = 600

# Result caching
cache_size = 1000
cache_timeout = 3600
```

### Database Performance

```ini
[database]
# SQLite optimization
pragma_journal_mode = WAL
pragma_synchronous = NORMAL
pragma_cache_size = 10000
pragma_temp_store = MEMORY

# Connection pooling
max_connections = 10
connection_timeout = 30
```

## Module Optimization

### Module Selection

#### Performance-Focused Modules
```bash
# Fast passive modules
FAST_PASSIVE="sfp_dnsresolve,sfp_whois,sfp_ssl"

# Efficient threat intelligence
EFFICIENT_TI="sfp_threatcrowd,sfp_virustotal,sfp_alienvault"

# Lightweight web analysis
LIGHT_WEB="sfp_robots,sfp_webheader"
```

#### Resource-Intensive Modules
```bash
# Avoid or limit these for large scans
HEAVY_MODULES="sfp_spider,sfp_portscan_tcp,sfp_subdomain_enum"
```

### Module Configuration

```ini
[modules]
# DNS modules
sfp_dnsresolve.timeout = 10
sfp_dnsresolve.threads = 5
sfp_dnsresolve.cache_results = true

# HTTP modules
sfp_webheader.timeout = 15
sfp_webheader.max_redirects = 3
sfp_webheader.user_agent_rotation = true

# Scanning modules
sfp_portscan_tcp.timeout = 5
sfp_portscan_tcp.max_ports = 1000
sfp_portscan_tcp.randomize = true
```

## Workflow Optimization

### Multi-Target Scanning

```bash
# Optimize for system capacity
python sfworkflow.py multi-scan ws_123 \
  --modules sfp_dnsresolve,sfp_ssl \
  --options '{
    "_maxthreads": 5,
    "_timeout": 120,
    "_delay": 0.5
  }'
```

### Correlation Performance

```ini
[correlation]
# Parallel processing
parallel_processing = true
max_workers = 8

# Result limits
max_results_per_rule = 1000
confidence_threshold = 75

# Caching
cache_correlations = true
cache_duration = 3600
```

## Monitoring and Profiling

### System Monitoring

```bash
# Monitor SpiderFoot processes
top -p $(pgrep -f "sf.py")

# Memory usage
ps aux | grep sf.py | awk '{print $4, $6}'

# Network connections
netstat -tnlp | grep :5001
```

### Performance Metrics

```python
# Custom performance monitoring
import psutil
import time

def monitor_performance():
    process = psutil.Process()
    
    while True:
        cpu_percent = process.cpu_percent()
        memory_mb = process.memory_info().rss / 1024 / 1024
        threads = process.num_threads()
        
        print(f"CPU: {cpu_percent}%, Memory: {memory_mb:.1f}MB, Threads: {threads}")
        time.sleep(60)
```

### Profiling Tools

```bash
# Profile Python code
python -m cProfile -o profile.stats sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Analyze profile
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"
```

## Network Optimization

### Proxy Configuration

```ini
[network]
# HTTP proxy
http_proxy = http://proxy.example.com:8080
https_proxy = http://proxy.example.com:8080

# Connection pooling
max_connections_per_host = 10
max_total_connections = 100

# Timeouts
connect_timeout = 10
read_timeout = 30
```

### DNS Optimization

```ini
[network]
# Fast DNS servers
dns_servers = 1.1.1.1,8.8.8.8,9.9.9.9

# DNS caching
dns_cache_enabled = true
dns_cache_size = 1000
dns_cache_ttl = 300

# Concurrent DNS queries
dns_max_concurrent = 10
```

## Scaling Strategies

### Horizontal Scaling

#### Multi-Instance Setup
```bash
# Instance 1: Passive modules
python sf.py -l 127.0.0.1:5001 -d passive.db

# Instance 2: Active modules  
python sf.py -l 127.0.0.1:5002 -d active.db

# Instance 3: Threat intelligence
python sf.py -l 127.0.0.1:5003 -d ti.db
```

#### Load Balancer Configuration
```nginx
upstream spiderfoot {
    server 127.0.0.1:5001;
    server 127.0.0.1:5002;
    server 127.0.0.1:5003;
}

server {
    listen 80;
    location / {
        proxy_pass http://spiderfoot;
    }
}
```

### Vertical Scaling

#### Resource Allocation
```bash
# Increase process limits
ulimit -n 65536
ulimit -u 32768

# CPU affinity
taskset -c 0-7 python sf.py -l 127.0.0.1:5001

# Memory allocation
export PYTHONMALLOC=malloc
export MALLOC_ARENA_MAX=2
```

## Cloud Optimization

### AWS Configuration

```yaml
# CloudFormation template
Resources:
  SpiderFootInstance:
    Type: AWS::EC2::Instance
    Properties:
      InstanceType: c5.2xlarge
      ImageId: ami-0abcdef1234567890
      SecurityGroups:
        - !Ref SpiderFootSecurityGroup
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash
          yum update -y
          yum install -y python3 git
          git clone https://github.com/smicallef/spiderfoot.git
          cd spiderfoot
          pip3 install -r requirements.txt
```

### Docker Optimization

```dockerfile
# Multi-stage build for smaller image
FROM python:3.9-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.9-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY . .

# Performance tuning
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MALLOC_ARENA_MAX=2

CMD ["python", "sf.py", "-l", "0.0.0.0:5001"]
```

## Troubleshooting Performance Issues

### Common Bottlenecks

#### High CPU Usage
```bash
# Reduce thread count
_maxthreads = 3

# Increase delays
_delay = 2

# Limit concurrent modules
max_concurrent_modules = 25
```

#### High Memory Usage
```bash
# Enable garbage collection
gc_enabled = true
gc_threshold = 500

# Limit result cache
max_cache_size = 1000
cache_cleanup_interval = 300
```

#### Slow Database Operations
```bash
# Optimize database
VACUUM;
REINDEX;
ANALYZE;

# Enable WAL mode
PRAGMA journal_mode=WAL;
```

### Performance Testing

```bash
# Benchmark scan performance
time python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve

# Load testing
for i in {1..10}; do
  python sf.py -s "test$i.example.com" -t DOMAIN_NAME -m sfp_dnsresolve &
done
wait
```

Ready for production? Check out [Security Considerations](security_considerations.md) and [Docker Deployment](docker_deployment.md).
