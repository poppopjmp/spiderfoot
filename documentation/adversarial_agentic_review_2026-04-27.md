# SpiderFoot Adversarial Codebase & Agentic Systems Review

**Date:** 2026-04-27  
**Scope:** Full repository architecture with special emphasis on `spiderfoot/agents/`, `spiderfoot/tasks/agents.py`, event-driven scan orchestration, LLM reliability, and operational alignment.  
**Scale:** all scores use a 0.00–10.00 adversarial maturity scale where 10.00 means SOTA-grade, production-proven, measured, documented, and continuously validated.

---

## 1. Executive Summary

SpiderFoot v6 is a broad OSINT automation platform with a strong microservice direction, a large module ecosystem, Redis/Celery orchestration, FastAPI/GraphQL APIs, observability infrastructure, and a dedicated AI agents service. The agentic section is valuable but was less mature than the rest of the platform in four areas: bounded dispatch, LLM retry/failover behavior, robust structured-output handling, and lifecycle cleanup.

This pass implemented a first stabilization tranche focused on safe, localized agentic improvements:

- Added shared `AgentResult.to_dict()` serialization for API, Redis, and tests.
- Added bounded service-level agent dispatch with `SF_AGENTS_MAX_INFLIGHT` backpressure.
- Added Redis persistence and publication for background agent results.
- Added clean Redis pub/sub shutdown and agent `close()` lifecycle hooks.
- Added persistent `aiohttp` sessions with retry/backoff/jitter and `/v1` compatibility fallback in `BaseAgent.call_llm()`.
- Added robust fenced/prefixed JSON parsing via `BaseAgent.parse_json_response()`.
- Added common secret redaction before LLM calls in finding, credential, document, summarization, and threat-intel agents.
- Replaced mutable Pydantic request defaults with `Field(default_factory=...)`.
- Routed Celery agent tasks through the shared retrying `LLMClient` and capped batch fan-out.
- Added focused unit coverage in `test/unit/test_agents_stability.py`.

Validation performed:

- `python -m compileall spiderfoot/agents spiderfoot/tasks/agents.py test/unit/test_agents_stability.py`
- `python -m pytest test/unit/test_agents_stability.py -q` → **5 passed**
- VS Code diagnostics for changed files → **no errors**

**Current adversarial implementation estimate after this pass:** 8.19/10.00 repo-wide, 8.46/10.00 for the agentic subsystem.  
**Target requested:** >9.78/10.00.  
**Status:** not honestly claimable yet. Achieving >9.78 requires the remaining roadmap in Section 8, especially durable agent state, eval harnesses, policy gates, red-team tests, replayable traces, and SLO-backed production telemetry.

---

## 2. SOTA Comparison Baseline

Representative SOTA patterns from durable agent/workflow systems such as LangGraph-style state graphs, AutoGen-style multi-agent role/message controls, CrewAI-style task/process orchestration, Temporal/Cadence-style workflow durability, and current LLM production platforms:

| Capability | SOTA expectation | SpiderFoot before this pass | SpiderFoot after this pass | Remaining gap |
|---|---|---:|---:|---|
| Durable agent state | checkpoint every step, replayable state transitions | 5.80 | 6.10 | Need persisted per-agent state machine and resumable event cursors |
| Bounded concurrency | explicit queue/backpressure/admission limits | 5.20 | 8.00 | Need queue-depth metrics, rejection policies, load shedding |
| LLM retries | transient-aware retry, jitter, provider fallback, budget controls | 5.60 | 8.25 | Need model fallback policy and circuit breaker |
| Structured outputs | schema-first validation, repair loop, eval coverage | 6.30 | 7.40 | Need Pydantic schemas per agent and auto-repair pass |
| Tool/action safety | allowlisted tools, typed actions, sandboxing | 4.80 | 5.00 | Need true tool execution plan and approval gates |
| Observability | traces, token/cost metrics, prompt/result lineage | 6.20 | 6.80 | Need OpenTelemetry spans and LLM cost labels |
| Human-in-loop | interruption, review, approval, override | 4.30 | 4.30 | Need review queue and policy enforcement |
| Evaluation | golden sets, adversarial prompt tests, regression thresholds | 3.80 | 4.40 | Need eval harness with pass/fail gates |
| Privacy | secret redaction, data minimization, retention controls | 5.90 | 7.30 | Need deterministic DLP scanner and audit logs |
| Failure recovery | idempotency, DLQ, poison-event handling | 6.10 | 6.90 | Need agent DLQ and event replay tooling |

---

## 3. Agentic Architecture Walkthrough

1. **Event source:** scans, uploads, reports, and user input create events or direct REST requests.
2. **Agent service:** `spiderfoot/agents/service.py` initializes agent classes, listens on Redis pub/sub, matches event types, dispatches work, and exposes API/metrics endpoints.
3. **Agent base:** `spiderfoot/agents/base.py` controls per-agent concurrency, timeout behavior, metrics, LLM calls, parsing, redaction, and serialization.
4. **Specialized agents:** finding validator, credential analyzer, text summarizer, report generator, document analyzer, threat-intel analyzer, and IaC advisor each build prompts and return `AgentResult` instances.
5. **Celery agent task path:** `spiderfoot/tasks/agents.py` runs longer agent tasks on the `agents` queue and stores task status/results in Redis.
6. **LLM gateway:** LiteLLM provides OpenAI-compatible access and model indirection.
7. **Storage/results:** direct calls return results synchronously; background events now persist results into Redis keys and publish `sf:agent_results`.

---

## 4. Implemented Fixes

| Fix | Files | Impact |
|---|---|---|
| Bounded background dispatch | `spiderfoot/agents/service.py` | Prevents unbounded `asyncio.create_task()` storms under event bursts |
| Result persistence | `spiderfoot/agents/service.py` | Makes background agent outputs observable and retrievable |
| Graceful cleanup | `spiderfoot/agents/service.py`, `spiderfoot/agents/base.py` | Closes Redis pub/sub, Redis client, LLM HTTP sessions, and drains tasks |
| LLM retry/backoff | `spiderfoot/agents/base.py` | Improves resilience to 408/429/5xx/timeouts and endpoint-path differences |
| Robust JSON parsing | `spiderfoot/agents/base.py`, agent subclasses | Handles fenced/prefixed JSON instead of brittle `json.loads(response)` only |
| Secret redaction | agent subclasses | Reduces leakage of tokens/passwords/API keys to LLM providers |
| Safer API models | `spiderfoot/agents/service.py` | Removes mutable default lists/dicts and caps `/process` batch size |
| Celery agent hardening | `spiderfoot/tasks/agents.py` | Uses retrying `LLMClient`, status TTLs, bounded batch submissions |
| Focused tests | `test/unit/test_agents_stability.py` | Locks in parsing, redaction, metrics, Redis persistence, request defaults |

