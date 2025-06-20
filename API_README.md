# SpiderFoot API Setup and Usage Guide

This guide covers the setup and usage of the new SpiderFoot FastAPI-based REST API with complete workspace and scan management capabilities.

## Features

The SpiderFoot API provides complete feature parity with the web UI and CLI, including:

### Core Features
- **Full workspace management** (create, list, show, delete, clone, merge)
- **Target management** (add, remove, list targets in workspaces)  
- **Scan management** (create, start, stop, delete, export scans)
- **Multi-target scanning** with workflow support
- **Real-time updates** via WebSocket connections
- **Data export** in JSON, CSV, and XML formats
- **Configuration management** 
- **Module and event type introspection**

### API Endpoints

#### Health & Configuration
- `GET /api/health` - Health check
- `GET /api/config` - Get configuration  
- `GET /api/modules` - List available modules
- `GET /api/event-types` - List event types

#### Scan Management
- `GET /api/scans` - List all scans
- `POST /api/scans` - Create and start new scan
- `GET /api/scans/{scan_id}` - Get scan details
- `DELETE /api/scans/{scan_id}` - Delete scan
- `POST /api/scans/{scan_id}/stop` - Stop running scan
- `GET /api/scans/{scan_id}/events` - Get scan events/results
- `GET /api/scans/{scan_id}/export` - Export scan results

#### Workspace Management  
- `GET /api/workspaces` - List workspaces
- `POST /api/workspaces` - Create workspace
- `GET /api/workspaces/{workspace_id}` - Get workspace details
- `DELETE /api/workspaces/{workspace_id}` - Delete workspace
- `POST /api/workspaces/{workspace_id}/targets` - Add target to workspace
- `GET /api/workspaces/{workspace_id}/targets` - List workspace targets
- `DELETE /api/workspaces/{workspace_id}/targets/{target_id}` - Remove target
- `POST /api/workspaces/{workspace_id}/multi-scan` - Start multi-target scan

#### WebSocket Endpoints
- `WS /ws/scans/{scan_id}` - Real-time scan updates

## Setup

### Option 1: Virtual Environment Setup (Recommended)

1. **Automatic Setup**:
   ```bash
   python setup_venv.py
   ```

2. **Manual Setup**:
   ```bash
   # Create virtual environment
   python -m venv .venv
   
   # Activate virtual environment
   # Windows:
   .venv\Scripts\activate
   # Linux/Mac:
   source .venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Activate Environment**:
   ```bash
   # Windows:
   activate_venv.bat
   # Linux/Mac: 
   source activate_venv.sh
   ```

### Option 2: Docker Setup

1. **Build the image**:
   ```bash
   docker build -t spiderfoot:latest .
   ```

2. **Run API service**:
   ```bash
   # API only
   docker run -p 8001:8001 spiderfoot:latest python sfapi.py --host 0.0.0.0 --port 8001
   
   # Web UI only  
   docker run -p 5001:5001 spiderfoot:latest python sf.py -l 0.0.0.0:5001
   ```

3. **Using Docker Compose**:
   ```bash
   # Both services
   docker-compose -f docker-compose-new.yml up
   
   # API only
   docker-compose -f docker-compose-new.yml up spiderfoot-api
   
   # With nginx proxy
   docker-compose -f docker-compose-new.yml --profile proxy up
   ```

## Running the API

### Development Mode
```bash
# With virtual environment activated
python sfapi.py --host 0.0.0.0 --port 8001 --reload

# Or using uvicorn directly
uvicorn sfapi:app --host 0.0.0.0 --port 8001 --reload
```

### Production Mode
```bash
# Standard mode
python sfapi.py --host 0.0.0.0 --port 8001

# With custom config
python sfapi.py --host 0.0.0.0 --port 8001 --config /path/to/config.json
```

## API Usage Examples

### Authentication
If API keys are enabled, include the Authorization header:
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8001/api/scans
```

### Basic Operations

#### Create a Workspace
```bash
curl -X POST http://localhost:8001/api/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Security Assessment",
    "description": "Comprehensive security scan workspace"
  }'
```

#### Add Target to Workspace
```bash
curl -X POST http://localhost:8001/api/workspaces/{workspace_id}/targets \
  -H "Content-Type: application/json" \
  -d '{
    "target": "example.com",
    "target_type": "INTERNET_NAME"
  }'
```

#### Start a Scan
```bash
curl -X POST http://localhost:8001/api/scans \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example.com Security Scan",
    "target": "example.com",
    "modules": ["sfp_dnsresolve", "sfp_whois", "sfp_subdomain_enum"]
  }'
```

#### Multi-Target Scan
```bash
curl -X POST http://localhost:8001/api/workspaces/{workspace_id}/multi-scan \
  -H "Content-Type: application/json" \
  -d '{
    "modules": ["sfp_dnsresolve", "sfp_whois", "sfp_subdomain_enum"],
    "scan_options": {"max_threads": 10}
  }'
```

#### Get Scan Results
```bash
# Get scan events
curl http://localhost:8001/api/scans/{scan_id}/events?limit=100

# Export scan results
curl http://localhost:8001/api/scans/{scan_id}/export?format=csv > results.csv
```

### WebSocket Connection (JavaScript)
```javascript
const ws = new WebSocket('ws://localhost:8001/ws/scans/{scan_id}');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Scan update:', data);
    
    if (data.type === 'status_update') {
        console.log('Status:', data.status, 'Events:', data.event_count);
    } else if (data.type === 'new_events') {
        console.log('New events:', data.events);
    }
};
```

## API Documentation

The API provides interactive documentation:
- **Swagger UI**: http://localhost:8001/api/docs
- **ReDoc**: http://localhost:8001/api/redoc
- **OpenAPI Schema**: http://localhost:8001/api/openapi.json

## Configuration

### Environment Variables
- `SPIDERFOOT_DATA` - Data directory path
- `SPIDERFOOT_LOGS` - Logs directory path  
- `SPIDERFOOT_CACHE` - Cache directory path

### API Configuration
- API keys can be configured in the SpiderFoot configuration
- CORS settings can be modified in the FastAPI app configuration
- Rate limiting and security headers are configurable in the nginx proxy

## Deployment Considerations

### Production Setup
1. **Use a reverse proxy** (nginx, Apache) for SSL termination and load balancing
2. **Configure proper authentication** with API keys or OAuth
3. **Set up monitoring** for API health and performance
4. **Configure rate limiting** to prevent abuse
5. **Use environment-specific configurations**

### Security
- Enable API key authentication for production use
- Use HTTPS in production environments
- Configure CORS appropriately for your frontend domains
- Implement proper logging and monitoring
- Regular security updates for dependencies

### Performance
- Use gunicorn or similar WSGI server for production
- Configure appropriate worker counts based on server resources
- Monitor memory usage for large scans
- Consider using Redis for session management and caching

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated and all dependencies are installed
2. **Database Errors**: Check database permissions and path configuration
3. **Module Loading**: Verify SpiderFoot modules are properly installed
4. **Port Conflicts**: Ensure ports 8001 (API) and 5001 (Web UI) are available

### Logs
- API logs are available in the configured log directory
- Use `--reload` flag for development debugging
- Check Docker logs: `docker logs spiderfoot-api`

### Support
- Check the main SpiderFoot documentation
- Review API documentation at `/api/docs`
- File issues on the SpiderFoot GitHub repository
