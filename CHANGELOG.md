# Changelog

All notable changes to SpiderFoot are documented in this file.  
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [5.9.2] — 2026-02-20 — Deep Security & Quality Hardening

### Security — P0 Critical
- **JWT hardening**: Replaced hand-rolled HMAC-SHA256 JWT with PyJWT library; auto-detects insecure default secrets (`changeme`, `secret`, etc.) and generates cryptographic random secret at startup; logs CRITICAL warning for insecure configurations
- **Auth bypass lockdown**: API key dev-mode bypass now requires explicit `SF_AUTH_DISABLED=true` environment variable (previously any misconfiguration could skip auth)
- **CORS lockdown**: Default allowed origins changed from `*` to `http://localhost:3000,https://localhost`; logs WARNING when wildcard CORS is active
- **XSS prevention**: Wrapped all 7 `dangerouslySetInnerHTML` usages in `ScanDetail.tsx` and `Workspaces.tsx` with DOMPurify sanitization (strict tag/attribute allow-list)
- Removed `python-jose` dependency in favor of sole `pyjwt` JWT library

### Refactored — Frontend Architecture
- **ScanDetail.tsx split**: Decomposed 1,979-line monolith into 10 focused tab components (`SummaryTab`, `BrowseTab`, `CorrelationsTab`, `GraphTab`, `GeoMapTab`, `ReportTab`, `SettingsTab`, `LogTab`, `MiniStat`, `ExportDropdown`) + shared `geo.ts` utility; page shell reduced to ~130 lines
- **ESLint flat config**: Added `eslint.config.js` (ESLint v9) with `typescript-eslint`, `react-hooks` plugin, and `@typescript-eslint/no-explicit-any` warning rule
- **Eliminated all 18 explicit `any` types**: Created shared `getErrorMessage()` utility using `axios.isAxiosError()` for type-safe error extraction; replaced 15 `catch(err: any)` patterns, fixed 1 `onError: (err: any)`, fixed 2 untyped `.map()` callbacks
- Fixed ESLint errors: unnecessary escape characters, ternary-as-statement expressions

### Reliability — Module Stop Guards
- Added `self.checkForStop()` guards to 35 critical module loops (15 critical ≥40 body lines, 20 high-priority 24-39 body lines) enabling graceful scan cancellation
- Modules patched: `sfp_leakcheck`, `sfp_tool_tlsx`, `sfp_tool_sslyze`, `sfp_tool_testsslsh`, `sfp_keybase`, `sfp_leakix`, `sfp_greynoise`, `sfp_arbitrum`, `sfp_grep_app`, `sfp_tool_dnsx`, `sfp_builtwith`, `sfp_names`, `sfp_certspotter`, `sfp_dehashed`, `sfp_mnemonic`, `sfp_circllu`, `sfp_tool_onesixtyone`, `sfp_tool_gitleaks`, `sfp_alienvault`, `sfp_aparat`, `sfp_tool_linkfinder`, `sfp_tool_sslscan`, `sfp_apileak`, `sfp_tool_gospider`, `sfp_company`, `sfp_discord`, `sfp_wechat`, `sfp_douyin`, `sfp_rocketreach`, `sfp_xiaohongshu`, `sfp_emailcrawlr`, `sfp_tool_nikto`, `sfp_tool_dalfox`, `sfp_apple_itunes`, `sfp_hackertarget`

### Cleanup — Dead Code Removal
- Removed dead `import urllib.error` and `import urllib.request` from 30 modules (only `urllib.parse` was used)
- Fixed `sfp_zoomeye` latent `NameError` bug: was catching `urllib.error.HTTPError/URLError` without importing `urllib` — dead except blocks removed since module uses `self.fetch_url()`
- Removed 3,445 lines of dead test code: 120 never-implemented integration test stubs (`@unittest.skip("todo")` with dummy data), 4 broken unit test stubs (had `selfdepth=0` instead of `self, depth=0`)
- Fixed unconditional `skipIf(True)` in `test_sfcli_enhanced.py` → proper `os.name == 'nt'` platform guard

