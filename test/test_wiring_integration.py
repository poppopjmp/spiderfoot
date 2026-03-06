"""Integration tests for disconnected-module wiring.

Validates that all 33 previously-disconnected modules are now:
  1. Re-exported from their package ``__init__.py``.
  2. Importable at the symbol level.
  3. Registered in the service registry where applicable.
  4. Accessible via CLI sub-commands.

Run:
    pytest test/test_wiring_integration.py -v
"""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest


# ===================================================================
# 1. Package-level re-export smoke tests
# ===================================================================

@pytest.mark.parametrize("module,symbol", [
    # security
    ("spiderfoot.security", "SecretManager"),
    ("spiderfoot.security", "get_secret_manager"),
    ("spiderfoot.security", "check_startup_secrets"),
    ("spiderfoot.security", "EncryptedFileSecretBackend"),
    # observability
    ("spiderfoot.observability", "ErrorClass"),
    ("spiderfoot.observability", "ErrorTelemetry"),
    ("spiderfoot.observability", "get_error_telemetry"),
    ("spiderfoot.observability", "get_tracer"),
    ("spiderfoot.observability", "trace_span"),
    ("spiderfoot.observability", "shutdown_tracer"),
    # ops
    ("spiderfoot.ops", "ScanBenchmark"),
    ("spiderfoot.ops", "BenchmarkResult"),
    ("spiderfoot.ops", "PostgresTuningAdvisor"),
    ("spiderfoot.ops", "PerformanceRegressionRunner"),
    ("spiderfoot.ops", "ModuleWatcher"),
    ("spiderfoot.ops", "HealthChecker"),
    ("spiderfoot.ops", "CircuitBreaker"),
    ("spiderfoot.ops", "DeadLetterQueue"),
    ("spiderfoot.ops", "SLOTracker"),
    ("spiderfoot.ops", "AlertManager"),
    # research
    ("spiderfoot.research", "GraphRiskScorer"),
    ("spiderfoot.research", "AutonomousScanPlanner"),
    ("spiderfoot.research", "FederatedScanCoordinator"),
    ("spiderfoot.research", "PassiveMonitor"),
    ("spiderfoot.research", "FalsePositiveReducer"),
    ("spiderfoot.research", "NaturalLanguageParser"),
    # ai
    ("spiderfoot.ai", "SeverityLevel"),
    ("spiderfoot.ai", "RiskAssessmentOutput"),
    ("spiderfoot.ai", "ScanReportOutput"),
    ("spiderfoot.ai", "IntelligenceGraph"),
    ("spiderfoot.ai", "ConfidenceCalibrator"),
    ("spiderfoot.ai", "PromptCache"),
    ("spiderfoot.ai", "Verdict"),
    # core
    ("spiderfoot.core", "ModuleManager"),
    ("spiderfoot.core", "ValidationUtils"),
    # eventbus
    ("spiderfoot.eventbus", "ResilientEventBus"),
    ("spiderfoot.eventbus", "ResilientConfig"),
    # recon
    ("spiderfoot.recon", "FingerprintEvasionEngine"),
    ("spiderfoot.recon", "JA3Calculator"),
    ("spiderfoot.recon", "JA4Calculator"),
    ("spiderfoot.recon", "list_profile_names"),
    # scan
    ("spiderfoot.scan", "WorkStealingScheduler"),
    ("spiderfoot.scan", "BackpressureController"),
    ("spiderfoot.scan", "EventDeduplicator"),
    ("spiderfoot.scan", "ScanSplitter"),
    # api
    ("spiderfoot.api", "APIChangelog"),
    ("spiderfoot.api", "OpenAPIGenerator"),
    ("spiderfoot.api", "strip_internal_fields"),
    ("spiderfoot.api", "APIVersionManager"),
    # db
    ("spiderfoot.db", "QueryDiagnostics"),
    ("spiderfoot.db", "ExplainResult"),
    ("spiderfoot.db", "PgNotifyService"),
    ("spiderfoot.db", "PartitionManager"),
    ("spiderfoot.db", "MigrationManager"),
    ("spiderfoot.db", "DbAdapter"),
    # correlation
    ("spiderfoot.correlation", "VectorCollectionManager"),
    ("spiderfoot.correlation", "get_collection_manager"),
    # ecosystem
    ("spiderfoot.ecosystem", "ModuleSubmissionPipeline"),
    ("spiderfoot.ecosystem", "ModuleSigner"),
    ("spiderfoot.ecosystem", "SDKGenerator"),
])
def test_symbol_importable(module: str, symbol: str) -> None:
    """Every wired symbol must be importable from its package."""
    mod = importlib.import_module(module)
    assert hasattr(mod, symbol), f"{module}.{symbol} not found"


