# Changelog

All notable changes to SpiderFoot are documented in this file.  
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [5.160.0] — RC Cycle 88: Core Class Docstrings

### Added
- Added docstrings to 8 core classes: `SpiderFoot`, `EventManager`, `EventEnricher`, `TargetAlias`, `Tree`, `ExtractedLink`, `CircuitState` (×2)

## [5.159.0] — RC Cycle 87: Narrow Broad Except Clauses

### Changed
- Narrowed 15 `except Exception` clauses to specific types across 5 files
- `socket.gethostbyname_ex/gethostbyaddr/getaddrinfo` → `(socket.gaierror, socket.herror, OSError)`
- `urllib.parse.urlparse` → `ValueError` / `(ValueError, AttributeError)`
- `float()`/`int()` conversions → `(ValueError, TypeError)`
- `json.loads` → `(json.JSONDecodeError, ValueError)`
- `yaml.safe_load` + file read → `(yaml.YAMLError, OSError)`
- `str.split()` → `(AttributeError, TypeError)`

## [5.158.0] — RC Cycle 86: String Formatting Cleanup

### Changed
- Replaced 7 `%`-style string interpolations with f-strings in `webui/scan.py` and `webui/routes.py`
- Fixed potential bytes-interpolation bugs in error response formatting

## [5.157.0] — RC Cycle 84: Module Exports & Safety Fixes

### Added
- Added `__all__` to `constants.py` (18 public constants)
- Added `__all__` to `logging_config.py` (6 constants + 3 public functions)
- Added `__all__` to `scan_state_map.py` (10 constants + 6 public functions)

### Changed
- Replaced bare `assert` with `TypeError` in `threadpool.py` stop setter
- Removed unguarded `sys.path.insert` hack in `security_integration.py`

## [5.156.0] — RC Cycle 83: Modernize test/ & Top-level Typing

### Changed
- Ran `pyupgrade --py39-plus` on 10 test files and 7 top-level Python files
- Modernized type annotations to Python 3.9+ syntax (22 files, 41 ins, 54 del)

## [5.155.0] — RC Cycle 81: Modernize Typing Annotations

### Changed
- Ran `pyupgrade --py39-plus` across 170 files to modernize type annotations
- `typing.List` → `list`, `typing.Dict` → `dict`, `typing.Set` → `set`, `typing.Tuple` → `tuple`
- `typing.Optional[X]` → `X | None`, `typing.Union[X, Y]` → `X | Y`
- Removed Python 3.7 compatibility shims (version-gated TypedDict fallbacks)

## [5.154.0] — RC Cycle 80: String Concat & Misc Cleanup

### Changed
- Replaced 8 string concatenation operations with f-strings in `sflib/config.py` (6) and `sflib/helpers.py` (2)
- Removed redundant `.keys()` in membership tests in `helpers.py` and `core/scan.py`
- Removed unnecessary `else` after `return` in `session_security.py` (2 instances)
- Simplified `True if x == "1" else False` to `x == "1"` in `sflib/config.py`

## [5.153.0] — RC Cycle 78: Final Annotations on Constants

### Changed
- Added `typing.Final` to 18 constants in `constants.py` (ports, URLs, timeouts, limits)
- Added `typing.Final` to 6 constants in `logging_config.py` (log format strings)
- Added `typing.Final` to 10 constants in `scan_state_map.py` (DB status strings)

## [5.152.0] — RC Cycle 77: Comprehensions & Misc Cleanup

### Changed
- Converted 6 for-append loops to list comprehensions / `list()` / `extend()` in `sflib/helpers.py`, `sflib/core.py`, `webui/scan.py`
- Also removed redundant `list(dict.keys())` to direct `in dict` membership test
- Added `encoding='utf-8'` to last bare `open()` call in `cli_service.py`
- Added `-> None` return type to 2 `__init__` methods (`SpiderFootModuleLoader`, `SpiderFootDb`)

## [5.151.0] — RC Cycle 76: Remove Unused Imports & DB Type Hints

### Changed
- Removed ~47 unused imports across 39 files via Pylance `source.unusedImports` refactoring
- Added return type hints to 4 DB facade methods: `scanInstanceSet`, `scanConfigDelete`, `scanLogEvent`, `scanResultDelete`

## [5.150.0] — RC Cycle 74: Immutable Target Types

### Changed
- Converted `_validTypes` from mutable `list` to immutable `frozenset` in `target.py`
- Provides O(1) membership testing (was O(n) list scan) and prevents accidental mutation
- Updated class-level type annotation to `typing.FrozenSet[str]`
- Updated docstring attribute type from `typing.List[str]` to `typing.FrozenSet[str]`

## [5.149.0] — RC Cycle 73: helpers.py Type Hints

### Changed
- Added type hints to 5 remaining untyped public methods in `helpers.py` (100% coverage)
- Methods: `loadModulesAsDict`, `loadCorrelationRulesRaw`, `sanitiseInput`, `fixModuleImport`, `fix_module_for_tests`

## [5.148.0] — RC Cycle 72: Raise From Exception Chaining

### Fixed
- Added `from e` to 7 `raise` statements in `except` blocks across 4 files
- Files: `api_security.py`, `api_security_fastapi.py`, `api_gateway.py`, `llm_client.py` (4 fixes)
- Preserves original traceback context per PEP 3134

## [5.147.0] — RC Cycle 70: Plugin Type Hints

### Changed
- Added parameter type hints to 10 public methods in `plugin.py` (sendEvent, setup, setTarget, setDbh, registerListener, setOutputFilter, notifyListeners, handleEvent, poolExecute, setSharedThreadPool)
- Fixed mutable default argument: `setup(userOpts={})` → `setup(userOpts=None)`
- Added `Callable` import to `typing` imports

## [5.146.0] — RC Cycle 69: Excess Blank Lines

### Changed
- Reduced 3+ consecutive blank lines to PEP 8 maximum of 2 in `security_middleware.py`, `db/__init__.py`, `api/routers/scan.py`

## [5.145.0] — RC Cycle 68: Trailing Whitespace Cleanup

### Changed
- Stripped trailing whitespace from 3,016 lines across 58 files

## [5.144.0] — RC Cycle 66: Lazy Log Formatting

### Changed
- Converted 269 f-string log calls to lazy `%` formatting across 27 files
- Avoids unnecessary string interpolation when log level is disabled (perf)

## [5.143.0] — RC Cycle 65: PEP 257 Docstring Cleanup

### Changed
- Added trailing period to 95 single-line docstrings across 13 files (PEP 257)

## [5.142.0] — RC Cycle 64: Centralize Log Format Strings

### Added
- `LOG_FORMAT_SECURITY`, `LOG_FORMAT_SECURITY_CONSOLE`, `LOG_FORMAT_NAMED` constants in `logging_config.py`

### Changed
- Wired constants into `security_logging.py` (3 inline formats removed) and `service_runner.py` (1)

## [5.141.0] — RC Cycle 63: Logger Formatter Performance Fix

### Fixed
- `SpiderFootLogHandler.format()` — cached `Formatter` as instance attribute (was creating new one per call)
- Wired `LOG_FORMAT_TEXT`/`LOG_FORMAT_DEBUG` constants into `logger.py` (replaced 3 inline format strings)

## [5.140.0] — RC Cycle 61: os.path → pathlib Conversion

### Changed
- Converted `openapi_spec.py` `_read_version()` from `os.path` to `pathlib.Path`
- Converted `helpers.py` `loadCorrelationRulesRaw()` from `os.listdir`/`os.path.join` to `Path.glob()`
- Removed unused `os` import from `openapi_spec.py`

