# SpiderFoot v6.0.1 — Codebase Audit & Alignment

**Date:** 2026-05-31
**Branch:** `claude/codebase-audit-alignment-I4YfS`
**Method:** Systematic, segment-by-segment audit performed by a swarm of parallel
read-only agents (one per segment: core, modules, CLI, web, tests, docs), followed
by verified, incrementally-committed fixes.

This document records the findings and tracks which were fixed on this branch.
Every fix is a discrete, git-revertible commit. Items marked **(deferred)** are
documented here as follow-up work that was out of scope for a safe single-pass
change (too large, too risky, or requiring product decisions).

---

## Second pass — deferred items tackled (with verification)

A follow-up pass worked through the deferred backlog. Each change was verified
(unit tests / tsc / vitest / go build+vet+test / import smokes) before commit.

### Fixed
- **Core auth (security):** `update_sso_provider` blocklist → explicit column
  allowlist; PATCH `/sso/providers/{id}` now uses a typed `UpdateSSOProviderRequest`
  (`extra="forbid"`); JWT secret routed through `_resolve_jwt_secret()` (CRITICAL
  log when `SF_JWT_SECRET` unset); OAuth2-CSRF "Redis missing" log → CRITICAL;
  `_row_to_sso_provider` maps by column name (no magic indices).
- **Core db:** consolidated the two event-type catalogs — 95 entries in
  `db_core.py` aligned to the canonical `db/__init__.py` catalog (0 conflicts;
  zero runtime change since `__init__` is upserted last); added opt-in
  `limit`/`offset` to `scanResultEvent`.
- **Modules:** `json.loads` guards (6 modules); relocated 20 misplaced
  `handleEvent` docstrings; added top-of-`handleEvent` `errorState` guard to 97
  modules (storage modules excluded). Full module suite: 1372 passed, 0 failures.
- **CLI:** URL-escape query params (scan search/summary, report list), validate
  `compare` scan IDs, read password from `SF_PASSWORD`.
- **Frontend:** `RequirePermission` gated on `isLoading`; keyboard-accessible IaC
  toggles; fixed a version-assertion test regression from the 6.0.1 bump.
- **Infra:** Vector image tag aligned (helm ↔ compose); `sf-enrichment` MinIO
  bucket pre-created.

### Investigated — verified NON-issues (no change needed)
- **`sfp_tool_phoneinfoga` "7 unregistered events":** all 7 are already in the
  canonical `db/__init__.py` catalog (the agent only checked `db_core.py`).
- **Webhook SSRF on DNS failure:** the dispatcher already re-resolves and
  **fail-closes** at delivery time (`_is_ssrf_target` returns True on
  `gaierror`); registration leniency is harmless.
- **CI `spiderfoot-webui` references:** the helm chart still ships a
  `webui-deployment.yaml`, so `deploy.yml`'s rollout check is correct — not a
  stale reference.
- **`sf-enrichment` bucket "missing":** the enrichment pipeline auto-creates it
  on first use (still added to `minio-init` for consistency).
- **`tsconfig "types":["node"]`, frontend `workspaceApi.update`, `refreshPromise`:**
  re-confirmed correct (tsc clean with deps installed; backend reads query
  params; `finally` resets the promise).
- **`sfp_tool_phoneinfoga` `json.loads`:** already inside a `try/except`.

### Deferred (require product decision / infra / large refactor)
- JWT logout revocation (Redis `jti` denylist) — needs Redis + token-lifecycle design.
- Frontend tokens `localStorage` → `sessionStorage` — auth-persistence UX
  tradeoff (sessionStorage is equally XSS-readable; only narrows the window).
- `test_sfp_abusech` "live HTTP": it's an **integration** test (not in the unit
  CI path) and the module fetches via `self.fetch_url`, not `requests.get`, so a
  correct fix is a fetch_url-based rewrite — deferred.
- gRPC fixed test ports → `port=0`: only matters under pytest-xdist, which isn't
  used here; needs a coordinated server/test change.
- Frontend generated-SDK consolidation; eliminating 916 broad `except Exception`;
  implementing/removing the 6 stubbed social modules; `verify=False` on clearnet
  module requests; test coverage for the 84 untested modules / `spiderfoot/tasks/`.

---

## Third pass — test maturity & a routing bug class

