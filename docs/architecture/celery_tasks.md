# Celery Task Architecture

SpiderFoot v6 uses [Celery](https://docs.celeryq.dev/) for
distributed scan execution. This document explains how scans are
distributed across workers, what queues exist, and how to extend
the system.

## Overview

```
┌─────────────┐     ┌───────────┐     ┌──────────────┐
│  FastAPI     │────▶│  Redis    │────▶│  Celery      │
│  (submit)   │     │  (broker) │     │  Workers     │
└─────────────┘     └───────────┘     └──────┬───────┘
                                             │
                                      ┌──────▼───────┐
                                      │  PostgreSQL  │
                                      │  (results)   │
                                      └──────────────┘
```

1. **FastAPI** receives scan requests and creates Celery tasks
2. **Redis** acts as the message broker
3. **Celery workers** consume tasks and execute modules
4. **PostgreSQL** stores scan results

## Worker Configuration

Key settings from `celery_config.py`:

| Setting | Value | Purpose |
|---------|-------|---------|
| `worker_max_memory_per_child` | 2 GB | Restart worker after 2 GB |
| `worker_max_tasks_per_child` | 200 | Restart after 200 tasks |
| `worker_prefetch_multiplier` | 1 | Fetch one task at a time |
| `task_acks_late` | True | Ack after completion |
| `task_time_limit` | 86400 | Max 24h per task |
| `task_soft_time_limit` | 82800 | Soft limit at 23h |

### Why `worker_prefetch_multiplier=1`?

Scans are long-running and resource-intensive. Prefetching
multiple tasks would cause workers to hold work they can't
immediately process, starving other workers.

### Why `task_acks_late=True`?

If a worker crashes mid-scan, unacknowledged tasks return to
the queue for retry. This ensures no scan is silently lost.

## Task Queues

SpiderFoot uses multiple queues for priority routing:

```python
# Default queue for scan tasks
CELERY_TASK_DEFAULT_QUEUE = "scans"

# Queue routing
CELERY_TASK_ROUTES = {
    "spiderfoot.tasks.run_scan": {"queue": "scans"},
    "spiderfoot.tasks.run_module": {"queue": "modules"},
    "spiderfoot.tasks.correlate": {"queue": "correlations"},
    "spiderfoot.tasks.notify": {"queue": "notifications"},
}
```

### Queue Descriptions

| Queue | Purpose | Concurrency |
|-------|---------|-------------|
| `scans` | Scan orchestration tasks | 2-4 per worker |
| `modules` | Individual module execution | 8-16 per worker |
| `correlations` | Post-scan correlation analysis | 2-4 per worker |
| `notifications` | Webhooks, email alerts | 4-8 per worker |

## Scan Lifecycle

### 1. Scan Submission

```python
# API endpoint receives scan request
scan_id = create_scan(target="example.com", modules=["sfp_dns"])

# Celery task created
from spiderfoot.tasks import run_scan
run_scan.delay(scan_id)
```

### 2. Scan Orchestration

The `run_scan` task:

1. Loads scan configuration from PostgreSQL
2. Resolves module dependencies
3. Creates the initial root event
4. Dispatches module tasks via `run_module.apply_async()`

### 3. Module Execution

Each module runs as a separate Celery task:

```python
@app.task(bind=True, max_retries=3)
def run_module(self, scan_id, module_name, event_data):
    module = load_module(module_name)
    results = module.handleEvent(event_data)

    for result in results:
        # Store in PostgreSQL
        store_event(scan_id, result)
        # Dispatch to consuming modules
        for consumer in get_consumers(result.event_type):
            run_module.delay(scan_id, consumer, result)
```

### 4. Completion

A scan is complete when all module tasks have finished:

- No more events in flight
- All modules have processed their queued events
- The scan status transitions to `FINISHED`

## Adding a New Queue

### 1. Define the Queue

```python
# In celery_config.py or settings
from kombu import Queue

CELERY_TASK_QUEUES = (
    Queue("scans", routing_key="scan.#"),
    Queue("modules", routing_key="module.#"),
    Queue("my_new_queue", routing_key="myqueue.#"),
)
```

### 2. Route Tasks

```python
CELERY_TASK_ROUTES = {
    "spiderfoot.tasks.my_new_task": {"queue": "my_new_queue"},
}
```

### 3. Start Workers for the Queue

```bash
celery -A spiderfoot.celery_app worker \
    --queues my_new_queue \
    --concurrency 4 \
    --loglevel info
```

### 4. Docker Configuration

Add a new worker service in `docker-compose.yml`:

```yaml
my-queue-worker:
  image: spiderfoot:latest
  command: >
    celery -A spiderfoot.celery_app worker
    --queues my_new_queue
    --concurrency 4
  depends_on:
    - redis
    - postgres
```

## Monitoring

### Flower Dashboard

SpiderFoot includes Flower for Celery monitoring:

```bash
celery -A spiderfoot.celery_app flower --port=5555
```

### Key Metrics

- **Active tasks**: Tasks currently being processed
- **Reserved tasks**: Tasks prefetched but not yet started
- **Succeeded/Failed**: Task completion rates
- **Worker uptime**: How long each worker has been running

### Health Checks

Workers expose health via the `/health/ready` endpoint which
checks Redis connectivity and task queue depth.

## Troubleshooting

### Tasks Stuck in PENDING

1. Check Redis is running: `redis-cli ping`
2. Check workers are consuming: `celery -A spiderfoot.celery_app inspect active`
3. Check queue length: `celery -A spiderfoot.celery_app inspect reserved`

### Worker OOM Kills

If workers are being killed by the OS:

1. Lower `worker_max_memory_per_child` (default 2 GB)
2. Reduce `worker_concurrency`
3. Check for memory leaks in modules

### Task Timeouts

Tasks exceeding `task_time_limit` (24h) are killed:

1. Check module isn't looping infinitely
2. Consider breaking large scans into smaller tasks
3. Adjust `task_time_limit` if legitimately needed

---

*SpiderFoot v6 — Celery Task Architecture*