## [5.139.0] — RC Cycle 60: Remove Redundant Coding Declarations

### Changed
- Removed `# -*- coding: utf-8 -*-` from 65 Python files (redundant in Python 3)

## [5.138.0] — RC Cycle 59: Add `__repr__` to Core Classes

### Added
- `SpiderFootTarget.__repr__()` → `SpiderFootTarget('example.com', 'INTERNET_NAME')`
- `SpiderFootPlugin.__repr__()` → `SpiderFootPlugin('sfp_dns')`

## [5.137.0] — RC Cycle 58: Explicit File Encoding

### Fixed
- Added `encoding='utf-8'` to 10 bare `open()` calls across 7 files
- Fixed file handle leak in `logger.py` (bare `open().close()` → `with` block)
- Files fixed: secret_manager.py (4), logger.py (1), helpers.py (1), openapi_spec.py (1), db_migrate.py (1), security_integration.py (1), core/server.py (1)

## [5.136.0] — RC Cycle 56: TODO Comment Cleanup

### Changed
- Converted 3 remaining TODO/Todo comments to tracked `NOTE(v6)` / `Note: Future:` comments
- target.py, sflib/helpers.py, helpers.py — zero TODO/FIXME/HACK/XXX in production code

## [5.135.0] — RC Cycle 55: Shutdown Module Consolidation

### Removed
- Deleted `shutdown_manager.py` (superseded by `graceful_shutdown.py`)

### Changed
- Migrated api/main.py and api/routers/health.py to `get_shutdown_coordinator()`
- Added `registered_services()` and `status()` compat methods to `ShutdownCoordinator`

## [5.134.0] — RC Cycle 54: Logger Naming Standardization

### Changed
- Renamed `logger` → `log` in 12 files (142 replacements) for codebase consistency
- Fixed logger name collision: `shutdown_manager.py` and `graceful_shutdown.py` both used `"spiderfoot.shutdown"`

## [5.133.0] — RC Cycle 53: Scan State Enum Deduplication

### Changed
- Replaced local `ScanState` enum in `scan_scheduler.py` with import from canonical `scan_state.py`
- Removed unused `ScanStatus` enum from `api/schemas.py`
- Mapped scheduler's local enum values (ABORT_REQUESTED→STOPPING, ABORTED→CANCELLED, FINISHED→COMPLETED, ERROR→FAILED)

## [5.132.0] — RC Cycle 51: Database Type Annotations

### Changed
- Added return type annotations to 26 `SpiderFootDb` facade methods
- Added `typing` imports (`Any`, `Dict`, `List`, `Optional`) to db package
- Typed parameters: `scan_id: str`, `optMap: dict`, `sfEvent: Any`, etc.

## [5.131.0] — RC Cycle 50: Scan Status Constants

### Changed
- Created 10 named `DB_STATUS_*` constants in `scan_state_map.py`
- Replaced 60 bare magic strings (`"FINISHED"`, `"ABORTED"`, `"ERROR-FAILED"`,
  `"ABORT-REQUESTED"`, `"RUNNING"`, `"STARTED"`, `"STARTING"`) across 9 files
- Key files: scanner.py (31), api/routers/scan.py (7), core/scan.py (5),
  scan_hooks.py (4), webui/scan.py (3), scan_metadata_service.py (3)

## [5.130.0] — RC Cycle 49: Hardcoded URL/Default Constants

### Changed
- Added 5 new constants to `constants.py`: `DEFAULT_OPENAI_BASE_URL`,
  `DEFAULT_OLLAMA_BASE_URL`, `DEFAULT_VLLM_BASE_URL`, `DEFAULT_DOH_URL`,
  `DEFAULT_DATABASE_NAME`
- Wired into llm_client.py, rag_pipeline.py, embedding_service.py,
  dns_service.py, data_service/factory.py, webui/routes.py

## [5.129.0] — RC Cycle 48: Missing Package Init

### Added
- `spiderfoot/scan_service/__init__.py` with docstring and `__all__`

## [5.128.0] — RC Cycle 46: Module-Level Docstrings

### Added
- Module-level docstrings to 14 core infrastructure files:
  plugin.py, event.py, target.py, db/__init__.py, sflib/__init__.py,
  sflib/core.py, sflib/helpers.py, sflib/network.py, sflib/config.py,
  helpers.py, logger.py, threadpool.py, __version__.py, api/__init__.py

## [5.127.0] — RC Cycle 45: `__all__` Exports

### Added
- `__all__` to sflib/helpers.py (15 public functions)
- `__all__` to sflib/__init__.py (18 re-exported symbols)
- Wildcard imports now expose only the intended public API

## [5.126.0] — RC Cycle 44: Security Hardening

### Security
- Replaced hardcoded `'default-secret'` CSRF fallback with `secrets.token_hex(32)` + warning log
- Scoped global `ssl._create_unverified_context` override to per-instance `_ssl_context` in sflib/core.py

## [5.125.0] — RC Cycle 43: Silent Exception Cleanup (Batch 5)

### Changed
- Fixed final 14 `except: pass` blocks across 7 files
- core/performance.py (3 Redis ops), db/__init__.py (4), db/db_event.py (2),
  eventbus/nats_bus.py (1), helpers.py (1), sflib/network.py (1), correlation_service.py (1)
- **Total silent exceptions fixed across RC38–43: 62 blocks**

## [5.124.0] — RC Cycle 42: Silent Exception Cleanup (Batch 4)

### Changed
- Fixed 14 `except: pass` blocks across 8 files
- benchmark.py (2), event_indexer.py (1), api_security.py (1),
  rate_limit_middleware.py (1), llm_client.py (2), scan_service/scanner.py (3),
  sflib/network.py (3), webui/scan.py (1)

## [5.123.0] — RC Cycle 41: Silent Exception Cleanup (Batch 3)

### Changed
- Fixed 13 `except: pass` blocks across 11 files
- alert_rules.py, audit_log.py, db_migrate.py, event_pipeline.py,
  hot_reload.py, module_health.py, eventbus_hardening.py, api_gateway.py,
  correlation_service.py (2), export_service.py (2), openapi_spec.py

## [5.122.0] — RC Cycle 39: Silent Exception Cleanup (Batch 2)

### Changed
- Fixed 10 more `except Exception: pass` blocks with debug logging
- api/routers/config.py (4), rag_correlation.py (3), retry.py (3)

## [5.121.0] — RC Cycle 38: Silent Exception Cleanup (Batch 1)

### Changed
- Fixed 11 `except Exception: pass` blocks in api/routers/scan.py with contextual debug logging
- Covers scan hooks, state machine, config retrieval, metadata copy, log export

## [5.120.0] — RC Cycle 37: Unused Import Cleanup

### Removed
- Removed unused imports from 5 API layer files: SecureConfigManager, get_app_config, Query, ValidationError, Callable/List

## [5.119.0] — RC Cycle 36: Debug Print Cleanup

### Changed
- Replaced 3 `print(f"[DEBUG]...")` calls with `self.log.debug()` in correlation/rule_executor.py

## [5.118.0] — RC Cycle 34: Port Constants

### Changed
- Replaced hardcoded 8001/5001 port numbers with `DEFAULT_API_PORT`/`DEFAULT_WEB_PORT` from `constants.py`
- Updated in `app_config.py`, `core/config.py`, `core/server.py`, `core/validation.py`

## [5.117.0] — RC Cycle 33: TTL Constants

