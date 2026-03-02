# ADR-001: PostgreSQL-Only Database Backend

## Status

**Accepted** — 2025-07-08

## Context

SpiderFoot v5 supported both SQLite and PostgreSQL. The dual-database
architecture caused several problems:

1. **Schema drift**: Schema changes had to be written and tested for
   both databases
2. **Query incompatibilities**: SQL dialects differ (e.g., `UPSERT`,
   `RETURNING`, window functions)
3. **Performance disparity**: SQLite couldn't handle concurrent writes
   from multiple Celery workers
4. **Connection pooling**: SQLite doesn't support connection pools,
   requiring workarounds
5. **Testing burden**: Every database change needed tests for both backends

## Decision

SpiderFoot v6 uses **PostgreSQL exclusively**. SQLite support has been
removed.

## Consequences

### Positive

- **Single schema**: One migration path, one SQL dialect
- **Concurrent writes**: PostgreSQL handles concurrent Celery workers
  natively with MVCC
- **Connection pooling**: `psycopg2.pool.ThreadedConnectionPool` with
  min=2, max=20 connections
- **Advanced features**: Window functions, CTEs, JSON operators, full-text
  search, `LISTEN/NOTIFY`
- **Data integrity**: Full ACID transactions, proper foreign keys
- **Reduced test surface**: ~40% fewer database tests needed

### Negative

- **Higher deployment cost**: Requires a PostgreSQL server (Docker
  Compose provides one)
- **No embedded option**: Cannot run SpiderFoot as a single binary
  with embedded database
- **Migration required**: v5 users must migrate data from SQLite

### Mitigations

- Docker Compose includes PostgreSQL out of the box
- Migration scripts provided for v5 → v6 upgrade
- PostgreSQL can run on low-resource machines (512 MB RAM)

---

# ADR-002: FastAPI Replaces CherryPy

## Status

**Accepted** — 2025-07-08

## Context

SpiderFoot v5 used CherryPy for its web server. CherryPy is a mature
framework but:

1. **No async support**: CherryPy is synchronous, blocking during I/O
2. **No OpenAPI**: No automatic API documentation generation
3. **Limited ecosystem**: Fewer middleware, auth, and validation libraries
4. **Performance**: Slower than modern ASGI frameworks for I/O-bound work

## Decision

SpiderFoot v6 uses **FastAPI** as the web framework.

## Consequences

### Positive

- **Async native**: Full `async/await` support for non-blocking I/O
- **Automatic OpenAPI**: API documentation generated from type hints
- **Pydantic validation**: Request/response validation via Pydantic models
- **WebSocket support**: Real-time scan progress via WebSockets
- **Performance**: 3-10x faster for concurrent requests
- **GraphQL**: Easy integration with Strawberry GraphQL

### Negative

- **Breaking change**: All API endpoints changed structure
- **New dependency tree**: uvicorn, Starlette, Pydantic
- **Learning curve**: Team needed to learn FastAPI patterns

---

# ADR-003: Celery for Distributed Scanning

## Status

**Accepted** — 2025-07-08

## Context

SpiderFoot v5 ran scans in-process using threads. This caused:

1. **GIL contention**: Python's GIL limited true parallelism
2. **Single-machine limit**: Scans couldn't span multiple machines
3. **No retry**: Failed module executions couldn't be retried
4. **Memory isolation**: Memory leaks in one module affected all scans

## Decision

SpiderFoot v6 uses **Celery** with Redis as the message broker for
distributed scan execution.

## Consequences

### Positive

- **True parallelism**: Each worker process runs independently
- **Horizontal scaling**: Add workers on any machine
- **Automatic retry**: Failed tasks retry up to 3 times
- **Memory isolation**: `worker_max_memory_per_child` enforces limits
- **Task routing**: Priority queues for different task types
- **Monitoring**: Flower dashboard for real-time monitoring

### Negative

- **Infrastructure complexity**: Requires Redis + multiple worker processes
- **Message overhead**: Serializing events between processes adds latency
- **Debugging complexity**: Distributed logs are harder to trace

---

# ADR-004: Async-First Module Architecture

## Status

**Accepted** — 2025-07-08

## Context

SpiderFoot v5 modules used synchronous code with blocking I/O calls
(`requests.get`, `urllib`, `socket`). This wasted worker time waiting
for network responses.

## Decision

SpiderFoot v6 modules use `SpiderFootAsyncPlugin` with:

- `async def handleEvent()` as the main handler
- `aiohttp` or `httpx` for HTTP requests
- `aiodns` for DNS resolution
- `asyncio.wait_for()` for timeouts

## Consequences

### Positive

- **Higher throughput**: Workers process events during I/O waits
- **Natural timeouts**: `asyncio.wait_for()` replaces manual timeout logic
- **Event loop efficiency**: Single thread handles many concurrent I/O operations
- **Compatibility**: 304 out of 309 modules migrated to async

### Negative

- **Migration effort**: All modules needed rewriting
- **Complexity**: `async/await` adds cognitive load
- **Library constraints**: Some libraries don't support async

### Legacy Support

5 modules use `SpiderFootModernPlugin` (synchronous) for libraries
that don't support async. These run in thread pool executors.

---

# ADR-005: React Frontend with SSR

## Status

**Accepted** — 2025-07-08

## Context

SpiderFoot v5 used server-rendered HTML with Jinja2 templates
and jQuery. This approach:

1. Limited interactivity (full page reloads)
2. Made complex UIs (scan diff, timeline) difficult
3. Had no component reuse
4. Was hard to test

## Decision

SpiderFoot v6 uses **React** with server-side rendering for the
frontend.

## Consequences

### Positive

- **Rich interactivity**: Real-time scan updates, drag-and-drop
- **Component reuse**: Shared components across pages
- **Testing**: React Testing Library for unit tests
- **Type safety**: TypeScript catches errors at compile time
- **Ecosystem**: Large library of UI components (charts, maps, tables)

### Negative

- **Build complexity**: Node.js toolchain required
- **Bundle size**: Initial load larger than server-rendered HTML
- **SSR complexity**: Server-side rendering adds infrastructure
- **Two language stacks**: Python + TypeScript

---

*SpiderFoot v6 — Architecture Decision Records*
