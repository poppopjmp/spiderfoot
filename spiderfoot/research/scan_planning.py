"""Phase 8a — Autonomous Scan Planning + Federated Scan Distribution.

Cycles 651-700: AI-driven module selection based on discovered attack surface.
Cycles 851-900: Distributed scan coordination across multiple instances.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Attack Surface Model ──────────────────────────────────────────────


class AssetType(Enum):
    """Types of assets discovered during a scan."""

    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP_ADDRESS = "ip_address"
    EMAIL = "email"
    URL = "url"
    OPEN_PORT = "open_port"
    TECHNOLOGY = "technology"
    CERTIFICATE = "certificate"
    PERSON = "person"
    ORGANIZATION = "organization"
    ASN = "asn"


@dataclass
class Asset:
    """A discovered asset in the attack surface."""

    asset_type: AssetType
    value: str
    source_module: str = ""
    confidence: float = 1.0
    discovered_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.asset_type.value}:{self.value}"


class AttackSurface:
    """Tracks the discovered attack surface during a scan."""

    def __init__(self) -> None:
        self._assets: dict[str, Asset] = {}

    def add_asset(self, asset: Asset) -> bool:
        """Add an asset. Returns True if new."""
        if asset.key in self._assets:
            return False
        self._assets[asset.key] = asset
        return True

    def get_assets(
        self,
        asset_type: AssetType | None = None,
        min_confidence: float = 0.0,
    ) -> list[Asset]:
        """Get assets, optionally filtered."""
        result = []
        for a in self._assets.values():
            if asset_type and a.asset_type != asset_type:
                continue
            if a.confidence < min_confidence:
                continue
            result.append(a)
        return result

    def get_type_counts(self) -> dict[str, int]:
        """Count assets by type."""
        counts: dict[str, int] = {}
        for a in self._assets.values():
            counts[a.asset_type.value] = counts.get(a.asset_type.value, 0) + 1
        return counts

    @property
    def total_assets(self) -> int:
        return len(self._assets)

    def has_type(self, asset_type: AssetType) -> bool:
        return any(a.asset_type == asset_type for a in self._assets.values())

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_assets": self.total_assets,
            "type_counts": self.get_type_counts(),
            "asset_types": list(set(a.asset_type.value for a in self._assets.values())),
        }


# ── Module Knowledge Base ────────────────────────────────────────────


@dataclass
class ModuleCapability:
    """Describes a module's capability for the planner."""

    module_name: str
    input_types: list[str] = field(default_factory=list)
    output_types: list[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high
    is_passive: bool = True
    avg_duration_seconds: float = 10.0
    requires_api_key: bool = False
    description: str = ""
    tags: list[str] = field(default_factory=list)


class ModuleKnowledgeBase:
    """Registry of module capabilities for the scan planner."""

    DEFAULT_MODULES: list[dict[str, Any]] = [
        {
            "module_name": "sfp_dns",
            "input_types": ["domain", "subdomain"],
            "output_types": ["ip_address", "subdomain", "domain"],
            "risk_level": "low",
            "is_passive": True,
            "avg_duration_seconds": 5.0,
            "description": "DNS resolution and record enumeration",
            "tags": ["dns", "infrastructure"],
        },
        {
            "module_name": "sfp_whois",
            "input_types": ["domain", "ip_address"],
            "output_types": ["email", "person", "organization"],
            "risk_level": "low",
            "is_passive": True,
            "avg_duration_seconds": 8.0,
            "description": "WHOIS registration data",
            "tags": ["whois", "registration"],
        },
        {
            "module_name": "sfp_ssl",
            "input_types": ["domain", "ip_address"],
            "output_types": ["certificate", "email", "domain"],
            "risk_level": "low",
            "is_passive": True,
            "avg_duration_seconds": 10.0,
            "description": "SSL/TLS certificate analysis",
            "tags": ["ssl", "certificates"],
        },
        {
            "module_name": "sfp_portscan",
            "input_types": ["ip_address"],
            "output_types": ["open_port", "technology"],
            "risk_level": "high",
            "is_passive": False,
            "avg_duration_seconds": 120.0,
            "description": "TCP port scanning",
            "tags": ["ports", "active"],
        },
        {
            "module_name": "sfp_email",
            "input_types": ["domain"],
            "output_types": ["email", "person"],
            "risk_level": "low",
            "is_passive": True,
            "avg_duration_seconds": 15.0,
            "description": "Email address harvesting",
            "tags": ["email", "osint"],
        },
        {
            "module_name": "sfp_subdomain",
            "input_types": ["domain"],
            "output_types": ["subdomain"],
            "risk_level": "low",
            "is_passive": True,
            "avg_duration_seconds": 30.0,
            "description": "Subdomain enumeration",
            "tags": ["subdomain", "discovery"],
        },
        {
            "module_name": "sfp_shodan",
            "input_types": ["ip_address", "domain"],
            "output_types": ["open_port", "technology", "certificate"],
            "risk_level": "low",
            "is_passive": True,
            "avg_duration_seconds": 5.0,
            "requires_api_key": True,
            "description": "Shodan passive reconnaissance",
            "tags": ["shodan", "passive", "api"],
        },
        {
            "module_name": "sfp_webtech",
            "input_types": ["url", "domain"],
            "output_types": ["technology"],
            "risk_level": "low",
            "is_passive": True,
            "avg_duration_seconds": 10.0,
            "description": "Web technology detection",
            "tags": ["web", "technology"],
        },
    ]

    def __init__(self) -> None:
        self._modules: dict[str, ModuleCapability] = {}
        for m in self.DEFAULT_MODULES:
            self.register(ModuleCapability(**m))

    def register(self, cap: ModuleCapability) -> None:
        self._modules[cap.module_name] = cap

    def get(self, name: str) -> ModuleCapability | None:
        return self._modules.get(name)

    def get_all(self) -> list[ModuleCapability]:
        return list(self._modules.values())

    def find_by_input(self, asset_type: str) -> list[ModuleCapability]:
        """Find modules that can process the given asset type."""
        return [m for m in self._modules.values() if asset_type in m.input_types]

    def find_by_output(self, asset_type: str) -> list[ModuleCapability]:
        """Find modules that can produce the given asset type."""
        return [m for m in self._modules.values() if asset_type in m.output_types]

    def find_by_tag(self, tag: str) -> list[ModuleCapability]:
        return [m for m in self._modules.values() if tag in m.tags]

    @property
    def module_count(self) -> int:
        return len(self._modules)


# ── Scan Planner ──────────────────────────────────────────────────────


class ScanObjective(Enum):
    """High-level scan objectives."""

    FULL_RECON = "full_recon"
    PASSIVE_ONLY = "passive_only"
    EMAIL_HARVEST = "email_harvest"
    INFRASTRUCTURE = "infrastructure"
    VULNERABILITY = "vulnerability"
    QUICK_OVERVIEW = "quick_overview"


@dataclass
class ScanPlan:
    """A plan generated by the autonomous scan planner."""

    target: str
    objective: ScanObjective
    phases: list[ScanPhase] = field(default_factory=list)
    estimated_duration_seconds: float = 0.0
    total_modules: int = 0
    passive_only: bool = True
    reasoning: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "objective": self.objective.value,
            "phases": [p.to_dict() for p in self.phases],
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "total_modules": self.total_modules,
            "passive_only": self.passive_only,
            "reasoning": self.reasoning,
        }


