"""Tests for Vector.dev bootstrap utility."""

import json
import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spiderfoot.vector_bootstrap import (
    VectorBootstrap,
    VectorBootstrapConfig,
    VectorHealthStatus,
    VectorSinkType,
)


# ===========================================================================
# VectorHealthStatus
# ===========================================================================

class TestVectorHealthStatus:
    """Tests for VectorHealthStatus dataclass."""

    def test_default_values(self):
        status = VectorHealthStatus()
        assert status.reachable is False
        assert status.version == ""
        assert status.uptime_seconds == 0.0
        assert status.error == ""

    def test_to_dict(self):
        status = VectorHealthStatus(reachable=True, version="0.34.0", uptime_seconds=120.5)
        d = status.to_dict()
        assert d["reachable"] is True
        assert d["version"] == "0.34.0"
        assert d["uptime_seconds"] == 120.5
        assert d["error"] == ""

    def test_to_dict_with_error(self):
        status = VectorHealthStatus(error="Connection refused")
        d = status.to_dict()
        assert d["reachable"] is False
        assert d["error"] == "Connection refused"


# ===========================================================================
# VectorBootstrapConfig
# ===========================================================================

class TestVectorBootstrapConfig:
    """Tests for VectorBootstrapConfig defaults."""

    def test_defaults(self):
        config = VectorBootstrapConfig()
        assert config.vector_api_url == "http://localhost:8686"
        assert config.health_timeout == 5.0
        assert "console" in config.enabled_sinks

    def test_custom_values(self):
        config = VectorBootstrapConfig(
            vector_api_url="http://vector:9090",
            health_timeout=10.0,
        )
        assert config.vector_api_url == "http://vector:9090"
        assert config.health_timeout == 10.0


# ===========================================================================
# VectorBootstrap — construction
# ===========================================================================

class TestVectorBootstrapConstruction:
    """Tests for bootstrap construction."""

    def test_default_construction(self):
        bootstrap = VectorBootstrap()
        assert bootstrap.config.vector_api_url == "http://localhost:8686"

    def test_from_config_dict(self):
        sf_config = {
            "_vector_endpoint": "http://vector-svc:8686",
            "_vector_config_path": "/etc/vector/vector.toml",
        }
        bootstrap = VectorBootstrap.from_config(sf_config)
        assert bootstrap.config.vector_api_url == "http://vector-svc:8686"
        assert bootstrap.config.config_path == "/etc/vector/vector.toml"

    def test_from_config_uses_defaults(self):
        bootstrap = VectorBootstrap.from_config({})
        assert bootstrap.config.vector_api_url == "http://localhost:8686"
        assert bootstrap.config.config_path == "config/vector.toml"


# ===========================================================================
# VectorBootstrap — health check
# ===========================================================================

class TestVectorBootstrapHealth:
    """Tests for health checking."""

    def test_health_no_httpx(self):
        with patch("spiderfoot.vector_bootstrap.HTTPX_AVAILABLE", False):
            bootstrap = VectorBootstrap()
            status = bootstrap.check_health()
            assert status.reachable is False
            assert "httpx not installed" in status.error

    def test_health_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"version": "0.35.0", "uptime_secs": 300.0}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response

        with patch("spiderfoot.vector_bootstrap.HTTPX_AVAILABLE", True), \
             patch("spiderfoot.vector_bootstrap.httpx") as mock_httpx:
            mock_httpx.Client.return_value = mock_client
            bootstrap = VectorBootstrap()
            status = bootstrap.check_health()
            assert status.reachable is True
            assert status.version == "0.35.0"

    def test_health_connection_error(self):
        with patch("spiderfoot.vector_bootstrap.HTTPX_AVAILABLE", True), \
             patch("spiderfoot.vector_bootstrap.httpx") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = ConnectionError("refused")
            mock_httpx.Client.return_value = mock_client

            bootstrap = VectorBootstrap()
            status = bootstrap.check_health()
            assert status.reachable is False
            assert "refused" in status.error

    def test_health_caches_result(self):
        with patch("spiderfoot.vector_bootstrap.HTTPX_AVAILABLE", True), \
             patch("spiderfoot.vector_bootstrap.httpx") as mock_httpx:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = ConnectionError("down")
            mock_httpx.Client.return_value = mock_client

            bootstrap = VectorBootstrap()
            bootstrap.check_health()
            assert bootstrap._health_cache is not None
            assert bootstrap._health_cache.reachable is False


# ===========================================================================
# VectorBootstrap — sink detection
# ===========================================================================