### Dependencies
- Removed unused `werkzeug` from requirements (never imported)
- Moved `openai` to optional comment (LLM client uses raw HTTP, never imports the package)
- Added note that `weasyprint` is optional (PDF export only)

### Fixed — Frontend Visualization Bugs
- **Modules page**: Enabled/Disabled stat cards now compute counts client-side from per-module status map; previously relied on server aggregate fields that could lag after toggling a module
- **GeoMap tab**: Fixed latitude projection using correct simplemaps SVG bounds (83.65°N – 56°S) instead of ±90° pole-to-pole; southern-hemisphere markers were shifted up to 141 px northward

### Changed
- Version bump to 5.9.2 across all files (VERSION, package.json, Layout.tsx, README badge, Homebrew formula, ARCHITECTURE.md, overview.md, sfp_aprsfi User-Agent, test fixtures)

## [5.9.1] — 2026-02-17 — Docker Compose Profile Consolidation

### Removed — Defunct Data Sources
- Deleted 8 modules for offline/shutdown services: `sfp_crobat_api` (sonar.omnisint.io shut down 2022), `sfp_crxcavator` (CRXcavator shut down 2023), `sfp_dnsgrep` (bufferover.run shut down), `sfp_fsecure_riddler` (riddler.io discontinued 2021), `sfp_phishstats` (phishstats.info offline), `sfp_psbdmp` (psbdmp.cc offline), `sfp_punkspider` (punkspider.org shut down), `sfp_robtex` (free API deprecated)
- Deleted corresponding unit and integration tests (16 test files)

### Fixed — Module API Migrations
- **sfp_flickr**: Replaced broken `retrieveApiKey()` (scraped `YUI_config.flickr.api.site_key`) with user-provided API key; changed model from `FREE_NOAUTH_UNLIMITED` to `FREE_AUTH_UNLIMITED`
- **sfp_keybase**: Added null-safety checks and maintenance-mode note (Zoom acquisition 2020); removed unused imports
- **sfp_virustotal**: Full v2 → v3 API migration (endpoints, auth header `x-apikey`, relationships API, response parsing)
- **sfp_greynoise**: Full v2 → v3 API migration (IP lookup, GNQL queries, `cve` → `cves` field, response normalization)
- **sfp_nameapi**: Fixed HTTP → HTTPS for API endpoint
- **sfp_subdomainradar**: Fixed 3 critical API structure mismatches (auth header, response parsing, endpoint paths)

### Changed — Docker Compose Profiles
- Consolidated `docker-compose-microservices.yml` and `docker-compose-simple.yml` into a **single compose file** using Docker Compose profiles
- 5 core services (postgres, redis, api, celery-worker, frontend) always start without any profile
- 7 opt-in profiles: `scan`, `proxy`, `storage`, `monitor`, `ai`, `scheduler`, `sso`
- `full` meta-profile activates all profiles except `sso`
- Core services use `${VAR:-fallback}` env var patterns for graceful degradation without optional services (embedding/reranker default to `mock`, qdrant to `memory`, minio/tika/OTEL to empty)

### Removed
- Deleted `docker-compose-simple.yml` (replaced by core-only profile of unified compose file)
- Deleted `docker/env.simple.example` (replaced by `.env.example` profile sections)

### Changed — Documentation
- Updated README.md with profile-based Quick Start, Deployment Modes, and Services tables
- Updated `docker_deployment.md`, `quickstart.md`, `getting_started.md`, `user_guide.md`, `installation.md`, `active-scan-worker.md` with profile commands
- Restructured `.env.example` with profile-organized sections (core active, profile vars commented)

## [5.9.0] — 2026-02-16 — Platform Hardening, Scan Profiles & Light Theme

