# SpiderFoot Microservice Architecture

This document describes the microservice architecture implementation for SpiderFoot, providing a path to migrate from the existing monolithic design to a more scalable and maintainable distributed system.

## Overview

The microservice architecture addresses several challenges with the current monolithic SpiderFoot application:

- **Deployment bottlenecks**: Changes require full application redeployment
- **Scaling inefficiencies**: Cannot scale individual components independently  
- **Development conflicts**: Multiple teams working on the same codebase
- **Technology constraints**: Locked into a single technology stack
- **Fault tolerance**: Single point of failure affects entire application

## Architecture Components

### 1. Service Discovery (Port 8000)

A lightweight service registry that enables microservices to find and communicate with each other.

**Features:**
- Service registration and deregistration
- Health monitoring with automatic cleanup
- Service metadata and capability tracking
- RESTful API for service coordination

**API Endpoints:**
- `POST /register` - Register a new service
- `DELETE /register/{service_id}` - Deregister a service
- `POST /discover` - Discover services by criteria
- `GET /services` - List all registered services
- `POST /heartbeat/{service_id}` - Service heartbeat
- `GET /health` - Health check

### 2. Configuration Service (Port 8001)

Centralized configuration management for all SpiderFoot services.

**Features:**
- Configuration CRUD operations via REST API
- Configuration versioning and history tracking
- Environment-specific configurations
- Database persistence with SQLite backend
- Automatic service registration with discovery

**API Endpoints:**
- `GET /config` - Get all configurations for scope
- `GET /config/{key}` - Get specific configuration
- `POST /config/{key}` - Set configuration value
- `PUT /config` - Update multiple configurations
- `DELETE /config/{key}` - Delete configuration
- `GET /config/{key}/history` - Get configuration history
- `GET /health` - Health check

### 3. Service Client Library

Simplified client library for inter-service communication.

**Features:**
- Automatic service discovery integration
- Service caching and load balancing
- Graceful fallback to monolithic mode
- Both async and sync APIs for compatibility

### 4. Configuration Adapter

Backward compatibility layer for existing SpiderFoot code.

**Features:**
- Transparent migration to microservice configuration
- Automatic fallback when microservices unavailable
- Legacy format conversion
- Environment-based activation

## Getting Started

### Prerequisites

- Python 3.11+
- All dependencies from `requirements.txt`
- Docker (optional, for containerized deployment)

### Starting Services Manually

1. **Start Service Discovery:**
   ```bash
   python services/service_discovery.py --host localhost --port 8000
   ```

2. **Start Configuration Service:**
   ```bash
   python services/config_service.py --host localhost --port 8001 --migrate
   ```

3. **Verify Services:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8001/health
   curl http://localhost:8000/services
   ```

### Using Docker Compose

```bash
docker-compose -f docker-compose.microservices.yml up -d
```

This starts:
- Service Discovery (port 8000)
- Configuration Service (port 8001)  
- API Gateway (port 8080)
- Monitoring stack (Prometheus: 9090, Grafana: 3000)

## Integration with Existing Code

### Automatic Integration

The microservice integration is automatic when environment variables are set:

```bash
export USE_MICROSERVICES=true
export SERVICE_DISCOVERY_URL=http://localhost:8000
```

### Manual Integration

```python
from services.config_adapter import initialize_config_adapter

# Initialize microservice integration
adapter = initialize_config_adapter(
    use_microservices=True,
    service_discovery_url="http://localhost:8000"
)

# Use existing SpiderFoot code - configuration will use microservices
from sflib import SpiderFoot
sf = SpiderFoot({'_debug': False})

# Configuration methods now use microservices with fallback
sf.configSet('new_setting', 'value')
value = sf.configGet('new_setting')
```

## Testing

Run the comprehensive test suite:

```bash
python services/test_microservices.py
```

Tests include:
- Service health checks
- Configuration CRUD operations
- Service discovery functionality
- Legacy code integration
- Fallback behavior

## Migration Strategy

### Phase 1: Configuration Service (Current)
- ✅ Extract configuration management
- ✅ Implement service discovery
- ✅ Create backward compatibility layer
- ✅ Validate with existing code

### Phase 2: Scan Management Service
- Extract scan lifecycle management
- Independent scan state tracking
- Parallel scan execution
- Resource isolation

### Phase 3: Module Management Service  
- Extract module loading and execution
- Independent module scaling
- Plugin architecture enhancements
- Module marketplace support

### Phase 4: Reporting Service
- Extract report generation
- Asynchronous report processing
- Multiple output formats
- Report caching and delivery

### Phase 5: User Management Service
- Extract authentication and authorization
- Multi-tenant support
- Role-based access control
- Session management

## Monitoring and Operations

### Health Checks

All services provide health check endpoints:
- Service Discovery: `GET /health`
- Configuration Service: `GET /health`

### Service Discovery

View registered services:
```bash
curl http://localhost:8000/services | jq .
```

### Configuration Management

View current configuration:
```bash
curl http://localhost:8001/config | jq .
```

Set new configuration:
```bash
curl -X POST http://localhost:8001/config/my_key \
  -H "Content-Type: application/json" \
  -d '{"key": "my_key", "value": "my_value", "scope": "global"}'
```

### Logs

Services use structured logging with timestamps:
- Service Discovery: Service registration/deregistration events
- Configuration Service: Configuration changes with history

## Security Considerations

### Current Implementation
- Services run on localhost by default
- No authentication (suitable for development)
- HTTP communication (not HTTPS)

### Production Recommendations
- Deploy behind reverse proxy/API gateway
- Implement service-to-service authentication
- Use HTTPS/TLS for all communication
- Network segmentation for service isolation
- Service mesh for advanced networking

## Benefits Achieved

### Development Benefits
- **Independent development**: Teams can work on separate services
- **Technology freedom**: Each service can use optimal technology
- **Reduced conflicts**: Smaller, focused codebases
- **Faster testing**: Unit test individual services

### Operational Benefits  
- **Independent deployment**: Deploy services separately
- **Granular scaling**: Scale services based on demand
- **Fault isolation**: Service failures don't affect entire system
- **Rolling updates**: Zero-downtime deployments

### Architectural Benefits
- **Clear boundaries**: Well-defined service interfaces
- **Data ownership**: Each service owns its data
- **Loose coupling**: Services communicate via APIs
- **High cohesion**: Related functionality grouped together

## Limitations and Trade-offs

### Current Limitations
- **Async context issues**: Some async operations need refinement
- **Network overhead**: HTTP calls vs direct function calls
- **Complexity**: More moving parts to manage
- **Development setup**: Additional services to run

### Planned Improvements
- Service mesh for advanced networking
- Containerization for easier deployment
- Monitoring and observability enhancements
- Performance optimizations

## Conclusion

This microservice implementation provides a solid foundation for migrating SpiderFoot from a monolithic to a distributed architecture. The phased approach allows for gradual migration while maintaining backward compatibility and operational stability.

The Configuration Service demonstrates the core principles and patterns that will be applied to future service extractions, providing a blueprint for the complete architectural transformation.