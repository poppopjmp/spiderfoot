# Streaming Export Guide

This guide covers the JSONL streaming export and SSE live event stream endpoints introduced in SpiderFoot v6.0.0.

---

## Overview

SpiderFoot provides two streaming mechanisms for scan data:

| Endpoint | Format | Use Case |
|----------|--------|----------|
| `GET /api/scans/{id}/export/jsonl` | JSONL (Newline-Delimited JSON) | Bulk export for pipelines |
| `GET /events/stream` | SSE (Server-Sent Events) | Real-time event delivery |

---

## JSONL Export

### Endpoint

```
GET /api/scans/{scan_id}/export/jsonl
Authorization: Bearer <token>
```

### Response

Content-Type: `application/x-ndjson`

Each line is a complete JSON object representing one scan event:

```json
{"type": "IP_ADDRESS", "data": "93.184.216.34", "module": "sfp_dnsresolve", "source": "example.com", "confidence": 100, "timestamp": "2026-02-21T10:30:00Z"}
{"type": "INTERNET_NAME", "data": "www.example.com", "module": "sfp_dnsbrute", "source": "example.com", "confidence": 90, "timestamp": "2026-02-21T10:30:01Z"}
{"type": "RAW_RIR_DATA", "data": "{...}", "module": "sfp_shodan", "source": "93.184.216.34", "confidence": 100, "timestamp": "2026-02-21T10:30:02Z"}
```

### Event Fields

Each JSONL line contains the enriched `SpiderFootEvent.asDict()` output:

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Event type identifier (e.g., `IP_ADDRESS`, `DOMAIN_NAME`) |
| `data` | string | Event payload |
| `module` | string | Module that produced the event |
| `source` | string | Source data that triggered this event |
| `confidence` | int | Confidence score (0–100) |
| `timestamp` | string | ISO 8601 timestamp |
| `sourceEvent` | string | Parent event hash (optional) |

### Usage Examples

#### Stream to file
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://localhost/api/scans/abc123/export/jsonl" > scan_results.jsonl
```

#### Pipe to jq for filtering
```bash
curl -sH "Authorization: Bearer $TOKEN" \
  "https://localhost/api/scans/abc123/export/jsonl" \
  | jq 'select(.type == "IP_ADDRESS")'
```

#### Bulk ingest into Elasticsearch
```bash
curl -sH "Authorization: Bearer $TOKEN" \
  "https://localhost/api/scans/abc123/export/jsonl" \
  | while read -r line; do
      echo "{\"index\":{}}"
      echo "$line"
    done \
  | curl -X POST "http://elastic:9200/spiderfoot/_bulk" \
    -H "Content-Type: application/x-ndjson" --data-binary @-
```

#### Python processing
```python
import httpx
import json

with httpx.stream("GET", f"{base_url}/api/scans/{scan_id}/export/jsonl",
                   headers={"Authorization": f"Bearer {token}"}) as response:
    for line in response.iter_lines():
        event = json.loads(line)
        if event["type"] == "VULNERABILITY":
            process_vulnerability(event)
```

---

## SSE Live Event Stream

### Endpoint

```
GET /events/stream
Authorization: Bearer <token>
```

### Response

Content-Type: `text/event-stream`

```
data: {"type": "IP_ADDRESS", "data": "93.184.216.34", "scanId": "abc123", "module": "sfp_dnsresolve"}

data: {"type": "SCAN_PROGRESS", "data": {"completed": 42, "total": 100}, "scanId": "abc123"}

data: {"type": "SCAN_COMPLETE", "scanId": "abc123"}
```

### Frontend Integration

The React frontend uses `fetch` + `ReadableStream` (not `EventSource`) to avoid leaking JWT tokens in URLs:

```typescript
const response = await fetch('/events/stream', {
  headers: { 'Authorization': `Bearer ${token}` },
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const text = decoder.decode(value);
  for (const line of text.split('\n')) {
    if (line.startsWith('data: ')) {
      const event = JSON.parse(line.slice(6));
      handleEvent(event);
    }
  }
}
```

### Event Types

| SSE Event Type | Payload | Description |
|---------------|---------|-------------|
| `SCAN_PROGRESS` | `{completed, total}` | Periodic progress update |
| `SCAN_COMPLETE` | `{scanId}` | Scan finished |
| `SCAN_ERROR` | `{scanId, error}` | Scan error occurred |
| All data events | `{type, data, module, ...}` | Individual scan findings |

---

## Comparison

| Feature | JSONL Export | SSE Stream |
|---------|-------------|------------|
| **Timing** | After scan completes | During scan execution |
| **Data** | All events for one scan | Events from all active scans |
| **Format** | Newline-delimited JSON | Server-Sent Events |
| **Use case** | Bulk ETL, archival, analysis | Dashboards, real-time alerts |
| **Backpressure** | HTTP streaming | SSE reconnection |
