# API Development Guide

This guide covers extending SpiderFoot's REST API and developing integrations with external systems.

## API Architecture

### Flask Framework

SpiderFoot's web interface and API are built using Flask:

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/custom-endpoint', methods=['GET', 'POST'])
def custom_endpoint():
    if request.method == 'GET':
        return jsonify({'status': 'success', 'data': {}})
    
    elif request.method == 'POST':
        data = request.get_json()
        # Process data
        return jsonify({'status': 'success', 'result': result})
```

### Authentication

```python
from functools import wraps

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not validate_token(auth_header):
            return jsonify({'error': 'Authentication required'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/protected-endpoint')
@require_auth
def protected_endpoint():
    return jsonify({'data': 'protected'})
```

## Extending the API

### Adding New Endpoints

Create new API endpoints in the main Flask application:

```python
# In sf.py or separate API module
@app.route('/api/custom/scan-status/<scan_id>')
def get_custom_scan_status(scan_id):
    """Get enhanced scan status information."""
    try:
        # Get scan details
        scan_info = sf.getScanMeta(scan_id)
        
        if not scan_info:
            return jsonify({'error': 'Scan not found'}), 404
        
        # Add custom processing
        enhanced_status = {
            'scan_id': scan_id,
            'status': scan_info[5],
            'target': scan_info[1],
            'started': scan_info[3],
            'ended': scan_info[4],
            'events_count': get_events_count(scan_id),
            'high_risk_events': get_high_risk_count(scan_id)
        }
        
        return jsonify(enhanced_status)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_events_count(scan_id):
    """Count total events for scan."""
    return len(sf.scanEventsByType(None, scan_id))

def get_high_risk_count(scan_id):
    """Count high-risk events for scan."""
    high_risk_events = []
    for event in sf.scanEventsByType(None, scan_id):
        if event[4] == 'HIGH':  # Risk level
            high_risk_events.append(event)
    return len(high_risk_events)
```

### Workspace API Extensions

```python
@app.route('/api/workspaces/<workspace_id>/analytics')
def workspace_analytics(workspace_id):
    """Get workspace analytics and statistics."""
    try:
        workspace = load_workspace(workspace_id)
        
        analytics = {
            'targets_count': len(workspace.get_targets()),
            'scans_count': len(workspace.get_scans()),
            'total_events': get_workspace_events_count(workspace_id),
            'risk_distribution': get_risk_distribution(workspace_id),
            'module_usage': get_module_usage(workspace_id),
            'scan_duration_avg': get_avg_scan_duration(workspace_id)
        }
        
        return jsonify(analytics)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_risk_distribution(workspace_id):
    """Get distribution of risk levels."""
    risk_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'INFO': 0}
    
    # Process all scans in workspace
    for scan_id in get_workspace_scans(workspace_id):
        for event in sf.scanEventsByType(None, scan_id):
            risk_level = event[4]
            if risk_level in risk_counts:
                risk_counts[risk_level] += 1
    
    return risk_counts
```

## Custom Integrations

### SIEM Integration

```python
class SIEMIntegration:
    def __init__(self, siem_config):
        self.endpoint = siem_config['endpoint']
        self.api_key = siem_config['api_key']
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def send_events(self, events):
        """Send events to SIEM system."""
        siem_events = []
        
        for event in events:
            siem_event = {
                'timestamp': event['timestamp'],
                'source': 'SpiderFoot',
                'event_type': event['type'],
                'data': event['data'],
                'risk_level': event['risk'],
                'scan_id': event['scan_id']
            }
            siem_events.append(siem_event)
        
        response = requests.post(
            f"{self.endpoint}/events",
            json={'events': siem_events},
            headers=self.headers
        )
        
        return response.status_code == 200

# API endpoint for SIEM integration
@app.route('/api/siem/export/<scan_id>')
def export_to_siem(scan_id):
    """Export scan results to SIEM."""
    try:
        events = sf.scanEventsByType(None, scan_id)
        
        # Convert to SIEM format
        formatted_events = []
        for event in events:
            formatted_events.append({
                'timestamp': event[2],
                'type': event[1],
                'data': event[0],
                'risk': event[4],
                'scan_id': scan_id
            })
        
        # Send to SIEM
        siem = SIEMIntegration(app.config['SIEM_CONFIG'])
        success = siem.send_events(formatted_events)
        
        if success:
            return jsonify({'status': 'exported', 'count': len(formatted_events)})
        else:
            return jsonify({'error': 'SIEM export failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Ticketing System Integration

```python
class TicketingIntegration:
    def __init__(self, ticket_config):
        self.api_url = ticket_config['api_url']
        self.username = ticket_config['username']
        self.password = ticket_config['password']
    
    def create_ticket(self, title, description, priority='medium'):
        """Create ticket for high-risk findings."""
        ticket_data = {
            'title': title,
            'description': description,
            'priority': priority,
            'tags': ['spiderfoot', 'security', 'automated']
        }
        
        response = requests.post(
            f"{self.api_url}/tickets",
            json=ticket_data,
            auth=(self.username, self.password)
        )
        
        if response.status_code == 201:
            return response.json()['ticket_id']
        return None

@app.route('/api/tickets/create-from-scan/<scan_id>')
def create_tickets_from_scan(scan_id):
    """Create tickets for high-risk findings."""
    try:
        high_risk_events = []
        
        for event in sf.scanEventsByType(None, scan_id):
            if event[4] == 'HIGH':  # High risk
                high_risk_events.append(event)
        
        ticketing = TicketingIntegration(app.config['TICKETING_CONFIG'])
        created_tickets = []
        
        for event in high_risk_events:
            title = f"High Risk Finding: {event[1]}"
            description = f"SpiderFoot discovered: {event[0]}\nType: {event[1]}\nScan: {scan_id}"
            
            ticket_id = ticketing.create_ticket(title, description, 'high')
            if ticket_id:
                created_tickets.append(ticket_id)
        
        return jsonify({
            'status': 'success',
            'tickets_created': len(created_tickets),
            'ticket_ids': created_tickets
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

## Real-time APIs

### WebSocket Support

```python
from flask_socketio import SocketIO, emit

socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {'msg': 'Connected to SpiderFoot'})

@socketio.on('subscribe_scan')
def handle_scan_subscription(data):
    scan_id = data['scan_id']
    join_room(scan_id)
    emit('subscribed', {'scan_id': scan_id})

def broadcast_scan_progress(scan_id, progress):
    """Broadcast scan progress to subscribers."""
    socketio.emit('scan_progress', {
        'scan_id': scan_id,
        'progress': progress
    }, room=scan_id)

def broadcast_scan_event(scan_id, event):
    """Broadcast new scan events."""
    socketio.emit('scan_event', {
        'scan_id': scan_id,
        'event': event
    }, room=scan_id)
```

### Server-Sent Events (SSE)

```python
from flask import Response
import json
import time

@app.route('/api/stream/scan/<scan_id>')
def stream_scan_events(scan_id):
    """Stream scan events using Server-Sent Events."""
    
    def event_stream():
        last_event_id = 0
        
        while True:
            # Get new events since last check
            new_events = get_scan_events_since(scan_id, last_event_id)
            
            for event in new_events:
                data = {
                    'id': event['id'],
                    'type': event['type'],
                    'data': event['data'],
                    'timestamp': event['timestamp']
                }
                
                yield f"data: {json.dumps(data)}\n\n"
                last_event_id = event['id']
            
            # Check scan status
            scan_status = sf.getScanMeta(scan_id)[5]
            if scan_status in ['FINISHED', 'ABORTED', 'ERROR-FAILED']:
                yield f"data: {json.dumps({'type': 'scan_complete', 'status': scan_status})}\n\n"
                break
            
            time.sleep(1)  # Poll every second
    
    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )

def get_scan_events_since(scan_id, last_id):
    """Get scan events since last ID."""
    # Implementation depends on your event storage
    pass
```

## API Documentation

### Swagger/OpenAPI Integration

```python
from flask_restx import Api, Resource, fields

api = Api(app, doc='/api/docs/')

# Define models
scan_model = api.model('Scan', {
    'scan_id': fields.String(required=True, description='Scan identifier'),
    'target': fields.String(required=True, description='Scan target'),
    'status': fields.String(required=True, description='Scan status'),
    'started': fields.DateTime(description='Start time'),
    'ended': fields.DateTime(description='End time')
})

event_model = api.model('Event', {
    'event_id': fields.String(required=True),
    'event_type': fields.String(required=True),
    'event_data': fields.String(required=True),
    'risk_level': fields.String(required=True)
})

@api.route('/scans')
class ScanList(Resource):
    @api.marshal_list_with(scan_model)
    def get(self):
        """Get list of all scans."""
        return get_all_scans()
    
    @api.expect(scan_model)
    @api.marshal_with(scan_model)
    def post(self):
        """Create new scan."""
        data = api.payload
        return create_scan(data)

@api.route('/scans/<string:scan_id>/events')
class ScanEvents(Resource):
    @api.marshal_list_with(event_model)
    def get(self, scan_id):
        """Get events for specific scan."""
        return get_scan_events(scan_id)
```

## Testing APIs

### Unit Tests

```python
import unittest
from unittest.mock import patch, MagicMock

class TestCustomAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
    
    def test_scan_status_endpoint(self):
        """Test custom scan status endpoint."""
        with patch('sf.getScanMeta') as mock_scan:
            mock_scan.return_value = ['id', 'target', 'type', 'start', 'end', 'RUNNING']
            
            response = self.app.get('/api/custom/scan-status/test_scan')
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data['status'], 'RUNNING')
    
    def test_workspace_analytics(self):
        """Test workspace analytics endpoint."""
        response = self.app.get('/api/workspaces/test_workspace/analytics')
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('targets_count', data)
        self.assertIn('risk_distribution', data)