### Changed
- Replaced 20+ hardcoded `3600` values with `DEFAULT_TTL_ONE_HOUR` from `constants.py` across 14 files
- Covers session timeout, JWT expiry, cache TTL, rate limit windows, CSRF token lifetime

## [5.116.0] — RC Cycle 32: Constants Module

### Added
- Created `spiderfoot/constants.py` with 12 named constants for commonly used magic numbers

### Changed
- Replaced 23 hardcoded `0.2` retry backoff values with `DB_RETRY_BACKOFF_BASE` across 5 db module files

## [5.115.0] — RC Cycle 31: DB Duplicate Fix

### Fixed
- Removed thin delegate `close()` that shadowed the full 35-line resource cleanup in `db/__init__.py`
- Removed thin delegate `create()` that shadowed the full schema creation implementation

## [5.114.0] — RC Cycle 29: Plugin Dead Stub Removal

### Removed
- Removed 135 lines of dead stub methods from plugin.py
- 13 early stub methods that were shadowed by full implementations later in the class
- Removed orphaned `_run()` method (only caller was the dead early `start()`)
- Early stubs used wrong attribute names (`_scanId` vs `__scanId__`, `_dbh` vs `__sfdb__`)

## [5.113.0] — RC Cycle 28: Scan Endpoint Deduplication

### Removed
- Removed ~850 lines of duplicated methods in webui/scan.py
- 22 methods were copy-pasted 3-4 times, all shadowed by the last definition
- File reduced from 1,551 lines to 700 lines with 37 unique methods

## [5.112.0] — RC Cycle 27: Stub Module Flags

### Changed
- Marked 11 stub modules as `experimental` (sfp_ethereum, sfp_tron, sfp_bnb, sfp_openwifimap, sfp_unwiredlabs, sfp_wificafespots, sfp_wifimapio, sfp_instagram, sfp_rubika, sfp_soroush, sfp_whatsapp)
- All 11 have no-op `handleEvent()` methods — flag warns users they are not yet functional

## [5.111.0] — RC Cycle 26: Placeholder Endpoint Fixes

### Changed
- Replaced fake scan result endpoint with `NotImplementedError` in webui/performance.py
- Removed `(placeholder)` from workspace API response messages
- Replaced fake report download returning `"{}"` with HTTP 501 in webui/workspace.py
- Replaced placeholder CVE lookup with debug logging per source in sflib/core.py

## [5.110.0] — RC Cycle 24: Code Quality Cleanup

### Changed
- Added debug logging to 4 silent `except: pass` blocks in module_loader.py

### Removed
- Deleted commented-out `create_workflow` code from workspace.py

## [5.109.0] — RC Cycle 23: Final Print Cleanup

### Changed
- Converted 22 `print()` startup banner calls to `self.log.info()` in core/server.py

## [5.108.0] — RC Cycle 22: Dead Code Removal

### Removed
- Deleted 13 dead code files (4,022 lines): web_security_cherrypy.py, session_security_cherrypy.py, api_security_fastapi.py, rate_limiting_unified.py, security_migration.py, security_integration.py, db.py (shadowed), sflib/logging.py, webui/main.py, cli/history.py, correlation/external_checker.py, correlation/schema.py, core/error_handling.py
- Cleaned up security/__init__.py `__all__` list

## [5.107.0] — RC Cycle 21: Dead Import Cleanup

### Removed
- Removed unused imports from 6 files: cherrypy/wraps/secrets/InputValidator from web_security.py, duplicate import sys from __init__.py, unused sys from module_graph.py/plugin_test.py/sfp_tool_wappalyzer.py, unused wraps/JSONResponse from api_security_fastapi.py

## [5.106.0] — RC Cycle 19: Test Infrastructure Cleanup

### Removed
- Deleted unused test files: filesystem_fixtures.py, test/mocks/ (4 files), coverage_helpers.py, assertion_helpers.py
- Removed stale `docs/conf.py:A` per-file-ignore from setup.cfg
- Removed unused pytest markers (threadreaper, no_threadreaper, webui_timeout)
- Removed dead `legacy_test_helpers` import from conftest.py

## [5.105.0] — RC Cycle 18: Broad Exception Cleanup

### Changed
- Narrowed `except Exception` to specific types in cache_service.py (OSError for file ops)
- Replaced 5 silent `except Exception: pass` in modern_plugin.py with specific exceptions + debug logging
- Changed `queue.get()` except from `Exception` to `queue.Empty`

## [5.104.0] — RC Cycle 17: TODO/FIXME Cleanup

### Changed
- Removed stale TODO in sfp_tool_dnstwist (already implemented)
- Improved error message in sfp_spider with URL context
- Re-enabled Gravatar location extraction with validation
- Fixed misleading docstrings in plugin.py (_updateSocket, tempStorage)

## [5.103.0] — RC Cycle 16: Stale Flask References

### Removed
- Removed unused `from flask import session, request, g` from session_security.py
- Removed dead Flask decorator code from rate_limiting.py (rate_limit, api_rate_limit, etc.)
- Removed broken `create_secure_app()`, `require_auth()`, `require_permission()` from web_security.py

### Changed
- Updated "Flask response object" docstrings to "HTTP response object"
- Updated security.md to remove "(requires Flask context)" notes

## [5.102.0] — RC Cycle 15: .dockerignore Reorganization

### Changed
- Deduplicated entries, organized into sections, added threadreaper pattern

## [5.101.0] — RC Cycle 14: setup.cfg Cleanup

### Fixed
- Fixed `flake8-max-line-length` → `max-line-length`
- Removed stale `spiderfoot/db.py:SFS101` per-file-ignore
- Removed redundant `[options] install_requires` section

## [5.100.0] — RC Cycle 13: print→logging (plugin.py, sfp__stor_db.py)

### Changed
- Converted last `print()` calls to `logging.getLogger()` in plugin.py and sfp__stor_db.py

## [5.99.0] — RC Cycle 12: print→logging (sfp__stor_db_advanced.py)

### Changed
- Converted 11 `print()` fallbacks to `_log` module-level logger calls

## [5.98.0] — RC Cycle 11: print→logging (DB/API)

### Changed
- Added logging to api_security.py, db/__init__.py, db/db_utils.py
- Converted 4 remaining `print()` calls to `log.error()`

## [5.97.0] — RC Cycle 10: Documentation Update

### Changed
- CHANGELOG.md, README.md updated with Release Candidate Cycles 1-10

## [5.96.0] — RC Cycle 9: traceback.format_exc() Cleanup

### Changed
- Replaced 12 `traceback.format_exc()` calls with `logger.exception()` / `exc_info=True`
- Removed 4 unused `import traceback` statements
- Files: module_sandbox.py, threadpool.py, plugin.py, core/modules.py, scanner.py, security_logging.py

## [5.96.0] — RC Cycle 8: Docker Compose Cleanup

### Changed
- Removed deprecated `version:` field from all 3 docker-compose files

## [5.95.0] — RC Cycle 7: Dockerfile Modernization

### Changed
- Base image upgraded from `bullseye` to `bookworm` (Debian 12)
- Added OCI metadata labels (`org.opencontainers.image.*`)
- Added `HEALTHCHECK` instruction for API endpoint
- Standardized `as` → `AS` build stage convention

## [5.94.0] — RC Cycle 6: Backup File Cleanup

### Removed
- Deleted 247 `.threadreaper_backup` files (16,539 lines of dead code)
- Added `*.threadreaper_backup` to `.gitignore`

