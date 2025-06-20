# REST API Reference

SpiderFoot provides a comprehensive REST API for automation, integration, and programmatic access to all functionality. This reference covers all available endpoints and usage examples.

## API Overview

### Base URL
```
http://localhost:5001/api
```

### Authentication
```bash
# If authentication is enabled
curl -H "Authorization: Bearer your-api-token" http://localhost:5001/api/scans
```

### Response Format
All API responses use JSON format:
```json
{
  "status": "success|error",
  "data": {...},
  "message": "Optional message",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Traditional Scanning API

### Start New Scan
```http
POST /api/scans
Content-Type: application/json

{
  "scanName": "Example Scan",
  "scanTarget": "example.com",
  "targetType": "DOMAIN_NAME",
  "moduleList": ["sfp_dnsresolve", "sfp_ssl", "sfp_whois"],
  "scanOptions": {
    "_maxthreads": 3,
    "_timeout": 300
  }
}
```

### Get Scan Status
```http
GET /api/scans/{scanId}/status
```

### Get Scan Results
```http
GET /api/scans/{scanId}/data?format=json
```

### Stop Scan
```http
POST /api/scans/{scanId}/stop
```

### Delete Scan
```http
DELETE /api/scans/{scanId}
```

## Workspace API

### Create Workspace
```http
POST /api/workspaces
Content-Type: application/json

{
  "name": "Security Assessment 2024",
  "description": "Q1 security assessment targets",
  "metadata": {
    "client": "Example Corp",
    "assessment_type": "external"
  }
}
```

### List Workspaces
```http
GET /api/workspaces
```

### Get Workspace Details
```http
GET /api/workspaces/{workspaceId}
```

### Update Workspace
```http
PUT /api/workspaces/{workspaceId}
Content-Type: application/json

{
  "name": "Updated Assessment Name",
  "description": "Updated description"
}
```

### Delete Workspace
```http
DELETE /api/workspaces/{workspaceId}
```

## Target Management API

### Add Target to Workspace
```http
POST /api/workspaces/{workspaceId}/targets
Content-Type: application/json

{
  "target": "example.com",
  "target_type": "DOMAIN_NAME",
  "metadata": {
    "priority": "high",
    "environment": "production",
    "owner": "security-team"
  }
}
```

### List Targets
```http
GET /api/workspaces/{workspaceId}/targets
```

### Update Target
```http
PUT /api/workspaces/{workspaceId}/targets/{targetId}
Content-Type: application/json

{
  "metadata": {
    "priority": "medium",
    "notes": "Updated target information"
  }
}
```

### Remove Target
```http
DELETE /api/workspaces/{workspaceId}/targets/{targetId}
```

## Multi-Target Scanning API

### Start Multi-Target Scan
```http
POST /api/workspaces/{workspaceId}/multi-scan
Content-Type: application/json

{
  "targets": [
    {"value": "example.com", "type": "DOMAIN_NAME"},
    {"value": "192.168.1.1", "type": "IP_ADDRESS"}
  ],
  "modules": ["sfp_dnsresolve", "sfp_ssl", "sfp_portscan_tcp"],
  "scan_options": {
    "_maxthreads": 3,
    "_timeout": 300
  },
  "wait_for_completion": false
}
```

### Get Multi-Scan Status
```http
GET /api/workspaces/{workspaceId}/multi-scan/{scanId}/status
```

### Stop Multi-Target Scan
```http
POST /api/workspaces/{workspaceId}/multi-scan/{scanId}/stop
```

## Correlation API

### Run Correlation Analysis
```http
POST /api/workspaces/{workspaceId}/correlations
Content-Type: application/json

{
  "correlation_rules": [
    "cross_scan_shared_infrastructure",
    "cross_scan_threat_indicators"
  ],
  "confidence_threshold": 75
}
```

### Get Correlation Results
```http
GET /api/workspaces/{workspaceId}/correlations
```

### Get Specific Correlation
```http
GET /api/workspaces/{workspaceId}/correlations/{correlationId}
```

## CTI Reports API

### Generate CTI Report
```http
POST /api/workspaces/{workspaceId}/cti-reports
Content-Type: application/json

{
  "report_type": "threat_assessment",
  "custom_prompt": "Focus on critical vulnerabilities and threat actor attribution",
  "format": "json",
  "include_graphs": true
}
```

### List CTI Reports
```http
GET /api/workspaces/{workspaceId}/cti-reports
```

### Get CTI Report
```http
GET /api/workspaces/{workspaceId}/cti-reports/{reportId}
```

### Export CTI Report
```http
POST /api/workspaces/{workspaceId}/cti-reports/{reportId}/export
Content-Type: application/json

{
  "format": "html",
  "output_path": "/path/to/export/report.html"
}
```

## Data Export API

### Export Workspace Data
```http
POST /api/workspaces/{workspaceId}/export
Content-Type: application/json

{
  "format": "json",
  "include_scans": true,
  "include_correlations": true,
  "event_types": ["IP_ADDRESS", "DOMAIN_NAME", "VULNERABILITY"],
  "risk_levels": ["HIGH", "MEDIUM"]
}
```

### Export Scan Data
```http
GET /api/scans/{scanId}/export?format=csv&events=IP_ADDRESS,DOMAIN_NAME
```

## Search API

### Search Events
```http
POST /api/search/events
Content-Type: application/json