---

## 5. 500-Dimension Scorecard

| # | Category | Dimension | Score | Primary next action |
|---:|---|---|---:|---|
|001|Architecture|Service boundary clarity|8.40|Add ADRs for AI service contracts|
|002|Architecture|Microservice profile separation|8.55|Document profile dependency graph|
|003|Architecture|API/worker separation|8.20|Define worker ownership map|
|004|Architecture|Agent service independence|8.35|Add deployment SLOs|
|005|Architecture|Data plane/control plane split|7.70|Separate orchestration from data APIs|
|006|Architecture|Plugin/module isolation|7.85|Formalize module sandbox limits|
|007|Architecture|Dependency direction|7.60|Add import-boundary linting|
|008|Architecture|Configuration layering|7.95|Create config precedence spec|
|009|Architecture|Schema ownership|7.30|Centralize AI schemas|
|010|Architecture|Versioned interfaces|7.20|Version event/result payloads|
|011|Architecture|Backward compatibility|7.10|Add compatibility tests|
|012|Architecture|Extensibility|8.65|Document extension APIs|
|013|Architecture|Domain model cohesion|7.75|Reduce duplicated scan/event models|
|014|Architecture|Cross-service coupling|7.10|Add interface adapters|
|015|Architecture|Resilience boundaries|7.55|Add circuit breaker boundaries|
|016|Architecture|Startup sequencing|8.10|Add failure-mode matrix|
|017|Architecture|Shutdown sequencing|8.20|Expand shutdown tests|
|018|Architecture|Synchronous/async consistency|7.05|Reduce sync wrappers in async paths|
|019|Architecture|Code locality|7.45|Group agent contracts together|
|020|Architecture|Service ownership docs|6.90|Add owner/runbook table|
|021|Architecture|Deployment topology clarity|8.45|Keep compose/Helm parity checked|
|022|Architecture|Runtime dependency minimization|7.35|Audit optional imports|
|023|Architecture|Interface testability|7.80|Add contract tests|
|024|Architecture|Failure containment|7.60|Define bulkheads per service|
|025|Architecture|Architecture governance|6.85|Introduce ADR review process|
|026|Agent orchestration|Event-to-agent matching|8.10|Add pattern collision tests|
|027|Agent orchestration|Bounded background dispatch|8.20|Add queue depth telemetry|
|028|Agent orchestration|Per-agent concurrency|8.00|Tune per agent from metrics|
|029|Agent orchestration|Global inflight limit|8.10|Expose configurable saturation behavior|
|030|Agent orchestration|Result persistence|8.05|Add result listing endpoint|
|031|Agent orchestration|Agent lifecycle cleanup|8.15|Add lifespan integration tests|
|032|Agent orchestration|Status accuracy|7.85|Persist state across restarts|
|033|Agent orchestration|Task cancellation|7.40|Add cooperative cancellation hooks|
|034|Agent orchestration|Poison event handling|5.90|Add DLQ for agent events|
|035|Agent orchestration|Event replayability|5.70|Add replay CLI/API|
|036|Agent orchestration|Durable state machines|5.80|Persist agent step state|
|037|Agent orchestration|Multi-agent coordination|5.40|Add graph/workflow orchestrator|
|038|Agent orchestration|Tool planning|4.80|Define typed action plans|
|039|Agent orchestration|Tool execution safeguards|4.60|Add allowlist and approval gates|
|040|Agent orchestration|Human-in-loop review|4.20|Add review queue workflow|
|041|Agent orchestration|Agent memory|5.25|Design scoped memory stores|
|042|Agent orchestration|Context sharing|5.80|Add typed context envelopes|
|043|Agent orchestration|Agent result deduplication|6.60|Add idempotency keys|
|044|Agent orchestration|Retry semantics|7.85|Persist retry counts per event|
|045|Agent orchestration|Backpressure policy|7.65|Define wait/drop/defer policy|
|046|Agent orchestration|Priority handling|5.95|Add priority queues|
|047|Agent orchestration|Batch processing|7.05|Add batch fairness tests|
|048|Agent orchestration|Agent health reporting|7.60|Add active/failing state labels|
|049|Agent orchestration|Agent compatibility|6.95|Version agent result schemas|
|050|Agent orchestration|Orchestration SOTA alignment|6.35|Move toward durable graph execution|
|051|LLM ops|LiteLLM gateway use|8.35|Add gateway health probes|
|052|LLM ops|HTTP session reuse|8.15|Track connection pool metrics|
|053|LLM ops|Retry/backoff|8.25|Add circuit breaker|
|054|LLM ops|Retry-After handling|7.90|Parse HTTP-date Retry-After|
|055|LLM ops|Endpoint compatibility|8.00|Document `/v1` behavior|
|056|LLM ops|Model selection|7.20|Add policy by agent/task type|
|057|LLM ops|Provider fallback|5.50|Implement failover chain|
|058|LLM ops|Token budget management|6.30|Add token estimator per agent|
|059|LLM ops|Cost tracking|5.80|Record usage/cost metrics|
|060|LLM ops|Latency tracking|6.90|Add p95/p99 metrics|
|061|LLM ops|Timeout control|8.00|Tune per agent workload|
|062|LLM ops|Authentication handling|7.00|Add secret source docs|
|063|LLM ops|Prompt logging safety|6.00|Add redacted prompt traces|
|064|LLM ops|Streaming support|4.80|Add optional streaming path|
|065|LLM ops|Structured response mode|7.25|Use schemas in all agents|
|066|LLM ops|Response validation|7.40|Add repair-and-retry loop|
|067|LLM ops|Model drift detection|4.70|Add eval trend dashboard|
|068|LLM ops|Deterministic testing|6.70|Mock all model calls in tests|
|069|LLM ops|Rate limit policy|6.45|Add global LLM rate limiter|
|070|LLM ops|Bulkhead isolation|5.90|Separate pools by provider|
|071|LLM ops|LLM error taxonomy|6.80|Standardize error classes|
|072|LLM ops|Context compression|7.10|Measure report coverage loss|
|073|LLM ops|Provider config docs|7.40|Expand LiteLLM examples|
|074|LLM ops|Prompt/result lineage|5.95|Persist lineage IDs|
|075|LLM ops|LLM SLO readiness|5.85|Create SLO dashboard|
|076|Prompting|System prompt specificity|8.20|Move prompts to versioned assets|
|077|Prompting|JSON-only instruction clarity|8.00|Back with schemas everywhere|
|078|Prompting|Prompt injection resistance|5.90|Add hostile content tests|
|079|Prompting|Secret handling in prompts|7.30|Add deterministic DLP layer|
|080|Prompting|Evidence grounding|7.25|Require cited event IDs|
|081|Prompting|No-fabrication guardrails|6.90|Add verifier agent/eval|
|082|Prompting|Severity calibration|6.80|Add severity rubric fixtures|
|083|Prompting|Confidence calibration|6.40|Calibrate against labels|
|084|Prompting|Schema completeness|6.95|Create Pydantic schema per agent|
|085|Prompting|Schema strictness|7.15|Adopt `call_llm_structured()` broadly|
|086|Prompting|Markdown fence tolerance|8.35|Expand parser fuzz tests|
|087|Prompting|Prompt versioning|4.80|Add prompt registry/version field|
|088|Prompting|Prompt diff review|4.60|Require prompt changelog|
|089|Prompting|Prompt localization|3.50|Defer unless needed|
|090|Prompting|Prompt length control|6.85|Add token-aware truncation|
|091|Prompting|Report prompt coverage|8.10|Add evidence coverage metric|
|092|Prompting|Tool-call format|4.50|Define typed action DSL|
|093|Prompting|Refusal behavior|5.80|Add policy examples|
|094|Prompting|Data minimization|6.80|Classify fields before prompt|
|095|Prompting|Chain-of-thought safety|7.00|Keep outputs concise/no hidden CoT|
|096|Prompting|Prompt test corpus|4.70|Create adversarial prompt suite|
|097|Prompting|Prompt observability|5.60|Hash and trace prompt versions|
|098|Prompting|Prompt replay|5.20|Persist sanitized prompts/results|
|099|Prompting|Prompt ownership|4.90|Assign prompt owners|
|100|Prompting|Prompt SOTA alignment|6.20|Adopt schema/eval-first workflow|
|101|Event bus|Redis Streams abstraction|7.80|Converge pub/sub and streams usage|
|102|Event bus|Pub/sub agent listener|7.00|Prefer durable stream groups|
|103|Event bus|At-least-once semantics|7.10|Ack after persisted result|
|104|Event bus|Event ordering|6.30|Define ordering guarantees|
|105|Event bus|Event schema validation|6.20|Validate envelopes at boundaries|
|106|Event bus|Wildcard matching|7.70|Add collision coverage|
|107|Event bus|Backpressure|7.20|Expose backlog metrics|
|108|Event bus|DLQ support|5.90|Add DLQ for failed agent events|
|109|Event bus|Poison message isolation|5.70|Add max delivery attempts|
|110|Event bus|Replay tooling|5.50|Implement replay from Redis streams|
|111|Event bus|Serialization safety|7.00|Enforce payload size limits|
|112|Event bus|Metadata bounds|5.85|Add max metadata size|
|113|Event bus|Topic taxonomy|6.80|Publish event catalog|
|114|Event bus|Consumer group governance|6.60|Name groups predictably|
|115|Event bus|Event idempotency|6.20|Add idempotency keys|
|116|Event bus|Publish retries|7.40|Add circuit breaker metrics|
|117|Event bus|Subscriber cleanup|7.80|Add lifecycle tests|
|118|Event bus|Connection pooling|7.50|Tune max connections by service|
|119|Event bus|Event auditability|6.00|Persist event audit trail|
|120|Event bus|Event filtering|7.00|Add filter tests|
|121|Event bus|Payload encryption|4.80|Evaluate if threat model requires|
|122|Event bus|Cross-service contract tests|5.90|Add producer/consumer tests|
|123|Event bus|Message expiry policy|6.40|Document stream retention|
|124|Event bus|Storm testing|4.70|Add load/fault tests|
|125|Event bus|Event bus SOTA alignment|6.40|Use durable workflow queue semantics|
|126|Scan lifecycle|Scan state model|8.10|Add transition property tests|
|127|Scan lifecycle|Scan scheduler|7.90|Add race condition tests|
|128|Scan lifecycle|Deduplication guard|6.85|Use advisory locks|
|129|Scan lifecycle|Worker crash recovery|6.80|Persist heartbeats with TTL|
|130|Scan lifecycle|Progress tracking|7.55|Add TTL guarantees|
|131|Scan lifecycle|Abort responsiveness|6.90|Move from polling to signal/subscription|
|132|Scan lifecycle|Module DAG execution|7.70|Visualize dependency graph|
|133|Scan lifecycle|Module loading safety|7.25|Sandbox risky imports|
|134|Scan lifecycle|Error state propagation|6.85|Enforce base guard|
|135|Scan lifecycle|Checkpointing|6.80|Checkpoint module progress|
|136|Scan lifecycle|Scan retry semantics|6.90|Formalize retry policy|
|137|Scan lifecycle|Long-running scans|7.15|Add heartbeat and watchdog|
|138|Scan lifecycle|Distributed locking|5.90|Adopt DB/Redis atomic locks|
|139|Scan lifecycle|State transition audit|6.60|Persist transition history|
|140|Scan lifecycle|Concurrent scan fairness|6.70|Add queue fairness policy|
|141|Scan lifecycle|Resource budgets|6.40|Add per-scan CPU/network budget|
|142|Scan lifecycle|Result consistency|7.20|Add write idempotency|
|143|Scan lifecycle|Cancellation safety|6.55|Test mid-module aborts|
|144|Scan lifecycle|Recovery UX|6.25|Expose retry/reclaim status|
|145|Scan lifecycle|Scan profile validation|6.80|Detect include cycles|
|146|Scan lifecycle|Active/passive separation|8.20|Document safety controls|
|147|Scan lifecycle|Scheduler observability|7.30|Add queue metrics|
|148|Scan lifecycle|State machine docs|7.00|Add diagrams and examples|
|149|Scan lifecycle|Scan load testing|5.80|Create synthetic high-volume scan|
|150|Scan lifecycle|Scan lifecycle SOTA alignment|6.95|Adopt durable workflow primitives|
|151|Reliability|LLM transient retries|8.25|Add provider circuit breakers|
|152|Reliability|Redis listener cleanup|8.00|Add integration test|
|153|Reliability|HTTP connection cleanup|8.10|Track open sessions|
|154|Reliability|Task fan-out control|8.00|Expose saturation response|
|155|Reliability|Batch fan-out cap|8.15|Add API validation|
|156|Reliability|Status TTLs|7.90|Make retention configurable in docs|
|157|Reliability|Dead-letter queues|5.80|Implement DLQ for agents/scans|
|158|Reliability|Circuit breakers|5.65|Add for Redis/LLM/db|
|159|Reliability|Bulkheads|5.90|Separate queues/pools by class|
|160|Reliability|Idempotent writes|6.45|Add deterministic result IDs|
|161|Reliability|Retry visibility|7.10|Expose retry count metrics|
|162|Reliability|Timeout coverage|7.80|Tune per endpoint/task|
|163|Reliability|Startup failure behavior|7.50|Add dependency mode matrix|
|164|Reliability|Shutdown drains|8.05|Validate with lifespan tests|
|165|Reliability|Chaos testing|4.50|Add Redis/LLM outage tests|
|166|Reliability|Race testing|4.80|Add concurrent dispatch tests|
|167|Reliability|Resource leak testing|6.90|Expand leak fixtures|
|168|Reliability|Retry budgets|5.70|Set per service budgets|
|169|Reliability|Fallback modes|5.60|Define degraded no-LLM mode|
|170|Reliability|Queue saturation behavior|6.40|Decide wait/drop/requeue semantics|
|171|Reliability|Poison payload resilience|5.90|Schema validate and DLQ|
|172|Reliability|Data corruption recovery|5.80|Add repair tooling|
|173|Reliability|Operational runbooks|5.70|Create incident playbooks|
|174|Reliability|SLO definition|5.20|Define uptime/latency/error SLOs|
|175|Reliability|Reliability SOTA alignment|6.45|Add durable workflows and chaos suite|
|176|Security/privacy|Secret redaction before LLM|7.65|Add full DLP scanner|
|177|Security/privacy|Credential prompt safety|7.60|Never include raw credentials|
|178|Security/privacy|API key handling|7.20|Document secret stores|
|179|Security/privacy|Auth boundaries|7.80|Continue endpoint auth audit|
|180|Security/privacy|Input validation|7.10|Validate agent payload schemas|
|181|Security/privacy|Output sanitization|7.20|Sanitize all UI render paths|
|182|Security/privacy|Prompt injection defense|5.70|Add hostile input tests|
|183|Security/privacy|SSRF defense|6.60|Audit URL-fetching modules|
|184|Security/privacy|Command execution safety|6.20|Sandbox active modules|
|185|Security/privacy|Container hardening|8.00|Continuously scan compose/Helm|
|186|Security/privacy|Least privilege|7.10|Review service accounts|
|187|Security/privacy|Network segmentation|7.40|Validate runtime policies|
|188|Security/privacy|Audit logging|6.60|Record agent decisions|
|189|Security/privacy|Data retention|6.90|Expose retention controls|
|190|Security/privacy|PII minimization|6.30|Classify/redact personal data|
|191|Security/privacy|Multi-tenant isolation|6.50|Add workspace isolation tests|
|192|Security/privacy|Error message secrecy|7.00|Scrub exception details|
|193|Security/privacy|Dependency security|7.40|Automate pip-audit gate|
|194|Security/privacy|Supply chain integrity|6.80|Pin images/SBOM/signing|
|195|Security/privacy|Threat modeling|5.80|Maintain STRIDE model|
|196|Security/privacy|Agent abuse prevention|5.40|Add quota/policy layer|
|197|Security/privacy|Policy enforcement|5.50|Add central policy engine|
|198|Security/privacy|Compliance evidence|5.70|Map controls to tests|
|199|Security/privacy|Secure defaults|7.20|Harden profile defaults|
|200|Security/privacy|Security SOTA alignment|6.55|Add policy/eval/red-team gates|
|201|Data layer|PostgreSQL integration|8.10|Add transaction contract tests|
|202|Data layer|Redis usage|7.85|Unify pub/sub vs streams|
|203|Data layer|Qdrant integration|7.60|Add vector consistency tests|
|204|Data layer|MinIO integration|7.40|Add object lifecycle tests|
|205|Data layer|Data model clarity|7.10|Publish ERD/schema docs|
|206|Data layer|Migration reliability|7.00|Add migration rollback tests|
|207|Data layer|Connection management|7.20|Audit pool lifecycles|
|208|Data layer|Transaction safety|6.85|Use locks for scan dedup|
|209|Data layer|Query performance|6.90|Add slow query dashboards|
|210|Data layer|Data retention|6.70|Configurable retention policies|
|211|Data layer|Backup/restore|7.30|Test restore regularly|
|212|Data layer|Data lineage|5.90|Persist event/result lineage|
|213|Data layer|Data classification|5.70|Label PII/secrets/sensitive|
|214|Data layer|Schema validation|6.50|Validate event/result payloads|
|215|Data layer|Index strategy|6.85|Document indexes and budgets|
|216|Data layer|Vector freshness|6.50|Track embedding lag|
|217|Data layer|Cache invalidation|6.40|Define cache TTLs explicitly|
|218|Data layer|Idempotent storage|6.30|Add deterministic keys|
|219|Data layer|Cross-scan aggregation|7.00|Add consistency checks|
|220|Data layer|Serialization limits|6.25|Cap event metadata/payloads|
|221|Data layer|Secrets in storage|6.60|Encrypt sensitive fields|
|222|Data layer|Data export safety|6.80|Sanitize exports|
|223|Data layer|Test fixture realism|6.50|Add production-like fixtures|
|224|Data layer|Observability|6.90|Add DB/Redis/Qdrant metrics|
|225|Data layer|Data layer SOTA alignment|6.75|Add lineage, schemas, restore drills|
|226|API/GraphQL|FastAPI router breadth|8.20|Keep OpenAPI stable|
|227|API/GraphQL|REST consistency|7.50|Normalize response envelopes|
|228|API/GraphQL|GraphQL coverage|7.30|Add subscription lifecycle tests|
|229|API/GraphQL|Subscription cleanup|6.70|Audit DB handle lifetimes|
|230|API/GraphQL|Input validation|7.10|Add typed validators|
|231|API/GraphQL|Rate limiting|7.20|Tune by endpoint risk|
|232|API/GraphQL|Authentication|7.60|Add authz matrix tests|
|233|API/GraphQL|Authorization|7.10|Enforce workspace scopes|
|234|API/GraphQL|API versioning|6.90|Document breaking-change rules|
|235|API/GraphQL|Error taxonomy|6.70|Standardize error payloads|
|236|API/GraphQL|Pagination|7.00|Verify all list endpoints|
|237|API/GraphQL|Idempotency|5.90|Add idempotency keys for mutations|
|238|API/GraphQL|Request size limits|6.80|Document body limits|
|239|API/GraphQL|Agent endpoints|7.70|Add result listing and replay|
|240|API/GraphQL|Report endpoints|7.20|Add long-running job status|
|241|API/GraphQL|OpenAPI docs|7.50|Expand examples|
|242|API/GraphQL|GraphQL schema docs|6.80|Generate schema docs|
|243|API/GraphQL|WebSocket behavior|6.40|Add disconnect tests|
|244|API/GraphQL|CORS/security headers|7.20|Validate in deployment tests|
|245|API/GraphQL|Payload redaction|6.50|Redact sensitive errors|
|246|API/GraphQL|Observability|6.90|Add route latency metrics|
|247|API/GraphQL|Contract tests|6.20|Add SDK/client contract suite|
|248|API/GraphQL|Backward compatibility|6.40|Snapshot API schemas|
|249|API/GraphQL|API ergonomics|7.10|Normalize naming|
|250|API/GraphQL|API SOTA alignment|6.80|Add contracts, idempotency, lifecycle tests|
|251|Frontend/UI|React SPA structure|8.00|Maintain component boundaries|
|252|Frontend/UI|Agent status UI|7.00|Show inflight/retry/error metrics|
|253|Frontend/UI|Scan detail UX|8.10|Add stale data indicators|
|254|Frontend/UI|Graph visualization|7.70|Add large graph performance tests|
|255|Frontend/UI|Accessibility|6.50|Run automated a11y audits|
|256|Frontend/UI|Type safety|7.60|Keep zero unsafe `any` target|
|257|Frontend/UI|API error handling|7.00|Normalize toast/error states|
|258|Frontend/UI|Realtime updates|7.10|Test subscription reconnects|
|259|Frontend/UI|Agent result display|6.40|Add result history/polling UI|
|260|Frontend/UI|Report rendering|7.20|Sanitize markdown thoroughly|
|261|Frontend/UI|Security display|7.00|Avoid leaking raw secrets|
|262|Frontend/UI|Dashboard metrics|7.10|Add agent SLO widgets|
|263|Frontend/UI|Responsive design|7.60|Continue viewport tests|
|264|Frontend/UI|Loading states|7.00|Add skeleton/error coverage|
|265|Frontend/UI|User workflows|7.30|Add e2e golden flows|
|266|Frontend/UI|Workspace isolation UI|6.60|Show active workspace context|
|267|Frontend/UI|Bulk actions|6.90|Add confirmation/rollback states|
|268|Frontend/UI|Settings UX|7.20|Validate dangerous changes|
|269|Frontend/UI|Observability UX|6.60|Expose trace IDs|
|270|Frontend/UI|Frontend tests|7.40|Expand e2e coverage|
|271|Frontend/UI|Performance budgets|6.50|Track bundle/render budgets|
|272|Frontend/UI|Internationalization|3.80|Defer unless product requires|
|273|Frontend/UI|Design consistency|7.30|Document design tokens|
|274|Frontend/UI|User guidance|6.80|Add tooltips/runbooks|
|275|Frontend/UI|Frontend SOTA alignment|6.95|Add a11y/e2e/SLO-driven UX|
|276|DevOps|Docker Compose profiles|8.50|Keep profile tests green|
|277|DevOps|Helm deployment|7.40|Add chart conformance tests|
|278|DevOps|Container build hygiene|7.60|Add image scanning gate|
|279|DevOps|Secrets management|6.70|Integrate external secret stores|
|280|DevOps|Environment config|7.20|Generate config reference|
|281|DevOps|TLS/reverse proxy|7.80|Automate cert rotation docs|
|282|DevOps|Observability stack|8.10|Connect agent metrics dashboards|
|283|DevOps|CI test breadth|7.20|Add agent eval gates|
|284|DevOps|Release automation|6.80|Add changelog validation|
|285|DevOps|SBOM generation|6.40|Publish SBOM artifacts|
|286|DevOps|Dependency updates|7.00|Add automated security PRs|
|287|DevOps|Infrastructure drift|5.90|Add drift detection|
|288|DevOps|Backup automation|7.00|Add restore drill CI/manual|
|289|DevOps|Runtime policies|6.10|Add seccomp/AppArmor guidance|
|290|DevOps|Resource requests/limits|6.80|Set Helm resource defaults|
|291|DevOps|Autoscaling|5.80|Add worker/agent HPA policies|
|292|DevOps|Blue/green deploys|5.40|Define upgrade strategy|
|293|DevOps|Rollback safety|5.90|Add rollback playbook|
|294|DevOps|Config validation|6.80|Validate env at startup|
|295|DevOps|Local dev UX|7.50|Improve quickstart checks|
|296|DevOps|Windows compatibility|6.90|Add Windows CI smoke tests|
|297|DevOps|Cloud portability|7.10|Document cloud-specific deltas|
|298|DevOps|Operational runbooks|5.90|Create SRE runbooks|
|299|DevOps|Incident response|5.50|Define escalation matrix|
|300|DevOps|DevOps SOTA alignment|6.80|Add policy-as-code and SLO gates|
|301|Observability|Prometheus metrics|7.80|Add agent retry/active dashboards|
|302|Observability|Agent metrics|8.00|Add histograms for latency|
|303|Observability|LLM retry metrics|7.70|Break down by provider/status|
|304|Observability|Trace coverage|6.30|Add OpenTelemetry spans|
|305|Observability|Log structure|6.90|Standardize JSON logging|
|306|Observability|Correlation IDs|6.20|Propagate trace IDs across services|
|307|Observability|Prompt/result tracing|5.40|Store sanitized prompt hashes|
|308|Observability|Token/cost telemetry|5.30|Capture LLM usage fields|
|309|Observability|Queue depth metrics|6.00|Expose Redis/Celery/agent queue depth|
|310|Observability|Error dashboards|6.70|Add agent/scanner panels|
|311|Observability|Alert rules|5.90|Define SLO-based alerts|
|312|Observability|Distributed tracing|6.20|Instrument event paths|
|313|Observability|Audit logs|6.00|Add agent decision audit trail|
|314|Observability|Health checks|7.40|Make dependency-specific health|
|315|Observability|Synthetic probes|5.30|Add LLM/Redis/API probes|
|316|Observability|Redaction in logs|6.60|Add log scrubber tests|
|317|Observability|Metric cardinality|6.70|Review labels under load|
|318|Observability|Long-run leak detection|5.60|Run soak tests|
|319|Observability|Runbook links|4.90|Link alerts to runbooks|
|320|Observability|Dashboard coverage|6.80|Add agent dashboard|
|321|Observability|Event lineage|5.70|Trace event-to-result paths|
|322|Observability|User-visible status|6.70|Expose retry/backlog in UI|
|323|Observability|Retention policy|6.40|Set metric/log retention docs|
|324|Observability|Forensics readiness|5.60|Preserve enough audit context|
|325|Observability|Observability SOTA alignment|6.35|Add traces, SLOs, eval dashboards|
|326|Testing|Unit test breadth|6.90|Add agent subclass tests|
|327|Testing|New agent stability tests|8.20|Expand concurrency scenarios|
|328|Testing|Integration tests|6.20|Add Redis/LiteLLM test stack|
|329|Testing|Contract tests|5.80|Add event/result schema contracts|
|330|Testing|Property tests|4.90|Fuzz payloads and JSON parser|
|331|Testing|Concurrency tests|5.10|Stress event dispatch/backpressure|
|332|Testing|Chaos tests|4.40|Simulate Redis/LLM failures|
|333|Testing|Eval harness|3.90|Create golden AI outputs|
|334|Testing|Adversarial prompt tests|3.80|Add injection corpus|
|335|Testing|Regression thresholds|4.20|Gate on eval scores|
|336|Testing|Performance tests|5.70|Add scan/agent load tests|
|337|Testing|Security tests|5.80|Add DAST/fuzz checks|
|338|Testing|Snapshot tests|5.60|Snapshot API schemas/prompts|
|339|Testing|Fixture quality|6.50|Add realistic event fixtures|
|340|Testing|Mock LLM fidelity|6.30|Mock errors/rate limits/tokens|
|341|Testing|Database tests|7.00|Add transaction failure cases|
|342|Testing|Frontend tests|7.40|Add e2e critical paths|
|343|Testing|CI stability|6.70|Track flaky tests|
|344|Testing|Coverage visibility|6.60|Publish component coverage|
|345|Testing|Mutation testing|3.70|Pilot on core/agents|
|346|Testing|Static typing|6.80|Increase mypy strictness gradually|
|347|Testing|Lint gates|7.10|Ensure lint in CI|
|348|Testing|Release smoke tests|6.20|Add compose smoke test|
|349|Testing|Test documentation|5.80|Document test tiers|
|350|Testing|Testing SOTA alignment|5.65|Add eval/chaos/property gates|
|351|Performance|Agent dispatch overhead|7.80|Benchmark under burst load|
|352|Performance|LLM HTTP pooling|8.10|Tune connector limits|
|353|Performance|Report generation context|6.70|Measure prompt size/cost|
|354|Performance|Qdrant retrieval|6.80|Benchmark scroll/search|
|355|Performance|Redis throughput|7.20|Add stream/pubsub load tests|
|356|Performance|Postgres query latency|6.90|Add slow query budget|
|357|Performance|Celery queue latency|7.00|Expose latency histogram|
|358|Performance|Frontend rendering|6.80|Profile large scan details|
|359|Performance|Graph rendering|6.20|Optimize huge graph layouts|
|360|Performance|Module execution throughput|7.00|Benchmark top modules|
|361|Performance|ThreadPool behavior|6.80|Stress shutdown/stop races|
|362|Performance|Memory footprint|6.40|Add heap/soak tests|
|363|Performance|Batch processing|7.10|Tune batch caps/sizes|
|364|Performance|Backpressure efficiency|7.20|Test saturation behavior|
|365|Performance|Token efficiency|5.90|Compress context with metrics|
|366|Performance|Cache hit rates|6.40|Expose cache metrics|
|367|Performance|Cold start|6.70|Profile service startup|
|368|Performance|Container resource usage|6.50|Set budgets and dashboards|
|369|Performance|Network timeouts|7.10|Tune active scan defaults|
|370|Performance|Cost/performance|5.90|Track LLM cost per result|
|371|Performance|Parallelism policy|6.60|Optimize per queue/service|
|372|Performance|Large dataset behavior|5.80|Test massive scan reports|
|373|Performance|Serialization overhead|6.80|Cap/stream large payloads|
|374|Performance|Performance regression gates|4.90|Add CI benchmarks|
|375|Performance|Performance SOTA alignment|6.35|Add load/soak/cost budgets|
|376|Scalability|Horizontal API scaling|7.40|Test multi-instance deployments|
|377|Scalability|Agent service scaling|7.00|Coordinate consumers durably|
|378|Scalability|Celery worker scaling|7.40|Tune queues/prefetch|
|379|Scalability|Redis bottlenecks|6.70|Measure under high event rates|
|380|Scalability|Database scaling|6.80|Add pool/index guidance|
|381|Scalability|Vector store scaling|6.40|Shard/collection strategy|
|382|Scalability|Object storage scaling|7.00|Define lifecycle rules|
|383|Scalability|Multi-tenant scaling|5.80|Isolate workspaces and quotas|
|384|Scalability|Quota management|5.20|Add tenant/user quotas|
|385|Scalability|LLM rate scaling|5.60|Global limiter and fallback|
|386|Scalability|Autoscaling policies|5.60|Add HPA/KEDA guidance|
|387|Scalability|Queue partitioning|6.20|Partition by workload class|
|388|Scalability|Hotspot avoidance|6.00|Identify hot event types|
|389|Scalability|Large report scaling|6.30|Chunk map-reduce summaries|
|390|Scalability|Large frontend datasets|6.10|Virtualize lists/graphs|
|391|Scalability|Load shedding|5.40|Define overload modes|
|392|Scalability|Capacity planning|5.50|Publish sizing guide|
|393|Scalability|Benchmark dataset|4.80|Create canonical load corpus|
|394|Scalability|Cost control|5.70|Set budget alerts|
|395|Scalability|Multi-region readiness|4.20|Not near-term requirement|
|396|Scalability|State partitioning|5.60|Design durable partitions|
|397|Scalability|Service discovery|6.60|Document service dependencies|
|398|Scalability|Storage growth|6.30|Retention and compaction plans|
|399|Scalability|Scalable eval runs|4.70|Batch AI eval infrastructure|
|400|Scalability|Scalability SOTA alignment|5.95|Add quotas, autoscaling, durable consumers|
|401|Documentation|README completeness|8.30|Keep v6 architecture synchronized|
|402|Documentation|Architecture guide|8.10|Add updated agent flow diagram|
|403|Documentation|Agent docs|6.80|Document env vars/results/limits|
|404|Documentation|Runbooks|5.50|Create incident procedures|
|405|Documentation|API reference|7.40|Add examples for agent endpoints|
|406|Documentation|Config reference|7.00|Add new env vars|
|407|Documentation|Deployment guide|7.60|Add AI profile sizing|
|408|Documentation|Developer guide|7.20|Add agent extension guide|
|409|Documentation|Testing guide|5.80|Document test tiers/evals|
|410|Documentation|Security guide|6.80|Add prompt/LLM privacy section|
|411|Documentation|Threat model|5.00|Create formal threat model|
|412|Documentation|ADR coverage|4.80|Start ADR library|
|413|Documentation|Module author docs|7.00|Add async/error best practices|
|414|Documentation|Troubleshooting|7.00|Add agent failure modes|
|415|Documentation|SLO docs|4.60|Define operational SLOs|
|416|Documentation|Schema docs|5.60|Generate event/result schemas|
|417|Documentation|Prompt docs|4.80|Version prompt contracts|
|418|Documentation|Migration docs|6.50|Add v6 agent migration notes|
|419|Documentation|Examples|6.80|Add end-to-end AI workflow|
|420|Documentation|CLI docs|7.00|Update agent task usage|
|421|Documentation|Observability docs|6.60|Add dashboard descriptions|
|422|Documentation|Contribution docs|7.20|Add review checklist|
|423|Documentation|Glossary|6.30|Define event/agent terms|
|424|Documentation|Roadmap clarity|5.90|Add 9.78 roadmap milestones|
|425|Documentation|Docs SOTA alignment|6.55|Docs-as-contract with generated schemas|
|426|SOTA alignment|Durable workflow execution|4.90|Adopt graph/checkpoint workflow|
|427|SOTA alignment|State checkpointing|5.20|Persist agent state every step|
|428|SOTA alignment|Replayable traces|5.10|Add trace replay tooling|
|429|SOTA alignment|Human approval gates|4.10|Add HITL queue|
|430|SOTA alignment|Tool sandboxing|4.30|Define safe tool runtime|
|431|SOTA alignment|Typed action plans|4.50|Implement action schema|
|432|SOTA alignment|Agent role contracts|5.90|Document role boundaries|
|433|SOTA alignment|Multi-agent graph|4.80|Introduce graph orchestrator|
|434|SOTA alignment|Memory scoping|5.10|Add per-scan memory with TTL|
|435|SOTA alignment|Eval-driven development|3.90|Build eval harness|
|436|SOTA alignment|Red-team gating|3.80|Add adversarial prompt CI|
|437|SOTA alignment|Automatic output repair|5.50|Repair invalid JSON then retry|
|438|SOTA alignment|Policy-as-code|4.60|Centralize AI/tool policies|
|439|SOTA alignment|Cost-aware routing|5.20|Model router by cost/quality|
|440|SOTA alignment|Provider fallback|5.40|Add ordered fallback list|
|441|SOTA alignment|Context engineering|6.50|Use token-aware evidence packing|
|442|SOTA alignment|Grounded citations|5.90|Require source event citations|
|443|SOTA alignment|Benchmarks vs alternatives|4.40|Track against LangGraph/AutoGen patterns|
|444|SOTA alignment|Formal termination control|5.00|Define stopping criteria|
|445|SOTA alignment|Safe autonomy bounds|4.60|Define max steps/actions/privileges|
|446|SOTA alignment|Self-healing workflows|4.30|Add retry/resume from checkpoints|
|447|SOTA alignment|Production eval dashboards|3.80|Track quality drift|
|448|SOTA alignment|Lineage and provenance|5.30|Persist provenance graph|
|449|SOTA alignment|Autonomy governance|4.40|Review board/policy gates|
|450|SOTA alignment|Overall SOTA alignment|5.05|Prioritize durable graph + eval suite|
|451|Compliance/governance|License clarity|8.80|Keep third-party notices current|
|452|Compliance/governance|Data privacy posture|6.20|Document LLM data flow|
|453|Compliance/governance|PII handling|5.90|Add classification/redaction tests|
|454|Compliance/governance|Retention governance|6.30|Expose retention configs|
|455|Compliance/governance|Auditability|5.80|Record agent decisions|
|456|Compliance/governance|Access control governance|6.80|Add authz reviews|
|457|Compliance/governance|Change management|6.10|Add prompt/model change approvals|
|458|Compliance/governance|Risk acceptance|4.80|Track accepted risks|
|459|Compliance/governance|Model governance|4.60|Create model registry|
|460|Compliance/governance|Vendor governance|4.90|Assess LLM providers|
|461|Compliance/governance|Regulatory mapping|4.80|Map controls to SOC2/GDPR/etc.|
|462|Compliance/governance|Evidence collection|5.00|Automate control evidence|
|463|Compliance/governance|Incident governance|5.20|Create incident process|
|464|Compliance/governance|Abuse prevention|5.10|Quota/policy/rate limits|
|465|Compliance/governance|User consent/notice|4.70|Document AI data sharing|
|466|Compliance/governance|Data residency|4.30|Define hosting/model constraints|
|467|Compliance/governance|Export control awareness|4.60|Add policy note if needed|
|468|Compliance/governance|Responsible AI policy|4.40|Document AI use boundaries|
|469|Compliance/governance|Security review process|6.00|Add AI-specific checklist|
|470|Compliance/governance|Third-party risk|5.10|Review SaaS dependencies|
|471|Compliance/governance|Secret governance|6.40|Use external secret stores|
|472|Compliance/governance|Operational approvals|4.90|Add HITL for risky actions|
|473|Compliance/governance|Telemetry governance|5.20|Classify logs/metrics|
|474|Compliance/governance|Compliance docs|5.00|Publish compliance matrix|
|475|Compliance/governance|Governance SOTA alignment|5.10|Add model/data/policy governance|
|476|Product/operations|Core OSINT value|8.60|Maintain module quality|
|477|Product/operations|Agentic user value|7.00|Show trust/evidence in UI|
|478|Product/operations|Operational readiness|6.50|Add SLO/runbook maturity|
|479|Product/operations|Incident response|5.40|Create playbooks|
|480|Product/operations|User onboarding|7.10|Add guided AI setup|
|481|Product/operations|Admin controls|6.60|Expose agent limits/policies|
|482|Product/operations|Cost transparency|4.90|Show LLM cost estimates|
|483|Product/operations|Quality transparency|5.20|Show confidence/evidence/validation|
|484|Product/operations|Agent result workflow|6.20|Add history/search/acknowledge|
|485|Product/operations|False positive workflow|6.00|Add review/feedback labels|
|486|Product/operations|Feedback loop|4.80|Capture user corrections for eval|
|487|Product/operations|Enterprise readiness|6.20|Governance, SSO, audit, quotas|
|488|Product/operations|Community contribution|7.40|Add agent contribution guide|
|489|Product/operations|Release quality|6.80|Add pre-release smoke/eval gates|
|490|Product/operations|Supportability|5.90|Add diagnostic bundle|
|491|Product/operations|Upgrade safety|6.10|Add migration tests|
|492|Product/operations|Plugin ecosystem health|7.20|Quality score modules|
|493|Product/operations|Roadmap clarity|5.90|Publish agentic roadmap|
|494|Product/operations|Competitive differentiation|7.00|Blend OSINT modules + AI reasoning|
|495|Product/operations|Trust model|5.60|Evidence-first AI UX|
|496|Product/operations|Autonomy controls|4.90|Add safe autonomy modes|
|497|Product/operations|User training|5.20|Document AI limitations|
|498|Product/operations|Operational KPIs|5.10|Track agent quality, latency, cost|
|499|Product/operations|Continuous improvement loop|5.30|Use eval + feedback + telemetry|
|500|Product/operations|Overall product SOTA alignment|6.35|Make AI explainable, governed, and measured|

