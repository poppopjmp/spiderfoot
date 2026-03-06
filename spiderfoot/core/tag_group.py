"""
Tag & Group System — organize scan targets, assets, and findings.

Provides:
  - Hierarchical tag taxonomy with color coding
  - Asset groups with dynamic membership rules
  - Tag-based filtering across scans and events
  - Auto-tagging rules based on event types
  - Tag inheritance and propagation
  - Group-level statistics and aggregation

v5.7.3
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

_log = logging.getLogger("spiderfoot.tags")


class TagColor(str, Enum):
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"
    PINK = "pink"
    GRAY = "gray"
    TEAL = "teal"
    INDIGO = "indigo"


@dataclass
class Tag:
    """A tag for labelling scans, assets, and findings."""
    tag_id: str = ""
    name: str = ""
    slug: str = ""
    description: str = ""
    color: str = TagColor.BLUE.value
    parent_tag: str = ""          # Hierarchical parent tag_id
    auto_apply_rules: list[dict] = field(default_factory=list)
    created_by: str = ""
    tenant_id: str = ""
    created_at: float = 0.0
    usage_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AssetGroup:
    """A group of related assets or scan targets."""
    group_id: str = ""
    name: str = ""
    description: str = ""
    members: list[str] = field(default_factory=list)      # Asset/target identifiers
    tags: list[str] = field(default_factory=list)          # Tag IDs applied to group
    dynamic_rules: list[dict] = field(default_factory=list)  # Auto-membership rules
    owner: str = ""
    tenant_id: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    @property
    def member_count(self) -> int:
        return len(self.members)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["member_count"] = self.member_count
        return d


@dataclass
class TagAssignment:
    """A tag applied to a specific resource."""
    assignment_id: str = ""
    tag_id: str = ""
    resource_type: str = ""  # scan, event, asset, group, target
    resource_id: str = ""
    assigned_by: str = ""    # user or "auto"
    assigned_at: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class TagGroupManager:
    """Manage tags, groups, and tag assignments.

    Features:
      - Tag CRUD with hierarchical taxonomy
      - Group CRUD with static and dynamic membership
      - Tag assignment to any resource type
      - Auto-tagging based on configurable rules
      - Bulk operations and statistics
    """

    # Auto-tagging rules: event_type_prefix → suggested tags
    DEFAULT_AUTO_RULES = {
        "VULNERABILITY_CVE_CRITICAL": ["critical-vuln", "security"],
        "VULNERABILITY_CVE_HIGH": ["high-vuln", "security"],
        "MALICIOUS_": ["malicious", "threat"],
        "BLACKLISTED_": ["blacklisted", "reputation"],
        "SSL_CERTIFICATE_EXPIRED": ["ssl-issue", "compliance"],
        "CLOUD_STORAGE_BUCKET_OPEN": ["cloud-risk", "data-exposure"],
        "EMAILADDR_COMPROMISED": ["breach", "credential-leak"],
        "TCP_PORT_OPEN": ["open-port", "infrastructure"],
    }

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._tags: dict[str, Tag] = {}
        self._groups: dict[str, AssetGroup] = {}
        self._assignments: list[TagAssignment] = []
        self._seed_default_tags()

    # ── Tag CRUD ──────────────────────────────────────────────────────

    def create_tag(self, config: dict) -> Tag:
        t = Tag(**{k: v for k, v in config.items() if k in Tag.__dataclass_fields__})
        if not t.tag_id:
            t.tag_id = str(uuid.uuid4())[:10]
        if not t.slug:
            t.slug = t.name.lower().replace(" ", "-").replace("_", "-")
        t.created_at = time.time()

        self._tags[t.tag_id] = t
        self._persist_tag(t)
        return t

    def get_tag(self, tag_id: str) -> Tag | None:
        return self._tags.get(tag_id)

    def find_tag_by_slug(self, slug: str) -> Tag | None:
        for t in self._tags.values():
            if t.slug == slug:
                return t
        return None

    def list_tags(
        self,
        parent: str | None = None,
        tenant_id: str | None = None,
    ) -> list[Tag]:
        tags = list(self._tags.values())
        if parent is not None:
            tags = [t for t in tags if t.parent_tag == parent]
        if tenant_id is not None:
            tags = [t for t in tags if t.tenant_id == tenant_id or t.tenant_id == ""]
        return sorted(tags, key=lambda t: t.name)

    def update_tag(self, tag_id: str, updates: dict) -> Tag | None:
        t = self._tags.get(tag_id)
        if not t:
            return None
        updates.pop("tag_id", None)
        updates.pop("created_at", None)
        for k, v in updates.items():
            if hasattr(t, k):
                setattr(t, k, v)
        self._persist_tag(t)
        return t

    def delete_tag(self, tag_id: str) -> bool:
        if tag_id in self._tags:
            del self._tags[tag_id]
            # Remove all assignments for this tag
            self._assignments = [a for a in self._assignments if a.tag_id != tag_id]
            return True
        return False

    def get_tag_tree(self) -> list[dict]:
        """Build a hierarchical tag tree."""
        roots = [t for t in self._tags.values() if not t.parent_tag]
        return [self._build_tree_node(t) for t in sorted(roots, key=lambda t: t.name)]

    def _build_tree_node(self, tag: Tag) -> dict:
        children = [
            t for t in self._tags.values() if t.parent_tag == tag.tag_id
        ]
        node = tag.to_dict()
        node["children"] = [
            self._build_tree_node(c) for c in sorted(children, key=lambda t: t.name)
        ]
        return node

    # ── Group CRUD ────────────────────────────────────────────────────

    def create_group(self, config: dict) -> AssetGroup:
        g = AssetGroup(**{k: v for k, v in config.items()
                         if k in AssetGroup.__dataclass_fields__})
        if not g.group_id:
            g.group_id = str(uuid.uuid4())[:10]
        g.created_at = time.time()
        g.updated_at = time.time()

        self._groups[g.group_id] = g
        self._persist_group(g)
        return g

    def get_group(self, group_id: str) -> AssetGroup | None:
        return self._groups.get(group_id)

    def list_groups(self, tenant_id: str | None = None) -> list[AssetGroup]:
        groups = list(self._groups.values())
        if tenant_id is not None:
            groups = [g for g in groups if g.tenant_id == tenant_id or g.tenant_id == ""]
        return sorted(groups, key=lambda g: g.name)

    def update_group(self, group_id: str, updates: dict) -> AssetGroup | None:
        g = self._groups.get(group_id)
        if not g:
            return None
        updates.pop("group_id", None)
        updates.pop("created_at", None)
        updates["updated_at"] = time.time()
        for k, v in updates.items():
            if hasattr(g, k):
                setattr(g, k, v)
        self._persist_group(g)
        return g

    def delete_group(self, group_id: str) -> bool:
        return self._groups.pop(group_id, None) is not None

    def add_member(self, group_id: str, member: str) -> bool:
        g = self._groups.get(group_id)
        if not g:
            return False
        if member not in g.members:
            g.members.append(member)
            g.updated_at = time.time()
            self._persist_group(g)
        return True

    def remove_member(self, group_id: str, member: str) -> bool:
        g = self._groups.get(group_id)
        if not g or member not in g.members:
            return False
        g.members.remove(member)
        g.updated_at = time.time()
        self._persist_group(g)
        return True

    # ── Tag assignments ───────────────────────────────────────────────

    def assign_tag(
        self,
        tag_id: str,
        resource_type: str,
        resource_id: str,
        assigned_by: str = "user",
    ) -> TagAssignment | None:
        if tag_id not in self._tags:
            return None

        # Check if already assigned
        for a in self._assignments:
            if (a.tag_id == tag_id and a.resource_type == resource_type
                    and a.resource_id == resource_id):
                return a  # Already assigned

        assignment = TagAssignment(
            assignment_id=str(uuid.uuid4())[:10],
            tag_id=tag_id,
            resource_type=resource_type,
            resource_id=resource_id,
            assigned_by=assigned_by,
            assigned_at=time.time(),
        )
        self._assignments.append(assignment)
        self._tags[tag_id].usage_count += 1
        return assignment

    def unassign_tag(
        self, tag_id: str, resource_type: str, resource_id: str,
    ) -> bool:
        for i, a in enumerate(self._assignments):
            if (a.tag_id == tag_id and a.resource_type == resource_type
                    and a.resource_id == resource_id):
                self._assignments.pop(i)
                if tag_id in self._tags:
                    self._tags[tag_id].usage_count = max(
                        0, self._tags[tag_id].usage_count - 1)
                return True
        return False

    def get_tags_for_resource(
        self, resource_type: str, resource_id: str,
    ) -> list[Tag]:
        tag_ids = [
            a.tag_id for a in self._assignments
            if a.resource_type == resource_type and a.resource_id == resource_id
        ]
        return [self._tags[tid] for tid in tag_ids if tid in self._tags]

    def get_resources_by_tag(
        self, tag_id: str, resource_type: str | None = None,
    ) -> list[TagAssignment]:
        results = [a for a in self._assignments if a.tag_id == tag_id]
        if resource_type:
            results = [a for a in results if a.resource_type == resource_type]
        return results

    def auto_tag_event(self, event_type: str, resource_id: str) -> list[TagAssignment]:
        """Apply auto-tagging rules based on event type."""
        applied = []
        for prefix, tag_slugs in self.DEFAULT_AUTO_RULES.items():
            if event_type.startswith(prefix):
                for slug in tag_slugs:
                    tag = self.find_tag_by_slug(slug)
                    if tag:
                        a = self.assign_tag(tag.tag_id, "event", resource_id,
                                           assigned_by="auto")
                        if a:
                            applied.append(a)
        return applied

    # ── Statistics ────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "total_tags": len(self._tags),
            "total_groups": len(self._groups),
            "total_assignments": len(self._assignments),
            "top_tags": sorted(
                [{"tag": t.name, "usage": t.usage_count}
                 for t in self._tags.values()],
                key=lambda x: x["usage"], reverse=True,
            )[:10],
            "resource_types": dict(
                defaultdict(
                    int,
                    {a.resource_type: 0 for a in self._assignments},
                    **{a.resource_type: sum(
                        1 for x in self._assignments
                        if x.resource_type == a.resource_type
                    ) for a in self._assignments},
                )
            ),
        }

    # ── Private helpers ───────────────────────────────────────────────

    def _persist_tag(self, t: Tag) -> None:
        if self._redis:
            try:
                self._redis.hset("sf:tags", t.tag_id, json.dumps(asdict(t)))
            except Exception:
                pass

    def _persist_group(self, g: AssetGroup) -> None:
        if self._redis:
            try:
                self._redis.hset("sf:groups", g.group_id, json.dumps(asdict(g)))
            except Exception:
                pass

    def _seed_default_tags(self) -> None:
        """Create sensible default tags."""
        now = time.time()
        defaults = [
            ("security", "Security", "Security-related findings", TagColor.RED.value, ""),
            ("critical-vuln", "Critical Vulnerability", "Critical severity CVEs", TagColor.RED.value, "security"),
            ("high-vuln", "High Vulnerability", "High severity CVEs", TagColor.ORANGE.value, "security"),
            ("malicious", "Malicious", "Malicious indicators", TagColor.RED.value, "security"),
            ("blacklisted", "Blacklisted", "Blacklisted IP/domain", TagColor.ORANGE.value, "security"),
            ("infrastructure", "Infrastructure", "Infrastructure findings", TagColor.BLUE.value, ""),
            ("open-port", "Open Port", "Discovered open ports", TagColor.BLUE.value, "infrastructure"),
            ("ssl-issue", "SSL Issue", "Certificate problems", TagColor.YELLOW.value, "infrastructure"),
            ("cloud-risk", "Cloud Risk", "Cloud misconfigurations", TagColor.PURPLE.value, "security"),
            ("data-exposure", "Data Exposure", "Exposed data findings", TagColor.RED.value, "security"),
            ("breach", "Breach", "Data breach related", TagColor.RED.value, "security"),
            ("credential-leak", "Credential Leak", "Leaked credentials", TagColor.RED.value, "breach"),
            ("compliance", "Compliance", "Compliance-relevant", TagColor.GREEN.value, ""),
            ("threat", "Threat", "Active threat indicators", TagColor.RED.value, "security"),
            ("reviewed", "Reviewed", "Manually reviewed", TagColor.GREEN.value, ""),
            ("false-positive", "False Positive", "Confirmed false positive", TagColor.GRAY.value, ""),
            ("priority", "Priority", "High-priority items", TagColor.ORANGE.value, ""),
            ("external", "External", "External-facing assets", TagColor.TEAL.value, ""),
            ("internal", "Internal", "Internal assets", TagColor.INDIGO.value, ""),
        ]

        parent_slugs: dict[str, str] = {}
        for slug, name, desc, color, parent_slug in defaults:
            tag = Tag(
                tag_id=slug,
                name=name,
                slug=slug,
                description=desc,
                color=color,
                parent_tag=parent_slugs.get(parent_slug, parent_slug),
                created_at=now,
            )
            self._tags[tag.tag_id] = tag
            parent_slugs[slug] = slug