## [5.93.0] — RC Cycle 5: Debug Print Removal

### Changed
- Removed 5 DEBUG print statements from production code
  - webui/scan.py, sfp_azureblobstorage.py, sflib/core.py
- Converted 5 DB `_log_db_error()` methods from `print()` to `logging`
  - db_scan.py, db_event.py, db_correlation.py, db_config.py, db_core.py

## [5.92.0] — RC Cycle 4: Bare Except Clause Fixes

### Changed
- Fixed all 10 bare `except:` clauses with specific exception types
  - `queue.Empty`, `ValueError`, `json.JSONDecodeError`, `Exception`
- Files: logger.py, routes.py, interactive.py, workspaces_enhanced.py, export.py,
  sfp__security_hardening.py, sfp__stor_db.py, sfp__stor_db_advanced.py

## [5.91.0] — RC Cycle 3: Print/Traceback Antipattern Fix

### Changed
- Replaced `print(traceback.format_exc())` with `logger.exception()` in data.py
- Removed inline `import traceback` statements

## [5.90.0] — RC Cycle 2: requirements.txt Cleanup

### Changed
- Removed duplicate `uvicorn` and `python-multipart` entries
- Removed unused `ipaddr==2.2.0` dependency (stdlib `ipaddress` used instead)
- Removed `-i https://pypi.org/simple` (belongs in pip.conf)
- Pinned upper bounds for `fastapi`, `openai`, `telethon`, `websockets`, `markdown`
- Organized into logical sections with comments
- Removed stale Flask migration comments

## [5.89.0] — RC Cycle 1: Critical Security Fixes

### Security
- **CRITICAL**: Replaced `pickle.loads()` with `json.loads()` in performance.py (RCE prevention)
- **CRITICAL**: Eliminated traceback disclosure in webui/routes.py error handler
- **CRITICAL**: Sanitized hardcoded credentials in docstrings (3 files)

## [5.88.1] — Final Documentation Update (Cycle 100)

### Changed
- README.md, ARCHITECTURE.md, CHANGELOG.md updated with Cycles 92-100 entries
- This marks the completion of 100 improvement cycles

## [5.88.0] — Response Compression Middleware (Cycle 99)

### Added
- `spiderfoot/api/compression_middleware.py` — gzip compression for API responses
  - Configurable min size threshold and compression level
  - Content-type aware (JSON, CSV, STIX, SARIF, etc.)
  - Env vars: `SF_API_COMPRESS_MIN_SIZE`, `SF_API_COMPRESS_LEVEL`
- Wired into `main.py` middleware stack

## [5.87.0] — Scan Retry Endpoint (Cycle 98)

### Added
- `spiderfoot/api/routers/scan.py` — `POST /scans/{id}/retry`
  - Creates new scan from failed/aborted scan's config
  - Copies metadata (tags, annotations) with retry provenance
  - State validation (cannot retry running scans)

## [5.86.0] — Per-Module Config Validation (Cycle 97)

### Added
- `spiderfoot/api/routers/data.py` — `POST /data/modules/{name}/validate-config`
  - Type checking against default option types
  - Unknown option detection
  - API key requirement warnings
  - Returns effective config with errors/warnings

## [5.85.0] — Event Deduplication Detection (Cycle 96)

### Added
- `spiderfoot/api/routers/scan.py` — `GET /scans/{id}/dedup`
  - Fingerprints events by (type, data) pairs
  - Configurable threshold, shows module overlap
  - Dedup ratio metric

## [5.84.0] — Config Change History (Cycle 95)

### Added
- `spiderfoot/api/routers/config.py` — config audit trail
  - `GET /config/history` — in-memory config change log (capped at 200)
  - `GET /config/diff` — diff current config against defaults

## [5.83.0] — API Key Scoping (Cycle 94)

### Added
- `spiderfoot/api/routers/config.py` — scope-based key permissions
  - `GET /config/api-keys/scopes` — list available scope definitions
  - `PUT /config/api-keys/{id}/scopes` — assign scopes to a key
  - `GET /config/api-keys/{id}/scopes` — view key's current scopes
  - 7 predefined scopes: admin, read, scans, scans:read, config:read, export, webhooks

## [5.82.0] — Per-Event Annotations (Cycle 93)

### Added
- `spiderfoot/api/routers/scan.py` — event-level annotation CRUD
  - `GET /scans/{id}/annotations` — list annotations
  - `PUT /scans/{id}/annotations/{result_id}` — set annotation
  - `DELETE /scans/{id}/annotations/{result_id}` — remove annotation
  - Stored in scan metadata under `_annotations` key

## [5.81.0] — Streaming JSONL Export (Cycle 92)

### Added
- `spiderfoot/api/routers/export.py` — `GET /scans/{id}/export/stream`
  - Newline-delimited JSON (NDJSON) streaming for large scans
  - Event type filtering, no memory buffering
  - `application/x-ndjson` content type

## [5.80.1] — Documentation Update (Cycle 91)

### Changed
- ARCHITECTURE.md, CHANGELOG.md, README.md updated with Cycles 84-91 entries

## [5.80.0] — Graceful Shutdown Manager (Cycle 90)

### Added
- `spiderfoot/shutdown_manager.py` — centralized shutdown coordination
  - LIFO callback execution with per-service timeouts
  - SIGINT/SIGTERM signal handling + atexit integration
  - Thread-safe registration, status introspection
- `spiderfoot/api/main.py` — FastAPI lifespan context for shutdown
- `spiderfoot/api/routers/health.py` — `GET /health/shutdown` status endpoint

## [5.79.0] — Scan Search/Filter API (Cycle 89)

### Added
- `spiderfoot/api/routers/scan.py` — `GET /scans/search`
  - Filter by target (substring), status, tag, date range, module
  - Faceted results with status counts
  - Configurable sorting and offset/limit pagination

## [5.78.0] — Module Enable/Disable API (Cycle 88)

### Added
- `spiderfoot/api/routers/data.py` — runtime module management
  - `GET /data/modules/status` — view enable/disable state of all modules
  - `POST /data/modules/{name}/disable` — disable module at runtime
  - `POST /data/modules/{name}/enable` — re-enable module
  - `POST /data/modules/bulk-disable` — disable multiple modules at once
  - Thread-safe in-memory disabled-module set

## [5.77.0] — Scan Timeline Endpoint (Cycle 87)

### Added
- `spiderfoot/api/routers/scan.py` — `GET /scans/{id}/timeline`
  - Chronological event timeline with module attribution
  - Filter by event type, configurable limit
  - Summary statistics (event type counts, module counts, time range)

## [5.76.0] — Request ID Propagation (Cycle 86)

### Added
- `spiderfoot/data_service/http_client.py` — X-Request-ID header on outbound HTTP
- `spiderfoot/data_service/grpc_client.py` — x-request-id metadata on gRPC calls
- `spiderfoot/webhook_dispatcher.py` — X-Request-ID on webhook deliveries

## [5.75.1] — Response Schemas Wiring (Cycle 85)

### Added
- `spiderfoot/api/schemas.py` — 4 new response models (EntityTypes, ModuleList, ModuleDetail, RiskLevels)

### Changed
- Config router: wired `response_model=` on 5 endpoints
- Data router: wired `response_model=RiskLevelsResponse`

## [5.75.0] — Recurring Scan Schedule API (Cycle 84)

### Added
- `spiderfoot/recurring_schedule.py` — time-based scan scheduling
  - RecurringSchedule dataclass with interval/one-shot timing
  - RecurringScheduler with background check loop
  - Singleton factory, pause/resume support, max_runs limit