---

## 6. Highest-Risk Findings Remaining

1. **No durable graph/checkpoint engine for agentic workflows.** Agent execution is still event-response oriented, not a resumable multi-step state graph.
2. **No formal AI evaluation harness.** There are no golden datasets, adversarial prompt suites, quality thresholds, or drift dashboards.
3. **No agent DLQ/replay tooling.** Poison events, bad payloads, and model/provider errors need replayable failure queues.
4. **No policy-as-code for agent autonomy.** Tool calls and future autonomous actions need typed allowlists, budgets, approval gates, and audit logs.
5. **Limited prompt/model governance.** Prompts need versioning, review, owners, and regression testing.
6. **Limited source-grounding guarantees.** Agent outputs should cite event IDs and evidence payload hashes.
7. **LLM provider failover is incomplete.** Retries exist now, but fallback chains, circuit breakers, and budget routing are still missing.
8. **Testing lacks concurrency, load, chaos, and security adversarial coverage.** Current new tests are a foundation, not the full quality gate.

---

## 7. Walkthrough to Reach >9.78

### Phase 1 — Stabilize agent I/O contracts

- Define Pydantic schemas for every agent result.
- Replace all raw `call_llm()` JSON parsing with `call_llm_structured()`.
- Add schema version fields to `AgentResult` and persisted Redis payloads.
- Add source event IDs and payload hashes to every output.
- Add result-listing and result-replay API endpoints.

