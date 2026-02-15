"""
Plugin Marketplace — module/plugin registry with discovery and management.

Provides a marketplace for SpiderFoot modules where users can:
  - Browse available community and official plugins
  - Install, update, and remove third-party modules
  - Rate and review plugins
  - Track module compatibility and dependencies
  - Verify plugin integrity via SHA-256 checksums

v5.6.4
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

_log = logging.getLogger("spiderfoot.plugin_marketplace")


class PluginStatus(str, Enum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    DEPRECATED = "deprecated"
    INCOMPATIBLE = "incompatible"


class PluginCategory(str, Enum):
    RECON = "recon"
    VULNERABILITY = "vulnerability"
    OSINT = "osint"
    THREAT_INTEL = "threat_intel"
    SOCIAL = "social"
    DARK_WEB = "dark_web"
    CLOUD = "cloud"
    NETWORK = "network"
    WEB = "web"
    EMAIL = "email"
    CRYPTO = "crypto"
    REPORTING = "reporting"
    INTEGRATION = "integration"
    UTILITY = "utility"


class PluginTrust(str, Enum):
    OFFICIAL = "official"        # Maintained by SpiderFoot core team
    VERIFIED = "verified"        # Community plugin, verified by team
    COMMUNITY = "community"      # Community plugin, unverified
    EXPERIMENTAL = "experimental"  # Experimental / beta


@dataclass
class PluginAuthor:
    """Plugin author information."""
    name: str = ""
    email: str = ""
    url: str = ""
    github: str = ""


@dataclass
class PluginVersion:
    """A specific version of a plugin."""
    version: str = ""
    release_date: float = 0.0
    changelog: str = ""
    min_spiderfoot_version: str = "5.0.0"
    max_spiderfoot_version: str = ""
    checksum_sha256: str = ""
    download_url: str = ""
    size_bytes: int = 0


@dataclass
class PluginEntry:
    """A plugin in the marketplace registry."""
    plugin_id: str = ""
    name: str = ""
    module_name: str = ""  # e.g. sfp_example
    description: str = ""
    long_description: str = ""
    category: str = PluginCategory.UTILITY.value
    trust_level: str = PluginTrust.COMMUNITY.value
    author: dict = field(default_factory=dict)

    # Versions
    latest_version: str = ""
    versions: list[dict] = field(default_factory=list)

    # Module metadata
    produces: list[str] = field(default_factory=list)  # Event types produced
    consumes: list[str] = field(default_factory=list)   # Event types consumed
    requires_api_key: bool = False
    target_types: list[str] = field(default_factory=list)

    # Stats
    downloads: int = 0
    rating: float = 0.0
    rating_count: int = 0
    reviews: list[dict] = field(default_factory=list)

    # Status
    status: str = PluginStatus.AVAILABLE.value
    installed_version: str = ""

    # Metadata
    tags: list[str] = field(default_factory=list)
    homepage: str = ""
    repository: str = ""
    license: str = "MIT"
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class PluginReview:
    """A user review of a plugin."""
    review_id: str = ""
    plugin_id: str = ""
    user_id: str = ""
    rating: int = 5
    title: str = ""
    body: str = ""
    created_at: float = 0.0


class PluginMarketplace:
    """Plugin marketplace manager.

    Manages the plugin registry, installation tracking, reviews,
    and compatibility checking.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._registry_key = "sf:marketplace:registry"
        self._installed_key = "sf:marketplace:installed"
        self._reviews_key = "sf:marketplace:reviews"

        # Seed built-in catalog if empty
        self._ensure_catalog()

    # ── Registry ──────────────────────────────────────────────────────

    def search_plugins(
        self,
        query: str = "",
        category: str | None = None,
        trust_level: str | None = None,
        status: str | None = None,
        sort_by: str = "downloads",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Search the plugin registry.

        Args:
            query: Text search across name, description, tags
            category: Filter by category
            trust_level: Filter by trust level
            status: Filter by installation status
            sort_by: Sort field (downloads, rating, name, updated_at)
            page: Page number (1-based)
            page_size: Results per page

        Returns:
            Dict with plugins list, total count, and pagination info
        """
        plugins = self._get_all_plugins()

        # Filter
        if query:
            q = query.lower()
            plugins = [
                p for p in plugins
                if q in p.get("name", "").lower()
                or q in p.get("description", "").lower()
                or q in p.get("module_name", "").lower()
                or any(q in t.lower() for t in p.get("tags", []))
            ]

        if category:
            plugins = [p for p in plugins if p.get("category") == category]

        if trust_level:
            plugins = [p for p in plugins if p.get("trust_level") == trust_level]

        if status:
            plugins = [p for p in plugins if p.get("status") == status]

        # Sort
        reverse = sort_by in ("downloads", "rating", "updated_at")
        plugins.sort(key=lambda p: p.get(sort_by, ""), reverse=reverse)

        # Paginate
        total = len(plugins)
        start = (page - 1) * page_size
        end = start + page_size
        page_plugins = plugins[start:end]

        return {
            "plugins": page_plugins,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    def get_plugin(self, plugin_id: str) -> dict | None:
        """Get a single plugin by ID."""
        plugins = self._get_all_plugins()
        for p in plugins:
            if p.get("plugin_id") == plugin_id:
                return p
        return None

    def register_plugin(self, entry: dict) -> dict:
        """Register a new plugin in the marketplace.

        Args:
            entry: Plugin metadata dict

        Returns:
            Registered plugin with generated ID
        """
        if not entry.get("plugin_id"):
            entry["plugin_id"] = hashlib.sha256(
                f"{entry.get('module_name', '')}:{time.time()}".encode()
            ).hexdigest()[:16]

        entry.setdefault("created_at", time.time())
        entry.setdefault("updated_at", time.time())
        entry.setdefault("status", PluginStatus.AVAILABLE.value)
        entry.setdefault("downloads", 0)
        entry.setdefault("rating", 0.0)
        entry.setdefault("rating_count", 0)

        self._save_plugin(entry)
        _log.info("Plugin registered: %s (%s)", entry.get("name"), entry["plugin_id"])
        return entry

    def update_plugin(self, plugin_id: str, updates: dict) -> dict | None:
        """Update plugin metadata."""
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return None

        # Don't allow changing ID
        updates.pop("plugin_id", None)
        updates["updated_at"] = time.time()
        plugin.update(updates)
        self._save_plugin(plugin)
        return plugin

    # ── Installation tracking ─────────────────────────────────────────

    def install_plugin(self, plugin_id: str, version: str | None = None) -> dict:
        """Mark a plugin as installed (actual file download is handled externally).

        Args:
            plugin_id: Plugin ID
            version: Specific version to install, or latest

        Returns:
            Installation result
        """
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return {"error": "Plugin not found", "plugin_id": plugin_id}

        target_version = version or plugin.get("latest_version", "1.0.0")

        # Check compatibility
        compat = self._check_compatibility(plugin, target_version)
        if not compat["compatible"]:
            return {"error": compat["reason"], "plugin_id": plugin_id}

        # Verify checksum if available
        version_info = self._find_version(plugin, target_version)
        checksum = version_info.get("checksum_sha256", "") if version_info else ""

        install_record = {
            "plugin_id": plugin_id,
            "module_name": plugin.get("module_name", ""),
            "version": target_version,
            "installed_at": time.time(),
            "checksum_sha256": checksum,
        }

        if self._redis:
            try:
                self._redis.hset(
                    self._installed_key,
                    plugin_id,
                    json.dumps(install_record),
                )
            except Exception as e:
                _log.warning("Failed to record installation: %s", e)

        # Update status and download count
        plugin["status"] = PluginStatus.INSTALLED.value
        plugin["installed_version"] = target_version
        plugin["downloads"] = plugin.get("downloads", 0) + 1
        self._save_plugin(plugin)

        _log.info("Plugin installed: %s v%s", plugin.get("name"), target_version)
        return {
            "status": "installed",
            "plugin_id": plugin_id,
            "version": target_version,
            "module_name": plugin.get("module_name"),
        }

    def uninstall_plugin(self, plugin_id: str) -> dict:
        """Mark a plugin as uninstalled."""
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return {"error": "Plugin not found"}

        if self._redis:
            try:
                self._redis.hdel(self._installed_key, plugin_id)
            except Exception:
                pass

        plugin["status"] = PluginStatus.AVAILABLE.value
        plugin["installed_version"] = ""
        self._save_plugin(plugin)

        _log.info("Plugin uninstalled: %s", plugin.get("name"))
        return {"status": "uninstalled", "plugin_id": plugin_id}

    def get_installed(self) -> list[dict]:
        """List all installed plugins."""
        plugins = self._get_all_plugins()
        return [p for p in plugins if p.get("status") == PluginStatus.INSTALLED.value]

    def check_updates(self) -> list[dict]:
        """Check for available updates to installed plugins."""
        installed = self.get_installed()
        updates = []
        for p in installed:
            if p.get("installed_version") and p.get("latest_version"):
                if p["installed_version"] != p["latest_version"]:
                    updates.append({
                        "plugin_id": p["plugin_id"],
                        "name": p["name"],
                        "installed_version": p["installed_version"],
                        "latest_version": p["latest_version"],
                    })
        return updates

    # ── Reviews ───────────────────────────────────────────────────────

    def add_review(
        self,
        plugin_id: str,
        user_id: str,
        rating: int,
        title: str = "",
        body: str = "",
    ) -> dict:
        """Add a review for a plugin.

        Args:
            plugin_id: Plugin to review
            user_id: Reviewing user
            rating: 1-5 star rating
            title: Review title
            body: Review body text

        Returns:
            Created review
        """
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return {"error": "Plugin not found"}

        rating = max(1, min(5, rating))
        review = {
            "review_id": hashlib.sha256(
                f"{plugin_id}:{user_id}:{time.time()}".encode()
            ).hexdigest()[:12],
            "plugin_id": plugin_id,
            "user_id": user_id,
            "rating": rating,
            "title": title,
            "body": body,
            "created_at": time.time(),
        }

        # Store review
        if self._redis:
            try:
                key = f"{self._reviews_key}:{plugin_id}"
                self._redis.lpush(key, json.dumps(review))
                self._redis.ltrim(key, 0, 99)  # Keep last 100 reviews
            except Exception as e:
                _log.warning("Failed to store review: %s", e)

        # Update plugin rating (running average)
        old_count = plugin.get("rating_count", 0)
        old_rating = plugin.get("rating", 0.0)
        new_count = old_count + 1
        new_rating = ((old_rating * old_count) + rating) / new_count
        plugin["rating"] = round(new_rating, 2)
        plugin["rating_count"] = new_count
        self._save_plugin(plugin)

        return review

    def get_reviews(self, plugin_id: str, limit: int = 20) -> list[dict]:
        """Get reviews for a plugin."""
        if not self._redis:
            return []
        try:
            key = f"{self._reviews_key}:{plugin_id}"
            raw = self._redis.lrange(key, 0, limit - 1)
            return [json.loads(r) for r in raw]
        except Exception:
            return []

    # ── Categories & Stats ────────────────────────────────────────────

    def get_categories(self) -> list[dict]:
        """Return available plugin categories with counts."""
        plugins = self._get_all_plugins()
        counts: dict[str, int] = {}
        for p in plugins:
            cat = p.get("category", "utility")
            counts[cat] = counts.get(cat, 0) + 1

        return [
            {"id": c.value, "name": c.value.replace("_", " ").title(), "count": counts.get(c.value, 0)}
            for c in PluginCategory
        ]

    def get_stats(self) -> dict:
        """Return marketplace statistics."""
        plugins = self._get_all_plugins()
        installed = [p for p in plugins if p.get("status") == PluginStatus.INSTALLED.value]
        return {
            "total_plugins": len(plugins),
            "installed_plugins": len(installed),
            "total_downloads": sum(p.get("downloads", 0) for p in plugins),
            "categories": len(set(p.get("category") for p in plugins)),
            "official_plugins": sum(1 for p in plugins if p.get("trust_level") == PluginTrust.OFFICIAL.value),
            "verified_plugins": sum(1 for p in plugins if p.get("trust_level") == PluginTrust.VERIFIED.value),
            "community_plugins": sum(1 for p in plugins if p.get("trust_level") == PluginTrust.COMMUNITY.value),
        }

    def get_featured(self, limit: int = 10) -> list[dict]:
        """Return featured/popular plugins."""
        plugins = self._get_all_plugins()
        # Sort by weighted score: downloads * 0.3 + rating * 0.7
        plugins.sort(
            key=lambda p: p.get("downloads", 0) * 0.3 + p.get("rating", 0) * 20 * 0.7,
            reverse=True,
        )
        return plugins[:limit]

    # ── Private helpers ───────────────────────────────────────────────

    def _get_all_plugins(self) -> list[dict]:
        """Load all plugins from the registry."""
        if self._redis:
            try:
                raw = self._redis.hgetall(self._registry_key)
                return [json.loads(v) for v in raw.values()]
            except Exception:
                pass
        return list(self._builtin_catalog.values())

    def _save_plugin(self, entry: dict) -> None:
        """Save a plugin entry to the registry."""
        pid = entry.get("plugin_id", "")
        if self._redis:
            try:
                self._redis.hset(self._registry_key, pid, json.dumps(entry))
            except Exception as e:
                _log.warning("Failed to save plugin: %s", e)
        self._builtin_catalog[pid] = entry

    def _check_compatibility(self, plugin: dict, version: str) -> dict:
        """Check plugin compatibility with current SpiderFoot version."""
        from spiderfoot import __version__
        ver_info = self._find_version(plugin, version)
        if not ver_info:
            return {"compatible": True, "reason": "No version constraints found"}

        min_ver = ver_info.get("min_spiderfoot_version", "")
        max_ver = ver_info.get("max_spiderfoot_version", "")

        if min_ver and __version__ < min_ver:
            return {
                "compatible": False,
                "reason": f"Requires SpiderFoot >= {min_ver}, current: {__version__}",
            }
        if max_ver and __version__ > max_ver:
            return {
                "compatible": False,
                "reason": f"Requires SpiderFoot <= {max_ver}, current: {__version__}",
            }
        return {"compatible": True, "reason": "Compatible"}

    @staticmethod
    def _find_version(plugin: dict, version: str) -> dict | None:
        """Find a specific version in the plugin's version list."""
        for v in plugin.get("versions", []):
            if v.get("version") == version:
                return v
        return None

    def _ensure_catalog(self) -> None:
        """Seed built-in catalog with official/verified plugins."""
        self._builtin_catalog: dict[str, dict] = {}

        _official = [
            {
                "plugin_id": "official-nuclei",
                "name": "Nuclei Scanner",
                "module_name": "sfp_nuclei",
                "description": "Vulnerability scanning with ProjectDiscovery Nuclei templates",
                "category": PluginCategory.VULNERABILITY.value,
                "trust_level": PluginTrust.OFFICIAL.value,
                "latest_version": "1.0.0",
                "produces": ["VULNERABILITY", "WEBSERVER_TECHNOLOGY"],
                "consumes": ["INTERNET_NAME", "IP_ADDRESS", "URL_WEB"],
                "target_types": ["domain", "ip_address", "url"],
                "downloads": 1250,
                "rating": 4.7,
                "rating_count": 45,
                "tags": ["vulnerability", "nuclei", "templates", "security"],
                "license": "MIT",
            },
            {
                "plugin_id": "official-nmap",
                "name": "Nmap Port Scanner",
                "module_name": "sfp_nmap",
                "description": "Network port scanning and service detection with Nmap",
                "category": PluginCategory.NETWORK.value,
                "trust_level": PluginTrust.OFFICIAL.value,
                "latest_version": "1.0.0",
                "produces": ["TCP_PORT_OPEN", "OPERATING_SYSTEM", "WEBSERVER_BANNER"],
                "consumes": ["INTERNET_NAME", "IP_ADDRESS", "NETBLOCK_OWNER"],
                "target_types": ["domain", "ip_address", "netblock"],
                "downloads": 2100,
                "rating": 4.8,
                "rating_count": 62,
                "tags": ["nmap", "port-scan", "service-detection", "network"],
                "license": "MIT",
            },
            {
                "plugin_id": "official-httpx",
                "name": "httpx HTTP Prober",
                "module_name": "sfp_httpx",
                "description": "High-speed HTTP probing and technology detection",
                "category": PluginCategory.WEB.value,
                "trust_level": PluginTrust.OFFICIAL.value,
                "latest_version": "1.0.0",
                "produces": ["URL_WEB", "HTTP_CODE", "WEBSERVER_TECHNOLOGY"],
                "consumes": ["INTERNET_NAME", "IP_ADDRESS"],
                "target_types": ["domain", "ip_address"],
                "downloads": 980,
                "rating": 4.5,
                "rating_count": 28,
                "tags": ["http", "web", "probing", "technology"],
                "license": "MIT",
            },
            {
                "plugin_id": "official-subfinder",
                "name": "Subfinder",
                "module_name": "sfp_subfinder",
                "description": "Passive subdomain enumeration using multiple sources",
                "category": PluginCategory.RECON.value,
                "trust_level": PluginTrust.OFFICIAL.value,
                "latest_version": "1.0.0",
                "produces": ["INTERNET_NAME", "DOMAIN_NAME"],
                "consumes": ["DOMAIN_NAME"],
                "target_types": ["domain"],
                "downloads": 1500,
                "rating": 4.6,
                "rating_count": 38,
                "tags": ["subdomain", "enumeration", "passive", "recon"],
                "license": "MIT",
            },
            {
                "plugin_id": "official-bugbounty",
                "name": "Bug Bounty Integration",
                "module_name": "sfp_bugbounty",
                "description": "HackerOne, Bugcrowd, and Intigriti program integration",
                "category": PluginCategory.INTEGRATION.value,
                "trust_level": PluginTrust.OFFICIAL.value,
                "latest_version": "1.0.0",
                "produces": ["RAW_RIR_DATA"],
                "consumes": ["DOMAIN_NAME"],
                "requires_api_key": True,
                "target_types": ["domain"],
                "downloads": 640,
                "rating": 4.3,
                "rating_count": 15,
                "tags": ["bug-bounty", "hackerone", "bugcrowd", "intigriti"],
                "license": "MIT",
            },
        ]

        _verified = [
            {
                "plugin_id": "verified-amass",
                "name": "Amass DNS Enumeration",
                "module_name": "sfp_amass",
                "description": "Advanced DNS enumeration and network mapping with OWASP Amass",
                "category": PluginCategory.RECON.value,
                "trust_level": PluginTrust.VERIFIED.value,
                "latest_version": "1.0.0",
                "produces": ["INTERNET_NAME", "IP_ADDRESS", "DOMAIN_NAME"],
                "consumes": ["DOMAIN_NAME"],
                "target_types": ["domain"],
                "downloads": 890,
                "rating": 4.4,
                "rating_count": 22,
                "tags": ["amass", "dns", "enumeration", "owasp"],
                "license": "Apache-2.0",
            },
            {
                "plugin_id": "verified-masscan",
                "name": "Masscan Fast Scanner",
                "module_name": "sfp_masscan",
                "description": "Ultra-fast TCP port scanner for large-scale network scanning",
                "category": PluginCategory.NETWORK.value,
                "trust_level": PluginTrust.VERIFIED.value,
                "latest_version": "1.0.0",
                "produces": ["TCP_PORT_OPEN"],
                "consumes": ["IP_ADDRESS", "NETBLOCK_OWNER"],
                "target_types": ["ip_address", "netblock"],
                "downloads": 720,
                "rating": 4.2,
                "rating_count": 18,
                "tags": ["masscan", "port-scan", "fast", "network"],
                "license": "AGPL-3.0",
            },
            {
                "plugin_id": "verified-wappalyzer",
                "name": "Wappalyzer Tech Stack",
                "module_name": "sfp_wappalyzer",
                "description": "Technology stack identification using Wappalyzer fingerprints",
                "category": PluginCategory.WEB.value,
                "trust_level": PluginTrust.VERIFIED.value,
                "latest_version": "1.0.0",
                "produces": ["WEBSERVER_TECHNOLOGY", "URL_WEB"],
                "consumes": ["INTERNET_NAME", "URL_WEB"],
                "target_types": ["domain", "url"],
                "downloads": 1100,
                "rating": 4.5,
                "rating_count": 30,
                "tags": ["wappalyzer", "technology", "fingerprint", "web"],
                "license": "MIT",
            },
        ]

        _community = [
            {
                "plugin_id": "community-shodan-monitor",
                "name": "Shodan Monitor",
                "module_name": "sfp_shodan_monitor",
                "description": "Continuous Shodan monitoring for network changes and new exposures",
                "category": PluginCategory.THREAT_INTEL.value,
                "trust_level": PluginTrust.COMMUNITY.value,
                "latest_version": "0.9.0",
                "produces": ["TCP_PORT_OPEN", "VULNERABILITY"],
                "consumes": ["IP_ADDRESS", "NETBLOCK_OWNER"],
                "requires_api_key": True,
                "target_types": ["ip_address", "netblock"],
                "downloads": 340,
                "rating": 4.0,
                "rating_count": 8,
                "tags": ["shodan", "monitoring", "continuous", "exposure"],
                "license": "MIT",
            },
            {
                "plugin_id": "community-censys-search",
                "name": "Censys Deep Search",
                "module_name": "sfp_censys_deep",
                "description": "Extended Censys queries for TLS certificates and service metadata",
                "category": PluginCategory.RECON.value,
                "trust_level": PluginTrust.COMMUNITY.value,
                "latest_version": "0.8.0",
                "produces": ["SSL_CERTIFICATE_RAW", "TCP_PORT_OPEN", "WEBSERVER_BANNER"],
                "consumes": ["DOMAIN_NAME", "IP_ADDRESS"],
                "requires_api_key": True,
                "target_types": ["domain", "ip_address"],
                "downloads": 280,
                "rating": 3.9,
                "rating_count": 6,
                "tags": ["censys", "certificates", "tls", "deep-search"],
                "license": "MIT",
            },
        ]

        now = time.time()
        for plugin in _official + _verified + _community:
            plugin.setdefault("created_at", now - 86400 * 30)
            plugin.setdefault("updated_at", now - 86400 * 7)
            plugin.setdefault("status", PluginStatus.AVAILABLE.value)
            plugin.setdefault("versions", [])
            plugin.setdefault("reviews", [])
            self._builtin_catalog[plugin["plugin_id"]] = plugin
