"""Tests for spiderfoot.scan_orchestrator module."""
from __future__ import annotations

import unittest

from spiderfoot.scan.scan_orchestrator import (
    ScanOrchestrator,
    ScanPhase,
)


class TestScanOrchestrator(unittest.TestCase):
    def setUp(self):
        self.orch = ScanOrchestrator(scan_id="test_001", target="example.com")

    def test_init(self):
        self.assertEqual(self.orch.scan_id, "test_001")
        self.assertEqual(self.orch.target, "example.com")
        self.assertEqual(self.orch.current_phase, ScanPhase.INIT)

    def test_start(self):
        self.orch.start()
        self.assertEqual(self.orch.current_phase, ScanPhase.INIT)
        self.assertFalse(self.orch.is_complete)

    def test_advance_phase(self):
        self.orch.start()
        p = self.orch.advance_phase()
        self.assertEqual(p, ScanPhase.DISCOVERY)
        p = self.orch.advance_phase()
        self.assertEqual(p, ScanPhase.ENUMERATION)

    def test_full_lifecycle(self):
        self.orch.start()
        phases_seen = [ScanPhase.INIT]
        while self.orch.current_phase != ScanPhase.COMPLETE:
            p = self.orch.advance_phase()
            phases_seen.append(p)
        self.assertEqual(phases_seen[-1], ScanPhase.COMPLETE)

    def test_register_module(self):
        self.orch.register_module("sfp_dns", ScanPhase.DISCOVERY, priority=10)
        self.orch.register_module("sfp_whois", ScanPhase.ENUMERATION)
        modules = self.orch.get_phase_modules(ScanPhase.DISCOVERY)
        self.assertIn("sfp_dns", modules)

    def test_register_chaining(self):
        result = self.orch.register_module("sfp_dns", ScanPhase.DISCOVERY)
        self.assertIs(result, self.orch)

    def test_unregister_module(self):
        self.orch.register_module("sfp_dns", ScanPhase.DISCOVERY)
        self.assertTrue(self.orch.unregister_module("sfp_dns"))
        self.assertFalse(self.orch.unregister_module("nonexistent"))

    def test_module_lifecycle(self):
        self.orch.register_module("sfp_dns", ScanPhase.DISCOVERY)
        self.assertEqual(self.orch.get_module_status("sfp_dns"), "pending")

        self.orch.module_started("sfp_dns")
        self.assertEqual(self.orch.get_module_status("sfp_dns"), "running")

        self.orch.module_completed("sfp_dns", events_produced=10)
        self.assertEqual(self.orch.get_module_status("sfp_dns"), "completed")
        self.assertEqual(self.orch.total_events, 10)

    def test_module_failed(self):
        self.orch.register_module("sfp_dns", ScanPhase.DISCOVERY)
        self.orch.module_started("sfp_dns")
        self.orch.module_failed("sfp_dns", error="timeout")
        self.assertEqual(self.orch.get_module_status("sfp_dns"), "failed")
        self.assertEqual(self.orch.total_errors, 1)

    def test_module_status_unknown(self):
        self.assertEqual(self.orch.get_module_status("unknown_module"), "unknown")

    def test_pending_modules(self):
        self.orch.register_module("sfp_dns", ScanPhase.DISCOVERY)
        self.orch.register_module("sfp_whois", ScanPhase.ENUMERATION)
        self.assertEqual(len(self.orch.get_pending_modules()), 2)
        self.orch.module_completed("sfp_dns")
        self.assertEqual(len(self.orch.get_pending_modules()), 1)

    def test_can_run_module_deps(self):
        self.orch.register_module("sfp_a", ScanPhase.DISCOVERY)
        self.orch.register_module("sfp_b", ScanPhase.ENUMERATION, depends_on={"sfp_a"})
        self.assertFalse(self.orch.can_run_module("sfp_b"))
        self.orch.module_completed("sfp_a")
        self.assertTrue(self.orch.can_run_module("sfp_b"))

    def test_can_run_unknown_module(self):
        self.assertFalse(self.orch.can_run_module("nonexistent"))

    def test_priority_ordering(self):
        self.orch.register_module("sfp_low", ScanPhase.DISCOVERY, priority=1)
        self.orch.register_module("sfp_high", ScanPhase.DISCOVERY, priority=10)
        modules = self.orch.get_phase_modules(ScanPhase.DISCOVERY)
        self.assertEqual(modules[0], "sfp_high")

    def test_complete(self):
        self.orch.start()
        self.orch.complete()
        self.assertTrue(self.orch.is_complete)
        self.assertEqual(self.orch.current_phase, ScanPhase.COMPLETE)

    def test_fail(self):
        self.orch.start()
        self.orch.fail("out of memory")
        self.assertTrue(self.orch.is_complete)
        self.assertEqual(self.orch.current_phase, ScanPhase.FAILED)

    def test_phase_callback(self):
        transitions = []
        self.orch.on_phase_change(lambda old, new: transitions.append((old.value, new.value)))
        self.orch.start()
        self.orch.advance_phase()
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0], ("init", "discovery"))

    def test_completion_callback(self):
        completed = []
        self.orch.on_completion(lambda o: completed.append(o.scan_id))
        self.orch.complete()
        self.assertEqual(completed, ["test_001"])

    def test_elapsed(self):
        self.orch.start()
        self.assertGreaterEqual(self.orch.elapsed_seconds, 0)

    def test_phase_results(self):
        self.orch.start()
        self.orch.advance_phase()
        results = self.orch.get_phase_results()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].phase, ScanPhase.INIT)

    def test_summary(self):
        self.orch.register_module("sfp_dns", ScanPhase.DISCOVERY)
        s = self.orch.summary()
        self.assertEqual(s["scan_id"], "test_001")
        self.assertEqual(s["modules_total"], 1)

    def test_to_dict(self):
        self.orch.start()
        self.orch.advance_phase()
        d = self.orch.to_dict()
        self.assertIn("phases", d)
        self.assertIn("scan_id", d)

    def test_get_phase_modules_empty(self):
        modules = self.orch.get_phase_modules(ScanPhase.REPORTING)
        self.assertEqual(modules, [])


if __name__ == "__main__":
    unittest.main()