class TestVectorBootstrapSinkDetection:
    """Tests for environment-based sink detection."""

    def test_base_sinks_always_present(self):
        bootstrap = VectorBootstrap()
        with patch.dict(os.environ, {}, clear=True):
            sinks = bootstrap.detect_enabled_sinks()
            assert "console" in sinks
            assert "file" in sinks

    def test_loki_sink_detected(self):
        bootstrap = VectorBootstrap()
        with patch.dict(os.environ, {"SF_LOKI_ENDPOINT": "http://loki:3100"}, clear=True):
            sinks = bootstrap.detect_enabled_sinks()
            assert "loki" in sinks

    def test_elasticsearch_sink_detected(self):
        bootstrap = VectorBootstrap()
        with patch.dict(os.environ, {"SF_ES_ENDPOINT": "http://es:9200"}, clear=True):
            sinks = bootstrap.detect_enabled_sinks()
            assert "elasticsearch" in sinks

    def test_s3_sink_detected(self):
        bootstrap = VectorBootstrap()
        with patch.dict(os.environ, {"SF_S3_BUCKET": "my-bucket"}, clear=True):
            sinks = bootstrap.detect_enabled_sinks()
            assert "s3" in sinks

    def test_webhook_sink_detected(self):
        bootstrap = VectorBootstrap()
        with patch.dict(os.environ, {"SF_ALERT_WEBHOOK_URL": "https://hooks.slack.com/x"}, clear=True):
            sinks = bootstrap.detect_enabled_sinks()
            assert "webhook" in sinks

    def test_multiple_sinks_detected(self):
        bootstrap = VectorBootstrap()
        env = {
            "SF_LOKI_ENDPOINT": "http://loki:3100",
            "SF_ES_ENDPOINT": "http://es:9200",
            "SF_S3_BUCKET": "archive",
            "SF_ALERT_WEBHOOK_URL": "https://hooks.slack.com/x",
        }
        with patch.dict(os.environ, env, clear=True):
            sinks = bootstrap.detect_enabled_sinks()
            assert len(sinks) == 6  # console, file, loki, es, s3, webhook


# ===========================================================================
# VectorBootstrap — config validation
# ===========================================================================

class TestVectorBootstrapConfigValidation:
    """Tests for config validation."""

    def test_validate_missing_config(self):
        bootstrap = VectorBootstrap(VectorBootstrapConfig(
            config_path="/nonexistent/vector.toml"
        ))
        result = bootstrap.validate_config()
        assert result["valid"] is False
        assert any("not found" in e for e in result["errors"])

    def test_validate_real_config(self):
        """Validate the actual config/vector.toml."""
        bootstrap = VectorBootstrap(VectorBootstrapConfig(
            config_path="config/vector.toml"
        ))
        result = bootstrap.validate_config()
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_config_no_sources(self, tmp_path):
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text("[sinks.out]\ntype = 'console'\n")
        bootstrap = VectorBootstrap(VectorBootstrapConfig(
            config_path=str(bad_config)
        ))
        result = bootstrap.validate_config()
        assert result["valid"] is False
        assert any("sources" in e for e in result["errors"])

    def test_validate_config_no_sinks(self, tmp_path):
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text("[sources.in]\ntype = 'stdin'\n")
        bootstrap = VectorBootstrap(VectorBootstrapConfig(
            config_path=str(bad_config)
        ))
        result = bootstrap.validate_config()
        assert result["valid"] is False
        assert any("sinks" in e for e in result["errors"])

    def test_config_exists_true(self):
        bootstrap = VectorBootstrap(VectorBootstrapConfig(
            config_path="config/vector.toml"
        ))
        assert bootstrap.config_exists() is True

    def test_config_exists_false(self):
        bootstrap = VectorBootstrap(VectorBootstrapConfig(
            config_path="/nowhere/vector.toml"
        ))
        assert bootstrap.config_exists() is False


# ===========================================================================
# VectorBootstrap — minimal config generation
# ===========================================================================

class TestVectorBootstrapMinimalConfig:
    """Tests for minimal config generation."""

    def test_generates_toml(self):
        bootstrap = VectorBootstrap()
        config = bootstrap.generate_minimal_config()
        assert "[sources.spiderfoot]" in config
        assert "[sinks.stdout]" in config
        assert "[sinks.file]" in config
        assert "ndjson" in config

    def test_config_is_valid_toml_structure(self):
        bootstrap = VectorBootstrap()
        config = bootstrap.generate_minimal_config()
        # Basic TOML structure checks
        assert config.count("[sources.") >= 1
        assert config.count("[sinks.") >= 1
        assert config.count("[transforms.") >= 1


# ===========================================================================
# VectorBootstrap — status summary
# ===========================================================================

class TestVectorBootstrapStatusSummary:
    """Tests for status summary aggregation."""

    def test_status_summary_structure(self):
        with patch("spiderfoot.vector_bootstrap.HTTPX_AVAILABLE", False):
            bootstrap = VectorBootstrap(VectorBootstrapConfig(
                config_path="config/vector.toml"
            ))
            with patch.dict(os.environ, {}, clear=True):
                summary = bootstrap.get_status_summary()

            assert "vector_enabled" in summary
            assert "config_valid" in summary
            assert "enabled_sinks" in summary
            assert "health" in summary
            assert "config_errors" in summary

    def test_status_summary_uses_cached_health(self):
        bootstrap = VectorBootstrap(VectorBootstrapConfig(
            config_path="config/vector.toml"
        ))
        # Pre-populate cache
        bootstrap._health_cache = VectorHealthStatus(reachable=True, version="0.36.0")
        with patch.dict(os.environ, {}, clear=True):
            summary = bootstrap.get_status_summary()
        assert summary["vector_enabled"] is True
        assert summary["health"]["version"] == "0.36.0"


# ===========================================================================
# VectorSinkType enum
# ===========================================================================

class TestVectorSinkType:
    """Tests for the VectorSinkType enum."""

    def test_all_types(self):
        assert VectorSinkType.CONSOLE.value == "console"
        assert VectorSinkType.LOKI.value == "loki"
        assert VectorSinkType.ELASTICSEARCH.value == "elasticsearch"
        assert VectorSinkType.S3.value == "aws_s3"
        assert VectorSinkType.WEBHOOK.value == "http"
        assert VectorSinkType.FILE.value == "file"
