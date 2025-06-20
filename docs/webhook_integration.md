# Webhook Integration Guide

SpiderFoot supports webhooks for real-time notifications of scan events, findings, and system status changes.

## Overview

Webhooks allow external systems to receive immediate notifications when:
- Scans start, complete, or fail
- High-risk events are discovered
- Correlation analysis completes
- CTI reports are generated
- System alerts occur

## Webhook Configuration

### Basic Setup

```ini
[webhooks]
# Enable webhooks
enabled = true

# Default webhook URL
default_url = https://your-server.com/webhook

# Webhook secret for signature verification
secret = your-webhook-secret

# Events to send
events = scan_completed,high_risk_event,correlation_found

# Retry configuration
max_retries = 3
retry_delay = 30
```

### Multiple Webhooks

```python
# Configure multiple webhook endpoints
webhooks = {
    'security_team': {
        'url': 'https://security.company.com/webhook',
        'events': ['high_risk_event', 'scan_completed'],
        'secret': 'security-team-secret'
    },
    'siem_system': {
        'url': 'https://siem.company.com/api/webhook',
        'events': ['all'],
        'secret': 'siem-system-secret'
    },
    'slack_alerts': {
        'url': 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK',
        'events': ['scan_failed', 'high_risk_event'],
        'format': 'slack'
    }
}
```

## Webhook Events

### Available Events

#### Scan Events
- **scan_started**: New scan initiated
- **scan_completed**: Scan finished successfully
- **scan_failed**: Scan encountered an error
- **scan_progress**: Periodic progress updates

#### Finding Events
- **high_risk_event**: High-risk security finding
- **medium_risk_event**: Medium-risk security finding
- **vulnerability_found**: Vulnerability discovered
- **malware_detected**: Malware or threat detected

#### Workflow Events
- **correlation_completed**: Cross-correlation analysis finished
- **cti_report_generated**: CTI report created
- **workspace_created**: New workspace created
- **multi_scan_completed**: Multi-target scan finished

#### System Events
- **system_alert**: System-level alert
- **resource_warning**: Resource usage warning
- **module_error**: Module execution error

### Event Payload Structure

```json
{
  "event_type": "scan_completed",
  "timestamp": "2024-01-01T12:00:00Z",
  "source": "spiderfoot",
  "version": "5.0.3",
  "data": {
    "scan_id": "scan_12345",
    "target": "example.com",
    "target_type": "DOMAIN_NAME",
    "status": "FINISHED",
    "events_found": 1234,
    "high_risk_events": 5,
    "duration": 3600,
    "modules_used": ["sfp_dnsresolve", "sfp_ssl", "sfp_portscan_tcp"]
  },
  "metadata": {
    "workspace_id": "ws_abc123",
    "user": "admin",
    "scan_name": "Weekly Security Scan"
  }
}
```

## Webhook Security

### Signature Verification

SpiderFoot signs webhook payloads using HMAC-SHA256:

```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    """Verify webhook signature."""
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Remove 'sha256=' prefix if present
    if signature.startswith('sha256='):
        signature = signature[7:]
    
    return hmac.compare_digest(expected_signature, signature)

# Usage in webhook handler
def webhook_handler(request):
    payload = request.body
    signature = request.headers.get('X-SpiderFoot-Signature')
    
    if not verify_webhook_signature(payload, signature, webhook_secret):
        return "Invalid signature", 401
    
    # Process webhook
    process_webhook(json.loads(payload))
    return "OK", 200
```

### IP Whitelisting

```python
# Whitelist SpiderFoot server IPs
ALLOWED_IPS = ['192.168.1.100', '10.0.0.50']

def check_ip_whitelist(request):
    client_ip = request.remote_addr
    if client_ip not in ALLOWED_IPS:
        return False
    return True
```

### HTTPS and TLS

```python
# Webhook configuration with TLS verification
webhook_config = {
    'url': 'https://secure-webhook.company.com/endpoint',
    'verify_tls': True,
    'ca_bundle': '/path/to/ca-bundle.pem',
    'client_cert': '/path/to/client.pem',
    'client_key': '/path/to/client.key'
}
```

