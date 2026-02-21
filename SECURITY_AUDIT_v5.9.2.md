# SpiderFoot v5.9.2 — Security Audit Report

**Audit Date:** 2025  
**Scope:** Full codebase — Python backend (`spiderfoot/`, `spiderfoot/api/`, `spiderfoot/db/`, `modules/`) + React/TypeScript frontend (`frontend/src/`)  
**Method:** Static analysis (full source review of critical paths, regex pattern scanning across all files)

---

## Findings Summary

### Backend (Python)

| Severity | Count | Description                        |
|----------|-------|------------------------------------|
| **P0**   | 2     | SQL injection, Server-side Template Injection  |
| **P1**   | 7     | SSRF, XSS, missing auth, default credentials, header injection |
| **P2**   | 5     | Untyped bodies, error detail leakage, thread safety, resource leak |
| **P3**   | 2     | No-backup config import, unbounded multi-export |

### Frontend (React/TypeScript) — see bottom of file

| Severity | Count | Description                        |
|----------|-------|------------------------------------|
| **P0**   | 1     | SSO tokens exposed in URL          |
| **P1**   | 4     | useEffect dep bugs, 3 pages bypass React Query, no AbortController, token storage race |
| **P2**   | 7     | No debounce, no React.memo, localStorage unbounded, duplicated logic, monolith files, canvas leak |
| **P3**   | 4     | Hardcoded credentials, hardcoded docs content, table a11y, popup blocker |

### Combined Totals: **P0: 3 | P1: 11 | P2: 12 | P3: 6** → 32 findings

---

## P0 — Critical

### 1. SQL Injection via String Formatting in `db_event.py`

