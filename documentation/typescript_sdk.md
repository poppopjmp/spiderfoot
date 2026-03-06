# TypeScript SDK Guide

This guide covers the auto-generated TypeScript API client used by SpiderFoot's React frontend.

---

## Overview

SpiderFoot v6.0.0 uses [`@hey-api/openapi-ts`](https://heyapi.dev/) to generate a fully typed, fetch-based API client from the FastAPI OpenAPI specification. The generated SDK provides:

- **Full type safety** — request parameters, response types, and error types
- **Native fetch** — no Axios dependency
- **JWT interceptor** — automatic token attachment
- **Clean method names** — post-processed `operationId` values

---

## Generated Files

```
frontend/src/api/generated/
├── index.ts          # Barrel export
├── types.gen.ts      # Request/response TypeScript interfaces
├── services.gen.ts   # API method implementations
└── core/
    ├── client.ts     # Fetch client configuration
    └── request.ts    # Request builder
```

---

## Regenerating the SDK

### Prerequisites

- Node.js 18+
- The API server running (for live spec extraction)

### Commands

```bash
cd frontend

# Regenerate from the live API
npm run generate:api

# Or manually with the OpenAPI spec file
npx @hey-api/openapi-ts \
  --input ../openapi.json \
  --output src/api/generated \
  --client fetch
```

### Pipeline

1. **Extract**: `dump_openapi.py` fetches `/api/openapi.json` from the running API
2. **Post-process**: Normalizes `operationId` values for clean SDK method names (e.g., `scans_list_scans_api_scans__get` → `listScans`)
3. **Generate**: `@hey-api/openapi-ts v0.92.4` produces the TypeScript client
4. **Output**: Generated files land in `frontend/src/api/generated/`

---

## Usage

### Basic API Call

```typescript
import { ScanService } from '@/api/generated';

// List all scans
const scans = await ScanService.listScans();

// Get a specific scan
const scan = await ScanService.getScan({ scanId: 'abc123' });

// Start a new scan
const newScan = await ScanService.createScan({
  requestBody: {
    target: 'example.com',
    modules: ['sfp_dnsresolve', 'sfp_shodan'],
  },
});
```

### With React Query

```typescript
import { useQuery, useMutation } from '@tanstack/react-query';
import { ScanService } from '@/api/generated';

// Query
const { data: scans } = useQuery({
  queryKey: ['scans'],
  queryFn: ({ signal }) => ScanService.listScans({ signal }),
});

// Mutation
const { mutate: startScan } = useMutation({
  mutationFn: (target: string) =>
    ScanService.createScan({ requestBody: { target } }),
});
```

### AbortSignal Support

All 84 generated API methods accept an optional `signal` parameter for request cancellation:

```typescript
const controller = new AbortController();

const scans = await ScanService.listScans({
  signal: controller.signal,
});

// Cancel the request
controller.abort();
```

React Query automatically passes its signal, providing free cancellation on unmount.

---

## JWT Interceptor

The client is configured with a request interceptor that attaches the JWT token:

```typescript
import { client } from '@/api/generated';

client.interceptors.request.use((request, options) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    request.headers.set('Authorization', `Bearer ${token}`);
  }
  return request;
});
```

This runs before every API call — no need to manually pass tokens.

---

## Type Safety

The SDK generates TypeScript interfaces for every request and response:

```typescript
// Generated types (from types.gen.ts)
export interface ScanCreateRequest {
  target: string;
  modules?: string[];
  options?: Record<string, unknown>;
}

export interface ScanResponse {
  id: string;
  target: string;
  status: 'RUNNING' | 'COMPLETED' | 'FAILED' | 'ABORTED';
  created: string;
  events_count: number;
}

// Compile-time type checking
const scan: ScanResponse = await ScanService.getScan({ scanId: 'abc123' });
console.log(scan.status); // Autocomplete: RUNNING | COMPLETED | FAILED | ABORTED
```

---

## Customizing the SDK

### Adding a New Endpoint

1. Add the FastAPI route in `spiderfoot/api/routers/`
2. Restart the API server
3. Run `npm run generate:api`
4. The new method and types appear automatically in `services.gen.ts` and `types.gen.ts`

### Post-Processing Operation Names

The `dump_openapi.py` script normalizes `operationId` values. If a new endpoint gets an ugly name, add a mapping rule:

```python
# In dump_openapi.py
OPERATION_ID_OVERRIDES = {
    "some_verbose_operation_name": "cleanName",
}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `npm run generate:api` fails | Ensure the API is running at the configured URL |
| Types don't match backend | Regenerate after backend changes |
| 401 errors | Check JWT interceptor setup in `client.ts` |
| Method not found | Run `npm run generate:api` to pick up new endpoints |
