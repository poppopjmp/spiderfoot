"""Attack Surface Management (ASM) asset inventory.

Provides a unified asset inventory that tracks all discovered assets
across scans, enabling continuous attack surface monitoring and
risk assessment.

Asset types: domains, subdomains, IPs, ports, technologies, certificates,
email addresses, cloud resources.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("spiderfoot.asm")


class AssetType(str, Enum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP_ADDRESS = "ip_address"
    PORT = "port"
    TECHNOLOGY = "technology"
    CERTIFICATE = "certificate"
    EMAIL = "email"
    CLOUD_RESOURCE = "cloud_resource"
    URL = "url"
    NETBLOCK = "netblock"
    ASN = "asn"
    PERSON = "person"
    ORGANIZATION = "organization"


class AssetRisk(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


class AssetStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    NEW = "new"
    CHANGED = "changed"
    REMOVED = "removed"


@dataclass
class AssetTag:
    key: str
    value: str
    source: str = ""


@dataclass
class Asset:
    """A discovered asset in the attack surface."""
    asset_id: str
    asset_type: AssetType
    value: str
    first_seen: str
    last_seen: str
    status: AssetStatus = AssetStatus.ACTIVE
    risk: AssetRisk = AssetRisk.UNKNOWN
    confidence: float = 1.0
    source_scans: list[str] = field(default_factory=list)
    source_modules: list[str] = field(default_factory=list)
    tags: list[AssetTag] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    related_assets: list[str] = field(default_factory=list)
    vulnerabilities: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["asset_type"] = self.asset_type.value
        d["status"] = self.status.value
        d["risk"] = self.risk.value
        return d


def _asset_id(asset_type: str, value: str) -> str:
    """Generate deterministic asset ID."""
    raw = f"{asset_type}:{value.lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# Event type → asset type mapping
_EVENT_TO_ASSET: dict[str, AssetType] = {
    "DOMAIN_NAME": AssetType.DOMAIN,
    "INTERNET_NAME": AssetType.SUBDOMAIN,
    "IP_ADDRESS": AssetType.IP_ADDRESS,
    "IPV6_ADDRESS": AssetType.IP_ADDRESS,
    "TCP_PORT_OPEN": AssetType.PORT,
    "UDP_PORT_OPEN": AssetType.PORT,
    "WEBSERVER_TECHNOLOGY": AssetType.TECHNOLOGY,
    "OPERATING_SYSTEM": AssetType.TECHNOLOGY,
    "SSL_CERTIFICATE_RAW": AssetType.CERTIFICATE,
    "EMAILADDR": AssetType.EMAIL,
    "LINKED_URL_INTERNAL": AssetType.URL,
    "NETBLOCK_OWNER": AssetType.NETBLOCK,
    "BGP_AS_OWNER": AssetType.ASN,
    "HUMAN_NAME": AssetType.PERSON,
    "COMPANY_NAME": AssetType.ORGANIZATION,
    "CLOUD_STORAGE_OPEN": AssetType.CLOUD_RESOURCE,
}

# Event types that indicate risk
_RISK_EVENTS: dict[str, AssetRisk] = {
    "VULNERABILITY_CVE_CRITICAL": AssetRisk.CRITICAL,
    "VULNERABILITY_CVE_HIGH": AssetRisk.HIGH,
    "VULNERABILITY_CVE_MEDIUM": AssetRisk.MEDIUM,
    "VULNERABILITY_CVE_LOW": AssetRisk.LOW,
    "VULNERABILITY_GENERAL": AssetRisk.MEDIUM,
    "MALICIOUS_IPADDR": AssetRisk.CRITICAL,
    "MALICIOUS_INTERNET_NAME": AssetRisk.CRITICAL,
    "MALICIOUS_AFFILIATE_IPADDR": AssetRisk.HIGH,
    "HASH_COMPROMISED": AssetRisk.HIGH,
    "EMAILADDR_COMPROMISED": AssetRisk.MEDIUM,
    "PASSWORD_COMPROMISED": AssetRisk.CRITICAL,
}


class AssetInventory:
    """Manages the attack surface asset inventory."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._assets: dict[str, Asset] = {}
        self._prefix = "sf:asm"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _redis_key(self, asset_id: str) -> str:
        return f"{self._prefix}:asset:{asset_id}"

    def ingest_event(
        self,
        event_type: str,
        data: str,
        scan_id: str = "",
        module: str = "",
    ) -> Asset | None:
        """Ingest a SpiderFoot event and create/update an asset."""
        asset_type = _EVENT_TO_ASSET.get(event_type)
        if asset_type is None:
            return None

        aid = _asset_id(asset_type.value, data)
        now = self._now()

        if aid in self._assets:
            # Update existing asset
            asset = self._assets[aid]
            asset.last_seen = now
            if scan_id and scan_id not in asset.source_scans:
                asset.source_scans.append(scan_id)
            if module and module not in asset.source_modules:
                asset.source_modules.append(module)
            if asset.status == AssetStatus.NEW:
                asset.status = AssetStatus.ACTIVE
        else:
            # Create new asset
            asset = Asset(
                asset_id=aid,
                asset_type=asset_type,
                value=data,
                first_seen=now,
                last_seen=now,
                status=AssetStatus.NEW,
                source_scans=[scan_id] if scan_id else [],
                source_modules=[module] if module else [],
            )
            self._assets[aid] = asset

        # Check for risk indicators
        risk = _RISK_EVENTS.get(event_type)
        if risk and risk.value < asset.risk.value if asset.risk != AssetRisk.UNKNOWN else True:
            asset.risk = risk

        # Persist to Redis if available
        if self._redis:
            try:
                self._redis.hset(
                    self._redis_key(aid),
                    mapping={"data": json.dumps(asset.to_dict())}
                )
                self._redis.sadd(f"{self._prefix}:index", aid)
                self._redis.sadd(f"{self._prefix}:type:{asset_type.value}", aid)
            except Exception as e:
                logger.warning("Redis ASM storage failed: %s", e)

        return asset

    def get_asset(self, asset_id: str) -> Asset | None:
        """Get an asset by ID."""
        asset = self._assets.get(asset_id)
        if asset:
            return asset
        # Try Redis
        if self._redis:
            try:
                data = self._redis.hget(self._redis_key(asset_id), "data")
                if data:
                    return self._deserialize_asset(json.loads(data))
            except Exception:
                pass
        return None

    def list_assets(
        self,
        asset_type: AssetType | None = None,
        risk: AssetRisk | None = None,
        status: AssetStatus | None = None,
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Asset]:
        """List assets with optional filters."""
        assets = list(self._assets.values())

        if asset_type:
            assets = [a for a in assets if a.asset_type == asset_type]
        if risk:
            assets = [a for a in assets if a.risk == risk]
        if status:
            assets = [a for a in assets if a.status == status]
        if search:
            search_lower = search.lower()
            assets = [a for a in assets if search_lower in a.value.lower()]

        # Sort by risk (critical first), then last_seen
        risk_order = {
            AssetRisk.CRITICAL: 0,
            AssetRisk.HIGH: 1,
            AssetRisk.MEDIUM: 2,
            AssetRisk.LOW: 3,
            AssetRisk.INFO: 4,
            AssetRisk.UNKNOWN: 5,
        }
        assets.sort(key=lambda a: (risk_order.get(a.risk, 5), a.last_seen), reverse=False)

        return assets[offset : offset + limit]

    def get_summary(self) -> dict[str, Any]:
        """Get asset inventory summary statistics."""
        assets = list(self._assets.values())
        by_type: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_status: dict[str, int] = {}

        for a in assets:
            by_type[a.asset_type.value] = by_type.get(a.asset_type.value, 0) + 1
            by_risk[a.risk.value] = by_risk.get(a.risk.value, 0) + 1
            by_status[a.status.value] = by_status.get(a.status.value, 0) + 1

        return {
            "total_assets": len(assets),
            "by_type": by_type,
            "by_risk": by_risk,
            "by_status": by_status,
            "unique_scans": len({s for a in assets for s in a.source_scans}),
            "unique_modules": len({m for a in assets for m in a.source_modules}),
        }

    def add_tag(self, asset_id: str, key: str, value: str, source: str = "") -> bool:
        """Add a tag to an asset."""
        asset = self._assets.get(asset_id)
        if not asset:
            return False
        # Avoid duplicates
        for t in asset.tags:
            if t.key == key and t.value == value:
                return True
        asset.tags.append(AssetTag(key=key, value=value, source=source))
        return True

    def link_assets(self, asset_id_1: str, asset_id_2: str) -> bool:
        """Create a bidirectional relationship between assets."""
        a1 = self._assets.get(asset_id_1)
        a2 = self._assets.get(asset_id_2)
        if not a1 or not a2:
            return False
        if asset_id_2 not in a1.related_assets:
            a1.related_assets.append(asset_id_2)
        if asset_id_1 not in a2.related_assets:
            a2.related_assets.append(asset_id_1)
        return True

    def mark_removed(self, asset_id: str) -> bool:
        """Mark an asset as removed from the attack surface."""
        asset = self._assets.get(asset_id)
        if not asset:
            return False
        asset.status = AssetStatus.REMOVED
        return True

    def delete_asset(self, asset_id: str) -> bool:
        """Permanently delete an asset."""
        if asset_id not in self._assets:
            return False
        del self._assets[asset_id]
        if self._redis:
            try:
                self._redis.delete(self._redis_key(asset_id))
                self._redis.srem(f"{self._prefix}:index", asset_id)
            except Exception:
                pass
        return True

    def _deserialize_asset(self, data: dict[str, Any]) -> Asset:
        """Deserialize asset from dict."""
        tags = [AssetTag(**t) for t in data.get("tags", [])]
        return Asset(
            asset_id=data["asset_id"],
            asset_type=AssetType(data["asset_type"]),
            value=data["value"],
            first_seen=data["first_seen"],
            last_seen=data["last_seen"],
            status=AssetStatus(data.get("status", "active")),
            risk=AssetRisk(data.get("risk", "unknown")),
            confidence=data.get("confidence", 1.0),
            source_scans=data.get("source_scans", []),
            source_modules=data.get("source_modules", []),
            tags=tags,
            attributes=data.get("attributes", {}),
            related_assets=data.get("related_assets", []),
            vulnerabilities=data.get("vulnerabilities", []),
            notes=data.get("notes", ""),
        )

    @property
    def total_count(self) -> int:
        return len(self._assets)
