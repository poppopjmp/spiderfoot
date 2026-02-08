# SpiderFoot Changelog — Cycles 81-100

## v5.46.0 — Release Finalization (Cycle 100)

Final release of the 100-cycle improvement initiative. All infrastructure,
modules, and test suites validated.

### Summary of Cycles 81-100

| Cycle | Version | Component | Tests |
|-------|---------|-----------|-------|
| 81 | 5.36.1 | Event filter chain | 27 |
| 82 | 5.37.0 | Module dependency resolver | 27 |
| 83 | 5.37.1 | Scan policy engine | 30 |
| 84 | 5.38.0 | Event correlation rules | 33 |
| 85 | 5.38.1 | Module metrics collector | 30 |
| 86 | 5.39.0 | Event pipeline | 25 |
| 87 | 5.39.1 | Scan orchestrator | 23 |
| 88 | 5.40.0 | Data export formats | 25 |
| 89 | 5.40.1 | Module sandbox | 36 |
| 90 | 5.41.0 | Cross-component integration tests | 16 |
| 91 | 5.41.1 | Event type taxonomy | 32 |
| 92 | 5.42.0 | Scan templates | 22 |
| 93 | 5.42.1 | Result caching layer | 34 |
| 94 | 5.43.0 | Module API client | 32 |
| 95 | 5.43.1 | Alert rules engine | 37 |
| 96 | 5.44.0 | Scan workflow DSL | 33 |
| 97 | 5.44.1 | Module versioning | 39 |
| 98 | 5.45.0 | Event store | 27 |
| 99 | 5.45.1 | Final validation suite | 14 |
| 100 | 5.46.0 | Release finalization | — |

### Total test count (Cycles 81-100): 562 tests

### New Infrastructure Modules

- `spiderfoot/event_filter_chain.py` — Composable event filters
- `spiderfoot/module_dependency_resolver.py` — Dependency graph with topological sort
- `spiderfoot/scan_policy.py` — Policy engine for scan governance
- `spiderfoot/correlation_rules.py` — Event correlation with windowed matching
- `spiderfoot/module_metrics.py` — Module performance metrics collection
- `spiderfoot/event_pipeline.py` — Multi-stage event processing pipeline
- `spiderfoot/scan_orchestrator.py` — Phase-based scan execution
- `spiderfoot/data_export.py` — JSON, CSV, and summary export formats
- `spiderfoot/module_sandbox.py` — Isolated module execution with resource limits
- `spiderfoot/event_taxonomy.py` — Hierarchical event type classification
- `spiderfoot/scan_templates.py` — Pre-configured scan template library
- `spiderfoot/result_cache.py` — TTL-based result caching with eviction
- `spiderfoot/module_api_client.py` — Standardized HTTP client with rate limiting
- `spiderfoot/alert_rules.py` — Alert rules engine with condition matching
- `spiderfoot/scan_workflow.py` — Composable workflow DSL
- `spiderfoot/module_versioning.py` — Semantic versioning with constraints
- `spiderfoot/event_store.py` — Persistent event storage with indexing

### Earlier Cycles (1-80)

Cycles 1-80 covered:
- Core plugin architecture modernization (SpiderFootModernPlugin)
- RAG+Qdrant vector database correlation engine
- Migration of all 277 sfp_* modules to modern plugin structure
- Database schema extensions, UI improvements, API enhancements
- Comprehensive test infrastructure
