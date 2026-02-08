"""Tests for the module migration tool."""

import textwrap
import pytest
from scripts.migrate_module import (
    MigrationResult,
    _is_legacy_module,
    _is_already_modern,
    migrate_content,
    migrate_file,
)


class TestDetection:
    """Test module detection helpers."""

    def test_is_legacy_import(self):
        assert _is_legacy_module("from spiderfoot import SpiderFootPlugin")

    def test_is_legacy_class(self):
        assert _is_legacy_module("class sfp_foo(SpiderFootPlugin):")

    def test_is_legacy_multi_import(self):
        assert _is_legacy_module(
            "from spiderfoot import SpiderFootHelpers, SpiderFootEvent, SpiderFootPlugin"
        )

    def test_not_legacy(self):
        assert not _is_legacy_module("import os\nimport json\n")

    def test_already_modern(self):
        assert _is_already_modern(
            "from spiderfoot.modern_plugin import SpiderFootModernPlugin"
        )

    def test_not_modern(self):
        assert not _is_already_modern(
            "from spiderfoot import SpiderFootPlugin"
        )


class TestImportMigration:
    """Test import line transformations."""

    def test_standalone_import(self):
        src = "from spiderfoot import SpiderFootPlugin\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "from spiderfoot.modern_plugin import SpiderFootModernPlugin" in out
        assert "SpiderFootPlugin" not in out
        assert result.migrated

    def test_multi_import(self):
        src = "from spiderfoot import SpiderFootEvent, SpiderFootPlugin\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "from spiderfoot import SpiderFootEvent" in out
        assert "from spiderfoot.modern_plugin import SpiderFootModernPlugin" in out
        assert result.migrated

    def test_multi_import_with_helpers(self):
        src = "from spiderfoot import SpiderFootHelpers, SpiderFootEvent, SpiderFootPlugin\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "SpiderFootModernPlugin" in out
        assert result.migrated


class TestBaseClassMigration:
    """Test class declaration transformations."""

    def test_base_class_swap(self):
        src = "class sfp_foo(SpiderFootPlugin):\n    pass\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "class sfp_foo(SpiderFootModernPlugin):" in out
        assert result.migrated

    def test_multiple_classes(self):
        src = (
            "class sfp_a(SpiderFootPlugin):\n    pass\n"
            "class sfp_b(SpiderFootPlugin):\n    pass\n"
        )
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert out.count("SpiderFootModernPlugin") >= 2


class TestSetupMigration:
    """Test setup() method refactoring."""

    def test_default_arg_dict(self):
        src = "    def setup(self, sfc, userOpts=dict()):\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "userOpts=None" in out
        assert "dict()" not in out

    def test_default_arg_braces(self):
        src = "    def setup(self, sfc, userOpts={}):\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "userOpts=None" in out

    def test_setup_body_rewrite(self):
        src = textwrap.dedent("""\
            def setup(self, sfc, userOpts=None):
                self.sf = sfc
                self.results = self.tempStorage()
                for opt in list(userOpts.keys()):
                    self.opts[opt] = userOpts[opt]
        """)
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "super().setup(sfc, userOpts or {})" in out
        assert "self.sf = sfc" not in out
        assert "for opt in" not in out
        assert result.migrated

    def test_setup_with_datasource(self):
        src = textwrap.dedent("""\
            def setup(self, sfc, userOpts=None):
                self.sf = sfc
                self.__dataSource__ = "Example Source"
                self.results = self.tempStorage()
                for opt in list(userOpts.keys()):
                    self.opts[opt] = userOpts[opt]
        """)
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "super().setup(sfc, userOpts or {})" in out
        assert "self.sf = sfc" not in out
        assert "for opt in" not in out
        assert '__dataSource__ = "Example Source"' in out

    def test_setup_with_extra_lines(self):
        """Modules with extra init lines should still be migrated."""
        src = textwrap.dedent("""\
            def setup(self, sfc, userOpts=None):
                self.sf = sfc
                self.errorState = False
                self.results = self.tempStorage()
                for opt in list(userOpts.keys()):
                    self.opts[opt] = userOpts[opt]
        """)
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "super().setup(sfc, userOpts or {})" in out
        assert "self.sf = sfc" not in out
        assert "for opt in" not in out
        assert "self.errorState = False" in out


class TestFetchUrlMigration:
    """Test fetchUrl → fetch_url swap."""

    def test_simple_fetchurl(self):
        src = '        res = self.sf.fetchUrl(url)\n'
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "self.fetch_url(url)" in out
        assert "self.sf.fetchUrl" not in out

    def test_fetchurl_with_args(self):
        src = '        res = self.sf.fetchUrl(url, timeout=30)\n'
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "self.fetch_url(url, timeout=30)" in out


