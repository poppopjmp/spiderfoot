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