### Added — PostgreSQL Report Storage
- **`PostgreSQLBackend`** for report storage — replaces SQLite in microservices deployments
- Auto-detection of `SF_POSTGRES_DSN` from environment — zero-config upgrade
- psycopg2-based backend with `ON CONFLICT` upsert, thread-local connections, same API as `SQLiteBackend`
- `StoreConfig` auto-selects PostgreSQL when DSN is available, falls back to SQLite otherwise
- `StorageBackend` enum expanded with `POSTGRESQL` variant
- Health dashboard now reports `"backend": "postgresql"` when running in Docker

### Added — Celery Task Queue for Scans
- **`spiderfoot.tasks.scan`** — Celery-based scan execution replacing `BackgroundTasks`/`mp.Process`
- `run_scan` task with 24h hard / 23h soft time limits, `acks_late=True`, deduplication guard
- Crash recovery via dedup guard (checks terminal states, stale `RUNNING` with progress age)
- Scan progress stored in Redis hashes (`sf:scan:progress:{scan_id}`) and published via pub/sub
- `abort_scan`, `run_batch_scans`, `update_scan_progress` supporting tasks
- **`celery_app.py`** — central Celery configuration with 6 task queues (`default`, `scan`, `report`, `export`, `agents`, `monitor`), auto-routing, JSON+msgpack serialization, beat schedule (hourly cleanup, 5-min health checks)

### Added — Scan Profiles System
- **`ScanProfile`** dataclass with module selection by flags, use cases, categories, explicit include/exclude
- **`ProfileManager`** singleton with 10 built-in profiles: `quick-recon`, `full-footprint`, `passive-only`, `vuln-assessment`, `social-media`, `dark-web`, `infrastructure`, `api-powered`, `minimal`, `tools-only`
- `ProfileCategory` enum (reconnaissance, vulnerability, social, infrastructure, dark_web, custom)
- JSON import/export, directory loading, auto-exclude deprecated modules
- API endpoints: `GET /scan-profiles`, `GET /scan-profiles/{name}`
- Frontend profile picker in New Scan page with category badges and module counts

### Added — Light Theme & Theme-Aware UI
- Full `[data-theme="light"]` CSS with reversed semantic color scale
- Theme-aware badge classes: `badge-critical`, `badge-high`, `badge-medium`, `badge-low`, `badge-info`, `badge-success`
- Status dot, risk pill, health badge, and correlation card classes with proper light-background contrast
- `StatusBadge` and `RiskPills` components with dual-theme CSS class system
- Three-way theme toggle (Light / Dark / System) in sidebar

### Added — Frontend Enhancements
- **New Scan page**: 4-tab module selection (By Use Case, By Profile, By Required Data, By Module), target type auto-detection (domain/IP/email/phone/ASN/BTC/ETH/username/name), document upload with drag-and-drop
- **Workspaces page**: multi-target workspace grouping with 6 tabs (overview, targets, scans, correlations, geomap, report)
- **Correlations tab**: first-class tab in scan detail and workspace views, on-demand correlation runs, risk breakdown summary
- **Dashboard**: health panel with `healthApi.dashboard`, stat cards from search/facets API, 15s auto-refresh
- **Scans page**: server-side search with facets, bulk stop/delete operations
- Services dropdown in sidebar: AI Agents, Grafana, Jaeger, Prometheus, Traefik, MinIO, Flower

### Changed — Tool Module Modernization
- 9 tool modules migrated to `SpiderFootModernPlugin` base class: `sfp_tool_whatweb`, `sfp_tool_trufflehog`, `sfp_tool_testsslsh`, `sfp_tool_snallygaster`, `sfp_tool_retirejs`, `sfp_tool_onesixtyone`, `sfp_tool_nbtscan`, `sfp_tool_dnstwist`, `sfp_tool_cmseek`
- All tool modules now have `from __future__ import annotations`, typed return annotations, and `toolDetails` in `meta` dict
- `setup()` signatures standardized with `super().setup(sfc, userOpts or {})`

