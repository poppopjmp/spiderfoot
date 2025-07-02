# SpiderFoot Modularization Roadmap

This document provides a step-by-step, risk-aware plan to refactor the main SpiderFoot entrypoints (`sf.py`, `sfcli.py`, `sfwebui.py`, `sfapi.py`) and the core library into a modular, maintainable, and testable architecture.

---

## Per-File Modularization Roadmap & Risk Analysis

### 1. sf.py (Main Entrypoint)
- **Current Role:** CLI and server entrypoint, scan orchestration, module loading, config, process management.
- **Plan:**
  - Move scan orchestration (scan startup, validation, process management, signal handling) to `scan_service.py`.
  - Move module loading (dynamic import, fallback logic) to `module_loader.py`.
  - Move config logic (default config, config merging, validation) to `config.py`.
  - Move server startup (web and API) to `web_server.py` and `api_server.py`.
  - Keep only argument parsing, high-level orchestration, and error handling in `sf.py`.
- **Risks & Mitigation:**
  - *Hidden config dependencies*: Grep for all config usage, refactor in small steps, add config unit tests.
  - *Process/threading bugs*: Use integration tests for scan startup, keep wrappers until stable.
- **First Steps:**
  1. Move all config-related code to `config.py`.
  2. Move scan startup and process management to `scan_service.py`.
  3. Move module loading logic to `module_loader.py`.
  4. Refactor `sf.py` to use these modules, keeping only CLI argument parsing and orchestration.

### 2. sfcli.py (Command-Line Interface)
- **Current Role:** CLI command parsing, output formatting, server communication, command history, interactive shell.
- **Plan:**
  - Move command handlers (all `do_*` methods) to `cli/commands.py`.
  - Move output formatting (pretty tables, color, history, spooling) to `output_utils.py`.
  - Move server communication (HTTP requests, authentication, error handling) to `api_client.py`.
  - Move config logic to `config.py`.
  - Keep only the CLI shell, argument parsing, and command dispatch in `sfcli.py`.
- **Risks & Mitigation:**
  - *Tight coupling of output/commands*: Extract functions one at a time, keep wrappers if needed, add snapshot tests.
  - *Auth/session handling*: Add unit tests for API client, ensure error cases are surfaced.
- **First Steps:**
  1. Extract output formatting to `output_utils.py`.
  2. Move HTTP request logic to `api_client.py`.
  3. Move command handlers to `cli/commands.py` and refactor shell to dispatch.
  4. Refactor config handling to use `config.py`.

### 3. sfwebui.py (Web UI)
- **Current Role:** CherryPy web server, route handlers, template rendering, config, scan/data export, error handling.
- **Plan:**
  - Move each logical group of route handlers to `webui/routes/`.
  - Move template helpers to `template_utils.py`.
  - Move data export to `export_utils.py`.
  - Move config logic to `config.py`.
  - Keep only app assembly, route registration, and minimal error handling in `sfwebui.py`.
- **Risks & Mitigation:**
  - *Tight coupling of routes/templates*: Extract one group at a time, add integration tests for web endpoints.
  - *Loss of features*: Test all UI features after each refactor.
- **First Steps:**
  1. Extract config management to `config.py`.
  2. Move data export logic to `export_utils.py`.
  3. Move template helpers to `template_utils.py`.
  4. Move route handlers to `webui/routes/` and refactor main class.

### 4. sfapi.py (REST API)
- **Current Role:** FastAPI app, Pydantic models, routers, config, websocket, background tasks, error handlers.
- **Plan:**
  - Move all Pydantic models to `api_models.py`.
  - Move each router to its own file in `api/`.
  - Move websocket manager to `websocket_manager.py`.
  - Move config logic to `config.py`.
  - Keep only app assembly, router inclusion, and error handler registration in `sfapi.py`.
- **Risks & Mitigation:**
  - *Circular imports, API breakage*: Move models first, then routers, update imports incrementally, verify with OpenAPI docs.
  - *Test coverage gaps*: Add/expand API endpoint tests.
- **First Steps:**
  1. Extract Pydantic models to `api_models.py`.
  2. Move routers to `api/` and update imports.
  3. Move websocket manager to `websocket_manager.py`.
  4. Refactor config handling to use `config.py`.

---

## spiderfoot/ Directory: Merge & Deduplication Opportunities