{
  "query": "example.com",
  "event_types": ["DOMAIN_NAME", "IP_ADDRESS"],
  "risk_levels": ["HIGH", "MEDIUM"],
  "date_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-12-31T23:59:59Z"
  },
  "limit": 100,
  "offset": 0
}
```

### Search Across Workspaces
```http
POST /api/search/workspaces
Content-Type: application/json

{
  "query": "malicious",
  "workspace_ids": ["ws_123", "ws_456"],
  "correlation_only": false
}
```

## System API

### Get System Status
```http
GET /api/system/status
```

### Get Module List
```http
GET /api/modules
```

### Get Module Information
```http
GET /api/modules/{moduleName}
```

### Test Module Configuration
```http
POST /api/modules/{moduleName}/test
Content-Type: application/json

{
  "target": "example.com",
  "target_type": "DOMAIN_NAME",
  "options": {
    "timeout": 30
  }
}
```

### Get Configuration
```http
GET /api/config
```

### Update Configuration
```http
PUT /api/config
Content-Type: application/json

{
  "section": "modules",
  "key": "sfp_virustotal.api_key",
  "value": "new_api_key"
}
```

## Error Handling

### HTTP Status Codes
- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Error Response Format
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_TARGET",
    "message": "Invalid target format provided",
    "details": {
      "target": "invalid-target",
      "expected_format": "Valid domain name, IP address, or email"
    }
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Rate Limiting

### Default Limits
- **Authenticated requests**: 1000 requests per hour
- **Unauthenticated requests**: 100 requests per hour
- **Scan creation**: 10 new scans per hour
- **Export operations**: 5 exports per hour

### Rate Limit Headers
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

## Authentication

### API Key Authentication
```bash
# Set API key in header
curl -H "Authorization: Bearer your-api-key" \
     http://localhost:5001/api/workspaces
```

### Session Authentication
```bash
# Login to get session
curl -X POST http://localhost:5001/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "password"}'

# Use session cookie
curl -b cookies.txt http://localhost:5001/api/workspaces
```

## SDKs and Libraries

### Python SDK Example
```python
import requests

class SpiderFootAPI:
    def __init__(self, base_url="http://localhost:5001", api_key=None):
        self.base_url = base_url
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def create_workspace(self, name, description=""):
        data = {"name": name, "description": description}
        response = requests.post(
            f"{self.base_url}/api/workspaces",
            json=data,
            headers=self.headers
        )
        return response.json()
    
    def start_multi_scan(self, workspace_id, targets, modules):
        data = {
            "targets": targets,
            "modules": modules
        }
        response = requests.post(
            f"{self.base_url}/api/workspaces/{workspace_id}/multi-scan",
            json=data,
            headers=self.headers
        )
        return response.json()

# Usage
api = SpiderFootAPI(api_key="your-api-key")
workspace = api.create_workspace("API Test")
```

### JavaScript SDK Example
```javascript
class SpiderFootAPI {
    constructor(baseUrl = 'http://localhost:5001', apiKey = null) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Content-Type': 'application/json'
        };
        if (apiKey) {
            this.headers['Authorization'] = `Bearer ${apiKey}`;
        }
    }

    async createWorkspace(name, description = '') {
        const response = await fetch(`${this.baseUrl}/api/workspaces`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ name, description })
        });
        return response.json();
    }

    async startMultiScan(workspaceId, targets, modules) {
        const response = await fetch(`${this.baseUrl}/api/workspaces/${workspaceId}/multi-scan`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ targets, modules })
        });
        return response.json();
    }
}

// Usage
const api = new SpiderFootAPI('http://localhost:5001', 'your-api-key');
const workspace = await api.createWorkspace('API Test');
```

## Webhooks

### Configure Webhooks
```http
POST /api/webhooks
Content-Type: application/json

{
  "url": "https://your-server.com/webhook",
  "events": ["scan_completed", "correlation_found", "high_risk_event"],
  "secret": "webhook-secret",
  "active": true
}
```

### Webhook Payload
```json
{
  "event": "scan_completed",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {
    "scan_id": "scan_123",
    "workspace_id": "ws_456",
    "status": "FINISHED",
    "events_found": 1234,
    "high_risk_events": 5
  },
  "signature": "sha256=..."
}
```

## Best Practices

### Performance
1. **Use pagination** for large result sets
2. **Cache responses** when appropriate
3. **Batch operations** when possible
4. **Monitor rate limits** to avoid throttling
5. **Use webhooks** for real-time updates

### Security
1. **Use HTTPS** in production
2. **Protect API keys** from exposure
3. **Validate all input** data
4. **Implement proper authentication**
5. **Log API access** for auditing

### Error Handling
1. **Check HTTP status codes**
2. **Parse error responses** properly
3. **Implement retry logic** for transient failures
4. **Handle rate limiting** gracefully
5. **Log errors** for debugging

For more examples and detailed implementation guides, see the [Python API Documentation](python_api.md) or [Webhook Integration Guide](webhook_integration.md).