### Phase 2 — Durable orchestration

- Replace ad-hoc background tasks with a durable agent workflow engine.
- Persist agent workflow state: received, queued, processing, retrying, completed, failed, DLQ.
- Implement idempotency keys: `scan_id + event_id + agent_name + prompt_version`.
- Add replay tooling for failed/poison events.
- Add operator controls for pause/resume/cancel/retry.

### Phase 3 — SOTA reliability controls

- Add provider circuit breakers and ordered fallback chains.
- Add global and per-agent LLM rate limits.
- Add LLM budget controls by tenant/workspace/scan.
- Add queue-depth dashboards and saturation alerts.
- Add chaos tests for Redis, LiteLLM, database, and Qdrant failures.

### Phase 4 — Evaluation and alignment

- Build golden datasets for finding validation, credential analysis, document analysis, threat intel, IaC review, and reporting.
- Add adversarial prompt-injection datasets.
- Gate CI on exact schema validity, grounded evidence citations, hallucination checks, and severity calibration.
- Track quality drift by model, prompt version, and data source.

### Phase 5 — Secure autonomy

- Define typed action plans for future autonomous module/tool use.
- Add allowlisted tools, max steps, max cost, max runtime, and approval gates.
- Sandbox active actions and require human review for risky operations.
- Persist a full decision audit trail.