### 1. Config, Helpers, and Logging
- **Merge Plan:**
  - Consolidate all configuration logic into `spiderfoot/config.py` (remove `sflib/config.py`).
  - Merge all general-purpose helpers into `spiderfoot/helpers.py` (remove `sflib/helpers.py`).
  - Move all logging setup and helpers to `spiderfoot/logger.py` (remove `sflib/logging.py`).
  - Ensure no duplication between `sflib/` and top-level `spiderfoot/`.

### 2. Database Layer
- **Merge Plan:**
  - If CRUD/connection logic is duplicated, move shared code to `db_core.py` or `db_utils.py`.
  - Keep specialized logic in their respective files, but ensure all DB access patterns are consistent.

### 3. Scan Service
- **Merge Plan:**
  - Centralize all scan orchestration, process management, and threadpool logic in `scan_service/`.
  - If `threadpool.py` is only used by scan service, move it to `scan_service/threadpool.py`.

### 4. Correlation
- **Merge Plan:**
  - If `event_enricher.py`, `external_checker.py`, and `result_aggregator.py` are tightly coupled, consider merging them into a single `correlation/engine.py` or similar.
  - Keep rules and schema separate for clarity.

### 5. SFLib
- **Merge Plan:**
  - Remove duplication with top-level modules. Only keep what is unique to `sflib/` or merge into main modules.

### 6. Target, Plugin, Workspace
- **Merge Plan:**
  - If there is shared logic or base classes, consider a `core.py` for shared abstractions.
  - Centralize workspace logic in `workspace.py`.

### 7. Static, Templates, Dicts
- **Merge Plan:**
  - No merge needed, but ensure all static assets are referenced from a single place and not duplicated.

---

## Concrete Merge Steps
1. **Audit all helpers and config files** and merge into `spiderfoot/helpers.py` and `spiderfoot/config.py`.
2. **Move all logging setup to `spiderfoot/logger.py`** and remove `sflib/logging.py` if redundant.
3. **Refactor database utilities**: Move shared DB logic to `db_core.py` or `db_utils.py`.
4. **Centralize scan orchestration in `scan_service/scanner.py`** and move `threadpool.py` if only used there.
5. **Update imports throughout the codebase** to use the new, merged modules.
6. **Remove any now-empty or redundant files** after merging.

---

## Critical Step Review & Risk Analysis

For each modularization step, review the actual methods, classes, and file content. Key risks and mitigations:

1. **Centralize Configuration**
   - *Risk:* Hidden dependencies, divergent config needs, test breakage.
   - *Mitigation:* Refactor in small steps, add unit tests, grep for all config usage.
2. **Extract Output and Export Utilities**
   - *Risk:* Tight coupling with command/UI logic, API drift, loss of features.
   - *Mitigation:* Extract functions one at a time, add snapshot tests, keep wrappers if needed.
3. **Modularize API Models and Routers**
   - *Risk:* Circular imports, API breakage, test coverage gaps.
   - *Mitigation:* Move models first, then routers, update imports incrementally, verify with OpenAPI docs.
4. **Extract Scan Orchestration and Module Loading**
   - *Risk:* Process/threading bugs, state management issues, module loader edge cases.
   - *Mitigation:* Use integration tests, keep old code as wrappers, document state transitions.
5. **Centralize Server Communication**
   - *Risk:* Auth/session handling, error handling changes.
   - *Mitigation:* Add unit tests, ensure error cases are surfaced.
6. **Refactor Entry Points**
   - *Risk:* Startup breakage, loss of features.
   - *Mitigation:* Add integration tests, test all startup modes after each refactor.

---

## Benefits
- **Maintainability:** Smaller, focused modules are easier to test and maintain.
- **Reusability:** Shared logic is not duplicated.
- **Testability:** Each module can be unit tested independently.
- **Extensibility:** New interfaces can reuse core logic.

---

## Next Steps
- Start with Step 1: Move all config logic to `spiderfoot/config.py` and update all entrypoints to use it.
- Proceed step-by-step, testing after each major refactor.
- Use this roadmap as a checklist for the modularization process.


## 1. Centralize Configuration (`spiderfoot/config.py`)

### **Current State**
- Config logic is spread across:
  - `spiderfoot/sflib/config.py` (functions: `configSerialize`, `configUnserialize`)
  - Entry points (`sf.py`, `sfcli.py`, `sfwebui.py`, `sfapi.py`) have their own config loading/merging/validation logic.
  - Some config logic may be in `spiderfoot/sflib/core.py` and `spiderfoot/helpers.py`.

### **What to Move**
- All config serialization/deserialization, default config dicts, merging, and validation.
- Remove duplication between `sflib/config.py` and entrypoints.

