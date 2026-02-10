"""Tests for the module validation script."""
from __future__ import annotations

import textwrap
import pytest
from scripts.validate_modules import validate_module, ValidationResult, validate_directory


VALID_MODULE = textwrap.dedent("""\
    from spiderfoot import SpiderFootEvent
    from spiderfoot.modern_plugin import SpiderFootModernPlugin

    class sfp_test(SpiderFootModernPlugin):
        meta = {'name': 'Test', 'summary': 'Test module'}
        opts = {}

        def setup(self, sfc, userOpts=None):
            super().setup(sfc, userOpts or {})
            self.results = self.tempStorage()

        def watchedEvents(self):
            return ["IP_ADDRESS"]

        def producedEvents(self):
            return ["RAW_RIR_DATA"]

        def handleEvent(self, event):
            pass
""")

LEGACY_MODULE = textwrap.dedent("""\
    from spiderfoot import SpiderFootEvent, SpiderFootPlugin

    class sfp_old(SpiderFootPlugin):
        meta = {'name': 'Old'}
        opts = {}

        def setup(self, sfc, userOpts=dict()):
            self.sf = sfc

        def watchedEvents(self):
            return ["IP_ADDRESS"]

        def producedEvents(self):
            return ["RAW_RIR_DATA"]

        def handleEvent(self, event):
            res = self.sf.fetchUrl("http://example.com")
""")


class TestValidateModule:
    def test_valid_module_passes(self, tmp_path):
        p = tmp_path / "sfp_test.py"
        p.write_text(VALID_MODULE)
        result = validate_module(str(p))
        assert result.ok
        assert len(result.failed) == 0

    def test_legacy_module_fails(self, tmp_path):
        p = tmp_path / "sfp_old.py"
        p.write_text(LEGACY_MODULE)
        result = validate_module(str(p))
        assert not result.ok
        fail_names = " ".join(result.failed)
        assert "legacy_import" in fail_names or "missing_modern_import" in fail_names

    def test_syntax_error_fails(self, tmp_path):
        p = tmp_path / "sfp_bad.py"
        p.write_text("def foo(\n")
        result = validate_module(str(p))
        assert not result.ok
        assert any("Syntax" in f for f in result.failed)

    def test_missing_methods(self, tmp_path):
        src = textwrap.dedent("""\
            from spiderfoot.modern_plugin import SpiderFootModernPlugin

            class sfp_incomplete(SpiderFootModernPlugin):
                meta = {}
                def watchedEvents(self):
                    return []
        """)
        p = tmp_path / "sfp_incomplete.py"
        p.write_text(src)
        result = validate_module(str(p))
        assert not result.ok
        fail_names = " ".join(result.failed)
        assert "missing_producedEvents" in fail_names
        assert "missing_handleEvent" in fail_names

    def test_mutable_default_fails(self, tmp_path):
        src = textwrap.dedent("""\
            from spiderfoot.modern_plugin import SpiderFootModernPlugin

            class sfp_mutable(SpiderFootModernPlugin):
                meta = {}
                opts = {}

                def setup(self, sfc, userOpts=dict()):
                    super().setup(sfc, userOpts or {})

                def watchedEvents(self):
                    return []

                def producedEvents(self):
                    return []

                def handleEvent(self, event):
                    pass
        """)
        p = tmp_path / "sfp_mutable.py"
        p.write_text(src)
        result = validate_module(str(p))
        assert not result.ok
        assert any("mutable_default" in f for f in result.failed)

    def test_no_super_setup_fails(self, tmp_path):
        src = textwrap.dedent("""\
            from spiderfoot.modern_plugin import SpiderFootModernPlugin

            class sfp_nosuper(SpiderFootModernPlugin):
                meta = {}
                opts = {}

                def setup(self, sfc, userOpts=None):
                    self.sfc = sfc

                def watchedEvents(self):
                    return []

                def producedEvents(self):
                    return []

                def handleEvent(self, event):
                    pass
        """)
        p = tmp_path / "sfp_nosuper.py"
        p.write_text(src)
        result = validate_module(str(p))
        assert not result.ok
        assert any("missing_super_setup" in f for f in result.failed)

    def test_validate_directory(self, tmp_path):
        (tmp_path / "sfp_a.py").write_text(VALID_MODULE)
        (tmp_path / "sfp_b.py").write_text(VALID_MODULE)
        (tmp_path / "not_a_module.py").write_text("x = 1\n")  # should be skipped
        results = validate_directory(str(tmp_path))
        assert len(results) == 2
        assert all(r.ok for r in results)

    def test_unreadable_file(self):
        result = validate_module("/nonexistent/sfp_nope.py")
        assert not result.ok
        assert any("Cannot read" in f for f in result.failed)
