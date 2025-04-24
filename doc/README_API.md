# SpiderFoot API Documentation

SpiderFoot provides a REST API that allows you to integrate and automate SpiderFoot scanning capabilities with your existing tools and workflows.

## API Implementations

SpiderFoot now supports two API backend implementations:

1. **CherryPy (Legacy)**: The original API implementation
2. **FastAPI (Recommended)**: A modern, high-performance API implementation

Both implementations provide the same functionality with slight differences in response formats and additional features in the FastAPI version.

## Starting the API Server

### Using the Controller (Recommended)

The API controller allows you to select which API implementation to use:

```bash
python sfapi_controller.py [options]
```

Options:
- `-s`, `--server`: API server type to use (`cherrypy` or `fastapi`)
- `-c`, `--config`: Path to configuration file
- `-d`, `--debug`: Enable debugging
- `-l`, `--listen`: IP address to listen on
- `-p`, `--port`: Port to listen on

Examples:

```bash
# Start FastAPI server on port 5001
python sfapi_controller.py -s fastapi -p 5001

# Start CherryPy server on port 5001
python sfapi_controller.py -s cherrypy -p 5001
```

### Using the Traditional Method

For backwards compatibility, you can still start the CherryPy API server using the original method:

```bash
python sf.py -l 127.0.0.1:5001
```

## API Documentation

### FastAPI Documentation

The FastAPI implementation provides built-in, interactive API documentation:

- **Swagger UI**: `/swaggerui`
- **ReDoc**: `/redoc`

These interfaces allow you to:
- Explore all available endpoints
- Test endpoints directly in your browser
- View request and response schemas
- See detailed parameter descriptions

### General API Usage

#### Authentication

Both API implementations use the same authentication mechanism. Set up authentication in your SpiderFoot configuration file.

#### Common Endpoints

Both implementations provide these core endpoints (paths shown are relative):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ping` | GET | Test connectivity to the API server |
| `/scanlist` | GET | Get list of all scans |
| `/scanstatus/{scan_id}` | GET | Get status of a specific scan |
| `/scaneventresults/{scan_id}` | GET | Get events from a scan |
| `/startscan` | POST | Start a new scan |
| `/stopscan` | POST | Stop a running scan |
| `/scanopts/{scan_id}` | GET | Get scan options |
| `/scandelete` | POST | Delete a scan |
| `/modules` | GET | List all modules |
| `/eventtypes` | GET | List all event types |

For a complete list of endpoints and detailed usage, refer to the Swagger UI documentation when using FastAPI.

## Migration

If you're currently using the CherryPy API and want to migrate to FastAPI, please refer to the [API Migration Guide](API_MIGRATION_GUIDE.md).

## Example Usage

Here's a Python example that works with both API implementations:

```python
import requests
import json

BASE_URL = "http://localhost:5001"

# Test connectivity
response = requests.get(f"{BASE_URL}/ping")
print(f"API Status: {response.text}")

# Start a scan
scan_data = {
    "scanname": "Test Scan",
    "scantarget": "example.com",
    "usecase": "passive"
}
response = requests.post(f"{BASE_URL}/startscan", json=scan_data)
scan_id = response.json().get("scan_id")

# Check scan status
response = requests.get(f"{BASE_URL}/scanstatus/{scan_id}")
print(f"Scan Status: {response.text}")
```

## Additional Resources

- [API Migration Guide](API_MIGRATION_GUIDE.md) - Guide for migrating from CherryPy to FastAPI
- [SpiderFoot Documentation](https://www.spiderfoot.net/documentation/) - General SpiderFoot documentation