if __name__ == '__main__':
    unittest.main()
```

### Integration Tests

```python
import requests
import json

class APIIntegrationTest:
    def __init__(self, base_url='http://localhost:5001'):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_full_workflow(self):
        """Test complete API workflow."""
        
        # 1. Create workspace
        workspace_data = {
            'name': 'API Test Workspace',
            'description': 'Test workspace for API integration'
        }
        
        response = self.session.post(
            f"{self.base_url}/api/workspaces",
            json=workspace_data
        )
        
        assert response.status_code == 201
        workspace_id = response.json()['workspace_id']
        
        # 2. Add target
        target_data = {
            'target': 'example.com',
            'target_type': 'DOMAIN_NAME'
        }
        
        response = self.session.post(
            f"{self.base_url}/api/workspaces/{workspace_id}/targets",
            json=target_data
        )
        
        assert response.status_code == 201
        
        # 3. Start scan
        scan_data = {
            'modules': ['sfp_dnsresolve', 'sfp_ssl']
        }
        
        response = self.session.post(
            f"{self.base_url}/api/workspaces/{workspace_id}/multi-scan",
            json=scan_data
        )
        
        assert response.status_code == 202
        scan_id = response.json()['scan_id']
        
        # 4. Monitor progress
        while True:
            response = self.session.get(
                f"{self.base_url}/api/scans/{scan_id}/status"
            )
            
            status = response.json()['status']
            if status in ['FINISHED', 'ABORTED', 'ERROR-FAILED']:
                break
            
            time.sleep(5)
        
        # 5. Get results
        response = self.session.get(
            f"{self.base_url}/api/scans/{scan_id}/data"
        )
        
        assert response.status_code == 200
        events = response.json()['events']
        assert len(events) > 0