Goal: raise the safety net (real tests, a coverage gate) and use the new tests
to surface latent defects. Coverage measured at **66.6%**; `--cov-fail-under=66`
added to CI so it cannot silently regress (to be ratcheted as tests land).

### Fixed (defects found via the new tests)
- **Route shadowing (8 routers, production bug):** a parameterized
  `GET /…/{param}` route declared *before* literal sibling paths made those
  literals unreachable (Starlette matches in declaration order) — they returned
  the param handler's 404 in production. Affected: `notification_rules`
  (`/history,/stats,/operators,/channels`), `report_templates`
  (`/history,/variables,/categories,/formats`), `scan_comparison`
  (`/categories,/severity-levels`), `tag_group` (`/tags/stats,/tags/colors`),
  `data` (`/data/modules/{stats,dependencies,status}`), `webhooks`
  (`/webhooks/event-types`), `health` (`/health/shutdown`), `scan`
  (`/scans/compare`, where `scan_id: SafeId` also matched the literal
  "compare"). Each parameterized route moved after its literal siblings;
  verified via Starlette route matching against the fully-assembled app.
  A permanent guard test (`test_api_route_shadowing.py`) asserts no literal GET
  route in the whole app is shadowed.
- **gRPC fixed test ports → `port=0`:** `ServiceServer.start()` now records the
  OS-assigned port (`server_address[1]`), eliminating the 19877/19878 collision
  that caused 8 cross-file test errors. (Closes a Second-pass deferred item.)

### Added (tests)
- API router tests via `TestClient` with auth dependency overridden:
  `sarif` (0→100%), `scan_metrics` (0→100%), `stix` (0→99%), `tenants` (0→96%),
  `audit` (0→100%), `notification_rules` (0→100%) — CRUD/round-trip/404 paths.
- `test_sfp_tool_wrappers_contract.py`: parametrized contract over the 20
  untested `sfp_tool_*` wrappers (100 subtests) — instantiation/setup,
  opts↔optdescs, watched/produced event types, errorState guard, and the
  missing-binary fail-safe path (asserts no subprocess spawned, no events
  emitted); each module 0→~40% line coverage.

### Deferred (still open from this pass)
- Reaching 85% coverage is multi-session: ~11k more statements across the
  remaining ~16 untested routers, `tasks/`, agents, and large service files.
- Cross-file test-isolation flakiness: several tests (scanner, event_relay,
  module_pipeline, scan_coordinator) pass in isolation but fail under the full
  unordered run due to shared global/DB/WebSocket state — needs fixture-level
  isolation, not a product fix.

---

## Segment 1 — Core (`spiderfoot/`, 339 files + `sfapi.py`)

### Fixed
- **CRITICAL** Broken import `spiderfoot.correlations.vector_collection_manager` (package is `spiderfoot.correlation`, singular) — `service_integration.py:248`, `api/routers/rag_correlation.py:318`, and logger name in `correlation/vector_collection_manager.py:31`. Vector/RAG features would `ImportError` at runtime.
- **HIGH** Broken import `from sflib import startSpiderFootScanner` — `workspace.py:934`. Correct path is `spiderfoot.scan.scanner`. Workspace-launched scans would `ModuleNotFoundError`.
- **HIGH** Tautological `WHERE` clause `AND (c.source_event_hash = 'ROOT' OR c.source_event_hash != 'ROOT')` (always TRUE) — `db/db_event.py:225`.
- **HIGH** `asyncio.get_event_loop()` in async handlers (deprecated, breaks on 3.12+) — `enrichment/service.py:90,115,141`, `ops/startup_sequencer.py`.
- **HIGH** `hashlib.md5(...)` without `usedforsecurity=False` (FIPS failure) — `recon/dns_stealth.py`, `scan/scan_coordinator.py`, `recon/stealth_integration.py`, `recon/tls_fingerprint.py`.
- **MEDIUM** Duplicated `url.strip()` + `urlparse()` block — `sflib/network.py:394–418`.
- **MEDIUM** Incorrect type hints in a `py.typed` package: `list = None` / `dict = None` params — `db/db_event.py:179–180`.

