# sfp_performance_optimizer - Performance Optimization Engine

## Overview

The Performance Optimizer module provides intelligent caching, rate limiting, and resource management capabilities for SpiderFoot. This module significantly improves scan performance, reduces API costs, and manages system resources efficiently.

## Features

### Intelligent Caching System
- **TTL-based Caching**: Time-to-live automatic cache expiration
- **LRU Eviction**: Least Recently Used cache replacement
- **Memory Management**: Configurable cache size limits
- **Cache Statistics**: Hit rates and performance metrics

### Adaptive Rate Limiting
- **Exponential Backoff**: Automatic delay adjustment
- **API Response Monitoring**: Success rate tracking
- **Domain-Specific Limits**: Per-service rate control
- **Burst Protection**: Handle traffic spikes

### Resource Monitoring
- **Memory Usage Tracking**: Real-time memory monitoring
- **Garbage Collection**: Intelligent cleanup triggers
- **Performance Metrics**: Comprehensive statistics
- **Resource Alerts**: Threshold-based warnings

### Request Optimization
- **Batch Processing**: Combine multiple requests
- **Deduplication**: Eliminate duplicate queries
- **Connection Pooling**: Reuse HTTP connections
- **Async Processing**: Non-blocking request handling

## Configuration

### Cache Configuration
```ini
[performance_optimizer]
# Enable caching system
cache_enabled = True

# Cache TTL in seconds
cache_ttl_seconds = 3600

# Maximum cache entries
max_cache_size = 50000

# Cache cleanup interval
cache_cleanup_interval = 300
```

### Rate Limiting Settings
```ini
# Enable rate limiting
rate_limiting_enabled = True

# Default delay between requests
default_delay_seconds = 1.0

# Enable adaptive backoff
adaptive_backoff = True

# Maximum delay for backoff
max_delay_seconds = 60.0
```

### Resource Monitoring
```ini
# Enable resource monitoring
resource_monitoring_enabled = True

# Memory threshold (MB)
memory_threshold_mb = 1024

# GC trigger threshold (%)
gc_threshold_percentage = 80.0
```

## Supported Event Types

### Input Events
- `*` (All event types for optimization)

### Output Events
- `PERFORMANCE_METRIC`
- `CACHE_STATISTICS`
- `RESOURCE_WARNING`
- `OPTIMIZATION_RECOMMENDATION`

## Performance Features

### Cache Management
```python
# Cache hit rate targeting
target_hit_rate = 0.6  # 60% minimum

# Automatic cache warming
cache_warming_enabled = True

# Cache compression
cache_compression = True

# Distributed caching support
distributed_cache = False  # Redis support available
```

### Rate Limiting Strategies
```python
# Per-domain rate limits
domain_limits = {
    'api.virustotal.com': 4.0,  # 4 requests per second
    'api.shodan.io': 1.0,       # 1 request per second
    'api.hunter.io': 10.0       # 10 requests per second
}

# Adaptive algorithm parameters
backoff_multiplier = 2.0
success_threshold = 0.9
failure_threshold = 0.7
```

## Usage Examples

### Basic Performance Optimization
```bash
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_performance_optimizer
```

### High-Volume Scanning
```bash
python sf.py -s targets.txt -t FILE -m sfp_portscan_tcp,sfp_banner,sfp_performance_optimizer
```

### API-Heavy Investigation
```bash
python sf.py -s user@example.com -t EMAILADDR -m sfp_hunter,sfp_haveibeen,sfp_virustotal,sfp_performance_optimizer
```

## Performance Metrics

### Cache Performance
- **Hit Rate**: Percentage of cache hits
- **Miss Rate**: Percentage of cache misses
- **Eviction Rate**: Cache entry replacement frequency
- **Memory Usage**: Cache memory consumption

### Request Performance
- **Response Time**: Average API response times
- **Success Rate**: Successful request percentage
- **Retry Rate**: Request retry frequency
- **Throughput**: Requests processed per minute

### Resource Utilization
- **Memory Usage**: Current and peak memory usage
- **CPU Usage**: Processing resource consumption
- **Garbage Collection**: GC frequency and duration
- **Connection Pool**: Active connection statistics

## Optimization Strategies