- `spiderfoot/api/routers/scan.py` — 6 schedule endpoints
  - `GET/POST /scans/schedules`, `GET/DELETE /scans/schedules/{id}`
  - `POST .../pause`, `POST .../resume`

## [5.74.1] — Documentation Update (Cycle 83)

### Changed
- README.md, ARCHITECTURE.md, CHANGELOG.md updated with Cycles 75-83 entries

## [5.74.0] — Module Dependency Graph (Cycle 82)

### Added
- `spiderfoot/api/routers/data.py` — `GET /data/modules/dependencies`
  - Module dependency graph showing producers/consumers per event type
  - Directed edges from producer to consumer modules
  - Identifies orphan producers and consumers

## [5.73.0] — Webhook Event Filtering (Cycle 81)

### Added
- `spiderfoot/api/routers/webhooks.py` — Event type discovery and filter management
  - `GET /webhooks/event-types` — lists all known event types by category
  - `PUT /webhooks/{id}/event-filter` — update event type subscription filter
  - Validates event types against known registry with warnings for unknowns

## [5.72.0] — Per-Endpoint Rate Limits (Cycle 80)

### Added
- `spiderfoot/api/rate_limit_middleware.py` — per-endpoint rate limit overrides
  - `SF_API_RATE_LIMIT_ENDPOINTS` env var for static overrides
  - Runtime management functions: `set_endpoint_override()`, `remove_endpoint_override()`
- `spiderfoot/api/routers/config.py` — rate limit management API
  - `GET /config/rate-limits` — view config + stats
  - `PUT /config/rate-limits/endpoints` — set per-endpoint override
  - `DELETE /config/rate-limits/endpoints` — remove override

## [5.71.0] — Bulk Scan Operations (Cycle 79)

### Added
- `spiderfoot/api/routers/scan.py` — bulk scan operations
  - `POST /scans/bulk/stop` — stop multiple scans
  - `POST /scans/bulk/delete` — delete multiple scans
  - `POST /scans/bulk/archive` — archive multiple scans
  - Per-scan results with summary counts

## [5.70.0] — Scan Tag Management (Cycle 78)

### Added
- `spiderfoot/api/routers/scan.py` — scan tag/label CRUD
  - `GET /scans/{id}/tags` — get tags
  - `PUT /scans/{id}/tags` — replace all tags
  - `POST /scans/{id}/tags` — add tags (merge)
  - `DELETE /scans/{id}/tags` — remove specific tags
  - Tags stored in scan metadata, normalized (lowercase, deduped, max 50)
- `spiderfoot/api/schemas.py` — `ScanTagsResponse` model

## [5.69.0] — Module Runtime Statistics (Cycle 77)

### Added
- `spiderfoot/api/routers/data.py` — `GET /data/modules/stats`
  - Aggregates timeout, output validation, and health stats per module
  - Consolidated view of module performance metrics

## [5.68.1] — CORS Middleware (Cycle 76)

### Added
- `spiderfoot/api/cors_config.py` — configurable CORS middleware
  - `SF_API_CORS_ORIGINS`, `SF_API_CORS_METHODS`, `SF_API_CORS_HEADERS`
  - Safety: disables credentials when origins="*"

## [5.68.0] — Body Size Limiter (Cycle 75)

### Added
- `spiderfoot/api/body_limit_middleware.py` — request size protection
  - Default 10MB general, 50MB for upload paths
  - `SF_API_MAX_BODY_SIZE`, `SF_API_MAX_UPLOAD_SIZE` env vars
  - Returns 413 Payload Too Large

## [5.67.1] — Documentation Update (Cycle 74)

### Changed
- README.md, ARCHITECTURE.md, CHANGELOG.md updated with Cycles 65-74 entries

## [5.67.0] — Scan Comparison Endpoint (Cycle 73)

### Added
- `spiderfoot/api/routers/scan.py` — `GET /scans/compare` endpoint
  - Takes two scan IDs, returns event-level diff
  - Groups by event type, shows only_in_a, only_in_b, common counts
  - Reports new/removed event types between scans

## [5.66.0] — API Key Rotation Endpoint (Cycle 72)

### Added
- `spiderfoot/api/routers/config.py` — `POST /config/api-keys/{id}/rotate`
  - Generates new key value preserving permissions
  - Tracks rotation count and timestamp
  - Returns new key (shown only once)

## [5.65.1] — Workspace Response Schemas (Cycle 71)

### Added
- `spiderfoot/api/schemas.py` — 7 new workspace response models
  - WorkspaceCreateResponse, WorkspaceDetailResponse, WorkspaceUpdateResponse
  - WorkspaceDeleteResponse, WorkspaceCloneResponse
  - TargetAddResponse, TargetDeleteResponse

### Changed
- `spiderfoot/api/routers/workspace.py` — response_model= on create/detail endpoints

## [5.65.0] — Correlation Export API (Cycle 70)

### Added
- `spiderfoot/api/routers/correlations.py` — `GET /scans/{id}/correlations/export`
  - CSV and JSON download of correlation results
  - Optional risk filter

## [5.64.1] — Comprehensive Config Validation (Cycle 69)

### Added
- `spiderfoot/api/routers/config.py` — `GET /config/validate`
  - Validates live running configuration
  - Checks AppConfig sections, environment variables, API key requirements
  - Returns severity-based report (error/warning/info)

## [5.64.0] — Health Check Deep Probes (Cycle 68)

### Added
- `spiderfoot/api/routers/health.py` — 4 new subsystem health checks
  - service_auth: ServiceTokenIssuer status and mode
  - scan_hooks: ScanLifecycleHooks event stats
  - module_timeout: ModuleTimeoutGuard configuration and stats
  - output_validator: ModuleOutputValidator mode and violation counts

## [5.63.1] — Wire Pagination into More Routers (Cycle 67)

### Changed
- `spiderfoot/api/routers/workspace.py` — list_workspaces and list_targets use PaginationParams
- `spiderfoot/api/routers/data.py` — list_modules uses PaginationParams with dict→list conversion

## [5.63.0] — Unified Scan Export API (Cycle 66)

### Added
- `spiderfoot/api/routers/export.py` — ExportService wired to REST API
  - `GET /scans/{id}/export` — unified export (format=json|csv|stix|sarif)
  - `GET /scans/{id}/export/stix` — convenience STIX 2.1 download
  - `GET /scans/{id}/export/sarif` — convenience SARIF download
  - Content-Disposition headers for file download

### Changed
- `spiderfoot/api/main.py` — export router added to versioned router list

## [5.62.1] — Documentation Update (Cycle 65)

### Changed
- README.md, ARCHITECTURE.md, CHANGELOG.md updated with Cycles 55-64 entries

## [5.62.0] — Module Output Validation (Cycle 64)

### Added
- `spiderfoot/module_output_validator.py` — runtime validation of module event output
  - ModuleOutputValidator with warn/strict/off modes (SF_MODULE_OUTPUT_VALIDATION)
  - Checks emitted events against producedEvents() declarations
  - Per-module statistics tracking (total, valid, undeclared counts)
  - Thread-safe with singleton via get_output_validator()

### Changed
- `spiderfoot/plugin.py` — both notifyListeners() methods now call output validator (best-effort)

## [5.61.0] — API Request Audit Logging (Cycle 63)