@dataclass
class ScanPhase:
    """A phase within a scan plan."""

    name: str
    order: int
    modules: list[str] = field(default_factory=list)
    estimated_duration: float = 0.0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "order": self.order,
            "modules": self.modules,
            "estimated_duration": self.estimated_duration,
            "description": self.description,
        }


class AutonomousScanPlanner:
    """AI-driven scan planner that selects modules based on attack surface.

    Given a target and objective, proposes which modules to run in what order,
    adapting to the discovered attack surface.
    """

    OBJECTIVE_TAGS: dict[ScanObjective, list[str]] = {
        ScanObjective.FULL_RECON: [],  # all modules
        ScanObjective.PASSIVE_ONLY: [],
        ScanObjective.EMAIL_HARVEST: ["email", "osint"],
        ScanObjective.INFRASTRUCTURE: ["dns", "infrastructure", "ports"],
        ScanObjective.VULNERABILITY: ["ports", "active", "web"],
        ScanObjective.QUICK_OVERVIEW: ["dns", "whois"],
    }

    def __init__(
        self,
        knowledge_base: ModuleKnowledgeBase | None = None,
        available_api_keys: list[str] | None = None,
        max_duration_seconds: float = 3600.0,
    ) -> None:
        self.kb = knowledge_base or ModuleKnowledgeBase()
        self.available_api_keys = set(available_api_keys or [])
        self.max_duration_seconds = max_duration_seconds

    def _classify_target(self, target: str) -> str:
        """Classify a target string into an asset type."""
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", target):
            return "ip_address"
        if "@" in target:
            return "email"
        if target.startswith(("http://", "https://")):
            return "url"
        return "domain"

    def _select_modules(
        self,
        target_type: str,
        objective: ScanObjective,
        surface: AttackSurface | None = None,
    ) -> list[ModuleCapability]:
        """Select appropriate modules for the target and objective."""
        candidates = self.kb.find_by_input(target_type)

        # Filter by objective tags
        tags = self.OBJECTIVE_TAGS.get(objective, [])
        if tags:
            tagged = [m for m in candidates if any(t in m.tags for t in tags)]
            # Fall back to all candidates if tag filter yields nothing
            if tagged:
                candidates = tagged

        # Filter passive-only for that objective
        if objective == ScanObjective.PASSIVE_ONLY:
            candidates = [m for m in candidates if m.is_passive]

        # Filter by available API keys
        candidates = [
            m
            for m in candidates
            if not m.requires_api_key or m.module_name in self.available_api_keys
        ]

        # If surface provided, also consider newly discovered types
        if surface:
            discovered_types = set(
                a.asset_type.value for a in surface.get_assets()
            )
            for dtype in discovered_types:
                extra = self.kb.find_by_input(dtype)
                for m in extra:
                    if m not in candidates:
                        if objective == ScanObjective.PASSIVE_ONLY and not m.is_passive:
                            continue
                        if m.requires_api_key and m.module_name not in self.available_api_keys:
                            continue
                        candidates.append(m)

        return candidates

    def _build_phases(self, modules: list[ModuleCapability]) -> list[ScanPhase]:
        """Organize modules into ordered phases."""
        passive_low = [m for m in modules if m.is_passive and m.risk_level == "low"]
        passive_other = [
            m for m in modules if m.is_passive and m.risk_level != "low"
        ]
        active = [m for m in modules if not m.is_passive]

        phases: list[ScanPhase] = []
        if passive_low:
            phases.append(
                ScanPhase(
                    name="Passive Reconnaissance",
                    order=1,
                    modules=[m.module_name for m in passive_low],
                    estimated_duration=sum(m.avg_duration_seconds for m in passive_low),
                    description="Low-risk passive data collection",
                )
            )
        if passive_other:
            phases.append(
                ScanPhase(
                    name="Extended Passive",
                    order=2,
                    modules=[m.module_name for m in passive_other],
                    estimated_duration=sum(
                        m.avg_duration_seconds for m in passive_other
                    ),
                    description="Higher-value passive reconnaissance",
                )
            )
        if active:
            phases.append(
                ScanPhase(
                    name="Active Probing",
                    order=3,
                    modules=[m.module_name for m in active],
                    estimated_duration=sum(m.avg_duration_seconds for m in active),
                    description="Active scanning (may be detected by target)",
                )
            )

        return phases

    def plan(
        self,
        target: str,
        objective: ScanObjective = ScanObjective.FULL_RECON,
        surface: AttackSurface | None = None,
    ) -> ScanPlan:
        """Generate a scan plan for the given target and objective."""
        target_type = self._classify_target(target)
        reasoning = [
            f"Target '{target}' classified as {target_type}",
            f"Objective: {objective.value}",
        ]

        modules = self._select_modules(target_type, objective, surface)

        # Enforce time budget
        sorted_modules = sorted(modules, key=lambda m: m.avg_duration_seconds)
        selected: list[ModuleCapability] = []
        budget = 0.0
        for m in sorted_modules:
            if budget + m.avg_duration_seconds <= self.max_duration_seconds:
                selected.append(m)
                budget += m.avg_duration_seconds

        if len(selected) < len(modules):
            reasoning.append(
                f"Time budget limited selection to {len(selected)}/{len(modules)} modules"
            )

        phases = self._build_phases(selected)
        is_passive = all(m.is_passive for m in selected)

        reasoning.append(
            f"Selected {len(selected)} modules in {len(phases)} phases"
        )

        return ScanPlan(
            target=target,
            objective=objective,
            phases=phases,
            estimated_duration_seconds=budget,
            total_modules=len(selected),
            passive_only=is_passive,
            reasoning=reasoning,
        )

    def adapt_plan(
        self,
        current_plan: ScanPlan,
        surface: AttackSurface,
    ) -> ScanPlan:
        """Adapt a plan based on newly discovered attack surface."""
        return self.plan(
            current_plan.target,
            current_plan.objective,
            surface=surface,
        )


