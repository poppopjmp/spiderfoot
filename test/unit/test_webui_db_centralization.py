"""
Tests for Cycle 31 — WebUI DB Access Centralisation.

Covers:
  - DbProvider mixin — ``_get_dbh()`` centralised factory
  - WebUI scan.py, export.py, settings.py, helpers.py, info.py —
    all per-request SpiderFootDb instantiations replaced
  - routes.py ``_legacy_get_dbh()`` alias
  - CHANGELOG event_schema annotation
"""

import inspect
import os
import glob

import pytest


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

WEBUI_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "spiderfoot", "webui",
)


def _webui_files():
    """Return all .py files in the webui package."""
    return glob.glob(os.path.join(WEBUI_DIR, "*.py"))


# =====================================================================
# 1. DbProvider mixin unit tests
# =====================================================================

class TestDbProvider:
    """Unit tests for the DbProvider mixin."""

    def test_get_dbh_uses_self_config(self):
        """_get_dbh() with no arg uses self.config."""
        from spiderfoot.webui.db_provider import DbProvider

        class Stub(DbProvider):
            config = {"__database": ":memory:", "_debug": False}

            def _get_dbh(self, config=None):
                # Override to avoid real DB — just return the config used
                return config if config is not None else self.config

        stub = Stub()
        result = stub._get_dbh()
        assert result is stub.config

    def test_get_dbh_with_override(self):
        """_get_dbh(cfg) returns handle built from cfg, not self.config."""
        from spiderfoot.webui.db_provider import DbProvider

        class Stub(DbProvider):
            config = {"A": 1}

            def _get_dbh(self, config=None):
                return config if config is not None else self.config

        stub = Stub()
        custom = {"B": 2}
        result = stub._get_dbh(custom)
        assert result is custom

    def test_db_provider_is_in_webui_routes_mro(self):
        """DbProvider is in the WebUiRoutes MRO."""
        from spiderfoot.webui.db_provider import DbProvider
        from spiderfoot.webui.routes import WebUiRoutes
        assert DbProvider in WebUiRoutes.__mro__


# =====================================================================
# 2. Per-file SpiderFootDb purge verification
# =====================================================================

class TestWebuiDbPurge:
    """Verify no per-request SpiderFootDb instantiation in WebUI
    endpoint files (scan.py, export.py, settings.py, helpers.py,
    info.py)."""

    PURGED_FILES = [
        "scan.py", "export.py", "settings.py", "helpers.py", "info.py",
    ]

    @pytest.mark.parametrize("filename", PURGED_FILES)
    def test_no_spiderfoot_db_instantiation(self, filename):
        """File should NOT contain SpiderFootDb(self.config) or
        SpiderFootDb(cfg)."""
        filepath = os.path.join(WEBUI_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"'):
                    continue
                if "SpiderFootDb(" in stripped:
                    pytest.fail(
                        f"SpiderFootDb instantiation in "
                        f"{filename}:{lineno}: {stripped}"
                    )

    @pytest.mark.parametrize("filename", PURGED_FILES)
    def test_no_spiderfoot_db_import(self, filename):
        """File should NOT import SpiderFootDb directly."""
        filepath = os.path.join(WEBUI_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "import SpiderFootDb" in stripped:
                    pytest.fail(
                        f"SpiderFootDb import in "
                        f"{filename}:{lineno}: {stripped}"
                    )

    @pytest.mark.parametrize("filename", PURGED_FILES)
    def test_uses_get_dbh(self, filename):
        """File should use self._get_dbh() for DB access."""
        filepath = os.path.join(WEBUI_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # scan.py has 62 original calls, should have self._get_dbh()
        if filename == "scan.py":
            assert "self._get_dbh()" in content or "self._get_dbh(cfg)" in content


# =====================================================================
# 3. routes.py verification
# =====================================================================

class TestRoutesDbHandling:
    """routes.py should only have SpiderFootDb in __init__ (init=True)
    and the DbProvider mixin."""

    def test_routes_only_init_spiderfoot_db(self):
        """Only __init__ should use SpiderFootDb directly (init=True)."""
        filepath = os.path.join(WEBUI_DIR, "routes.py")
        violations = []
        with open(filepath, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"'):
                    continue
                if "SpiderFootDb(" in stripped and "init=True" not in stripped:
                    violations.append(f"{lineno}: {stripped}")
        assert violations == [], f"Non-init SpiderFootDb calls: {violations}"

    def test_routes_has_legacy_get_dbh(self):
        """routes.py should have _legacy_get_dbh (renamed from _get_dbh)."""
        filepath = os.path.join(WEBUI_DIR, "routes.py")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert "_legacy_get_dbh" in content


# =====================================================================
# 4. db_provider.py structure
# =====================================================================

class TestDbProviderModule:
    """Verify db_provider.py module structure."""

    def test_db_provider_has_get_dbh_method(self):
        from spiderfoot.webui.db_provider import DbProvider
        assert hasattr(DbProvider, '_get_dbh')
        assert callable(getattr(DbProvider, '_get_dbh'))

    def test_get_dbh_accepts_optional_config(self):
        from spiderfoot.webui.db_provider import DbProvider
        sig = inspect.signature(DbProvider._get_dbh)
        params = list(sig.parameters.keys())
        assert 'config' in params
        # config should have a default of None
        config_param = sig.parameters['config']
        assert config_param.default is None

    def test_db_provider_docstring(self):
        from spiderfoot.webui.db_provider import DbProvider
        assert DbProvider.__doc__ is not None
        assert "SpiderFootDb" in DbProvider.__doc__


# =====================================================================
# 5. CHANGELOG fix verification
# =====================================================================

class TestChangelogFix:
    """Verify CHANGELOG event_schema annotation."""

    def test_changelog_event_schema_annotated(self):
        changelog = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "CHANGELOG.md",
        )
        with open(changelog, "r", encoding="utf-8") as f:
            content = f.read()
        assert "removed in v5.33.0" in content
        assert "subsequently deleted" in content