### **Risks**
- **High:** Config is foundational; breaking changes can prevent the app from starting.
- **Mitigation:** Add unit tests for config loading/merging before/after refactor. Refactor one entrypoint at a time.

---

## 2. Merge Helpers (`spiderfoot/helpers.py`)

### **Current State**
- Helper functions are in both `spiderfoot/helpers.py` and `spiderfoot/sflib/helpers.py`.
- Many utility functions (hashing, IP/domain validation, URL parsing, etc.) are duplicated or similar.
- Some helpers are also methods in `spiderfoot/sflib/core.py`.

### **What to Move**
- All stateless, general-purpose helpers to `spiderfoot/helpers.py`.
- Remove or refactor class-based helpers in `core.py` to use the new helpers.

### **Risks**
- **Medium:** Helper functions are used everywhere; missing a refactor can cause runtime errors.
- **Mitigation:** Use search/replace and static analysis to update all imports. Add/expand unit tests for helpers.

---

## 3. Centralize Logging (`spiderfoot/logger.py`)

### **Current State**
- Logging logic is in both `spiderfoot/logger.py` and `spiderfoot/sflib/logging.py`.
- Some logging is handled in the `SpiderFoot` class (`core.py`).

### **What to Move**
- All logging setup, handlers, and helpers to `spiderfoot/logger.py`.
- Remove `sflib/logging.py` if redundant.

### **Risks**
- **Low/Medium:** Logging is less critical, but errors can make debugging harder.
- **Mitigation:** Test logging output after refactor.

---

## 4. Refactor Database Utilities

### **Current State**
- `spiderfoot/db/` contains: `db_core.py`, `db_utils.py`, `db_event.py`, `db_scan.py`, `db_correlation.py`, `db_config.py`.
- Some CRUD/connection logic is duplicated.

### **What to Move**
- Shared DB logic to `db_core.py` or `db_utils.py`.
- Keep specialized logic in respective files.

### **Risks**
- **High:** Database changes can break data storage/retrieval.
- **Mitigation:** Add/expand integration tests for DB operations. Refactor incrementally.

---

## 5. Centralize Scan Orchestration (`scan_service/scanner.py`)

### **Current State**
- Scan logic is in `scan_service/scanner.py` and entrypoints (`sf.py`, `sfwebui.py`).
- Threadpool logic is in `spiderfoot/threadpool.py`.

### **What to Move**
- All scan orchestration, process management, and threadpool logic to `scan_service/`.
- Move `threadpool.py` if only used by scan service.

### **Risks**
- **Medium/High:** Scan orchestration is core to SpiderFoot’s operation.
- **Mitigation:** Add/expand tests for scan start/stop, threadpool, and process management.

---

## 6. Modularize API Models and Routers

### **Current State**
- All Pydantic models and routers are in `sfapi.py`.

### **What to Move**
- Models to `spiderfoot/api_models.py`.
- Routers to `spiderfoot/api/` (e.g., `scan_router.py`, `workspace_router.py`).

### **Risks**
- **Low/Medium:** API breakage is possible, but isolated.
- **Mitigation:** Add/expand API tests.

---

## 7. Extract Output and Export Utilities

### **Current State**
- Output formatting and data export logic is in `sfcli.py` and `sfwebui.py`.

### **What to Move**
- Pretty-printing, table formatting to `output_utils.py`.
- Data export (CSV, Excel, JSON) to `export_utils.py`.

### **Risks**
- **Low:** Output errors are visible and easy to debug.
- **Mitigation:** Add/expand CLI and web UI tests.

---

## 8. Centralize Server Communication (`api_client.py`)

### **Current State**
- HTTP request logic is in `sfcli.py`.

### **What to Move**
- All HTTP request logic to `spiderfoot/api_client.py`.

### **Risks**
- **Low:** Isolated to CLI/server communication.
- **Mitigation:** Add/expand CLI integration tests.

---

## 9. Refactor Entry Points

### **Current State**
- Entry points are monolithic and contain business logic.

### **What to Move**
- Keep only argument parsing, app assembly, and high-level orchestration.
- Delegate all logic to new modular components.

### **Risks**
- **Medium:** Integration issues if imports are missed.
- **Mitigation:** Add integration tests for each entrypoint.

---

## 10. Remove Redundant Files

### **Current State**
- After merging, some files in `sflib/` and elsewhere will be empty or redundant.

### **What to Move**
- Remove these files after confirming all logic is migrated.