### Changed — Vector.dev Telemetry Pipeline
- API health endpoint on port 8687 for container healthcheck
- Loki sink fixes for 400-error prevention
- Traefik access log source added
- Jaeger datasource added to Grafana provisioning
- Vector container healthcheck in docker-compose

### Changed — Infrastructure & Docker
- Docker CI workflow (`.github/workflows/docker.yml`) with two-stage build (base + 4-service matrix), GHCR push, semver tagging from `VERSION` file
- MinIO now creates 7 buckets (`sf-logs`, `sf-reports`, `sf-pg-backups`, `sf-qdrant-snapshots`, `sf-data`, `sf-loki-data`, `sf-loki-ruler`)
- `Dockerfile.active-worker` for active scan tools (external binaries)
- Flower monitoring dashboard for Celery added to compose

### Changed — Documentation
- `modules.md`: corrected to 36 external tool integrations, removed duplicate `sfp_tool_wappalyzer` table entry
- `docker_deployment.md`: corrected bucket list to 7 (was 5), fixed `sf-qdrant` → `sf-qdrant-snapshots` name
- `README.md`: version badge updated to 5.9.0

### Fixed — Bug Fixes
- **Scan restart loop**: scans no longer restart endlessly when Celery workers reconnect
- **Scan profiles API resolution**: profile-based module resolution now works correctly
- **Light theme contrast**: badges, status dots, risk pills, correlation cards now readable on white backgrounds
- **Health tab cleanup**: removed 6 broken health checks, kept 9 meaningful subsystem probes
- **Loki `expand-env` flag**: added `-config.expand-env=true` to Loki command for envvar interpolation
- **Report storage backend indicator**: health dashboard now correctly shows `postgresql` instead of `sqlite`
- **Orphaned `fetchUrl` method** removed from `spiderfoot/__init__.py` (module-level function with `self` parameter)
- **`__version__.py` fallback** corrected from nonsensical `5.245.0` to `5.9.0`
- **`PostgreSQLBackend` missing from `__all__`** in `spiderfoot/reporting/__init__.py`

## [5.3.3] — Infrastructure Integration: Nemesis-Compatible Architecture

### Added — Monitoring Stack (Phase 1)
- **Grafana 11.4.0** dashboard service with auto-provisioned SpiderFoot Overview (12 panels)
- **Loki 3.3.2** log aggregation with MinIO S3 backend, TSDB indexing, 30-day retention
- **Prometheus 2.54.1** metrics collection with 10 scrape targets (api, scanner, agents, enrichment, vector, qdrant, minio, jaeger, litellm, self)
- Pre-built Grafana datasources: Loki, Prometheus, PostgreSQL
- Activated Vector.dev → Loki log sink with service/job/level labels
- Activated Vector.dev → Prometheus exporter on :9598 with `spiderfoot` namespace

### Added — Distributed Tracing (Phase 2)
- **Jaeger 2.4.0** all-in-one tracing service
- Vector.dev OTLP source (gRPC :4317, HTTP :4318) for trace ingestion
- Vector.dev → Jaeger OTLP sink for trace forwarding
- `spiderfoot/observability/tracing.py` — OpenTelemetry instrumentation with `get_tracer()`, `trace_span()` context manager, graceful no-op fallback

### Added — LLM Gateway (Phase 3)
- **LiteLLM v1.74.0** unified LLM proxy with OpenAI-compatible API
- Multi-provider support: OpenAI (gpt-4o, gpt-4o-mini, gpt-3.5-turbo), Anthropic (claude-sonnet, claude-haiku), Ollama (llama3, mistral, codellama)
- Embedding models: text-embedding-3-small, text-embedding-3-large
- Redis-backed response caching (db:2), Prometheus callbacks for cost tracking
- Router aliases: default→gpt-4o-mini, fast→gpt-3.5-turbo, smart→gpt-4o, local→ollama/llama3
- API service now routes LLM calls through `SF_LLM_API_BASE=http://litellm:4000`

