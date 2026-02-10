"""Tests for spiderfoot.event_dedup module."""
from __future__ import annotations

import threading
import time
import unittest

from spiderfoot.event_dedup import (
    ContentNormalizer,
    DedupAction,
    DedupRecord,
    DedupStats,
    DedupStrategy,
    EventDeduplicator,
    ScanDeduplicator,
    get_event_deduplicator,
)


class TestDedupStrategy(unittest.TestCase):
    def test_values(self):
        self.assertEqual(DedupStrategy.EXACT.value, "exact")
        self.assertEqual(DedupStrategy.NORMALIZED.value, "normalized")
        self.assertEqual(DedupStrategy.SEMANTIC.value, "semantic")


class TestDedupAction(unittest.TestCase):
    def test_values(self):
        self.assertEqual(DedupAction.DROP.value, "drop")
        self.assertEqual(DedupAction.MERGE.value, "merge")
        self.assertEqual(DedupAction.TAG.value, "tag")


class TestDedupRecord(unittest.TestCase):
    def test_creation(self):
        r = DedupRecord(event_type="IP_ADDRESS", content_hash="abc123")
        self.assertEqual(r.event_type, "IP_ADDRESS")
        self.assertEqual(r.content_hash, "abc123")
        self.assertEqual(r.count, 1)
        self.assertIsInstance(r.modules, set)

    def test_touch(self):
        r = DedupRecord(event_type="IP_ADDRESS", content_hash="abc123")
        original_first = r.first_seen
        time.sleep(0.01)
        r.touch("sfp_dns")
        self.assertEqual(r.count, 2)
        self.assertIn("sfp_dns", r.modules)
        self.assertEqual(r.first_seen, original_first)
        self.assertGreater(r.last_seen, original_first)

    def test_touch_without_module(self):
        r = DedupRecord(event_type="IP_ADDRESS", content_hash="abc123")
        r.touch()
        self.assertEqual(r.count, 2)
        self.assertEqual(len(r.modules), 0)


class TestDedupStats(unittest.TestCase):
    def test_dedup_rate_zero(self):
        s = DedupStats()
        self.assertEqual(s.dedup_rate, 0.0)

    def test_dedup_rate(self):
        s = DedupStats(total_events=100, duplicates_found=25)
        self.assertAlmostEqual(s.dedup_rate, 25.0)

    def test_to_dict(self):
        s = DedupStats(total_events=10, unique_events=8, duplicates_found=2)
        d = s.to_dict()
        self.assertEqual(d["total_events"], 10)
        self.assertEqual(d["unique_events"], 8)
        self.assertEqual(d["duplicates_found"], 2)
        self.assertEqual(d["dedup_rate_pct"], 20.0)


class TestContentNormalizer(unittest.TestCase):
    def test_normalize_empty(self):
        self.assertEqual(ContentNormalizer.normalize("ANY", ""), "")

    def test_normalize_ip(self):
        result = ContentNormalizer.normalize("IP_ADDRESS", "  192.168.001.001  ")
        self.assertEqual(result, "192.168.1.1")

    def test_normalize_ip_v6(self):
        result = ContentNormalizer.normalize("IP_ADDRESS", "::1")
        self.assertEqual(result, "::1")

    def test_normalize_email(self):
        result = ContentNormalizer.normalize("EMAILADDR", "  User@Example.COM  ")
        self.assertEqual(result, "user@example.com")

    def test_normalize_url(self):
        result = ContentNormalizer.normalize("URL_WEB", "HTTP://Example.COM:80/path/#frag")
        self.assertEqual(result, "http://example.com/path")

    def test_normalize_url_https_default_port(self):
        result = ContentNormalizer.normalize("URL_WEB", "https://example.com:443/path")
        self.assertEqual(result, "https://example.com/path")

    def test_normalize_domain(self):
        result = ContentNormalizer.normalize("DOMAIN_NAME", "  Example.COM.  ")
        self.assertEqual(result, "example.com")

    def test_normalize_internet_name(self):
        result = ContentNormalizer.normalize("INTERNET_NAME", "WWW.Example.COM/")
        self.assertEqual(result, "www.example.com")

    def test_normalize_general_text(self):
        result = ContentNormalizer.normalize("RAW_RIR_DATA", "  Hello   World  ")
        self.assertEqual(result, "hello world")


