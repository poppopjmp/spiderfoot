# -*- coding: utf-8 -*-
"""
Subdomain Monitoring Service for SpiderFoot.

Continuously monitors target domains for subdomain changes by
comparing current enumeration results against stored baselines.

Features:
  - Baseline storage in Redis with per-domain snapshots
  - Change detection: new, removed, and IP-changed subdomains
  - Notification integration for alerts on changes
  - Celery task for periodic monitoring
  - REST API for managing monitored domains

Usage::

    from spiderfoot.subdomain_monitor import SubdomainMonitor

    monitor = SubdomainMonitor()
    monitor.add_domain("example.com")
    changes = monitor.check_domain("example.com")
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("spiderfoot.subdomain_monitor")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SubdomainRecord:
    """A single subdomain observation."""
    hostname: str
    ip_addresses: list[str] = field(default_factory=list)
    first_seen: float = 0.0
    last_seen: float = 0.0
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "hostname": self.hostname,
            "ip_addresses": self.ip_addresses,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubdomainRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SubdomainChange:
    """A detected change in subdomain state."""
    change_type: str  # "new", "removed", "ip_changed"
    hostname: str
    old_ips: list[str] = field(default_factory=list)
    new_ips: list[str] = field(default_factory=list)
    detected_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_type": self.change_type,
            "hostname": self.hostname,
            "old_ips": self.old_ips,
            "new_ips": self.new_ips,
            "detected_at": self.detected_at,
        }


@dataclass
class MonitoredDomain:
    """A domain being monitored for subdomain changes."""
    domain: str
    enabled: bool = True
    check_interval_hours: float = 24.0
    last_check_at: float = 0.0
    next_check_at: float = 0.0
    subdomain_count: int = 0
    total_changes: int = 0
    created_at: float = 0.0
    notify_on_change: bool = True
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "enabled": self.enabled,
            "check_interval_hours": self.check_interval_hours,
            "last_check_at": self.last_check_at,
            "next_check_at": self.next_check_at,
            "subdomain_count": self.subdomain_count,
            "total_changes": self.total_changes,
            "created_at": self.created_at,
            "notify_on_change": self.notify_on_change,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MonitoredDomain:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Redis-backed storage
# ---------------------------------------------------------------------------

def _get_redis():
    import redis as redis_lib
    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
    return redis_lib.from_url(redis_url)


class SubdomainMonitor:
    """Monitor domains for subdomain changes using Redis snapshots."""

    def __init__(self):
        self._redis = None

    @property
    def redis(self):
        if self._redis is None:
            self._redis = _get_redis()
        return self._redis

    # -- Domain management --

    def add_domain(
        self,
        domain: str,
        check_interval_hours: float = 24.0,
        notify_on_change: bool = True,
        tags: list[str] | None = None,
    ) -> MonitoredDomain:
        """Add a domain to monitor."""
        now = time.time()
        md = MonitoredDomain(
            domain=domain,
            enabled=True,
            check_interval_hours=check_interval_hours,
            last_check_at=0,
            next_check_at=now,
            subdomain_count=0,
            total_changes=0,
            created_at=now,
            notify_on_change=notify_on_change,
            tags=tags or [],
        )
        self.redis.set(f"sf:monitor:domain:{domain}", json.dumps(md.to_dict()))
        self.redis.sadd("sf:monitor:domains", domain)
        log.info("Added domain '%s' to monitoring", domain)
        return md

    def remove_domain(self, domain: str) -> bool:
        """Remove a domain from monitoring."""
        self.redis.delete(f"sf:monitor:domain:{domain}")
        self.redis.delete(f"sf:monitor:snapshot:{domain}")
        self.redis.delete(f"sf:monitor:changes:{domain}")
        self.redis.srem("sf:monitor:domains", domain)
        log.info("Removed domain '%s' from monitoring", domain)
        return True

    def get_domain(self, domain: str) -> MonitoredDomain | None:
        """Get a monitored domain."""
        raw = self.redis.get(f"sf:monitor:domain:{domain}")
        if raw:
            return MonitoredDomain.from_dict(json.loads(raw))
        return None

    def list_domains(self) -> list[MonitoredDomain]:
        """List all monitored domains."""
        domain_names = self.redis.smembers("sf:monitor:domains")
        domains = []
        for d in domain_names:
            d_str = d.decode("utf-8") if isinstance(d, bytes) else d
            md = self.get_domain(d_str)
            if md:
                domains.append(md)
        return domains

    def update_domain(self, domain: str, **kwargs) -> MonitoredDomain | None:
        """Update a monitored domain's settings."""
        md = self.get_domain(domain)
        if not md:
            return None
        for k, v in kwargs.items():
            if hasattr(md, k):
                setattr(md, k, v)
        self.redis.set(f"sf:monitor:domain:{domain}", json.dumps(md.to_dict()))
        return md

    # -- Snapshot management --

    def update_snapshot(self, domain: str, subdomains: list[SubdomainRecord]) -> None:
        """Update the subdomain baseline snapshot."""
        now = time.time()
        snapshot = {}
        for s in subdomains:
            s.last_seen = now
            if not s.first_seen:
                s.first_seen = now
            snapshot[s.hostname] = s.to_dict()

        self.redis.set(
            f"sf:monitor:snapshot:{domain}",
            json.dumps(snapshot),
        )

        # Update domain metadata
        md = self.get_domain(domain)
        if md:
            md.subdomain_count = len(snapshot)
            md.last_check_at = now
            md.next_check_at = now + (md.check_interval_hours * 3600)
            self.redis.set(f"sf:monitor:domain:{domain}", json.dumps(md.to_dict()))

    def get_snapshot(self, domain: str) -> dict[str, SubdomainRecord]:
        """Get the current subdomain snapshot."""
        raw = self.redis.get(f"sf:monitor:snapshot:{domain}")
        if not raw:
            return {}
        data = json.loads(raw)
        return {k: SubdomainRecord.from_dict(v) for k, v in data.items()}

    # -- Change detection --

    def detect_changes(
        self,
        domain: str,
        current_subdomains: list[SubdomainRecord],
    ) -> list[SubdomainChange]:
        """Compare current subdomains against the stored snapshot.

        Returns list of detected changes (new, removed, ip_changed).
        """
        now = time.time()
        old_snapshot = self.get_snapshot(domain)
        current_map = {s.hostname: s for s in current_subdomains}

        changes: list[SubdomainChange] = []

        # New subdomains
        for hostname, record in current_map.items():
            if hostname not in old_snapshot:
                changes.append(SubdomainChange(
                    change_type="new",
                    hostname=hostname,
                    new_ips=record.ip_addresses,
                    detected_at=now,
                ))

        # Removed subdomains
        for hostname, record in old_snapshot.items():
            if hostname not in current_map:
                changes.append(SubdomainChange(
                    change_type="removed",
                    hostname=hostname,
                    old_ips=record.ip_addresses,
                    detected_at=now,
                ))

        # IP changes
        for hostname in set(current_map) & set(old_snapshot):
            old_ips = sorted(old_snapshot[hostname].ip_addresses)
            new_ips = sorted(current_map[hostname].ip_addresses)
            if old_ips != new_ips:
                changes.append(SubdomainChange(
                    change_type="ip_changed",
                    hostname=hostname,
                    old_ips=old_ips,
                    new_ips=new_ips,
                    detected_at=now,
                ))

        # Store change history
        if changes:
            self._store_changes(domain, changes)
            md = self.get_domain(domain)
            if md:
                md.total_changes += len(changes)
                self.redis.set(f"sf:monitor:domain:{domain}", json.dumps(md.to_dict()))

        # Update snapshot
        self.update_snapshot(domain, current_subdomains)

        log.info("Domain '%s' check: %d change(s) detected", domain, len(changes))
        return changes

    def _store_changes(self, domain: str, changes: list[SubdomainChange]) -> None:
        """Store change history in Redis (capped list)."""
        key = f"sf:monitor:changes:{domain}"
        for c in changes:
            self.redis.lpush(key, json.dumps(c.to_dict()))
        self.redis.ltrim(key, 0, 999)  # Keep last 1000 changes

    def get_change_history(self, domain: str, limit: int = 100) -> list[SubdomainChange]:
        """Get recent change history for a domain."""
        raw_list = self.redis.lrange(f"sf:monitor:changes:{domain}", 0, limit - 1)
        changes = []
        for raw in raw_list:
            try:
                data = json.loads(raw)
                changes.append(SubdomainChange(**data))
            except (json.JSONDecodeError, TypeError):
                continue
        return changes

    def get_domains_due_for_check(self) -> list[MonitoredDomain]:
        """Get domains due for their next scheduled check."""
        now = time.time()
        due = []
        for md in self.list_domains():
            if md.enabled and md.next_check_at <= now:
                due.append(md)
        return due


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_monitor: SubdomainMonitor | None = None


def get_subdomain_monitor() -> SubdomainMonitor:
    """Get/create the singleton SubdomainMonitor."""
    global _monitor
    if _monitor is None:
        _monitor = SubdomainMonitor()
    return _monitor