if __name__ == '__main__':
    test = APIIntegrationTest()
    test.test_full_workflow()
    print("Integration test completed successfully")
```

## Deployment Considerations

### Production Setup

```python
# Production configuration
app.config.update(
    SECRET_KEY='your-secret-key',
    API_RATE_LIMIT='1000 per hour',
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max
    CORS_ORIGINS=['https://yourdomain.com']
)

# Rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"]
)

@app.route('/api/heavy-operation')
@limiter.limit("10 per minute")
def heavy_operation():
    pass
```

### Security Headers

```python
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response
```

## Best Practices

### API Design

1. **RESTful conventions**: Use standard HTTP methods
2. **Consistent responses**: Standardize response formats
3. **Proper status codes**: Use appropriate HTTP status codes
4. **Versioning**: Plan for API versioning
5. **Documentation**: Maintain comprehensive API docs

### Performance

1. **Caching**: Implement response caching where appropriate
2. **Pagination**: Use pagination for large result sets
3. **Compression**: Enable gzip compression
4. **Async operations**: Use async for long-running tasks
5. **Database optimization**: Optimize database queries

### Security

1. **Authentication**: Require authentication for sensitive endpoints
2. **Input validation**: Validate all input data
3. **Rate limiting**: Prevent API abuse
4. **HTTPS only**: Use HTTPS in production
5. **Security headers**: Implement security headers

For more information on SpiderFoot's core API, see the [REST API Documentation](../api/rest_api.md).
