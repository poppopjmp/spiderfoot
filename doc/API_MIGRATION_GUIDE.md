# SpiderFoot API Migration Guide: CherryPy to FastAPI

This guide walks you through the process of migrating from the CherryPy API to the FastAPI implementation.

## Overview

SpiderFoot now supports two API backends:
1. The original CherryPy-based API (legacy)
2. A new FastAPI-based implementation (recommended)

The FastAPI implementation offers several advantages:
- Better performance
- Automatic request/response validation
- Interactive API documentation (via Swagger UI)
- Better error handling
- Asynchronous request processing
- Modern Python typing support

## Migration Steps

### 1. Update your dependencies

Add the required FastAPI dependencies:

```bash
pip install fastapi uvicorn
```

### 2. Update your startup command

**CherryPy (old):**
```bash
python sf.py -l 0.0.0.0:5001
```

**FastAPI (new):**
```bash
python sfapi_controller.py -s fastapi -l 0.0.0.0 -p 5001
```

### 3. Update your API client code

#### Response format changes

Some endpoints have slight differences in response formats:

##### Example: `/ping` endpoint

CherryPy returns:
```json
["SUCCESS", "4.0.0"]
```

FastAPI returns:
```json
{
  "status": "SUCCESS",
  "version": "4.0.0"
}
```

You'll need to adapt your client code to handle these differences.

#### Error handling

FastAPI returns consistent error responses with HTTP status codes:

```json
{
  "error": {
    "http_status": 404,
    "message": "Scan ID not found"
  }
}
```

### 4. Configuration changes

When using the controller, add the following to your spiderfoot.cfg:

