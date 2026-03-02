# Operations and infrastructure utilities.
"""SpiderFoot operations subpackage — benchmarks, hot-reload, ops tooling."""

from __future__ import annotations

from .benchmarks import (
    BenchmarkResult,
    DBWriteBenchmark,
    EventPipelineBenchmark,
    MultiBenchmark,
    PerformanceRegressionRunner,
    PerformanceThreshold,
    PostgresTuningAdvisor,
    ScanBenchmark,
    ThresholdResult,
    ThroughputSimulator,
)

from .hot_reload import (
    ModuleState,
    ModuleWatcher,
    ReloadEvent,
)

from .ops_tooling import (
    AlertManager,
    AlertRule,
    CircuitBreaker,
    CircuitBreakerRegistry,
    ComponentHealth,
    DataRetentionManager,
    DeadLetterQueue,
    HealthChecker,
    HealthStatus,
    K8sConfigGenerator,
    LoadTestScenario,
    RetentionPolicy,
    ScanRecoveryManager,
    SLODefinition,
    SLOTracker,
    TenantIsolationValidator,
)

__all__ = [
    # Benchmarks
    "BenchmarkResult",
    "DBWriteBenchmark",
    "EventPipelineBenchmark",
    "MultiBenchmark",
    "PerformanceRegressionRunner",
    "PerformanceThreshold",
    "PostgresTuningAdvisor",
    "ScanBenchmark",
    "ThresholdResult",
    "ThroughputSimulator",
    # Hot-reload
    "ModuleState",
    "ModuleWatcher",
    "ReloadEvent",
    # Ops tooling
    "AlertManager",
    "AlertRule",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "ComponentHealth",
    "DataRetentionManager",
    "DeadLetterQueue",
    "HealthChecker",
    "HealthStatus",
    "K8sConfigGenerator",
    "LoadTestScenario",
    "RetentionPolicy",
    "ScanRecoveryManager",
    "SLODefinition",
    "SLOTracker",
    "TenantIsolationValidator",
]