class TestEventDeduplicator(unittest.TestCase):
    def test_first_event_not_duplicate(self):
        d = EventDeduplicator()
        self.assertFalse(d.check("IP_ADDRESS", "1.2.3.4", "sfp_dns"))

    def test_same_event_is_duplicate(self):
        d = EventDeduplicator()
        d.check("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        self.assertTrue(d.check("IP_ADDRESS", "1.2.3.4", "sfp_dns"))

    def test_different_type_not_duplicate(self):
        d = EventDeduplicator()
        d.check("IP_ADDRESS", "1.2.3.4")
        self.assertFalse(d.check("EMAILADDR", "1.2.3.4"))

    def test_different_data_not_duplicate(self):
        d = EventDeduplicator()
        d.check("IP_ADDRESS", "1.2.3.4")
        self.assertFalse(d.check("IP_ADDRESS", "5.6.7.8"))

    def test_normalized_strategy_detects_equivalent(self):
        d = EventDeduplicator(strategy=DedupStrategy.NORMALIZED)
        d.check("IP_ADDRESS", "192.168.001.001")
        self.assertTrue(d.check("IP_ADDRESS", "192.168.1.1"))

    def test_exact_strategy_misses_equivalent(self):
        d = EventDeduplicator(strategy=DedupStrategy.EXACT)
        d.check("IP_ADDRESS", "192.168.001.001")
        self.assertFalse(d.check("IP_ADDRESS", "192.168.1.1"))

    def test_per_module_scope(self):
        d = EventDeduplicator(scope="per_module")
        d.check("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        # Same data from different module is NOT a duplicate
        self.assertFalse(d.check("IP_ADDRESS", "1.2.3.4", "sfp_portscan"))
        # Same data from same module IS a duplicate
        self.assertTrue(d.check("IP_ADDRESS", "1.2.3.4", "sfp_dns"))

    def test_stats_tracking(self):
        d = EventDeduplicator()
        d.check("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        d.check("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        d.check("IP_ADDRESS", "5.6.7.8", "sfp_dns")

        stats = d.get_stats()
        self.assertEqual(stats.total_events, 3)
        self.assertEqual(stats.unique_events, 2)
        self.assertEqual(stats.duplicates_found, 1)
        self.assertEqual(stats.duplicates_by_type.get("IP_ADDRESS"), 1)

    def test_get_duplicates(self):
        d = EventDeduplicator()
        d.check("IP_ADDRESS", "1.2.3.4")
        d.check("IP_ADDRESS", "1.2.3.4")
        d.check("IP_ADDRESS", "5.6.7.8")  # Only once

        dups = d.get_duplicates(min_count=2)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0].event_type, "IP_ADDRESS")
        self.assertEqual(dups[0].count, 2)

    def test_get_top_duplicates(self):
        d = EventDeduplicator()
        for _ in range(5):
            d.check("IP_ADDRESS", "1.2.3.4")
        for _ in range(3):
            d.check("EMAILADDR", "test@test.com")
        d.check("DOMAIN_NAME", "example.com")  # Only once

        top = d.get_top_duplicates(n=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].count, 5)
        self.assertEqual(top[1].count, 3)

    def test_get_record(self):
        d = EventDeduplicator()
        d.check("IP_ADDRESS", "1.2.3.4")
        record = d.get_record("IP_ADDRESS", "1.2.3.4")
        self.assertIsNotNone(record)
        self.assertEqual(record.event_type, "IP_ADDRESS")

    def test_get_record_missing(self):
        d = EventDeduplicator()
        self.assertIsNone(d.get_record("IP_ADDRESS", "1.2.3.4"))

    def test_callback_on_duplicate(self):
        d = EventDeduplicator()
        detected = []
        d.on_duplicate(lambda et, data, mod, rec: detected.append((et, data)))

        d.check("IP_ADDRESS", "1.2.3.4")
        d.check("IP_ADDRESS", "1.2.3.4")  # Triggers callback

        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0], ("IP_ADDRESS", "1.2.3.4"))

    def test_callback_error_handled(self):
        d = EventDeduplicator()
        d.on_duplicate(lambda *a: 1 / 0)

        d.check("IP_ADDRESS", "1.2.3.4")
        # Should not raise
        d.check("IP_ADDRESS", "1.2.3.4")

    def test_disable_enable(self):
        d = EventDeduplicator()
        d.check("IP_ADDRESS", "1.2.3.4")
        d.disable()
        self.assertFalse(d.check("IP_ADDRESS", "1.2.3.4"))  # Not flagged when disabled
        d.enable()
        self.assertTrue(d.check("IP_ADDRESS", "1.2.3.4"))  # Flagged again

    def test_reset(self):
        d = EventDeduplicator()
        d.check("IP_ADDRESS", "1.2.3.4")
        d.check("IP_ADDRESS", "1.2.3.4")
        d.reset()

        self.assertEqual(d.record_count, 0)
        stats = d.get_stats()
        self.assertEqual(stats.total_events, 0)
        self.assertFalse(d.check("IP_ADDRESS", "1.2.3.4"))  # Not duplicate after reset

    def test_max_records(self):
        d = EventDeduplicator(max_records=2)
        d.check("IP_ADDRESS", "1.1.1.1")
        d.check("IP_ADDRESS", "2.2.2.2")
        d.check("IP_ADDRESS", "3.3.3.3")  # Over limit, should still return False
        self.assertEqual(d.record_count, 2)

    def test_record_count(self):
        d = EventDeduplicator()
        d.check("IP_ADDRESS", "1.1.1.1")
        d.check("IP_ADDRESS", "2.2.2.2")
        d.check("IP_ADDRESS", "1.1.1.1")  # Duplicate, shouldn't add record
        self.assertEqual(d.record_count, 2)

    def test_to_dict(self):
        d = EventDeduplicator(strategy=DedupStrategy.NORMALIZED, action=DedupAction.TAG)
        d.check("IP_ADDRESS", "1.2.3.4")
        result = d.to_dict()
        self.assertEqual(result["strategy"], "normalized")
        self.assertEqual(result["action"], "tag")
        self.assertEqual(result["record_count"], 1)
        self.assertIn("stats", result)

    def test_check_batch(self):
        d = EventDeduplicator()
        events = [
            ("IP_ADDRESS", "1.2.3.4", "sfp_dns"),
            ("IP_ADDRESS", "1.2.3.4", "sfp_dns"),  # Dup
            ("IP_ADDRESS", "5.6.7.8", "sfp_dns"),
        ]
        results = d.check_batch(events)
        self.assertEqual(results, [False, True, False])

    def test_thread_safety(self):
        d = EventDeduplicator()
        errors = []

        def add_events(prefix):
            try:
                for i in range(100):
                    d.check("IP_ADDRESS", f"{prefix}.{i}.0.1")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_events, args=(str(t),)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(d.record_count, 500)

    def test_modules_tracked_in_record(self):
        d = EventDeduplicator()
        d.check("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        d.check("IP_ADDRESS", "1.2.3.4", "sfp_portscan")  # Duplicate, different module

        record = d.get_record("IP_ADDRESS", "1.2.3.4")
        self.assertIn("sfp_dns", record.modules)
        self.assertIn("sfp_portscan", record.modules)


class TestScanDeduplicator(unittest.TestCase):
    def test_basic_dedup(self):
        sd = ScanDeduplicator(scan_id="scan-001")
        self.assertFalse(sd.is_duplicate("IP_ADDRESS", "1.2.3.4"))
        self.assertTrue(sd.is_duplicate("IP_ADDRESS", "1.2.3.4"))

    def test_type_specific_strategy(self):
        sd = ScanDeduplicator(scan_id="scan-001", default_strategy=DedupStrategy.EXACT)
        sd.set_strategy("IP_ADDRESS", DedupStrategy.NORMALIZED)

        # IP uses normalized → detects equivalent IPs
        sd.is_duplicate("IP_ADDRESS", "192.168.001.001")
        self.assertTrue(sd.is_duplicate("IP_ADDRESS", "192.168.1.1"))

        # Other types use exact → doesn't normalize
        sd.is_duplicate("RAW_DATA", "  hello  ")
        self.assertFalse(sd.is_duplicate("RAW_DATA", "hello"))

    def test_get_stats(self):
        sd = ScanDeduplicator(scan_id="scan-001")
        sd.set_strategy("IP_ADDRESS", DedupStrategy.NORMALIZED)
        sd.is_duplicate("IP_ADDRESS", "1.2.3.4")
        sd.is_duplicate("IP_ADDRESS", "1.2.3.4")
        sd.is_duplicate("EMAILADDR", "a@b.com")

        stats = sd.get_stats()
        self.assertEqual(stats["scan_id"], "scan-001")
        self.assertIn("default", stats)
        self.assertIn("type_specific", stats)

    def test_get_all_duplicates(self):
        sd = ScanDeduplicator(scan_id="scan-001")
        sd.is_duplicate("IP_ADDRESS", "1.2.3.4")
        sd.is_duplicate("IP_ADDRESS", "1.2.3.4")

        dups = sd.get_all_duplicates()
        self.assertEqual(len(dups), 1)

    def test_reset(self):
        sd = ScanDeduplicator(scan_id="scan-001")
        sd.is_duplicate("IP_ADDRESS", "1.2.3.4")
        sd.is_duplicate("IP_ADDRESS", "1.2.3.4")
        sd.reset()

        self.assertFalse(sd.is_duplicate("IP_ADDRESS", "1.2.3.4"))


class TestSingleton(unittest.TestCase):
    def test_get_event_deduplicator(self):
        d1 = get_event_deduplicator()
        d2 = get_event_deduplicator()
        self.assertIs(d1, d2)

    def test_singleton_is_normalized(self):
        d = get_event_deduplicator()
        self.assertEqual(d.strategy, DedupStrategy.NORMALIZED)


if __name__ == "__main__":
    unittest.main()