## Implementation Examples

### Flask Webhook Receiver

```python
from flask import Flask, request, jsonify
import json
import hmac
import hashlib

app = Flask(__name__)
WEBHOOK_SECRET = "your-webhook-secret"

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        # Verify signature
        payload = request.get_data(as_text=True)
        signature = request.headers.get('X-SpiderFoot-Signature', '')
        
        if not verify_signature(payload, signature):
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Parse webhook data
        webhook_data = json.loads(payload)
        
        # Process based on event type
        event_type = webhook_data.get('event_type')
        
        if event_type == 'scan_completed':
            handle_scan_completed(webhook_data)
        elif event_type == 'high_risk_event':
            handle_high_risk_event(webhook_data)
        elif event_type == 'correlation_completed':
            handle_correlation_completed(webhook_data)
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        app.logger.error(f"Webhook processing error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

def verify_signature(payload, signature):
    """Verify HMAC signature."""
    if signature.startswith('sha256='):
        signature = signature[7:]
    
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)

def handle_scan_completed(data):
    """Handle scan completion."""
    scan_data = data['data']
    print(f"Scan {scan_data['scan_id']} completed for {scan_data['target']}")
    
    # Send notification
    if scan_data['high_risk_events'] > 0:
        send_alert(f"High-risk findings in scan: {scan_data['scan_id']}")

def handle_high_risk_event(data):
    """Handle high-risk event."""
    event_data = data['data']
    
    # Create incident ticket
    create_incident_ticket({
        'title': f"High-risk finding: {event_data['event_type']}",
        'description': event_data['data'],
        'source': 'SpiderFoot',
        'priority': 'high'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### Slack Integration

```python
import requests