### Automatic Optimizations
1. **Query Deduplication**: Eliminate repeated requests
2. **Result Caching**: Store and reuse API responses
3. **Request Batching**: Combine multiple API calls
4. **Connection Reuse**: Maintain persistent connections

### Manual Optimizations
1. **Cache Prewarming**: Populate cache with common queries
2. **Rate Limit Tuning**: Adjust delays based on API limits
3. **Memory Management**: Configure appropriate cache sizes
4. **Parallel Processing**: Enable concurrent request handling

## Integration with Other Modules

### Recommended Usage
```bash
# Always include performance optimizer for large scans
-m sfp_dnsresolve,sfp_ssl,sfp_whois,sfp_performance_optimizer

# API-heavy investigations
-m sfp_virustotal,sfp_shodan,sfp_hunter,sfp_performance_optimizer

# Multi-target scanning
-m sfp_portscan_tcp,sfp_banner,sfp_ssl,sfp_performance_optimizer
```

### Module Compatibility
- **All Modules**: Universal compatibility
- **API Modules**: Maximum benefit for API-dependent modules
- **High-Volume Modules**: Significant performance improvements
- **Resource-Intensive Modules**: Memory and CPU optimization

## Performance Monitoring

### Real-Time Statistics
```python
# Access performance metrics
cache_stats = optimizer.get_cache_stats()
performance_metrics = optimizer.get_performance_metrics()
resource_usage = optimizer.get_resource_usage()

# Cache statistics
print(f"Cache hit rate: {cache_stats['hit_rate']:.2%}")
print(f"Memory usage: {cache_stats['memory_mb']:.1f} MB")

# Performance metrics
print(f"Average response time: {performance_metrics['avg_response_time']:.2f}s")
print(f"Success rate: {performance_metrics['success_rate']:.2%}")
```

### Performance Dashboard
- **Real-Time Metrics**: Live performance monitoring
- **Historical Trends**: Performance over time
- **Optimization Recommendations**: Automated suggestions
- **Resource Alerts**: Threshold-based notifications

## Advanced Features

### Distributed Caching
```ini
# Redis configuration for distributed caching
[performance_optimizer.redis]
enabled = True
host = localhost
port = 6379
db = 0
password = your_redis_password
```

### Custom Cache Strategies
```python
# Custom cache key generation
def custom_cache_key(module, event_type, data):
    return f"{module}:{event_type}:{hash(data)}"

# Custom eviction policies
eviction_policies = ['lru', 'lfu', 'ttl', 'custom']
```

### Performance Profiling
```python
# Enable detailed profiling
profiling_enabled = True
profile_memory = True
profile_cpu = True
profile_network = True

# Performance logging
performance_log_level = 'INFO'
performance_log_file = 'performance.log'
```

## Troubleshooting

### Common Performance Issues
1. **Low Cache Hit Rate**: Increase cache size or TTL
2. **High Memory Usage**: Reduce cache size or enable compression
3. **API Rate Limiting**: Adjust delay settings
4. **Slow Response Times**: Enable connection pooling

### Performance Tuning
```ini
# For high-volume scanning
cache_ttl_seconds = 7200
max_cache_size = 100000
default_delay_seconds = 0.5

# For memory-constrained environments
cache_ttl_seconds = 1800
max_cache_size = 10000
gc_threshold_percentage = 60.0
```

### Debugging Performance
```bash
# Enable detailed performance logging
SPIDERFOOT_LOG_LEVEL=DEBUG python sf.py -s target.com -t DOMAIN_NAME -m sfp_performance_optimizer

# Monitor real-time performance
tail -f performance.log | grep "PERFORMANCE"
```

## Security Considerations

### Cache Security
- **Data Encryption**: Optional cache encryption
- **Access Controls**: Restricted cache access
- **Data Sanitization**: Clean sensitive data from cache
- **Audit Logging**: Cache access logging

### Resource Protection
- **Memory Limits**: Prevent memory exhaustion
- **Rate Limiting**: Protect against abuse
- **Resource Monitoring**: Detect anomalous usage
- **Automatic Cleanup**: Prevent resource leaks

---

For more information on performance optimization, see the [Performance Guide](../advanced.md).