# ── Federated Scan Distribution (Cycles 851-900) ─────────────────────


class InstanceRegion(Enum):
    """Geographic regions for scan distribution."""

    US_EAST = "us-east"
    US_WEST = "us-west"
    EU_WEST = "eu-west"
    EU_CENTRAL = "eu-central"
    ASIA_EAST = "asia-east"
    ASIA_SOUTH = "asia-south"


@dataclass
class ScanInstance:
    """A SpiderFoot instance available for federated scanning."""

    instance_id: str
    region: InstanceRegion
    base_url: str
    capacity: int = 10  # concurrent scans
    current_load: int = 0
    api_key: str = ""
    is_healthy: bool = True
    latency_ms: float = 0.0
    supported_modules: list[str] = field(default_factory=list)

    @property
    def available_capacity(self) -> int:
        return max(0, self.capacity - self.current_load)


@dataclass
class ScanShard:
    """A portion of a scan assigned to a specific instance."""

    shard_id: str
    instance_id: str
    modules: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0
    results_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "instance_id": self.instance_id,
            "modules": self.modules,
            "targets": self.targets,
            "status": self.status,
            "results_count": self.results_count,
        }


class FederatedScanCoordinator:
    """Coordinates scan distribution across multiple SpiderFoot instances.

    Strategies:
    - Round-robin: Distribute shards evenly across healthy instances
    - Region-affinity: Prefer instances near the target
    - Capacity-based: Route to instance with most available capacity
    """

    def __init__(self) -> None:
        self._instances: dict[str, ScanInstance] = {}
        self._shards: dict[str, ScanShard] = {}
        self._shard_counter = 0

    def register_instance(self, instance: ScanInstance) -> None:
        self._instances[instance.instance_id] = instance

    def remove_instance(self, instance_id: str) -> bool:
        return self._instances.pop(instance_id, None) is not None

    def get_healthy_instances(
        self,
        region: InstanceRegion | None = None,
    ) -> list[ScanInstance]:
        """Get healthy instances, optionally filtered by region."""
        instances = [i for i in self._instances.values() if i.is_healthy]
        if region:
            instances = [i for i in instances if i.region == region]
        return instances

    def distribute_round_robin(
        self,
        modules: list[str],
        targets: list[str],
    ) -> list[ScanShard]:
        """Distribute work across instances using round-robin."""
        healthy = self.get_healthy_instances()
        if not healthy:
            return []

        shards: list[ScanShard] = []
        for i, module in enumerate(modules):
            instance = healthy[i % len(healthy)]
            self._shard_counter += 1
            shard = ScanShard(
                shard_id=f"shard-{self._shard_counter:04d}",
                instance_id=instance.instance_id,
                modules=[module],
                targets=targets,
            )
            self._shards[shard.shard_id] = shard
            shards.append(shard)

        return shards

    def distribute_capacity(
        self,
        modules: list[str],
        targets: list[str],
    ) -> list[ScanShard]:
        """Distribute work based on available capacity."""
        healthy = sorted(
            self.get_healthy_instances(),
            key=lambda i: i.available_capacity,
            reverse=True,
        )
        if not healthy:
            return []

        shards: list[ScanShard] = []
        for module in modules:
            # Pick instance with most capacity
            best = healthy[0]
            self._shard_counter += 1
            shard = ScanShard(
                shard_id=f"shard-{self._shard_counter:04d}",
                instance_id=best.instance_id,
                modules=[module],
                targets=targets,
            )
            self._shards[shard.shard_id] = shard
            shards.append(shard)

            # Update load tracking
            best.current_load += 1
            # Re-sort
            healthy.sort(key=lambda i: i.available_capacity, reverse=True)

        return shards

    def distribute_region_affinity(
        self,
        modules: list[str],
        targets: list[str],
        preferred_region: InstanceRegion,
    ) -> list[ScanShard]:
        """Distribute work preferring instances in a specific region."""
        regional = self.get_healthy_instances(region=preferred_region)
        if not regional:
            # Fall back to any healthy instance
            regional = self.get_healthy_instances()
        if not regional:
            return []

        shards: list[ScanShard] = []
        for i, module in enumerate(modules):
            instance = regional[i % len(regional)]
            self._shard_counter += 1
            shard = ScanShard(
                shard_id=f"shard-{self._shard_counter:04d}",
                instance_id=instance.instance_id,
                modules=[module],
                targets=targets,
            )
            self._shards[shard.shard_id] = shard
            shards.append(shard)

        return shards

    def get_shard(self, shard_id: str) -> ScanShard | None:
        return self._shards.get(shard_id)

    def update_shard_status(
        self,
        shard_id: str,
        status: str,
        results_count: int = 0,
    ) -> bool:
        shard = self._shards.get(shard_id)
        if not shard:
            return False
        shard.status = status
        if status == "running" and shard.started_at == 0:
            shard.started_at = time.time()
        elif status in ("completed", "failed"):
            shard.completed_at = time.time()
        shard.results_count = results_count
        return True

    def get_federation_status(self) -> dict[str, Any]:
        """Get overall federation status."""
        total_instances = len(self._instances)
        healthy = sum(1 for i in self._instances.values() if i.is_healthy)
        total_shards = len(self._shards)
        completed = sum(
            1 for s in self._shards.values() if s.status == "completed"
        )
        failed = sum(1 for s in self._shards.values() if s.status == "failed")
        total_results = sum(s.results_count for s in self._shards.values())

        return {
            "instances": {"total": total_instances, "healthy": healthy},
            "shards": {
                "total": total_shards,
                "completed": completed,
                "failed": failed,
                "pending": total_shards - completed - failed,
            },
            "total_results": total_results,
        }

    def merge_results(self) -> list[dict[str, Any]]:
        """Merge results from all completed shards."""
        results: list[dict[str, Any]] = []
        for shard in self._shards.values():
            if shard.status == "completed":
                results.append(shard.to_dict())
        return results

    @property
    def instance_count(self) -> int:
        return len(self._instances)

    @property
    def shard_count(self) -> int:
        return len(self._shards)