class SlackWebhookHandler:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
    
    def send_scan_alert(self, webhook_data):
        """Send scan alert to Slack."""
        scan_data = webhook_data['data']
        
        color = "good"
        if scan_data.get('high_risk_events', 0) > 0:
            color = "danger"
        elif scan_data.get('medium_risk_events', 0) > 0:
            color = "warning"
        
        message = {
            "text": f"SpiderFoot Scan Completed: {scan_data['target']}",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {
                            "title": "Target",
                            "value": scan_data['target'],
                            "short": True
                        },
                        {
                            "title": "Events Found",
                            "value": str(scan_data['events_found']),
                            "short": True
                        },
                        {
                            "title": "High Risk",
                            "value": str(scan_data.get('high_risk_events', 0)),
                            "short": True
                        },
                        {
                            "title": "Duration",
                            "value": f"{scan_data['duration']} seconds",
                            "short": True
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(self.webhook_url, json=message)
        return response.status_code == 200

# Usage
slack_handler = SlackWebhookHandler("https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK")

@app.route('/webhook/slack', methods=['POST'])
def slack_webhook():
    webhook_data = request.json
    
    if webhook_data['event_type'] == 'scan_completed':
        slack_handler.send_scan_alert(webhook_data)
    
    return "OK"
```

### SIEM Integration

```python
class SIEMWebhookHandler:
    def __init__(self, siem_endpoint, api_key):
        self.siem_endpoint = siem_endpoint
        self.api_key = api_key
    
    def send_security_event(self, webhook_data):
        """Send security event to SIEM."""
        event_data = {
            'timestamp': webhook_data['timestamp'],
            'source': 'SpiderFoot',
            'event_type': webhook_data['event_type'],
            'severity': self.map_severity(webhook_data),
            'raw_data': webhook_data['data'],
            'tags': ['osint', 'spiderfoot']
        }
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            f"{self.siem_endpoint}/events",
            json=event_data,
            headers=headers
        )
        
        return response.status_code == 200
    
    def map_severity(self, webhook_data):
        """Map SpiderFoot events to SIEM severity levels."""
        event_type = webhook_data['event_type']
        
        if event_type == 'high_risk_event':
            return 'HIGH'
        elif event_type == 'medium_risk_event':
            return 'MEDIUM'
        elif event_type == 'scan_failed':
            return 'MEDIUM'
        else:
            return 'LOW'
```

### Database Logging

```python
import sqlite3
from datetime import datetime

class WebhookLogger:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize webhook logging database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhook_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source_ip TEXT,
                payload TEXT NOT NULL,
                processed BOOLEAN DEFAULT FALSE,
                error_message TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_webhook(self, event_type, source_ip, payload, processed=True, error=None):
        """Log webhook event."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO webhook_logs 
            (timestamp, event_type, source_ip, payload, processed, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.utcnow().isoformat(),
            event_type,
            source_ip,
            json.dumps(payload),
            processed,
            error
        ))
        
        conn.commit()
        conn.close()

# Usage in webhook handler
logger = WebhookLogger('/var/log/webhooks.db')

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        webhook_data = request.json
        source_ip = request.remote_addr
        
        # Process webhook
        process_webhook_event(webhook_data)
        
        # Log successful processing
        logger.log_webhook(
            webhook_data['event_type'],
            source_ip,
            webhook_data,
            processed=True
        )
        
        return "OK"
        
    except Exception as e:
        # Log error
        logger.log_webhook(
            webhook_data.get('event_type', 'unknown'),
            request.remote_addr,
            request.json or {},
            processed=False,
            error=str(e)
        )
        
        return "Error", 500
```

## Webhook Testing

### Test Webhook Endpoint

```python
# Simple test webhook receiver
from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/test-webhook', methods=['POST'])
def test_webhook():
    print("Received webhook:")
    print(f"Headers: {dict(request.headers)}")
    print(f"Body: {request.get_data(as_text=True)}")
    
    try:
        data = request.json
        print(f"JSON Data: {json.dumps(data, indent=2)}")
    except:
        print("Failed to parse JSON")
    
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
```

### Webhook Simulation

```bash
# Test webhook with curl
curl -X POST http://localhost:8080/test-webhook \
  -H "Content-Type: application/json" \
  -H "X-SpiderFoot-Signature: sha256=test-signature" \
  -d '{
    "event_type": "scan_completed",
    "timestamp": "2024-01-01T12:00:00Z",
    "data": {
      "scan_id": "test_scan",
      "target": "example.com",
      "status": "FINISHED",
      "events_found": 100
    }
  }'
```

## Troubleshooting

### Common Issues

#### Webhook Not Received
1. **Check network connectivity** from SpiderFoot to webhook endpoint
2. **Verify firewall rules** allow outbound connections
3. **Check webhook URL** is accessible and correct
4. **Review SpiderFoot logs** for delivery errors

#### Signature Verification Fails
1. **Verify webhook secret** matches configuration
2. **Check signature header** format and encoding
3. **Ensure payload** is not modified in transit
4. **Debug signature calculation** step by step

#### High Latency or Timeouts
1. **Optimize webhook handler** processing time
2. **Use asynchronous processing** for heavy operations
3. **Implement webhook queuing** for high-volume scenarios
4. **Configure appropriate timeouts** in SpiderFoot

### Debugging

```python
# Enable webhook debugging
import logging

logging.basicConfig(level=logging.DEBUG)
webhook_logger = logging.getLogger('webhook')

def debug_webhook(webhook_data):
    webhook_logger.debug(f"Processing webhook: {webhook_data['event_type']}")
    webhook_logger.debug(f"Payload size: {len(json.dumps(webhook_data))} bytes")
    webhook_logger.debug(f"Timestamp: {webhook_data['timestamp']}")
```

## Best Practices

### Performance
1. **Process webhooks asynchronously** to avoid blocking SpiderFoot
2. **Implement webhook queuing** for high-volume scenarios  
3. **Use connection pooling** for outbound requests
4. **Cache frequently accessed data**

### Reliability
1. **Implement retry logic** with exponential backoff
2. **Log all webhook events** for debugging
3. **Monitor webhook endpoint health**
4. **Have fallback notification methods**

### Security
1. **Always verify signatures** in production
2. **Use HTTPS** for webhook endpoints
3. **Implement rate limiting** to prevent abuse
4. **Sanitize and validate** incoming data

For more integration examples, see the [REST API Documentation](rest_api.md) and [Python API Guide](python_api.md).