### Deferred (documented follow-ups)
- **HIGH (security)** SSRF "bypass" on DNS failure (`except socket.gaierror: pass`) — `api/routers/webhooks.py:66`. **Not changed:** the lenient handling is a *documented intentional* CI tradeoff, and a `_BLOCKED_HOSTNAMES` allowlist already runs first. The correct hardening (re-resolve and re-check at delivery time) is a larger change that risks breaking tests; deferred rather than flipping to fail-closed blindly.
- **CRITICAL (security)** `update_sso_provider` uses a 2-key *blocklist* over a raw `dict` body → arbitrary DB column injection (`auth/service.py:944`, `auth/routes.py:701`). Needs a typed Pydantic request model + allowlist. (Larger change touching the auth contract.)
- **HIGH (security)** JWT not revoked on logout — `auth/service.py:368`. Needs a Redis `jti` denylist (infra-dependent).
- **MEDIUM** JWT secret regenerated per-process when `SF_JWT_SECRET` unset — `auth/models.py:194`. Should fail-loud.
- **MEDIUM** OAuth2 CSRF state store silently disabled without `SF_REDIS_URL` — `auth/routes.py:44`.
- **HIGH (perf)** Unbounded `scanResultEvent()` (`fetchall()` of entire scan) — `db/db_event.py:177`. Needs pagination/streaming.
- **HIGH** Dual, conflicting event-type catalogs (`db/__init__.py` vs `db/db_core.py`): 8+ types disagree on ENTITY/DESCRIPTOR & `event_raw`. Needs single source of truth.
- **MEDIUM** Fragile positional SSO row indexing — `auth/service.py:875`.
- **MEDIUM** 916× broad `except Exception` swallowing; allowlist/blocklist inconsistency across `update_*` methods.

---

## Segment 2 — Scanner modules (`modules/`, ~310 plugins + `correlations/`)

### Fixed
- **MEDIUM** Case-inverted GTM placeholder filter (never matches) — `sfp_webanalytics.py:119`.
- **MEDIUM** Missing HTTP timeout (worker can hang) — `sfp_zoomeye.py:114`.
- **LOW (security)** Unused `import pickle` (latent deserialization risk) — `sfp__ai_threat_intel.py:34`.
- **LOW** File handle leak — `sfp_tool_cmseek.py:175`.

### Investigated — left as-is (not a defect)
- `sfp_citadel.py:100` "hardcoded API key": this is leak-lookup's **documented public/free-tier key** (the optdesc literally says *"Without this you're limited to the public API"*). Removing it would break free-tier functionality, so it was kept.
- `sfp_ipstack`/`sfp_ipapicom`/`sfp_malwarepatrol` plaintext-HTTP key transmission: the **free plans of these services only support HTTP** (HTTPS is paid-only). Forcing HTTPS would regress free-tier users. Deferred to a config/paid-plan decision rather than silently breaking the modules.

### Deferred
- **MEDIUM** Misplaced `handleEvent` docstrings after the `errorState` check (20 modules) — dead code / breaks introspection.
- **MEDIUM** 95 modules lack a `self.errorState` guard at the top of `handleEvent`.
- **MEDIUM** 6 fully-stubbed modules shipped (`sfp_instagram`, `sfp_reddit`, `sfp_rubika`, `sfp_soroush`, `sfp_telegram`, `sfp_whatsapp`) — implement or remove.
- **MEDIUM** Unprotected `json.loads` in 8 modules; 13 modules use `verify=False` on clearnet endpoints.
- **HIGH** `sfp_tool_phoneinfoga` emits 7 event types not registered in `db_core.py`.

---

## Segment 3 — Go CLI (`cli/`)

### Fixed
- Version literal `6.0.0` → read from build/VERSION alignment — `cmd/root.go:14`.
- API-contract drift (verified against `spiderfoot/api/`): scan-create payload field names, list/events/logs response envelope keys, wrong data endpoints. (See commits.)
- `README.md` documented non-existent `sf export excel` and `sf modules --filter` (missing `list`).

### Deferred
- **HIGH (security)** `--password` plaintext flag (visible in `ps`/history) — needs interactive prompt / env-var.
- Query params built by string concat without `url.QueryEscape`; `context.Context` not threaded for cancellation; stale `go.mod` deps.

---

## Segment 4 — Web frontend (`frontend/`)

### Fixed
- **LOW** Hardcoded `APP_VERSION = '6.0.0'` → `6.0.1` — `components/Layout.tsx:76`.