# ===================================================================
# 2. __all__ containment
# ===================================================================

@pytest.mark.parametrize("module,symbol", [
    ("spiderfoot.security", "SecretManager"),
    ("spiderfoot.security", "check_startup_secrets"),
    ("spiderfoot.observability", "ErrorTelemetry"),
    ("spiderfoot.observability", "get_tracer"),
    ("spiderfoot.ops", "ScanBenchmark"),
    ("spiderfoot.ops", "ModuleWatcher"),
    ("spiderfoot.research", "GraphRiskScorer"),
    ("spiderfoot.ai", "SeverityLevel"),
    ("spiderfoot.eventbus", "ResilientEventBus"),
    ("spiderfoot.recon", "FingerprintEvasionEngine"),
    ("spiderfoot.scan", "WorkStealingScheduler"),
    ("spiderfoot.api", "APIChangelog"),
    ("spiderfoot.ecosystem", "SDKGenerator"),
])
def test_symbol_in_all(module: str, symbol: str) -> None:
    """Key symbols must appear in __all__."""
    mod = importlib.import_module(module)
    all_list = getattr(mod, "__all__", [])
    assert symbol in all_list, f"{symbol} not in {module}.__all__"


# ===================================================================
# 3. Service registry constants
# ===================================================================

def test_service_constants_exist() -> None:
    """All new service constants must be importable."""
    from spiderfoot.service_registry import (
        SERVICE_RESULT_CACHE,
        SERVICE_RETRY,
        SERVICE_SCHEDULER,
        SERVICE_SECRETS,
        SERVICE_ERROR_TELEMETRY,
        SERVICE_DB_DIAGNOSTICS,
        SERVICE_DB_NOTIFY,
        SERVICE_MIGRATION,
        SERVICE_HOT_RELOAD,
    )
    assert SERVICE_RESULT_CACHE == "result_cache"
    assert SERVICE_RETRY == "retry"
    assert SERVICE_SCHEDULER == "scheduler"
    assert SERVICE_SECRETS == "secrets"
    assert SERVICE_ERROR_TELEMETRY == "error_telemetry"
    assert SERVICE_DB_DIAGNOSTICS == "db_diagnostics"
    assert SERVICE_DB_NOTIFY == "db_notify"
    assert SERVICE_MIGRATION == "migration"
    assert SERVICE_HOT_RELOAD == "hot_reload"


# ===================================================================
# 4. Service factories registered
# ===================================================================

def test_service_factories_registered() -> None:
    """Factories for new services must be registered after initialize_services()."""
    from spiderfoot.service_registry import (
        initialize_services,
        get_registry,
        SERVICE_RESULT_CACHE,
        SERVICE_RETRY,
        SERVICE_SCHEDULER,
        SERVICE_SECRETS,
        SERVICE_ERROR_TELEMETRY,
        SERVICE_DB_DIAGNOSTICS,
        SERVICE_DB_NOTIFY,
        SERVICE_MIGRATION,
        SERVICE_HOT_RELOAD,
    )

    initialize_services({})
    reg = get_registry()

    for svc_name in [
        SERVICE_RESULT_CACHE,
        SERVICE_RETRY,
        SERVICE_SCHEDULER,
        SERVICE_SECRETS,
        SERVICE_ERROR_TELEMETRY,
        SERVICE_DB_DIAGNOSTICS,
        SERVICE_DB_NOTIFY,
        SERVICE_MIGRATION,
        SERVICE_HOT_RELOAD,
    ]:
        assert reg.has(svc_name), f"Service '{svc_name}' not registered"


# ===================================================================
# 5. integrate_services() wires startup hooks
# ===================================================================