### **Risks**
- **Low:** As long as all logic is migrated, safe to remove.

---

# Summary Table

| Step | Main Files/Dirs | Key Classes/Functions | Risk | Mitigation |
|------|----------------|----------------------|------|------------|
| 1. Centralize Config | sflib/config.py, entrypoints | configSerialize, configUnserialize | High | Unit tests, incremental refactor |
| 2. Merge Helpers | sflib/helpers.py, helpers.py, core.py | hashstring, validIP, etc. | Medium | Static analysis, unit tests |
| 3. Centralize Logging | logger.py, sflib/logging.py, core.py | SpiderFootSqliteLogHandler, debug/info/error | Low/Med | Test logging output |
| 4. Refactor DB Utils | db_core.py, db_utils.py, db_event.py, etc. | CRUD, connect, eventAdd, etc. | High | Integration tests, incremental |
| 5. Scan Orchestration | scan_service/scanner.py, threadpool.py | SpiderFootScanner, start_scan | Med/High | Tests for scan start/stop |
| 6. API Models/Routers | sfapi.py | Pydantic models, routers | Low/Med | API tests |
| 7. Output/Export Utils | sfcli.py, sfwebui.py | pretty-print, export_csv | Low | CLI/web UI tests |
| 8. API Client | sfcli.py | HTTP request logic | Low | CLI tests |
| 9. Refactor Entrypoints | sf.py, sfcli.py, sfwebui.py, sfapi.py | main, CLI shell | Med | Integration tests |
| 10. Remove Redundant | sflib/, old helpers | - | Low | Confirm migration |

---

# Recommendations

- **Start with config and helpers**: These are most widely used and will have the biggest impact.
- **Add/expand tests before each major refactor**: This will catch regressions early.
- **Refactor incrementally**: Move one concern at a time, update imports, and test.
- **Document as you go**: Update the roadmap/checklist after each step.

## 1. **Centralize Configuration Management**

### **Current State**
- Config logic is spread across:
  - config.py
  - helpers.py and helpers.py
  - Entry points (sf.py, sfcli.py, sfwebui.py, sfapi.py)
  - Some config is also in __init__.py and possibly in `db/` modules.

### **Critical Steps**
- **Audit all config-related code**: Identify all default config dicts, config loading, merging, and validation logic.
- **Unify config logic**: Move all config logic to a new `spiderfoot/config.py` module.
- **Refactor all entrypoints and modules** to import and use the new config module.

### **Risks**
- **Hidden config dependencies**: Some modules may expect config to be global or mutable.
- **Circular imports**: If config is imported everywhere, refactoring must avoid circular dependencies.
- **Legacy/unused config**: Some config options may be obsolete or only used in legacy code.

### **Mitigation**
- Start with a read-only config object, then add mutability if needed.
- Add unit tests for config loading and merging.
- Refactor incrementally, updating imports and usage step by step.

---

## 2. **Extract Scan Orchestration**

### **Current State**
- Scan orchestration logic is in:
  - sf.py (functions like `start_scan`, `validate_arguments`, `process_target`, `prepare_modules`, `execute_scan`)
  - `scan_service/scanner.py` (core scan logic)
  - Possibly duplicated in sfwebui.py and sfapi.py

### **Critical Steps**
- **Move all scan orchestration logic** to `scan_service.py` (or expand `scan_service/scanner.py`).
- **Unify process/thread management**: Ensure all scan launching, monitoring, and aborting is handled in one place.
- **Update entrypoints** to use the new scan service.

### **Risks**
- **Tight coupling**: Scan logic may be tightly coupled to CLI or web UI code.
- **Process/thread safety**: Moving process management may introduce subtle bugs if not carefully tested.
- **API/CLI divergence**: Ensure both API and CLI use the same scan orchestration logic.

### **Mitigation**
- Write integration tests for scan start/stop/status.
- Refactor in small steps, keeping old and new logic side-by-side until stable.

---

## 3. **Modularize Module Loading**

### **Current State**
- Module loading logic is in:
  - sf.py (custom loader, dynamic import)
  - Possibly in core.py or helpers.py

### **Critical Steps**
- **Move all module loading logic** to `module_loader.py`.
- **Standardize dynamic import**: Use a single function for module discovery and import.
- **Update all code** to use the new loader.

### **Risks**
- **Dynamic import edge cases**: Some modules may have special requirements or side effects.
- **Test coverage**: Module loading is hard to test; ensure all modules are still discoverable.