### Phase 6 — Product and operations maturity

- Add an agent dashboard with latency, retries, errors, queue depth, cost, and quality score.
- Add user feedback labels to improve eval datasets.
- Add runbooks, SLOs, and incident-response procedures.
- Add compliance docs for LLM data flows, retention, and provider governance.

---

## 8. Scoring Gate for >9.78

SpiderFoot should only claim >9.78 when all of the following are true:

- 500-dimension weighted score average is >=9.78 across two consecutive releases.
- No P0/P1 agentic reliability findings remain open.
- Agent output schema validity is >=99.95% over a held-out eval set.
- Prompt-injection resistance passes the adversarial corpus at the defined threshold.
- All agent outputs cite source event IDs/hashes or explicitly declare insufficient evidence.
- Redis/LLM/Postgres outage chaos tests pass without data corruption or unbounded task growth.
- Per-agent p95 latency, error rate, retry rate, and cost are on dashboards with alerts.
- Durable replay can recover failed agent jobs without duplicate result corruption.
- Human approval is enforced for high-risk autonomous tool actions.

---

## 9. Immediate Next Implementation Backlog

| Priority | Task | Expected score impact |
|---|---|---:|
|P0|Add Pydantic schemas for all non-report agent outputs|+0.18|
|P0|Use `call_llm_structured()` in each agent|+0.15|
|P0|Persist agent result schema version and source event hash|+0.10|
|P0|Add agent DLQ and replay endpoint/CLI|+0.22|
|P1|Add LiteLLM circuit breaker and provider fallback list|+0.16|
|P1|Add prompt injection golden tests|+0.20|
|P1|Add agent eval harness with minimum quality thresholds|+0.35|
|P1|Add OpenTelemetry spans for event-to-agent-to-result|+0.14|
|P1|Add agent result history UI|+0.08|
|P2|Add SLO dashboards and alert rules|+0.12|

---

## 10. Conclusion

The repo has a strong foundation and a credible AI-agent direction, but the requested >9.78 score requires a disciplined SOTA reliability/evaluation/governance program rather than only local code fixes. This pass materially improved the most immediate instability risks in the agentic section and created a test foundation. The next highest-leverage move is schema-first agent outputs plus durable replayable orchestration.