### Added
- `spiderfoot/api/audit_middleware.py` — structured audit logging for all API requests
  - AuditLoggingMiddleware: method, path, status, duration_ms, client_ip, request_id
  - User identity extraction (service tokens, bearer, basic — redacted)
  - Configurable: SF_API_AUDIT_ENABLED, SF_API_AUDIT_BODY, SF_API_AUDIT_EXCLUDE
  - Severity-based log levels (info/warning/error by status code)

### Changed
- `spiderfoot/api/main.py` — audit logging middleware installed after error handlers

## [5.60.1] — Wire Service Auth into Clients (Cycle 62)

### Changed
- `spiderfoot/data_service/http_client.py` — ServiceTokenIssuer fallback auth
- `spiderfoot/webui/api_client.py` — ServiceTokenIssuer fallback auth
- `docker-compose-microservices.yml` — SF_SERVICE_SECRET/TOKEN/NAME for all services

## [5.60.0] — Inter-service Authentication (Cycle 61)

### Added
- `spiderfoot/service_auth.py` — service-to-service authentication
  - ServiceTokenIssuer: static token (SF_SERVICE_TOKEN) or HMAC (SF_SERVICE_SECRET)
  - HMAC tokens: `<service>:<timestamp>:<hmac_sha256>`, cached for 80% of TTL
  - ServiceTokenValidator with constant-time comparison, clock skew tolerance
  - generate_service_secret() utility

## [5.59.0] — Module Execution Timeout Guard (Cycle 60)

### Added
- `spiderfoot/module_timeout.py` — per-module timeout enforcement
  - ModuleTimeoutGuard with context manager timed() and decorator wrap()
  - Configurable via SF_MODULE_TIMEOUT (default 300s), SF_MODULE_TIMEOUT_HARD
  - Hard interrupt via ctypes.pythonapi.PyThreadState_SetAsyncExc (CPython)
  - Per-module overrides, timeout log (ring buffer 200), stats()

## [5.58.0] — Scan Lifecycle Event Hooks (Cycle 59)

### Added
- `spiderfoot/scan_hooks.py` — EventBus-integrated scan lifecycle notifications
  - 8 event types: CREATED, STARTED, COMPLETED, ABORTED, FAILED, DELETED, ARCHIVED, UNARCHIVED
  - ScanLifecycleHooks: EventBus publishing to `scan.lifecycle` topic + local listeners
  - Event history tracking, per-scan filtering, statistics

### Changed
- `spiderfoot/api/routers/scan.py` — hooks wired into create/delete/stop/archive/unarchive

## [5.57.0] — Config Source Tracing + Environment API (Cycle 58)

### Added
- `spiderfoot/api/routers/config.py` — two new endpoints:
  - `GET /config/sources` — provenance report for all config keys (filter by source)
  - `GET /config/environment` — active SF_* env overrides, unknown vars, deployment info

## [5.56.1] — Rich OpenAPI Metadata (Cycle 57)

### Changed
- `spiderfoot/api/main.py` — enhanced FastAPI initialization
  - Detailed API description (auth, versioning, error format sections)
  - MIT license_info
  - 13 openapi_tags with descriptions (health, scans, workspaces, data, etc.)

## [5.56.0] — Structured API Error Responses (Cycle 56)

### Added
- `spiderfoot/api/error_handlers.py` — consistent JSON error envelope
  - ErrorDetail/ErrorResponse Pydantic models
  - Handlers for HTTPException, RequestValidationError, unhandled Exception
  - Domain-specific error codes (SCAN_NOT_FOUND, MODULE_NOT_FOUND, etc.)
  - install_error_handlers(app) for easy wiring

### Changed
- `spiderfoot/api/main.py` — error handlers installed after middleware

## [5.55.0] — Wire Pydantic response_model on Scan Router (Cycle 55)

### Added
- `spiderfoot/api/schemas.py` — response envelope models
  - MessageResponse, ScanCreateResponse, ScanDeleteResponse, ScanStopResponse
  - ScanMetadataResponse, ScanNotesResponse, ScanRerunResponse, ScanCloneResponse
  - FalsePositiveResponse

### Changed
- `spiderfoot/api/routers/scan.py` — 15+ endpoints now use response_model=
  - Return values changed from raw dicts to Pydantic model instances

## [5.54.1] — Wire Startup/Shutdown into Entry Points (Cycle 54)

### Changed
- `sfapi.py` — runs StartupSequencer.wait_for_ready_sync() in microservice mode before uvicorn
- `sfapi.py` — installs ShutdownCoordinator signal handlers for SIGTERM/SIGINT
- `docker-entrypoint.sh` — auto-detects SF_SERVICE_ROLE from command arguments

## [5.54.0] — Graceful Shutdown Coordination (Cycle 53)

### Added
- `spiderfoot/graceful_shutdown.py` — priority-ordered shutdown with signal handling
  - ShutdownCoordinator with drain timeout (15s), force timeout (30s)
  - Priority-ordered handler registration (lower = first)
  - In-flight request tracking (track_request/release_request)
  - SIGTERM/SIGINT handlers with atexit fallback
  - Async handler support, singleton via get_shutdown_coordinator()

## [5.53.0] — Service Startup Sequencer (Cycle 52)

### Added
- `spiderfoot/startup_sequencer.py` — ordered dependency verification
  - DependencyProbe ABC with TcpProbe, HttpProbe, PostgresProbe, RedisProbe, NatsProbe
  - Auto-discovery of required probes by service role (api/scanner/webui)
  - Async wait_for_ready() with configurable retry/backoff (max 30 retries)
  - ProbeResult/StartupResult dataclasses with summary()

## [5.52.0] — Proto Schema Expansion (Cycle 51)

### Changed
- `proto/spiderfoot.proto` — expanded from ~290 to ~470 lines
  - 15 new DataService RPCs (SetScanStatus, metadata, notes, archive, batch events, etc.)
  - New CorrelationService (AnalyzeScan, ListRules, TestRule)
  - EventRecord expanded with visibility, risk, false_positive, source_data
  - 28 new message types

## [5.51.0] — ConfigService Microservice Enhancements (Cycle 50)

### Changed
- `spiderfoot/config_service.py` — config source tracing + 15 new env vars
  - Source tracking per key (default/file/env/runtime)
  - 15 new SF_* env vars for microservice configuration
  - New properties: is_microservice, service_role, service_name
  - discover_env_vars() flags unknown SF_* vars

## [5.50.0] — Module Interface Contracts (Cycle 49)

### Added
- `spiderfoot/module_contract.py` — typed module interface validation
  - SpiderFootModuleProtocol (runtime-checkable Protocol)
  - ModuleMeta Pydantic schema for meta dict validation
  - validate_module() / validate_module_batch() with diagnostics

### Changed
- `spiderfoot/module_registry.py` — non-blocking contract validation during discover()

## [5.49.0] — Pydantic Schemas for Service Boundaries (Cycle 48)

### Added
- `spiderfoot/api/schemas.py` — Pydantic v2 service boundary contracts
  - EventCreate/EventResponse with from_db_row() migration helper
  - ScanCreate/ScanResponse/ScanListResponse
  - ScanLogEntry/Create, ConfigEntry/Update
  - CorrelationResult/Summary, PaginationMeta/PaginatedResponse
  - ScanStatus enum (8 states)

## [5.48.0] — API Versioning with /api/v1/ Prefix (Cycle 47)

### Added
- `spiderfoot/api/versioning.py` — API versioning infrastructure
  - ApiVersionMiddleware (X-API-Version, Deprecation, Sunset, Link headers)
  - mount_versioned_routers() for dual-mount at /api/v1/ and /api/