**File:** [spiderfoot/db/db_event.py](spiderfoot/db/db_event.py#L400)  
**Lines:** 400, 422  
**Status:** NEW

`scanElementSourcesDirect()` and `scanElementChildrenDirect()` build SQL `IN` clauses
using Python `%`-formatting instead of parameterised placeholders:

```python
# Line 400
qry = f"... AND c.hash in ('%s')" % "','".join(hashIds)

# Line 422
qry = f"... AND c.source_event_hash in ('%s')" % "','".join(hashIds)
```

Although there is an `isalnum()` guard (line 396-398),:
- The guard silently drops non-alnum *but does not reject the request*, so a mixed list can still proceed.
- The `isalnum()` check does **not** prevent single-quote injection if it is ever relaxed or bypassed by hash format changes.
- Every other query in the entire codebase uses `{self._ph}` parameterised placeholders — these two are the only exceptions.

Both methods are called transitively by `scanElementSourcesAll()` and `scanElementChildrenAll()`, which are in turn used by the scan event tree UI endpoints.

**Recommended Fix:**  
Replace the string-concatenated `IN` clause with parameterised placeholders:

```python
placeholders = ",".join([self._ph] * len(hashIds))
qry = f"... AND c.hash IN ({placeholders})"
qvars = [instanceId] + hashIds
```

---

### 2. Server-Side Template Injection (SSTI) in Report Template Rendering

**File:** [spiderfoot/report_templates.py](spiderfoot/report_templates.py#L399)  
**Lines:** 399-415  
**Status:** NEW

The `_render_template()` method renders **user-created** template strings (supplied via `POST /api/report-templates` → `body_template` field) with full Jinja2 capabilities:

```python
env = Environment(loader=BaseLoader(), autoescape=True)
tmpl = env.from_string(template.body_template)  # user-controlled
body = tmpl.render(**context)
```

`autoescape=True` prevents XSS in HTML output but does **not** prevent SSTI. An attacker who can create a template can execute arbitrary Python:

```
{{ ''.__class__.__mro__[1].__subclasses__() }}
```

Additionally, the fallback path (when Jinja2 is not installed) uses Python `str.format()`:

```python
return template.body_template.format(**context)
```

This exposes attribute traversal (e.g., `{events.__class__.__init__.__globals__}`).

**Recommended Fix:**  
- Use `jinja2.sandbox.SandboxedEnvironment` instead of `Environment`.
- Remove the `str.format()` fallback entirely, or use a safe string substitution.

---

## P1 — High

### 3. SSRF via Unvalidated Webhook URLs

**Files:**  
- [spiderfoot/api/routers/webhooks.py](spiderfoot/api/routers/webhooks.py#L48) — `WebhookCreateRequest.url: str`  
- [spiderfoot/notifications.py](spiderfoot/notifications.py#L208) — `urllib.request.urlopen(req)` on lines 208, 252, 294  
- [spiderfoot/api/routers/webhook_delivery.py](spiderfoot/api/routers/webhook_delivery.py#L25) — `CreateDeliveryRequest.endpoint_url: str`  
**Status:** KNOWN REMAINING — confirmed still present

Webhook creation and notification channels accept arbitrary URLs with no validation against internal/private IP ranges. `urllib.request.urlopen()` will follow redirects and can reach `http://169.254.169.254/` (cloud metadata), `http://localhost:*`, or internal services.

**Recommended Fix:**  
Validate webhook URLs with an allowlist of schemes (`https://` only), resolve the hostname, and reject RFC 1918 / link-local / loopback addresses before `urlopen()`.

---

### 4. Stored XSS in Email Notification HTML

**File:** [spiderfoot/notifications.py](spiderfoot/notifications.py#L328)  
**Lines:** ~328-334  
**Status:** KNOWN REMAINING — confirmed still present

The `_send_email()` method interpolates scan event data into an HTML table without escaping:

```python
f"<td><b>{k}</b></td><td>{v}</td>"
```

Scan event keys/values originate from module outputs and may contain arbitrary HTML or JavaScript. `html.escape()` is only used in `report_formatter.py`, not here.

**Recommended Fix:**  
```python
import html
f"<td><b>{html.escape(str(k))}</b></td><td>{html.escape(str(v))}</td>"
```

---

### 5. Missing Authentication on Multiple Router Groups

**Files and status:**

| Router file | Endpoints affected | Auth present? |
|---|---|---|
| [sso.py](spiderfoot/api/routers/sso.py) | All 13 endpoints (provider CRUD, SAML/OIDC flows, session mgmt) | **NO** — no `api_key` or auth dependency |
| [report_templates.py](spiderfoot/api/routers/report_templates.py) | All 11 endpoints (template CRUD, render, import/export) | **NO** |
| [tag_group.py](spiderfoot/api/routers/tag_group.py) | All 14 endpoints (tag CRUD, group mgmt, assignments) | **NO** |
| [webhook_delivery.py](spiderfoot/api/routers/webhook_delivery.py) | All 9 endpoints (delivery CRUD, dead-letter queue, circuit breaker) | **NO** |
| [stix.py](spiderfoot/api/routers/stix.py) | All 7 endpoints (STIX export, TAXII server) | **NO** |
| [graphql/resolvers.py](spiderfoot/api/graphql/resolvers.py) | All mutations: `start_scan`, `stop_scan`, `delete_scan`, `set_false_positive`, `rerun_scan` | **NO** |

**Status:** KNOWN REMAINING for GraphQL; **NEW** for SSO, templates, tags, webhook delivery, STIX.

These routers import neither `get_api_key` nor `optional_auth` from `dependencies.py`.
An unauthenticated user can create SSO providers (with `client_secret` fields), render
templates (SSTI — see P0 #2), manage tags, replay webhooks, and export STIX bundles.

**Recommended Fix:**  
Add `api_key: str = Depends(get_api_key)` (or `optional_auth`) to every endpoint in these routers. For SSO login/callback flows, use a different auth mechanism (e.g., CSRF token).

---

### 6. Hardcoded Default Credentials for MinIO

**Files:**  
- [spiderfoot/storage/minio_manager.py](spiderfoot/storage/minio_manager.py#L66) — `secret_key: str = "changeme123"`  
- [spiderfoot/user_input/service.py](spiderfoot/user_input/service.py#L475) — `secret_key = os.environ.get("SF_MINIO_SECRET_KEY", "changeme123")`  
- [spiderfoot/tasks/report.py](spiderfoot/tasks/report.py#L246) — same pattern  
**Status:** NEW

Three separate files hardcode `changeme123` as the default MinIO secret key. If the
`SF_MINIO_SECRET_KEY` environment variable is not set (common in development or first
deployment), all MinIO storage (reports, logs, backups, Qdrant snapshots) is accessible
with known credentials. Additionally, `secure=False` is the default, meaning credentials
are transmitted in plaintext.

**Recommended Fix:**  
- Remove hardcoded defaults; fail fast if `SF_MINIO_SECRET_KEY` is not set.
- Default `secure` to `True`.
- Log a warning at startup if default credentials are detected.

---

### 7. Content-Disposition Header Injection via Scan Name

**File:** [spiderfoot/api/routers/scan.py](spiderfoot/api/routers/scan.py#L244)  
**Lines:** 244, 249, 290, 295, 1480, 1485  
**Status:** NEW

Several export endpoints use `record.name` (user-supplied scan name) directly in
`Content-Disposition` headers **without quoting or sanitising**:

```python
fname = f"{scan_name}-SpiderFoot.json"
# ...
headers={"Content-Disposition": f"attachment; filename={fname}"}
```

A scan name containing `\r\n` or `"` can inject arbitrary HTTP headers (response
splitting) or break the Content-Disposition parser. RFC 6266 requires the filename
to be quoted and `\` / `"` to be escaped.

Compare with [reports.py](spiderfoot/api/routers/reports.py#L644) and [export.py](spiderfoot/api/routers/export.py#L133) which
correctly use double quotes around the filename.

**Recommended Fix:**  
Sanitise the scan name (strip non-printable characters, remove `"`, `\`, newlines)
and always quote the filename:
```python
safe_name = re.sub(r'[^\w\s\-.]', '', scan_name)[:100]
headers={"Content-Disposition": f'attachment; filename="{safe_name}-SpiderFoot.json"'}
```

---

## P2 — Medium

### 8. Untyped `dict` Request Bodies Bypass Pydantic Validation

**Files and locations:**

| File | Line(s) | Endpoint |
|---|---|---|
| [config.py](spiderfoot/api/routers/config.py#L114) | 114, 182, 272, 354, 370, 405, 634 | PUT/POST config, module-config, API keys, credentials |
| [scan.py](spiderfoot/api/routers/scan.py#L2029) | 2029, 2059 | scan metadata, notes |
| [data.py](spiderfoot/api/routers/data.py#L223) | 223 | module config validate |
| [report_templates.py](spiderfoot/api/routers/report_templates.py#L158) | 158 | template import |

**Status:** KNOWN REMAINING — confirmed still present

Using `param: dict = Body(...)` instead of a typed Pydantic model means:
- No field validation (types, ranges, required fields)
- No OpenAPI schema generation for clients
- Arbitrary unexpected fields are silently accepted

**Recommended Fix:**  
Define Pydantic models for each endpoint. For config endpoints, at minimum use  
`dict[str, Any]` with a custom validator.

---

### 9. Error Detail Leaks Internal Exception Messages

**Files:**  
- [data.py](spiderfoot/api/routers/data.py#L62) — `detail=f"Failed to list entity types: {e}"`  
- [scan.py](spiderfoot/api/routers/scan.py#L740) — `detail=f"Invalid engine: {e}"`  
- [scan.py](spiderfoot/api/routers/scan.py#L1098) — `detail=f"Correlation failed: {e}"`  
- [scan.py](spiderfoot/api/routers/scan.py#L1822) — `detail=f"Scan [{new_scan_id}] failed: {e}"`  
- [visualization.py](spiderfoot/api/routers/visualization.py#L74) — 5 instances  
- [rag_correlation.py](spiderfoot/api/routers/rag_correlation.py#L291) — 6 instances  
- [storage.py](spiderfoot/api/routers/storage.py#L96) — 3 instances  
- [schedules.py](spiderfoot/api/routers/schedules.py#L299) — 1 instance  

**Status:** KNOWN REMAINING — confirmed still present (20+ occurrences across routers)

Exception objects (`{e}`, `{exc}`) are interpolated directly into HTTP 500 response
details, potentially exposing file paths, SQL queries, stack fragments, hostnames,
or credentials embedded in connection strings.

**Recommended Fix:**  
Log the full exception server-side (`log.error(..., exc_info=True)`), but return a
generic message to the client: `detail="Internal server error"`.

---

### 10. `_report_store` Dict Without Thread Synchronisation

**File:** [spiderfoot/api/routers/reports.py](spiderfoot/api/routers/reports.py#L44)  
**Line:** 44  
**Status:** KNOWN REMAINING — confirmed still present

The in-memory fallback `_report_store: dict[str, dict[str, Any]] = {}` is
accessed from both the async event loop (endpoint handlers) and `BackgroundTasks`
threads (`_generate_report_background`) without any lock. Functions `store_report`,
`get_stored_report`, `update_stored_report`, `delete_stored_report`, and
`list_stored_reports` all operate on this dict concurrently.

While CPython's GIL prevents data corruption at the bytecode level, dict mutation
during iteration (e.g., `list_stored_reports` while `store_report` runs) can raise
`RuntimeError`.

**Recommended Fix:**  
Wrap all access in a `threading.Lock`, or migrate entirely to the persistent
`ReportStore` backend and remove the fallback dict.

---

### 11. GraphQL `_get_db()` Creates Unclosed Database Connections

**File:** [spiderfoot/api/graphql/resolvers.py](spiderfoot/api/graphql/resolvers.py#L33)  
**Lines:** 33-37  
**Status:** NEW

```python
def _get_db() -> SpiderFootDb:
    from spiderfoot.db import SpiderFootDb
    return SpiderFootDb(...)
```

Every GraphQL resolver call creates a **new** `SpiderFootDb` instance (which opens
a new database connection). These are never explicitly closed. Under load, this will
exhaust SQLite file handles or PostgreSQL connection pool slots.

**Recommended Fix:**  
Use FastAPI's dependency injection with a context-managed DB session, or implement
a connection pool / singleton pattern with proper cleanup.

---

### 12. SQL Injection in `db_utils.py` Admin Functions

**File:** [spiderfoot/db/db_utils.py](spiderfoot/db/db_utils.py#L172)  
**Lines:** 172, 175, 195  
**Status:** KNOWN REMAINING — confirmed still present

```python
# Line 172
cursor.execute(f"DROP TABLE IF EXISTS {t}")
# Line 175
cursor.execute(f"DROP TABLE IF EXISTS {t}")
# Line 195
cursor.execute(f"SELECT ... WHERE table_name='{t}'")
```

Table names from `sqlite_master` / `pg_tables` are interpolated via f-strings.
While table names originate from the database itself (limiting exploitability to
post-compromise scenarios), the pattern is dangerous if any code path ever creates
tables from user input. Line 195 is especially unsafe with single-quote wrapping.

**Recommended Fix:**  
Use identifier quoting (`"table_name"`) via the DB-API's appropriate method, or
validate table names against an allowlist of known SpiderFoot tables.

---

## P3 — Low

### 13. Config Import Has No Backup/Rollback Mechanism

**File:** [spiderfoot/api/routers/config.py](spiderfoot/api/routers/config.py#L732)  
**Line:** 732  
**Status:** KNOWN REMAINING — confirmed still present

`POST /config/import` calls `config.replace_config(new_config)` then
`config.save_config()` with no snapshot of the prior configuration. A malformed
import permanently overwrites working config with no undo path.

**Recommended Fix:**  
Before `replace_config()`, save the current config to a timestamped backup file
or retain the previous config in memory for rollback on validation failure.

---

### 14. Multi-Export Endpoints Accept Unbounded Scan ID Lists

**File:** [spiderfoot/api/routers/scan.py](spiderfoot/api/routers/scan.py#L207)  
**Lines:** 207, 253, 305  
**Status:** KNOWN REMAINING — confirmed still present

`export_scan_json_multi`, `export_scan_viz_multi`, and `rerun_scan_multi` accept
a comma-separated `ids` query parameter with no upper bound. Passing hundreds of
scan IDs causes the server to load and serialise all their events in a single
request, resulting in memory exhaustion or very long response times.

**Recommended Fix:**  
Validate the `ids` parameter:
```python
id_list = [s.strip() for s in ids.split(",") if s.strip()]
if len(id_list) > 20:
    raise HTTPException(400, "Maximum 20 scan IDs per request")
```

---

## Verified Clean Areas

The following areas were scanned and found to be **clean** (confirming already-fixed items):

| Pattern searched | Scope | Result |
|---|---|---|
| `shell=True` | `modules/`, `spiderfoot/` | **No matches** |
| `eval(`, `exec(` | `modules/`, `spiderfoot/` | **No matches** |
| `pickle.loads`, `yaml.load`, `marshal.loads` | All Python files | **No matches** |
| `subprocess.call`, `subprocess.Popen`, `os.system` | `spiderfoot/`, `modules/` | **No matches** |
| `verify=False` (TLS skip) | `spiderfoot/` | **No matches** |

---

## Appendix: Files Reviewed

### Full reads (every line)
- `spiderfoot/db/db_utils.py` (202 lines)
- `spiderfoot/db/db_event.py` (624 lines)
- `spiderfoot/db/db_scan.py` (227 lines)
- `spiderfoot/db/db_correlation.py` (141 lines)
- `spiderfoot/notifications.py` (377 lines)
- `spiderfoot/notification_manager.py` (259 lines)
- `spiderfoot/worker_pool.py` (442 lines)
- `spiderfoot/webhook_dispatcher.py` (334 lines)
- `spiderfoot/api/graphql/resolvers.py` (914 lines)
- `spiderfoot/api/main.py` (222 lines)
- `spiderfoot/api/routers/webhooks.py` (306 lines)
- `spiderfoot/api/routers/export.py` (256 lines)
- `spiderfoot/api/routers/report_templates.py` (194 lines)
- `spiderfoot/api/routers/sso.py` (239 lines)
- `spiderfoot/report_templates.py` (599 lines — rendering engine)

### Partial reads + grep coverage
- `spiderfoot/api/routers/scan.py` (2286 lines — ~1200 read)
- `spiderfoot/api/routers/config.py` (1154 lines — ~800 read)
- `spiderfoot/api/routers/reports.py` (840 lines — ~700 read)
- `spiderfoot/api/routers/data.py` (716 lines — ~300 read)
- `spiderfoot/api/dependencies.py` (477 lines — ~350 read)
- `spiderfoot/storage/minio_manager.py` (448 lines — ~100 read)

### Pattern scans (full codebase)
- SQL f-string injection patterns across all `spiderfoot/db/` files
- `Content-Disposition` header patterns across all routers
- `detail=f"...{e}"` error leakage across all routers
- Auth dependency (`api_key`, `Depends`, `optional_auth`) across all routers
- Secret/credential patterns (`SECRET_KEY`, `changeme`, `password`) across all files

---

# Frontend Security Audit — React/TypeScript

**Scope:** All files in `frontend/src/` (12 pages, 10 scan-tab components, 5 lib modules, 3 component files)  
**Files Fully Read:** 30/30

## Already Fixed (verified — NOT re-reported)

1. ~~XSS via `dangerouslySetInnerHTML`~~ — All 7 usages now wrapped in `sanitizeHTML()` (DOMPurify)
2. ~~No ErrorBoundary~~ — `<ErrorBoundary>` wraps `<App />` in `main.tsx`
3. ~~Unsafe `JSON.parse` in ApiKeys.tsx~~ — try/catch added
4. ~~Dead file upload in NewScan~~ — Removed
5. ~~Mutations swallowing errors~~ — `onError` handlers added to 14 mutations
6. ~~ScanDetail 1979-line monolith~~ — Decomposed into 10 tab components
7. ~~18 explicit `any` types~~ — Replaced with `getErrorMessage()` + typed patterns
8. ~~ModalShell a11y~~ — `role="dialog"`, `aria-modal`, focus trap, Escape key added
9. ~~Duplicate ModalShell in SSOSettings~~ — Deduplicated to shared UI component
10. ~~Ethereum detection bug in Workspaces~~ — Fixed regex, added `ETHEREUM_ADDRESS` type

---

## Frontend Findings

### Findings Summary

| Severity | Count | Description                                    |
|----------|-------|------------------------------------------------|
| **P0**   | 1     | SSO tokens exposed in URL                      |
| **P1**   | 4     | useEffect dep bugs, 3 pages bypass React Query, no request cancellation, redundant token storage race |
| **P2**   | 7     | No debounce, no React.memo, localStorage report unbounded, detectTargetType duplication, Workspaces 1117 lines, api.ts monolith, GraphTab canvas leak |
| **P3**   | 4     | Hardcoded credentials in Layout, Documentation hardcoded guides, table a11y gaps, report PDF popup blocked |

---

## P0 — Critical

### F1. SSO Tokens Exposed in URL Query Parameters

**File:** [src/lib/auth.ts](frontend/src/lib/auth.ts#L253-L269)  
**Lines:** 253–269  
**Status:** KNOWN REMAINING — confirmed still present

```typescript
setTokensFromUrl: () => {
  const params = new URLSearchParams(window.location.search);
  const access = params.get('access_token');
  const refresh = params.get('refresh_token');
  if (access) {
    saveTokens(access, refresh || '');
    set({ accessToken: access, refreshToken: refresh, isAuthenticated: true });
    window.history.replaceState({}, '', window.location.pathname);
  }
},
```

After SSO callback, tokens travel through URL query parameters. Although the URL is cleaned via `replaceState`, tokens have already been:
- Logged by the web server (access logs contain full query strings)
- Stored in browser history (before `replaceState` fires)
- Potentially leaked via `Referer` header to any external resources on the page
- Visible in browser extensions with URL access

**Recommended Fix:**  
Switch the SSO backend to return tokens via a short-lived authorization code (`?code=XYZ`) and exchange it for tokens via a POST call. Alternatively, use `POST` form response mode or `fragment` (`#access_token=...`) which is not sent in `Referer` headers.

---

## P1 — High

### F2. useEffect Missing Dependencies in App.tsx

**File:** [src/App.tsx](frontend/src/App.tsx#L62-L70)  
**Lines:** 62–70  
**Status:** KNOWN REMAINING — confirmed still present

```typescript
useEffect(() => {
  setTokensFromUrl();
  fetchAuthStatus();
}, []);              // ← missing setTokensFromUrl, fetchAuthStatus

useEffect(() => {
  if (accessToken) {
    fetchCurrentUser();
  }
}, [accessToken]);   // ← missing fetchCurrentUser
```

Both `useEffect` hooks have incomplete dependency arrays. While Zustand store functions have stable references, this violates the React rules of hooks. If the store implementation ever changes (e.g., function reference changes), these effects will silently miss updates. React StrictMode double-invocation masks this in dev.

**Recommended Fix:**
```typescript
useEffect(() => {
  setTokensFromUrl();
  fetchAuthStatus();
}, [setTokensFromUrl, fetchAuthStatus]);

useEffect(() => {
  if (accessToken) fetchCurrentUser();
}, [accessToken, fetchCurrentUser]);
```

---

### F3. Three Admin Pages Bypass React Query (Stale Data, No Caching, No Dedup)

**Files:**
- [src/pages/Users.tsx](frontend/src/pages/Users.tsx#L96-L112) — `useState` + `useCallback` + `useEffect` with raw `api.get()`
- [src/pages/SSOSettings.tsx](frontend/src/pages/SSOSettings.tsx#L118-L128) — same pattern
- [src/pages/ApiKeys.tsx](frontend/src/pages/ApiKeys.tsx#L110-L121) — same pattern  
**Status:** KNOWN REMAINING — confirmed still present

Example from Users.tsx:
```typescript
const fetchUsers = useCallback(async () => {
  setLoading(true);
  setError(null);
  try {
    const res = await api.get('/api/auth/users');
    setUsers(res.data.items || []);
  } catch (err) {
    setError(getErrorMessage(err, 'Failed to load users'));
  } finally {
    setLoading(false);
  }
}, []);

useEffect(() => { fetchUsers(); }, [fetchUsers]);
```

Problems:
1. **No caching/dedup** — navigating away and back fires a redundant API call every time
2. **No stale-while-revalidate** — user sees loading spinner even for previously-fetched data
3. **No request cancellation** on unmount — if the user navigates away mid-request, the response still calls `setUsers()` on an unmounted component
4. **Manual refetch after mutations** — each CRUD operation calls `fetchUsers()` manually instead of `queryClient.invalidateQueries()`
5. **Inconsistent with the rest of the app** — all other pages (Dashboard, Scans, Modules, Settings, Agents, all scan tabs) use React Query properly

**Recommended Fix:**  
Refactor all three pages to use `useQuery` / `useMutation` with `queryClient.invalidateQueries()`, matching the pattern used in every other page.

---

### F4. No Request Cancellation (AbortController) Anywhere

**File:** [src/lib/api.ts](frontend/src/lib/api.ts) (entire file, 595 lines)  
**Status:** KNOWN REMAINING — confirmed still present

Zero usages of `AbortController` or `signal` across the entire frontend. Long-running requests (especially `agentsApi.report()`, `scanApi.exportEvents()`, and the force-directed graph viz data in `scanApi.viz()`) cannot be cancelled if:
- The user navigates away
- A component unmounts
- The user triggers a new request that makes the current one obsolete

React Query supports `signal` forwarding automatically when the `queryFn` is passed `({ signal })` — but none of the query functions use it.

**Recommended Fix:**  
Pass `signal` from React Query's `queryFn` context to axios calls:
```typescript
queryFn: ({ signal }) => api.get('/api/...', { signal }).then(r => r.data),
```

---

### F5. Redundant Triple Token Storage Creates Race Condition Window

**Files:**
- [src/lib/auth.ts](frontend/src/lib/auth.ts#L103-L108) — `saveTokens()` writes 3 keys
- [src/lib/api.ts](frontend/src/lib/api.ts#L10) — interceptor reads from 2 keys with fallback
- [src/lib/api.ts](frontend/src/lib/api.ts#L36-L37) — refresh interceptor writes 2 keys  
**Status:** KNOWN REMAINING — confirmed still present

```typescript
// auth.ts saveTokens()
localStorage.setItem('sf_access_token', access);
localStorage.setItem('sf_refresh_token', refresh);
localStorage.setItem('sf_api_key', access); // legacy dup

// api.ts request interceptor
const token = localStorage.getItem('sf_access_token') || localStorage.getItem('sf_api_key');

// api.ts refresh interceptor
localStorage.setItem('sf_access_token', newToken);
localStorage.setItem('sf_api_key', newToken);  // also duplicated here
```

Three localStorage keys store the same access token. The refresh interceptor in `api.ts` writes 2 keys while `saveTokens()` in `auth.ts` writes 3, creating an inconsistency where `sf_refresh_token` is NOT updated during refresh — only `sf_access_token` and `sf_api_key` are. A concurrent tab or race condition during refresh could read a stale token from the fallback key.

**Recommended Fix:**  
Consolidate to a single key (`sf_access_token`) and remove `sf_api_key` entirely. If backward compat is needed, write `sf_api_key` only during initial login, not on every refresh.

---

## P2 — Medium

### F6. SearchInput Has No Debounce — Fires API Call on Every Keystroke

**Files:**
- [src/components/ui/index.tsx](frontend/src/components/ui/index.tsx#L98-L113) — `SearchInput` component
- [src/pages/Scans.tsx](frontend/src/pages/Scans.tsx) — `scanApi.search()` on keystroke
- [src/components/scan/BrowseTab.tsx](frontend/src/components/scan/BrowseTab.tsx) — event filtering  
**Status:** KNOWN REMAINING — confirmed still present

```typescript
// SearchInput — fires onChange on every keystroke
<input
  type="text"
  value={value}
  onChange={(e) => onChange(e.target.value)}
/>
```

The `SearchInput` component passes every keystroke directly to the parent. In pages like Scans.tsx where the search triggers a `useQuery` with `searchQuery` in the query key, this fires a new API request on every character typed.

**Recommended Fix:**  
Add a `useDebounce` hook (300ms) inside `SearchInput` or create a `useDebouncedValue()` hook used by consuming pages.

---

### F7. Scan Tab Components Not Wrapped in React.memo — Unnecessary Re-renders

**File:** [src/pages/ScanDetail.tsx](frontend/src/pages/ScanDetail.tsx#L131-L139)  
**Lines:** 131–139  
**Status:** KNOWN REMAINING — confirmed still present

```typescript
{activeTab === 'summary' && <SummaryTab scanId={scanId} scan={scan} />}
{activeTab === 'browse' && <BrowseTab scanId={scanId} />}
{activeTab === 'correlations' && <CorrelationsTab scanId={scanId} />}
// ... 5 more tabs
```

All 8 tab components are conditionally rendered without `React.memo`. When the parent re-renders (e.g., `scan` data refetches every 5s while running), the currently-visible tab component is fully re-rendered even if its props (`scanId`, `scan`) haven't changed. For heavy components like `GraphTab` (force-directed canvas animation) and `GeoMapTab` (SVG with map projection), this is wasteful.

**Recommended Fix:**  
Wrap each tab export in `React.memo`:
```typescript
export default React.memo(function SummaryTab({ ... }) { ... });
```

---

### F8. ReportTab Stores Reports in localStorage Without Size Limit

**File:** [src/components/scan/ReportTab.tsx](frontend/src/components/scan/ReportTab.tsx#L151-L153)  
**Lines:** 151–153, 280, 364  
**Status:** KNOWN REMAINING — confirmed still present

```typescript
const storageKey = `sf_report_${scanId}`;
useEffect(() => {
  const saved = localStorage.getItem(storageKey);
  if (saved) setReportContent(saved);
}, [storageKey]);

// After generation:
localStorage.setItem(storageKey, md);
```

AI-generated reports are stored in localStorage with a unique key per scan. localStorage has a ~5MB limit across all keys. With many scans, reports accumulate without any eviction or size-checking. Once localStorage fills up, all `setItem` calls silently fail or throw `QuotaExceededError`.

The same pattern exists in WorkspaceReportCard (`sf_ws_report_${workspaceId}`).

**Recommended Fix:**  
Add an LRU eviction strategy: before writing, check total storage size and evict oldest reports. Alternatively, move report storage to IndexedDB or use server-side storage.

---

### F9. detectTargetType Duplicated with Different Logic

**Files:**
- [src/pages/Workspaces.tsx](frontend/src/pages/Workspaces.tsx#L27-L44) — `detectTargetType()` function
- [src/pages/NewScan.tsx](frontend/src/pages/NewScan.tsx#L65-L79) — `detectedType` useMemo  
**Status:** KNOWN REMAINING — confirmed still present

Workspaces.tsx:
```typescript
if (/^0x[0-9a-fA-F]{40}$/.test(t)) return 'ETHEREUM_ADDRESS';  // requires 0x prefix
```

NewScan.tsx:
```typescript
if (/^(0x)?[0-9a-fA-F]{40}$/.test(t)) return 'Ethereum Address'; // optional 0x prefix
```

Differences:
1. **Ethereum regex** — Workspaces requires `0x` prefix, NewScan makes it optional
2. **Return values** — Workspaces returns internal event types (`INTERNET_NAME`, `EMAILADDR`), NewScan returns human-readable labels (`Domain Name`, `Email Address`)
3. **Workspaces has `NETBLOCK_OWNER`** for CIDR notation, NewScan doesn't distinguish
4. **Workspaces has `BGP_AS_OWNER`**, NewScan has `ASN` — different naming for same thing
5. **Default fallback** — Workspaces defaults to `'INTERNET_NAME'`, NewScan defaults to `'Unknown'`

**Recommended Fix:**  
Extract into a shared `src/lib/targetDetection.ts` module with both the internal type and the display label, used by both pages.

---

### F10. Workspaces.tsx Still 1117 Lines — Needs Decomposition

**File:** [src/pages/Workspaces.tsx](frontend/src/pages/Workspaces.tsx) (1117 lines)  
**Status:** KNOWN REMAINING — confirmed still present

Contains: workspace list, create/edit/import modals, target manager, scan launcher, correlation viewer, geo-map mini-view, AI report card, and a full markdown renderer — all in one file. This is the largest file in the frontend after the ScanDetail decomposition.

**Recommended Fix:**  
Extract into sub-components: `WorkspaceList`, `WorkspaceDetail`, `WorkspaceTargets`, `WorkspaceScans`, `WorkspaceReportCard`, `WorkspaceGeoMap`, etc.

---

### F11. api.ts Monolith (595 Lines, All API Definitions)

**File:** [src/lib/api.ts](frontend/src/lib/api.ts) (595 lines)  
**Status:** KNOWN REMAINING — confirmed still present

Every API namespace (`scanApi`, `dataApi`, `configApi`, `workspaceApi`, `healthApi`, `aiConfigApi`, `agentsApi`), plus type definitions, plus helper functions, plus the axios instance and interceptors — all in one file. Makes it hard to tree-shake unused endpoints and increases cognitive load.

**Recommended Fix:**  
Split into: `api/client.ts` (axios instance + interceptors), `api/scans.ts`, `api/config.ts`, `api/workspace.ts`, `api/agents.ts`, `api/types.ts`.

---

### F12. GraphTab Canvas Animation Never Cleaned Up on Data Change

**File:** [src/components/scan/GraphTab.tsx](frontend/src/components/scan/GraphTab.tsx#L33-L142)  
**Lines:** 33–142  
**Status:** NEW

```typescript
useEffect(() => {
  // ... 110 lines of canvas animation ...
  let running = true;
  function tick() {
    if (!running || !ctx) return;
    // ...
    if (frame < maxFrames) requestAnimationFrame(tick);
  }
  tick();
  return () => { running = false; };
}, [nodes, edges]);
```

The cleanup sets `running = false` but does NOT cancel the pending `requestAnimationFrame`. If the `nodes`/`edges` data changes before the animation completes (200 frames), a new animation starts while the old `requestAnimationFrame` callback is still queued. Although `running = false` prevents the old callback from continuing, there's a single-frame overlap where both old and new animations draw to the same canvas.

Additionally, the `useEffect` depends on `[nodes, edges]` which are derived from `data` via `const nodes = data?.nodes ?? []` — creating new array references on every render even when the data hasn't changed, potentially restarting the animation unnecessarily.

**Recommended Fix:**  
Store the `requestAnimationFrame` ID and call `cancelAnimationFrame(id)` in cleanup. Use `useMemo` to stabilize `nodes`/`edges` references.

---

## P3 — Low

### F13. Hardcoded Default Credentials in Layout.tsx Service Links

**File:** [src/components/Layout.tsx](frontend/src/components/Layout.tsx#L52-L58)  
**Lines:** 52–58  
**Status:** KNOWN REMAINING — confirmed still present

```typescript
const SERVICE_LINKS = [
  { name: 'Grafana', url: '/grafana/', desc: 'Metrics & dashboards (admin/spiderfoot)' },
  { name: 'Traefik', url: '/dashboard/', desc: 'Reverse proxy (admin/spiderfoot)' },
  { name: 'MinIO', url: '/minio/', desc: 'Object storage (spiderfoot/changeme123)' },
  { name: 'Flower', url: '/flower/', desc: 'Celery monitor (admin/spiderfoot)' },
];
```

Default credentials for 4 services are hardcoded in the frontend source as description strings. While these are common Docker defaults and visible only to authenticated users, they appear in the production JS bundle where anyone with browser DevTools can read them.

**Recommended Fix:**  
Remove credentials from descriptions. If needed, link to a password management page or documentation instead.

---

### F14. Documentation.tsx Contains 150+ Lines of Hardcoded Guide Content

**File:** [src/pages/Documentation.tsx](frontend/src/pages/Documentation.tsx#L240-L390)  
**Lines:** ~240–390  
**Status:** KNOWN REMAINING — confirmed still present

The `GUIDES` array (~150 lines) contains all guide titles, descriptions, and content embedded as string literals in the component. This inflates the JS bundle and makes content updates require code changes and rebuilds.

**Recommended Fix:**  
Move guide content to static JSON/MDX files loaded at build time, or fetch from the backend.

---

### F15. Tables Lack Accessibility Attributes

**Files:** All pages with `<table>` elements:
- [src/components/scan/SummaryTab.tsx](frontend/src/components/scan/SummaryTab.tsx#L98-L109)
- [src/components/scan/BrowseTab.tsx](frontend/src/components/scan/BrowseTab.tsx#L110-L119)
- [src/components/scan/LogTab.tsx](frontend/src/components/scan/LogTab.tsx#L70-L78)
- [src/pages/Users.tsx](frontend/src/pages/Users.tsx)
- [src/pages/SSOSettings.tsx](frontend/src/pages/SSOSettings.tsx)
- [src/pages/ApiKeys.tsx](frontend/src/pages/ApiKeys.tsx)  
**Status:** KNOWN REMAINING — confirmed still present

No `<table>` in the frontend uses `scope="col"` on `<th>` elements, `aria-label` on tables, `<caption>`, or `role` attributes. The `ModalShell` modal has proper a11y (already fixed), but tables — the most common data display pattern — have none. Screen readers cannot associate data cells with their headers.

**Recommended Fix:**  
Add `scope="col"` to all `<th>` elements. Add `aria-label` or `<caption>` to each table describing its content.

---

### F16. ReportTab PDF Export Can Be Silently Blocked by Popup Blockers

**File:** [src/components/scan/ReportTab.tsx](frontend/src/components/scan/ReportTab.tsx#L486-L510)  
**Lines:** 486–510  
**Status:** NEW

```typescript
const exportPDF = () => {
  const printWindow = window.open('', '_blank');
  if (!printWindow) return;  // silently fails
  printWindow.document.write(`<!DOCTYPE html>...`);
  printWindow.document.close();
  setTimeout(() => { printWindow.print(); }, 500);
};
```

`window.open()` is commonly blocked by popup blockers because it's not triggered directly by a click event (it's inside a dropdown handler). When blocked, the function silently returns without user feedback. The user clicks "PDF" and nothing happens.

**Recommended Fix:**  
Show a toast message when `window.open()` returns `null`: `"Popup blocked — please allow popups for this site"`. Or use a server-side PDF generation endpoint and download the file directly.

---

## Coverage Matrix

| File | Lines | Fully Read | Issues Found |
|------|------:|:----------:|:------------:|
| `src/App.tsx` | 122 | ✅ | F2 |
| `src/main.tsx` | 33 | ✅ | — |
| `src/lib/api.ts` | 595 | ✅ | F4, F5, F11 |
| `src/lib/auth.ts` | 277 | ✅ | F1, F5 |
| `src/lib/errors.ts` | 17 | ✅ | — |
| `src/lib/sanitize.ts` | 39 | ✅ | — |
| `src/lib/geo.ts` | 54 | ✅ | — |
| `src/lib/theme.tsx` | 83 | ✅ | — |
| `src/pages/Login.tsx` | 331 | ✅ | — |
| `src/pages/Dashboard.tsx` | ~230 | ✅ | — |
| `src/pages/Scans.tsx` | 426 | ✅ | F6 |
| `src/pages/NewScan.tsx` | 468 | ✅ | F9 |
| `src/pages/ScanDetail.tsx` | 150 | ✅ | F7 |
| `src/pages/Settings.tsx` | 415 | ✅ | — |
| `src/pages/Modules.tsx` | ~400 | ✅ | — |
| `src/pages/Documentation.tsx` | 440 | ✅ | F14 |
| `src/pages/Agents.tsx` | 518 | ✅ | — |
| `src/pages/Users.tsx` | 762 | ✅ | F3, F15 |
| `src/pages/SSOSettings.tsx` | 761 | ✅ | F3, F15 |
| `src/pages/ApiKeys.tsx` | 689 | ✅ | F3, F15 |
| `src/pages/Workspaces.tsx` | 1117 | ✅ | F9, F10 |
| `src/components/Layout.tsx` | 323 | ✅ | F13 |
| `src/components/ErrorBoundary.tsx` | ~90 | ✅ | — |
| `src/components/ui/index.tsx` | 486 | ✅ | F6 |
| `src/components/scan/SummaryTab.tsx` | 131 | ✅ | F15 |
| `src/components/scan/BrowseTab.tsx` | 197 | ✅ | F15 |
| `src/components/scan/CorrelationsTab.tsx` | 100 | ✅ | — |
| `src/components/scan/GraphTab.tsx` | 165 | ✅ | F12 |
| `src/components/scan/GeoMapTab.tsx` | 241 | ✅ | — |
| `src/components/scan/ReportTab.tsx` | 643 | ✅ | F8, F16 |
| `src/components/scan/SettingsTab.tsx` | 82 | ✅ | — |
| `src/components/scan/LogTab.tsx` | 111 | ✅ | F15 |
| `src/components/scan/ExportDropdown.tsx` | 53 | ✅ | — |
| `src/components/scan/MiniStat.tsx` | 10 | ✅ | — |
| `src/components/scan/index.ts` | 11 | ✅ | — |
