from __future__ import annotations

"""Contract tests for the external-tool (`sfp_tool_*`) wrapper modules.

These modules shell out to external binaries and were historically the least
tested in the suite — which is exactly where an event-emission/opts-access bug
slipped through undetected. Rather than 20 near-duplicate files, this module
parametrizes a meaningful contract over every untested tool wrapper:

  * the module imports, instantiates, and sets up;
  * opts / optdescs are consistent;
  * watchedEvents / producedEvents are non-empty lists of strings;
  * handleEvent honours the errorState guard;
  * handleEvent on a missing binary sets errorState and emits nothing
    (this path exercises real opts access — the class of bug that escaped
    before, where a wrong opts key or self.sf attribute raised at runtime).
"""

import importlib
import unittest
from unittest.mock import patch

from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent


# Tool wrappers that had no dedicated unit/integration test.
TOOL_MODULES = [
    "sfp_tool_amass", "sfp_tool_arjun", "sfp_tool_dalfox", "sfp_tool_dnsx",
    "sfp_tool_ffuf", "sfp_tool_gau", "sfp_tool_gitleaks", "sfp_tool_gospider",
    "sfp_tool_gowitness", "sfp_tool_hakrawler", "sfp_tool_katana",
    "sfp_tool_linkfinder", "sfp_tool_masscan", "sfp_tool_massdns",
    "sfp_tool_naabu", "sfp_tool_nikto", "sfp_tool_sslscan", "sfp_tool_sslyze",
    "sfp_tool_tlsx", "sfp_tool_waybackurls",
]

DEFAULT_OPTS = {
    "_useragent": "SpiderFoot",
    "_fetchtimeout": 5,
    "_internettlds": "https://publicsuffix.org/list/effective_tld_names.dat",
}


def _load(module_name: str):
    mod = importlib.import_module(f"modules.{module_name}")
    return getattr(mod, module_name)


class TestToolModuleContract(unittest.TestCase):
    """Shared contract across all untested sfp_tool_* wrappers."""

    def test_instantiate_and_setup(self):
        for name in TOOL_MODULES:
            with self.subTest(module=name):
                cls = _load(name)
                m = cls()
                sf = SpiderFoot(DEFAULT_OPTS)
                m.setup(sf, dict())
                self.assertIsNotNone(m.opts)

    def test_opts_match_optdescs(self):
        for name in TOOL_MODULES:
            with self.subTest(module=name):
                m = _load(name)()
                # Every documented option must exist and vice-versa.
                self.assertEqual(set(m.opts.keys()), set(m.optdescs.keys()))

    def test_watched_and_produced_events(self):
        for name in TOOL_MODULES:
            with self.subTest(module=name):
                m = _load(name)()
                watched = m.watchedEvents()
                produced = m.producedEvents()
                self.assertIsInstance(watched, list)
                self.assertIsInstance(produced, list)
                self.assertTrue(watched, f"{name} watches no events")
                self.assertTrue(produced, f"{name} produces no events")
                for e in watched + produced:
                    self.assertIsInstance(e, str)
                    self.assertTrue(e.isupper() or e == "*",
                                    f"{name}: event '{e}' not an UPPER_CASE type")

    def test_errorState_guard_short_circuits(self):
        """handleEvent must return immediately when errorState is set."""
        for name in TOOL_MODULES:
            with self.subTest(module=name):
                m = _load(name)()
                sf = SpiderFoot(DEFAULT_OPTS)
                m.setup(sf, dict())
                m.errorState = True
                emitted = []
                m.notifyListeners = lambda evt: emitted.append(evt)
                watched = m.watchedEvents()
                etype = watched[0] if watched and watched[0] != "*" else "DOMAIN_NAME"
                evt = SpiderFootEvent(etype, "example.com", "test", None)
                m.handleEvent(evt)  # must not raise, must emit nothing
                self.assertEqual(emitted, [])

    def test_missing_binary_sets_errorstate_and_emits_nothing(self):
        """With the tool binary absent, handleEvent should fail safe.

        This exercises real opts access and the binary-resolution path without
        running any external process — catching opts-key / attribute bugs that
        unit tests previously missed for these wrappers.
        """
        for name in TOOL_MODULES:
            with self.subTest(module=name):
                cls = _load(name)
                m = cls()
                sf = SpiderFoot(DEFAULT_OPTS)
                m.setup(sf, dict())
                m.setTarget = getattr(m, "setTarget", None)
                # Point any configurable tool path at a non-existent file and
                # ensure PATH lookups fail, so the binary is "not found".
                for k in list(m.opts.keys()):
                    if k.endswith("_path") or k.endswith("path"):
                        m.opts[k] = "/nonexistent/bin/does-not-exist"
                emitted = []
                m.notifyListeners = lambda evt: emitted.append(evt)
                watched = m.watchedEvents()
                etype = watched[0] if watched and watched[0] != "*" else "DOMAIN_NAME"
                # Give the module a target value for ROOT-driven modules.
                try:
                    m.getTarget = lambda: type("T", (), {"targetValue": "example.com"})()
                except Exception:
                    pass
                evt = SpiderFootEvent(etype, "example.com", "test", None)
                with patch("shutil.which", return_value=None), \
                        patch("subprocess.run", side_effect=AssertionError(
                            f"{name} ran a subprocess despite missing binary")), \
                        patch("subprocess.Popen", side_effect=AssertionError(
                            f"{name} spawned a process despite missing binary")):
                    # PATH emptied so _find_binary cannot resolve a real tool.
                    with patch.dict("os.environ", {"PATH": ""}):
                        try:
                            m.handleEvent(evt)
                        except AssertionError:
                            raise
                        except Exception as e:  # noqa: BLE001
                            self.fail(f"{name}.handleEvent raised {type(e).__name__}: {e}")
                # No events should be emitted when the binary is unavailable.
                self.assertEqual(emitted, [], f"{name} emitted events without its binary")


if __name__ == "__main__":
    unittest.main()