### Changed
- `spiderfoot/api/main.py` — routes dual-mounted via versioning system
- `spiderfoot/api/routers/health.py` — added GET /version endpoint

## [5.47.0] — Per-Service Docker Isolation (Cycle 46)

### Changed
- `docker/Dockerfile.webui` — WebUI only on sf-frontend network
- `docker/Dockerfile.scanner` — scanner uses HTTP DataService
- `docker-compose-microservices.yml` — network isolation enforced

## [5.46.0] — WebUI API Proxy Layer (Cycle 45)

### Added
- `spiderfoot/webui/api_client.py` — HTTP client mimicking SpiderFootDb
- `spiderfoot/webui/db_provider.py` — dual-mode mixin (local or API proxy)

## [5.45.0] — Extract ScanMetadataService (Cycle 44)

### Added
- `spiderfoot/scan_metadata_service.py` — extracted from ScanServiceFacade

## [5.44.1] — Circuit Breaker for Remote DataService (Cycle 43)

### Added
- `spiderfoot/data_service/resilient.py` — DataServiceCircuitBreaker + ResilientDataService

## [5.44.0] — gRPC DataService Client (Cycle 42)

### Added
- `spiderfoot/data_service/grpc_client.py` — protobuf DataService backend

## [5.43.1] — DataService Health Check (Cycle 41)

### Changed
- `spiderfoot/api/routers/health.py` — added DataService probe

## [5.43.0] — HTTP DataService Client (Cycle 40)

### Added
- `spiderfoot/data_service/http_client.py` — REST DataService backend
- `spiderfoot/data_service/factory.py` — create_data_service() factory

## [5.42.0] — Domain Sub-Packages (Cycle 39)

### Changed
- Reorganized code into domain sub-packages for better organization

## [5.41.0] — Migrate ScanService Events to EventRepository (Cycle 38)

### Changed
- ScanService now uses EventRepository instead of raw database handles

## [5.40.0] — Framework-Agnostic Security (Cycle 37)

### Changed
- Security middleware decoupled from Flask, works with any ASGI/WSGI framework
- Flask dependency deprecated

## [5.39.0] — Replace Monkey-Patching with functools.wraps (Cycle 36)

### Changed
- Replaced all monkey-patching in decorators with proper functools.wraps

## [5.38.0] — Unified Scan State Mapping (Cycle 35)

### Added
- `spiderfoot/scan_state_map.py` — canonical scan state definitions

## [5.37.0] — Generate gRPC Stubs (Cycle 34)

### Changed
- Generated gRPC Python stubs from proto/spiderfoot.proto
- Wired stubs into grpc_service.py

## [5.36.0] — Add gRPC Dependencies (Cycle 33)

### Changed
- `requirements.txt` — added grpcio, grpcio-tools, protobuf

## [5.35.0] — Fix Silent Error Swallowing (Cycle 32)

### Fixed
- `spiderfoot/service_integration.py` — errors now properly logged instead of silently swallowed

## [5.21.0] — Database Migration Framework

### Added
- `spiderfoot/db_migrate.py` — Version-controlled schema evolution
  - Sequential numbered migration files with `upgrade()`/`downgrade()`
  - Migration tracking table (`_sf_migrations`) with checksums
  - Dry-run mode, scaffold generation, checksum validation
  - SQLite and PostgreSQL dialect support
  - Migration event callbacks

## [5.20.1] — Module Dependency Resolver