### **Mitigation**
- Add a test that loads all modules and checks for import errors.
- Document the expected module interface.

---

## 4. **Extract Output and Export Utilities**

### **Current State**
- Output formatting and export logic is in:
  - sfcli.py (pretty-printing, color, history)
  - sfwebui.py (Excel/CSV export, template rendering)
  - Possibly in helpers or duplicated in tests

### **Critical Steps**
- **Move all output formatting** to `output_utils.py`.
- **Move all export logic** to `export_utils.py`.
- **Update CLI and web UI** to use these utilities.

### **Risks**
- **Hidden dependencies**: Output functions may depend on CLI state or global variables.
- **Template coupling**: Web UI export may be tightly coupled to CherryPy or Mako templates.

### **Mitigation**
- Refactor output functions to be stateless and pure.
- Add unit tests for all output and export functions.

---

## 5. **Modularize API Models and Routers**

### **Current State**
- All Pydantic models and routers are in sfapi.py.

### **Critical Steps**
- **Move all Pydantic models** to `api_models.py`.
- **Move routers** to `api/` directory.
- **Update sfapi.py** to only assemble the app and include routers.

### **Risks**
- **Import order**: FastAPI requires routers to be included in a specific order.
- **Model dependencies**: Some models may depend on config or other models.

### **Mitigation**
- Add unit tests for API endpoints.
- Refactor in small steps, moving one router/model at a time.

---

## 6. **Centralize Server Communication**

### **Current State**
- HTTP request logic is in sfcli.py and possibly duplicated in tests.

### **Critical Steps**
- **Move all HTTP request logic** to `api_client.py`.
- **Update CLI and tests** to use the new API client.

### **Risks**
- **Authentication/session handling**: Ensure all auth flows are preserved.
- **Error handling**: Centralize and standardize error handling.

### **Mitigation**
- Add unit tests for the API client.
- Test all CLI commands that communicate with the server.

---

## 7. **Refactor Entry Points**

### **Current State**
- Entry points are large and contain business logic.

### **Critical Steps**
- **Keep only argument parsing and orchestration** in entry points.
- **Delegate all logic** to the new modular components.

### **Risks**
- **Breakage during refactor**: Entry points are the glue; any mistake can break the app.
- **Integration drift**: Ensure all entry points are tested after each refactor.

### **Mitigation**
- Add integration tests for all entry points.
- Refactor one entry point at a time.

---

## 8. **Merge/Deduplicate Core Library Files**

### **Current State**
- Many helpers, config, and logging files are duplicated between spiderfoot and sflib.

### **Critical Steps**
- **Audit all helpers, config, and logging files**.
- **Merge into single modules**: helpers.py, `spiderfoot/config.py`, logger.py.
- **Remove redundant files** from `sflib/`.

### **Risks**
- **Hidden dependencies**: Some modules may import from both locations.
- **Legacy code**: Some old modules may not be covered by tests.

### **Mitigation**
- Use grep/search to find all imports and update them.
- Add deprecation warnings to old files before removal.

---

## **Summary Table: Steps and Risks**

| Step                        | Main Files/Dirs Affected         | Key Risks                        | Mitigation                        |
|-----------------------------|----------------------------------|----------------------------------|-----------------------------------|
| Centralize Config           | config.py, helpers.py, entrypoints | Hidden deps, circular imports    | Incremental refactor, tests       |
| Extract Scan Orchestration  | scan_service.py, sf.py, scanner.py | Coupling, process safety         | Integration tests, stepwise move  |
| Modularize Module Loading   | module_loader.py, sf.py, helpers  | Dynamic import edge cases         | Loader tests, doc interface       |
| Output/Export Utilities     | output_utils.py, export_utils.py, sfcli.py, sfwebui.py | Hidden deps, template coupling   | Pure functions, unit tests        |
| API Models/Routers          | api_models.py, api/               | Import order, model deps         | Router/model tests, stepwise move |
| Server Communication        | api_client.py, sfcli.py           | Auth/session, error handling     | API client tests, CLI tests       |
| Refactor Entry Points       | sf.py, sfcli.py, sfwebui.py, sfapi.py | Breakage, integration drift      | Integration tests, one at a time  |
| Merge Core Library Files    | helpers.py, config.py, logger.py, sflib/ | Hidden deps, legacy code         | Search/replace, deprecation warn  |

---

## **Final Recommendations**

- **Test after every major refactor.**
- **Document all new/merged modules.**
- **Communicate changes to all contributors.**
- **Consider a deprecation period for old modules.**