### Investigated — false positives (no change needed)
- `workspaceApi.update` sending `params` as query string is **correct**: the backend `update_workspace` handler (`api/routers/workspace.py:86`) declares `name`/`description` as plain function args, which FastAPI reads as **query parameters**. The frontend matches the contract.
- `refreshPromise` **is** reset on success: the `finally { refreshPromise = null }` block (`lib/api.ts:113`) wraps the whole try, including the success-return path.
- `tsconfig.json` `"types": ["node"]` is fine: `@types/node` is in `devDependencies`. The `TS2688` the agent saw was an artifact of running `tsc` without `node_modules` installed.

### Deferred
- **HIGH (security)** JWT tokens in `localStorage` (XSS theft); `safeStorage` helper exists but unused.
- **HIGH (arch)** Generated OpenAPI SDK unused; 1500-line hand-written `lib/api.ts` duplicate maintained in parallel.
- **MEDIUM** `RequirePermission` not gated on auth `isLoading`; Mermaid SVG sanitization may strip content; toggle a11y; perf (LogTab 5000-row fetch, GraphTab O(n²) layout).

---

## Segment 5 — Tests (`test/`, ~700 files + CI)

### Fixed
- **HIGH (bug)** `psycopg2.connect(':memory:')` (PostgreSQL has no in-memory mode) → `sqlite3` `:memory:` — `test/fixtures/database_fixtures.py:48`.
- **HIGH (perf)** Removed autouse `check_resource_leaks` `time.sleep(0.1)` (ran after every test for a warning-only diagnostic; minutes of cumulative wall-clock) — `conftest.py:125`.

### Notes / Deferred
- `netaddr` "missing" was an **environment artifact** of a fresh container — it is declared in `requirements.txt` (and reaches tests via `test/requirements.txt`'s `-r ../requirements.txt`). After `pip install -r requirements.txt`, collection works (verified). No code change needed.
- gRPC fixed ports 19877/19878 — left as-is: switching to `port=0` requires the `ServiceServer` to surface its OS-assigned port; deferred to avoid breaking the test on an unverified API.
- Three `assert True` lines (`test_tls_fingerprint.py:857`, `test_request_orchestration.py:394`, `test_spiderfoothelpers_extended.py:192`) are weak but function as "did-not-raise" smoke tests; left as-is.
- **HIGH** `test_sfp_abusech.py` makes live HTTP calls; `pytest_runtest_protocol` discards reports; multi-second `time.sleep()` in several unit tests; 84/310 modules have no integration test; `spiderfoot/tasks/` untested.

---

## Segment 6 — Docs & config

### Fixed
- **MEDIUM** Added `[6.0.1]` CHANGELOG entry.
- **HIGH** Removed stale `sfwebui.py` / port `:5001` references across `documentation/` (component removed in v6.0.0): API examples → `:8001`, browser access → `:3000`, `sfwebui.py` → `uvicorn sfapi:app`.
- **HIGH** Corrected frontend test count (282/270 → 300) consistently; removed the `update_version.py` reference (file absent).
- **MEDIUM** Fixed `CONTRIBUTING.md` URLs (`smicallef` → `poppopjmp`).
- **MEDIUM** Fixed malformed README header image `src`.
- **LOW** Version literals `cli/cmd/root.go` and `Layout.tsx` → `6.0.1`; correlation-rule count `94 → 95`.

### Investigated — left as-is
- "36 tool modules" claim: **internally consistent** (33 `sfp_tool_*` + 3 standalone integrations `sfp_httpx`/`sfp_subfinder`/`sfp_nuclei` = 36). Not changed.
- `pytest-asyncio` in `requirements.txt`: **kept.** One CI job (`ci.yml:214`) installs only `requirements.txt` + bare `pytest`, so it relies on `pytest-asyncio` being there. Removing it risks breaking that job for a LOW-severity hygiene gain.

### Deferred
- `Pipfile` deeply stale (already marked DEPRECATED); `docker/env.example` carries CherryPy/v5 artefacts; Helm/compose `vector` image-tag drift; missing `sf-enrichment` MinIO bucket; broken `spiderfoot-webui` references in CI workflows.

---

## How to revert

Each fix below is an isolated commit on `claude/codebase-audit-alignment-I4YfS`.
Revert any single change with `git revert <sha>`, or inspect with `git log --oneline`.
</content>
</invoke>