class TestDnsMethodMigration:
    """Test DNS method swaps."""

    def test_resolve_host(self):
        src = "        addrs = self.sf.resolveHost(hostname)\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "self.resolve_host(hostname)" in out

    def test_resolve_host6(self):
        src = "        addrs = self.sf.resolveHost6(hostname)\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "self.resolve_host6(hostname)" in out

    def test_resolve_host_not_host6(self):
        """resolveHost should NOT match resolveHost6."""
        src = "        self.sf.resolveHost(h)\n        self.sf.resolveHost6(h)\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "self.resolve_host(h)" in out
        assert "self.resolve_host6(h)" in out

    def test_resolve_ip(self):
        src = "        names = self.sf.resolveIP(ip)\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert "self.reverse_resolve(ip)" in out


class TestFullModule:
    """Test migrating a complete module."""

    LEGACY_MODULE = textwrap.dedent("""\
        from spiderfoot import SpiderFootEvent, SpiderFootPlugin

        class sfp_example(SpiderFootPlugin):

            meta = {
                'name': "Example Module",
                'summary': "An example.",
            }

            opts = {
                'api_key': '',
            }

            optdescs = {
                'api_key': "Your API key.",
            }

            results = None

            def setup(self, sfc, userOpts=dict()):
                self.sf = sfc
                self.results = self.tempStorage()

                for opt in list(userOpts.keys()):
                    self.opts[opt] = userOpts[opt]

            def watchedEvents(self):
                return ["IP_ADDRESS"]

            def producedEvents(self):
                return ["RAW_RIR_DATA"]

            def handleEvent(self, event):
                url = f"https://api.example.com/{event.data}"
                res = self.sf.fetchUrl(url, timeout=15)
                if not res:
                    return

                addrs = self.sf.resolveHost(event.data)
                reverse = self.sf.resolveIP(event.data)

                evt = SpiderFootEvent("RAW_RIR_DATA", res['content'], self.__name__, event)
                self.notifyListeners(evt)
    """)

    def test_full_migration(self):
        result = MigrationResult("sfp_example.py")
        out = migrate_content(self.LEGACY_MODULE, result)

        # Imports
        assert "from spiderfoot import SpiderFootEvent" in out
        assert "from spiderfoot.modern_plugin import SpiderFootModernPlugin" in out

        # Base class
        assert "class sfp_example(SpiderFootModernPlugin):" in out

        # setup
        assert "super().setup(sfc, userOpts or {})" in out
        assert "userOpts=None" in out

        # Methods
        assert "self.fetch_url(url, timeout=15)" in out
        assert "self.resolve_host(event.data)" in out
        assert "self.reverse_resolve(event.data)" in out

        # No legacy leftovers
        assert "SpiderFootPlugin" not in out
        assert "self.sf.fetchUrl" not in out
        assert "self.sf.resolveHost(" not in out
        assert "self.sf.resolveIP" not in out

        assert result.migrated
        assert len(result.changes) >= 4


class TestMigrateFile:
    """Test file-level migration."""

    def test_migrate_file_not_found(self):
        result = migrate_file("/nonexistent/sfp_nope.py")
        assert result.error

    def test_migrate_file_dry_run(self, tmp_path):
        p = tmp_path / "sfp_test.py"
        p.write_text(
            "from spiderfoot import SpiderFootPlugin\n"
            "class sfp_test(SpiderFootPlugin):\n    pass\n"
        )
        result = migrate_file(str(p), dry_run=True)
        assert result.migrated
        # Original unchanged in dry-run
        assert "SpiderFootPlugin" in p.read_text()
        assert "SpiderFootModernPlugin" not in p.read_text()

    def test_migrate_file_write(self, tmp_path):
        p = tmp_path / "sfp_test.py"
        p.write_text(
            "from spiderfoot import SpiderFootPlugin\n"
            "class sfp_test(SpiderFootPlugin):\n    pass\n"
        )
        result = migrate_file(str(p), dry_run=False)
        assert result.migrated
        content = p.read_text()
        assert "SpiderFootModernPlugin" in content

    def test_skip_already_modern(self, tmp_path):
        p = tmp_path / "sfp_test.py"
        p.write_text(
            "from spiderfoot.modern_plugin import SpiderFootModernPlugin\n"
            "class sfp_test(SpiderFootModernPlugin):\n    pass\n"
        )
        result = migrate_file(str(p))
        assert not result.migrated
        assert any("Already" in w for w in result.warnings)


class TestNoChanges:
    """Test edge cases that should not be modified."""

    def test_empty_file(self):
        result = MigrationResult("test.py")
        out = migrate_content("", result)
        assert not result.migrated

    def test_unrelated_code(self):
        src = "import os\ndef main():\n    print('hello')\n"
        result = MigrationResult("test.py")
        out = migrate_content(src, result)
        assert not result.migrated
        assert out == src
