"""
Vector.dev pipeline bootstrapper for SpiderFoot.

Validates Vector.dev connectivity, generates minimal config for
quick-start deployments, and provides health checking for the
Vector integration.

Usage::

    from spiderfoot.vector_bootstrap import VectorBootstrap

    bootstrap = VectorBootstrap.from_config(sf_config)
    if bootstrap.check_health():
        print("Vector.dev is reachable")
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


log = logging.getLogger("spiderfoot.vector_bootstrap")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class VectorSinkType(Enum):
    """Supported Vector.dev sink types."""
    CONSOLE = "console"
    FILE = "file"
    LOKI = "loki"
    ELASTICSEARCH = "elasticsearch"
    S3 = "aws_s3"
    WEBHOOK = "http"


@dataclass
class VectorHealthStatus:
    """Result of a Vector.dev health check."""
    reachable: bool = False
    version: str = ""
    uptime_seconds: float = 0.0
    sources_count: int = 0
    sinks_count: int = 0
    events_processed: int = 0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reachable": self.reachable,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "sources_count": self.sources_count,
            "sinks_count": self.sinks_count,
            "events_processed": self.events_processed,
            "error": self.error,
        }


@dataclass
class VectorBootstrapConfig:
    """Configuration for the Vector bootstrapper."""
    vector_api_url: str = "http://localhost:8686"
    vector_graphql_url: str = "http://localhost:8686/graphql"
    config_path: str = "config/vector.toml"
    health_timeout: float = 5.0
    enabled_sinks: List[str] = field(default_factory=lambda: ["console", "file"])


# ---------------------------------------------------------------------------
# Main bootstrapper
# ---------------------------------------------------------------------------

class VectorBootstrap:
    """Vector.dev pipeline bootstrapper.

    Provides:
    - Health checking for the Vector.dev instance
    - Config validation
    - Sink availability detection based on environment variables
    - Minimal config generation for quick-start
    """

    def __init__(self, config: Optional[VectorBootstrapConfig] = None):
        self.config = config or VectorBootstrapConfig()
        self._health_cache: Optional[VectorHealthStatus] = None

    @classmethod
    def from_config(cls, sf_config: dict) -> "VectorBootstrap":
        """Create from SpiderFoot configuration dict."""
        endpoint = sf_config.get("_vector_endpoint", "http://localhost:8686")
        config_path = sf_config.get("_vector_config_path", "config/vector.toml")

        return cls(VectorBootstrapConfig(
            vector_api_url=endpoint,
            vector_graphql_url=f"{endpoint}/graphql",
            config_path=config_path,
        ))

    def check_health(self) -> VectorHealthStatus:
        """Check if Vector.dev is reachable and healthy.

        Returns:
            VectorHealthStatus with connectivity details.
        """
        status = VectorHealthStatus()

        if not HTTPX_AVAILABLE:
            status.error = "httpx not installed — cannot check Vector.dev health"
            return status

        try:
            with httpx.Client(timeout=self.config.health_timeout) as client:
                # Try the health endpoint
                resp = client.get(f"{self.config.vector_api_url}/health")
                if resp.status_code == 200:
                    status.reachable = True
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    status.version = data.get("version", "unknown")
                    status.uptime_seconds = data.get("uptime_secs", 0.0)
        except Exception as e:
            status.error = str(e)

        self._health_cache = status
        return status

    def detect_enabled_sinks(self) -> List[str]:
        """Detect which sinks should be enabled based on environment variables.

        Returns:
            List of sink type names that have their env vars configured.
        """
        sinks = ["console", "file"]  # Always enabled

        if os.environ.get("SF_LOKI_ENDPOINT"):
            sinks.append("loki")
        if os.environ.get("SF_ES_ENDPOINT"):
            sinks.append("elasticsearch")
        if os.environ.get("SF_S3_BUCKET"):
            sinks.append("s3")
        if os.environ.get("SF_ALERT_WEBHOOK_URL"):
            sinks.append("webhook")

        return sinks

    def config_exists(self) -> bool:
        """Check if the Vector config file exists."""
        return Path(self.config.config_path).exists()

    def validate_config(self) -> Dict[str, Any]:
        """Validate the Vector configuration file.

        Returns:
            Dict with 'valid' bool and 'errors' list.
        """
        result = {"valid": False, "errors": [], "path": self.config.config_path}

        config_path = Path(self.config.config_path)
        if not config_path.exists():
            result["errors"].append(f"Config file not found: {config_path}")
            return result

        content = config_path.read_text(encoding="utf-8")

        # Basic structural checks
        if "[sources." not in content:
            result["errors"].append("No [sources.*] section found")
        if "[sinks." not in content:
            result["errors"].append("No [sinks.*] section found")
        if "sf_events_http" not in content:
            result["errors"].append("Missing sf_events_http source")

        if not result["errors"]:
            result["valid"] = True

        return result

    def generate_minimal_config(self) -> str:
        """Generate a minimal Vector config for quick-start deployments.

        Returns:
            TOML config string with console + file sinks.
        """
        return textwrap.dedent("""\
        # Minimal Vector.dev config for SpiderFoot
        # Generated by VectorBootstrap

        data_dir = "/var/lib/vector"

        [sources.spiderfoot]
        type = "http_server"
        address = "0.0.0.0:8686"
        encoding.codec = "ndjson"

        [transforms.classify]
        type = "remap"
        inputs = ["spiderfoot"]
        source = \\'\\'\\'
        .pipeline = "spiderfoot"
        .ingested_at = now()
        if .type == "scan_event" { .stream = "events" }
        else if .type == "metric" { .stream = "metrics" }
        else { .stream = "logs" }
        \\'\\'\\'

        [sinks.stdout]
        type = "console"
        inputs = ["classify"]
        encoding.codec = "json"

        [sinks.file]
        type = "file"
        inputs = ["classify"]
        path = "/var/log/spiderfoot/all-%Y-%m-%d.jsonl"
        encoding.codec = "json"
        """).replace("\\'", "'")

    def get_status_summary(self) -> Dict[str, Any]:
        """Get a summary of the Vector.dev integration status.

        Returns:
            Dict with config, health, and sink information.
        """
        health = self._health_cache or self.check_health()
        sinks = self.detect_enabled_sinks()
        config_valid = self.validate_config()

        return {
            "vector_enabled": health.reachable,
            "config_valid": config_valid["valid"],
            "config_path": self.config.config_path,
            "enabled_sinks": sinks,
            "health": health.to_dict(),
            "config_errors": config_valid.get("errors", []),
        }