### Added — AI Agents Service (Phase 4)
- `spiderfoot/agents/` package with 6 analysis agents:
  - **FindingValidator** — validates MALICIOUS_*/VULNERABILITY_*/LEAKED_* findings, produces verdict/confidence/remediation
  - **CredentialAnalyzer** — assesses LEAKED_CREDENTIALS/API_KEY_* exposure risk
  - **TextSummarizer** — summarizes RAW_*/TARGET_WEB_CONTENT/PASTE_* content with entity/sentiment extraction
  - **ReportGenerator** — generates executive summaries on SCAN_COMPLETE with threat assessment
  - **DocumentAnalyzer** — analyzes DOCUMENT_UPLOAD/USER_DOCUMENT for entities/IOCs, supports large document chunking
  - **ThreatIntelAnalyzer** — maps MALICIOUS_*/CVE_*/DARKNET_* to MITRE ATT&CK techniques
- `BaseAgent` ABC with concurrency semaphore, timeout handling, LLM calling (aiohttp → LiteLLM), Prometheus metrics (processed_total, errors_total, avg_processing_time_ms)
- FastAPI agents service (:8100) with /agents/process, /agents/analyze, /agents/report, /agents/status, /metrics, /health endpoints
- Redis pub/sub event listener for automatic agent dispatch with wildcard pattern matching

### Added — Document Enrichment Pipeline (Phase 5)
- `spiderfoot/enrichment/` package:
  - **DocumentConverter** — PDF (pypdf), DOCX (python-docx), XLSX (openpyxl), HTML, RTF (striprtf), text; optional Tika fallback
  - **EntityExtractor** — pre-compiled regex for IPv4/IPv6, emails, URLs, domains, MD5/SHA1/SHA256, phone numbers, CVEs, Bitcoin/Ethereum, AWS keys, credit cards; smart dedup and private IP filtering
  - **EnrichmentPipeline** — orchestrates convert → extract → store (MinIO sf-enrichment bucket) with SHA256-based document IDs
- FastAPI enrichment service (:8200) with /enrichment/upload (100MB limit), /enrichment/process-text, /enrichment/batch, /enrichment/results/{id}, /metrics, /health

### Added — User-Defined Input Service (Phase 6)
- `spiderfoot/user_input/` package:
  - POST /input/document — upload → enrichment → agent analysis chain
  - POST /input/iocs — IOC list submission with deduplication
  - POST /input/report — structured report → entity extraction → agent analysis → MinIO
  - POST /input/context — scope/exclusions/known_assets/threat_model per scan
  - POST /input/targets — batch target list for multi-scan
- Automatic forwarding to enrichment and agents services via HTTP
- Submission tracking with GET /input/submissions and /input/submissions/{id}

### Changed — Infrastructure
- Docker Compose expanded from 10 → 17 containers
- MinIO init now creates 8 buckets (added sf-loki-data, sf-loki-ruler, sf-enrichment)
- Nginx config expanded with upstream blocks and location routing for Grafana (with WebSocket), Prometheus, Jaeger, LiteLLM, agents, enrichment, user-input
- `docker/env.example` expanded with monitoring, tracing, LLM, and resource limit variables
- `config/vector.toml` — Loki sink activated, Prometheus exporter activated, OTLP trace source + Jaeger sink added
- New `infra/` directory with configs: `loki/local-config.yaml`, `grafana/provisioning/`, `grafana/dashboards/`, `prometheus/prometheus.yml`, `litellm/config.yaml`
- Docker networks: sf-frontend (bridge), sf-backend (internal) — all new services on sf-backend
- New volumes: grafana-data, prometheus-data

### Changed — Documentation
- README.md: updated Mermaid architecture diagram (17 containers), version badge (5.3.3), services table, Quick Start URLs, project structure; added Monitoring, AI Agents, Document Enrichment, User-Defined Input, LLM Gateway sections
- ARCHITECTURE.md: updated topology diagram, service table, package listing; added AI Agents, Enrichment, User Input, LLM Gateway, Observability Stack sections
- `docker/env.example`: comprehensive example with all new service configuration