def test_integrate_services_runs() -> None:
    """integrate_services() must succeed and return True."""
    from spiderfoot.service_integration import integrate_services

    result = integrate_services({})
    assert result is True


# ===================================================================
# 6–7. CLI tests removed — CLI is now a Go binary (cli/)
# ===================================================================


# ===================================================================
# 8. Wire functions exist in service_integration
# ===================================================================

def test_wire_functions_exist() -> None:
    """_wire_result_cache and _wire_scheduler must be callable."""
    from spiderfoot import service_integration as si

    assert callable(getattr(si, "_wire_result_cache", None)), \
        "_wire_result_cache not found"
    assert callable(getattr(si, "_wire_scheduler", None)), \
        "_wire_scheduler not found"


# ===================================================================
# 9. Startup check runs safely
# ===================================================================

def test_startup_check_safe() -> None:
    """check_startup_secrets must return list without crashing."""
    from spiderfoot.security.startup_check import check_startup_secrets
    result = check_startup_secrets(fail_in_production=False)
    assert isinstance(result, list)


# ===================================================================
# 10. Error telemetry singleton
# ===================================================================

def test_error_telemetry_singleton() -> None:
    """get_error_telemetry must return same instance."""
    from spiderfoot.observability.error_telemetry import get_error_telemetry
    a = get_error_telemetry()
    b = get_error_telemetry()
    assert a is b


# ===================================================================
# 11. Tracing no-op fallback
# ===================================================================

def test_tracing_noop_fallback() -> None:
    """get_tracer should return a usable tracer (no-op if OTel missing)."""
    from spiderfoot.observability.tracing import get_tracer
    tracer = get_tracer("test")
    assert tracer is not None
    # Ensure span creation doesn't crash
    span = tracer.start_as_current_span("test_span")
    assert span is not None


# ===================================================================
# 12. TLS fingerprint profiles
# ===================================================================

def test_tls_profile_names_nonempty() -> None:
    """list_profile_names must return at least one profile."""
    from spiderfoot.recon.tls_fingerprint import list_profile_names
    names = list_profile_names()
    assert len(names) >= 1


# ===================================================================
# 13. Response filter strips fields
# ===================================================================

def test_response_filter_strips() -> None:
    """strip_internal_fields must remove password fields."""
    from spiderfoot.api.response_filter import strip_internal_fields
    data = {"username": "admin", "password": "secret123", "email": "a@b.com"}
    cleaned = strip_internal_fields(data)
    assert "password" not in cleaned
    assert cleaned["username"] == "admin"
    assert cleaned["email"] == "a@b.com"


# ===================================================================
# 14. Version negotiation basics
# ===================================================================

def test_version_manager_registers() -> None:
    """APIVersionManager must accept version registration."""
    from spiderfoot.api.version_negotiation import (
        APIVersionManager, APIVersion, VersionStatus,
    )
    vm = APIVersionManager(default_version="v2")
    vm.register_version(APIVersion(
        "v1", status=VersionStatus.DEPRECATED,
        deprecated_at="2025-06-01", sunset_at="2026-01-01",
    ))
    vm.register_version(APIVersion("v2", status=VersionStatus.CURRENT))
    assert len(vm._versions) >= 2


# ===================================================================
# 15. Ecosystem tooling basics
# ===================================================================

def test_module_submission_pipeline() -> None:
    """ModuleSubmissionPipeline must accept a submission."""
    from spiderfoot.ecosystem.ecosystem_tooling import (
        ModuleSubmission,
        ModuleSubmissionPipeline,
    )
    pipeline = ModuleSubmissionPipeline()
    sub = ModuleSubmission(
        module_name="sfp_test",
        author="test",
        version="1.0.0",
        description="Test module",
        source_code="class sfp_test: pass",
    )
    result = pipeline.submit(sub)
    assert result is not None


# ===================================================================
# 16. AI schema instantiation
# ===================================================================

def test_ai_schemas_instantiate() -> None:
    """AI output schemas must be instantiable."""
    from spiderfoot.ai.schemas import SeverityLevel, Finding
    f = Finding(
        title="Test finding",
        severity=SeverityLevel.LOW,
        description="Test",
    )
    assert f.title == "Test finding"
    assert f.severity == SeverityLevel.LOW
