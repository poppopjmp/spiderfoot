# SpiderFoot Microservices

This directory contains the microservice implementation of SpiderFoot, providing a modern, scalable architecture that addresses the limitations of the monolithic design.

## Quick Start

### Option 1: Startup Script (Recommended)
```bash
# Start all microservices
./services/start_microservices.sh
```

### Option 2: Manual Start
```bash
# Terminal 1: Service Discovery
python services/service_discovery.py

# Terminal 2: Configuration Service
python services/config_service.py --migrate

# Terminal 3: API Gateway
python services/api_gateway.py
```

### Option 3: Docker Compose
```bash
docker-compose -f docker-compose.microservices.yml up -d
```

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   API Gateway   │    │  Service Discovery  │    │ Configuration Service│
│   Port: 8080    │◄──►│    Port: 8000       │◄──►│    Port: 8001       │
└─────────────────┘    └─────────────────────┘    └─────────────────────┘
         │                        │                         │
         │                        │                         │
         ▼                        ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     SpiderFoot Legacy Components                       │
│                     (with microservice integration)                    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Services

### 1. Service Discovery (Port 8000)
- **Purpose**: Service registry and health monitoring
- **Database**: SQLite (`data/services/service_discovery.db`)
- **Key Endpoints**:
  - `GET /health` - Health check
  - `GET /services` - List registered services
  - `POST /register` - Register new service

### 2. Configuration Service (Port 8001)
- **Purpose**: Centralized configuration management
- **Database**: SQLite (`data/services/config_service.db`)
- **Key Endpoints**:
  - `GET /config` - Get all configurations
  - `GET /config/{key}` - Get specific configuration
  - `POST /config/{key}` - Set configuration
  - `GET /config/{key}/history` - Configuration history

### 3. API Gateway (Port 8080)
- **Purpose**: Request routing and load balancing
- **Key Endpoints**:
  - `GET /health` - Gateway and service health
  - `/api/config/*` - Route to Configuration Service
  - `/api/discovery/*` - Route to Service Discovery

## Testing

### Health Checks
```bash
# Gateway health (includes all services)
curl http://localhost:8080/health

# Individual service health
curl http://localhost:8000/health  # Service Discovery
curl http://localhost:8001/health  # Configuration Service
```

### Configuration Management
```bash
# Get all configurations
curl http://localhost:8080/api/config

# Set a configuration
curl -X POST http://localhost:8080/api/config/my_setting \
  -H "Content-Type: application/json" \
  -d '{"key": "my_setting", "value": "my_value", "scope": "global"}'

# Get specific configuration
curl http://localhost:8080/api/config/my_setting
```

### Service Discovery
```bash
# List all registered services
curl http://localhost:8080/api/discovery/services

# Register a new service (usually done automatically)
curl -X POST http://localhost:8080/api/discovery/register \
  -H "Content-Type: application/json" \
  -d '{"service_name": "my-service", "host": "localhost", "port": 9000}'
```

### Comprehensive Test
```bash
python services/test_microservices.py
```

## Integration with Existing SpiderFoot

### Automatic Integration
Set environment variables:
```bash
export USE_MICROSERVICES=true
export SERVICE_DISCOVERY_URL=http://localhost:8000
```

Then use existing SpiderFoot code - configuration will automatically use microservices:
```python
from sflib import SpiderFoot

sf = SpiderFoot({'_debug': False})
# Configuration methods now use microservices with fallback
sf.configSet('new_setting', 'value')
value = sf.configGet('new_setting')
```

### Manual Integration
```python
from services.config_adapter import initialize_config_adapter

# Initialize microservice integration
adapter = initialize_config_adapter(
    use_microservices=True,
    service_discovery_url="http://localhost:8000"
)

# Use existing SpiderFoot code
from sflib import SpiderFoot
sf = SpiderFoot({'_debug': False})
```

## Development

### Adding New Services

1. Create service implementation in `services/`
2. Add service registration logic
3. Update API Gateway routing
4. Add to Docker Compose
5. Update documentation

### Service Template
```python
#!/usr/bin/env python3
from fastapi import FastAPI
import uvicorn

app = FastAPI(title="My Service")

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Production Deployment

### Security Considerations
- Use HTTPS/TLS for all communication
- Implement service-to-service authentication
- Deploy behind reverse proxy
- Network segmentation

### Monitoring
- Enable structured logging
- Implement metrics collection
- Set up alerting for service failures
- Monitor database performance

### Scaling
- Use container orchestration (Kubernetes, Docker Swarm)
- Implement horizontal pod autoscaling
- Use external service discovery (Consul, etcd)
- External configuration management (ConfigMap, Vault)

## Files Overview

```
services/
├── __init__.py                 # Package initialization
├── service_discovery.py        # Service Discovery service
├── config_service.py          # Configuration Service
├── api_gateway.py             # API Gateway
├── client.py                  # Service client library
├── config_adapter.py          # Legacy integration adapter
├── test_microservices.py      # Test suite
├── start_microservices.sh     # Startup script
├── Dockerfile.service-discovery # Service Discovery container
├── Dockerfile.config-service   # Configuration Service container
└── nginx.conf                 # Nginx configuration for gateway
```

## Benefits Achieved

✅ **Independent Development**: Teams can work on separate services  
✅ **Independent Deployment**: Deploy services separately  
✅ **Technology Freedom**: Each service can use optimal technology  
✅ **Granular Scaling**: Scale services based on demand  
✅ **Fault Isolation**: Service failures don't affect entire system  
✅ **Clear Boundaries**: Well-defined service interfaces  
✅ **Backward Compatibility**: Existing code works with microservices  

## Next Steps

This implementation provides the foundation for migrating more SpiderFoot components:

1. **Scan Management Service** - Extract scan lifecycle management
2. **Module Management Service** - Extract module loading and execution  
3. **Reporting Service** - Extract report generation
4. **User Management Service** - Extract authentication and authorization

See [documentation/microservices.md](../documentation/microservices.md) for detailed architecture documentation.