### Added
- `spiderfoot/module_resolver.py` — Runtime module load-order resolution
  - `ModuleDescriptor` with watched/produced/required/optional event interfaces
  - Backward-walking resolution from target events to minimal module set
  - Topological sort (Kahn's algorithm) with cycle detection
  - Dependency satisfaction checking and diagnostics
  - Automatic module directory scanning

## [5.20.0] — Scan Queue with Backpressure

### Added
- `spiderfoot/scan_queue.py` — Bounded priority work queue
  - Three priority lanes: HIGH / NORMAL / LOW with fair-share dequeue
  - Backpressure actions: BLOCK, REJECT, DROP_OLDEST
  - Pressure monitoring (0.0–1.0) with level transition callbacks
  - Batch dequeue, requeue with retry tracking
  - Dead-letter queue for permanently failed items

## [5.19.2] — Error Telemetry

### Added
- `spiderfoot/error_telemetry.py` — Centralised error capture and analysis
  - Full context capture (exception, traceback, module, scan, event type)
  - Fingerprint-based error grouping and deduplication
  - Auto-classification (TRANSIENT_NETWORK, AUTH, DATA_PARSE, TIMEOUT, etc.)
  - Sliding-window error rate tracking (global and per-module)
  - Ring buffer of recent errors with filtered queries
  - Alert rules with configurable thresholds and callbacks

## [5.19.1] — API Versioning Framework

### Added
- `spiderfoot/api_versioning.py` — API version lifecycle management
  - `VersionStrategy`: URL_PREFIX, HEADER, QUERY, ACCEPT negotiation
  - `APIVersion` lifecycle: BETA → CURRENT → DEPRECATED → SUNSET
  - `VersionedRoute` management with cross-version route copying
  - Response transforms between versions
  - Deprecation headers (Sunset, Link successor-version)
  - Compatibility checking

## [5.19.0] — Secret Management

### Added
- `spiderfoot/secret_manager.py` — Secure credential management
  - Four backends: Memory, Environment, File (JSON), Encrypted File (PBKDF2+XOR)
  - Rotation tracking with configurable rotation periods
  - Access auditing with bounded log
  - Redaction of secret values in text output
  - Config injection for module API keys

## [5.18.2] — Performance Benchmarking

### Added
- `spiderfoot/benchmark.py` — Performance benchmarking suite
  - `BenchmarkResult` with ops/sec, p50/p95/p99 latencies, stdev
  - 7 built-in benchmarks: EventBus, Cache, RateLimiter, WorkerPool, Serialization, Threading, Hash
  - GC-disabled high-precision timing
  - `BenchmarkSuite` composable runner with JSON report output

## [5.18.1] — Distributed Scan Coordinator

### Added
- `spiderfoot/scan_coordinator.py` — Multi-node scan distribution
  - `ScannerNode` with capacity tracking, tags, heartbeat monitoring
  - 4 distribution strategies: LEAST_LOADED, ROUND_ROBIN, HASH_BASED, RANDOM
  - Tag-based node filtering
  - Automatic failover with work reassignment
  - Priority queue with timeout detection

## [5.18.0] — Plugin Testing Framework

### Added
- `spiderfoot/plugin_test.py` — Drop-in test harness for modules
  - `PluginTestHarness` with factory methods `for_module()` / `for_class()`
  - `FakeSpiderFoot` mock facade with real helper implementations
  - `EventCapture` with rich query API (of_type, find, has, count)
  - HTTP/DNS response mocking helpers
  - Assertion helpers (assert_produced, assert_not_produced, no_errors)

## [5.17.2] — OpenAPI Specification Generator

### Added
- `spiderfoot/openapi_spec.py` — Programmatic OpenAPI 3.1 spec
  - All REST API endpoints (scans, workspaces, data, config, correlations, etc.)
  - Component schemas, security schemes, reusable parameters
  - JSON/YAML output

## [5.17.1] — Data Retention Policies

### Added
- `spiderfoot/data_retention.py` — Automated data lifecycle management
  - Configurable retention rules with age/size/date criteria
  - Preview (dry-run) and enforce modes
  - `FileResourceAdapter` for file-based retention
  - Retention history tracking and statistics

## [5.17.0] — Scan Diff/Comparison

### Added
- `spiderfoot/scan_diff.py` — Scan result comparison
  - SHA-256 fingerprinted `Finding` objects
  - `ScanSnapshot` with import from event lists
  - `DiffResult` with added/removed/changed/unchanged findings
  - Set-based key comparison with content fingerprinting

## [5.16.2] — Audit Logging

### Added
- `spiderfoot/audit_log.py` — Immutable audit trail
  - 9 audit categories (AUTH, CONFIG, SCAN, DATA, MODULE, SYSTEM, EXPORT, API, ADMIN)
  - Multi-backend writes (Memory, File)
  - Audit hooks and convenience methods

## [5.16.1] — Notification Service

### Added
- `spiderfoot/notification_service.py` — Multi-channel notifications
  - 4 channels: Slack, Webhook, Email (SMTP), Log
  - Wildcard topic subscriptions
  - EventBus bridge for auto-trigger
  - Sync/async dispatch with stats

## [5.16.0] — CI/CD Pipeline Definitions

### Added
- `.github/workflows/ci.yml` — Lint + test matrix (Python 3.9–3.12)
- `.github/workflows/docker.yml` — Multi-stage Docker build + Trivy scan
- `.github/workflows/helm.yml` — Helm chart lint + OCI push
- `.github/workflows/release.yml` — Auto GitHub releases with changelog

## [5.15.2] — Rate Limiter Service

### Added
- `spiderfoot/rate_limiter.py` — Pluggable rate limiting
  - 3 algorithms: TOKEN_BUCKET, SLIDING_WINDOW, FIXED_WINDOW
  - Per-key rate limits with configurable burst
  - Rate limit headers (X-RateLimit-*)

## [5.15.1] — Plugin Marketplace Registry

### Added
- `spiderfoot/plugin_registry.py` — Module discovery and management
  - `PluginManifest` with rich metadata
  - Install from file/URL, uninstall, enable/disable/pin
  - Auto-scan modules directory, state persistence

## [5.15.0] — Kubernetes Helm Chart

### Added
- `helm/spiderfoot/` — Production K8s deployment
  - Chart.yaml, values.yaml, 6 deployment/service templates
  - Ingress, ServiceAccount, PVC, Secrets, HPA
  - PostgreSQL + Redis sub-charts

## [5.14.0] — Retry/Recovery Framework

### Added
- `spiderfoot/retry.py` — Configurable retry with backoff
  - Strategies: FIXED, EXPONENTIAL, LINEAR, NONE
  - Dead-letter queue for permanently failed operations
  - `@retry` decorator

## [5.13.2] — Module Hot-Reload

### Added
- `spiderfoot/hot_reload.py` — File change detection with syntax validation

## [5.13.1] — Scan Profiles/Templates

### Added
- `spiderfoot/scan_profile.py` — 10 built-in scan profiles
  - quick-recon, full-footprint, passive-only, etc.
  - ProfileManager with CRUD + JSON import/export

## [5.13.0] — WebSocket Event Streaming

### Added
- `spiderfoot/websocket_service.py` — Real-time scan events via WebSocket
  - Channel-based subscriptions per scan/module/event type
  - FastAPI WebSocket router integration

## [5.12.2] — Event Schema Validation *(removed in v5.33.0 — dead code)*

### Added *(subsequently deleted)*
- ~~`spiderfoot/event_schema.py` — Declarative event type schemas~~
  - 15 `DataFormat` validators (IPV4, DOMAIN, EMAIL, URL, etc.)
  - 70+ core event type schemas
  - `EventSchemaRegistry` singleton

## [5.12.1] — Module Dependency Graph

### Added
- `spiderfoot/module_graph.py` — Directed graph of module event relationships
  - Topological ordering, cycle detection
  - BFS output resolution
  - Mermaid/DOT export

## [5.12.0] — Export Service

### Added
- `spiderfoot/export_service.py` — Multi-format exporter (JSON/CSV/STIX/SARIF)

## [5.11.1] — Auth Middleware

### Added
- `spiderfoot/auth.py` — JWT/API-key/Basic authentication with RBAC
  - Roles: ADMIN, ANALYST, VIEWER, API
  - ASGI/WSGI integration

## [5.11.0] — Modern CLI

### Added
- `spiderfoot/cli_service.py` — argparse-based CLI (version, status, metrics, config, scan, correlate, modules)

## [5.10.2] — Health Checks

### Added
- `spiderfoot/health.py` — K8s-compatible liveness/readiness/startup probes

## [5.10.1] — Documentation

### Changed
- README.md and ARCHITECTURE.md initial comprehensive documentation

## [5.10.0] — Module Migration

### Added
- `modules/sfp_ipapico_modern.py`, `modules/sfp_ipinfo_modern.py` — Migration examples
- `documentation/MODULE_MIGRATION_GUIDE.md` — 6-step migration guide

## [5.9.2] — Correlation Service

### Added
- `spiderfoot/correlation_service.py` — Standalone correlation engine with EventBus triggers

## [5.9.1] — API Gateway

### Added
- `spiderfoot/api_gateway.py` — Circuit breaker, rate limiting, dual-mode routing

## [5.9.0] — gRPC Interfaces

### Added
- `proto/spiderfoot.proto` — Protobuf service definitions
- `spiderfoot/grpc_service.py` — gRPC/HTTP dual-mode RPC

## [5.8.2] — ConfigService

### Added
- `spiderfoot/config_service.py` — 40+ env-var mappings, validation, hot-reload

## [5.8.1] — Service Integration Wiring

### Added
- `spiderfoot/service_integration.py` — Wires services into scan engine

## [5.8.0] — SpiderFootModernPlugin

### Added
- `spiderfoot/modern_plugin.py` — Service-aware plugin base class

## [5.7.1] — Prometheus Metrics

### Added
- `spiderfoot/metrics.py` — Counter/Gauge/Histogram, 18 pre-defined metrics

## [5.7.0] — Docker Microservices

### Added
- `docker/` — Dockerfile.base/scanner/api/webui, docker-compose-microservices.yml
- `spiderfoot/service_runner.py` — Unified entry point for microservices

## [5.6.2] — ScanScheduler

### Added
- `spiderfoot/scan_scheduler.py` — Priority-queue scan lifecycle management

## [5.6.1] — WorkerPool

### Added
- `spiderfoot/worker_pool.py` — Thread/process pool for module execution

## [5.6.0] — ServiceRegistry

### Added
- `spiderfoot/service_registry.py` — Dependency injection container

## [5.5.3] — CacheService

### Added
- `spiderfoot/cache_service.py` — Memory/File/Redis caching

## [5.5.2] — DnsService

### Added
- `spiderfoot/dns_service.py` — DNS resolution with TTL cache

## [5.5.1] — HttpService

### Added
- `spiderfoot/http_service.py` — Connection-pooled HTTP client

## [5.5.0] — DataService

### Added
- `spiderfoot/data_service/` — DB abstraction layer

## [5.4.2] — Vector.dev Integration

### Added
- `spiderfoot/vector_sink.py` — Event/log/metric pipeline
- `config/vector.toml` — Vector.dev pipeline configuration

## [5.4.1] — Structured Logging

### Added
- `spiderfoot/structured_logging.py` — JSON structured logging

## [5.4.0] — EventBus

### Added
- `spiderfoot/eventbus/` — Pub/sub messaging (Memory, Redis Streams, NATS JetStream)
