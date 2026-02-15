"""Tests for spiderfoot.enrichment module."""
from __future__ import annotations

import threading
import unittest

from spiderfoot.enrichment import (
    DataSizeEnricher,
    Enricher,
    EnrichmentContext,
    EnrichmentPipeline,
    EnrichmentPriority,
    FunctionEnricher,
    TagEnricher,
    create_default_pipeline,
)


class TestEnrichmentPriority(unittest.TestCase):
    def test_ordering(self):
        self.assertLess(EnrichmentPriority.CRITICAL.value, EnrichmentPriority.HIGH.value)
        self.assertLess(EnrichmentPriority.HIGH.value, EnrichmentPriority.NORMAL.value)
        self.assertLess(EnrichmentPriority.NORMAL.value, EnrichmentPriority.LOW.value)


class TestEnrichmentContext(unittest.TestCase):
    def test_creation(self):
        ctx = EnrichmentContext(event_type="IP_ADDRESS", data="1.2.3.4")
        self.assertEqual(ctx.event_type, "IP_ADDRESS")
        self.assertEqual(ctx.data, "1.2.3.4")

    def test_add_enrichment(self):
        ctx = EnrichmentContext(event_type="IP_ADDRESS", data="1.2.3.4")
        ctx.add_enrichment("geo", {"country": "US"})
        self.assertTrue(ctx.has_enrichment("geo"))
        self.assertEqual(ctx.get_enrichment("geo")["country"], "US")

    def test_get_enrichment_default(self):
        ctx = EnrichmentContext(event_type="IP_ADDRESS", data="1.2.3.4")
        self.assertIsNone(ctx.get_enrichment("missing"))
        self.assertEqual(ctx.get_enrichment("missing", "fallback"), "fallback")

    def test_add_tag(self):
        ctx = EnrichmentContext(event_type="IP_ADDRESS", data="1.2.3.4")
        ctx.add_tag("network")
        ctx.add_tag("external")
        self.assertIn("network", ctx.tags)
        self.assertIn("external", ctx.tags)

    def test_to_dict(self):
        ctx = EnrichmentContext(event_type="IP_ADDRESS", data="1.2.3.4", module="sfp_dns")
        ctx.add_enrichment("test", True)
        ctx.add_tag("net")
        d = ctx.to_dict()
        self.assertEqual(d["event_type"], "IP_ADDRESS")
        self.assertIn("test", d["enrichments"])
        self.assertIn("net", d["tags"])

    def test_skip_remaining(self):
        ctx = EnrichmentContext(event_type="IP_ADDRESS", data="1.2.3.4")
        self.assertFalse(ctx.skip_remaining)
        ctx.skip_remaining = True
        self.assertTrue(ctx.skip_remaining)


class TestFunctionEnricher(unittest.TestCase):
    def test_wraps_function(self):
        def add_hello(ctx):
            ctx.add_enrichment("hello", "world")
            return ctx

        enricher = FunctionEnricher(add_hello, name="hello_enricher")
        ctx = EnrichmentContext(event_type="TEST", data="test")
        result = enricher.enrich(ctx)
        self.assertEqual(result.get_enrichment("hello"), "world")
        self.assertEqual(enricher.name, "hello_enricher")

    def test_default_name(self):
        def my_func(ctx):
            return ctx
        enricher = FunctionEnricher(my_func)
        self.assertEqual(enricher.name, "my_func")


class TestEnrichmentPipeline(unittest.TestCase):
    def test_empty_pipeline(self):
        p = EnrichmentPipeline()
        ctx = EnrichmentContext(event_type="TEST", data="test")
        result = p.process(ctx)
        self.assertEqual(result.data, "test")

    def test_single_enricher(self):
        p = EnrichmentPipeline()

        def add_flag(ctx):
            ctx.add_enrichment("flagged", True)
            return ctx

        p.add_function(add_flag)
        ctx = EnrichmentContext(event_type="TEST", data="test")
        result = p.process(ctx)
        self.assertTrue(result.get_enrichment("flagged"))

    def test_chaining(self):
        p = EnrichmentPipeline()

        def step_a(ctx):
            ctx.add_enrichment("a", 1)
            return ctx

        def step_b(ctx):
            ctx.add_enrichment("b", ctx.get_enrichment("a") + 1)
            return ctx

        p.add_function(step_a, priority=EnrichmentPriority.HIGH)
        p.add_function(step_b, priority=EnrichmentPriority.LOW)

        ctx = EnrichmentContext(event_type="TEST", data="test")
        result = p.process(ctx)
        self.assertEqual(result.get_enrichment("a"), 1)
        self.assertEqual(result.get_enrichment("b"), 2)

    def test_priority_ordering(self):
        p = EnrichmentPipeline()
        order = []

        def make_enricher(label, prio):
            def fn(ctx):
                order.append(label)
                return ctx
            p.add_function(fn, name=label, priority=prio)

        make_enricher("low", EnrichmentPriority.LOW)
        make_enricher("high", EnrichmentPriority.HIGH)
        make_enricher("critical", EnrichmentPriority.CRITICAL)

        p.process(EnrichmentContext(event_type="TEST", data="x"))
        self.assertEqual(order, ["critical", "high", "low"])

    def test_event_type_filtering(self):
        p = EnrichmentPipeline()

        def ip_only(ctx):
            ctx.add_enrichment("ip_processed", True)
            return ctx

        p.add_function(ip_only, event_types={"IP_ADDRESS"})

        # Should process IP
        ctx1 = EnrichmentContext(event_type="IP_ADDRESS", data="1.2.3.4")
        r1 = p.process(ctx1)
        self.assertTrue(r1.get_enrichment("ip_processed"))

        # Should skip email
        ctx2 = EnrichmentContext(event_type="EMAILADDR", data="a@b.com")
        r2 = p.process(ctx2)
        self.assertFalse(r2.has_enrichment("ip_processed"))

    def test_skip_remaining(self):
        p = EnrichmentPipeline()

        def stopper(ctx):
            ctx.skip_remaining = True
            ctx.add_enrichment("stopped_here", True)
            return ctx

        def never_reached(ctx):
            ctx.add_enrichment("reached", True)
            return ctx

        p.add_function(stopper, priority=EnrichmentPriority.HIGH)
        p.add_function(never_reached, priority=EnrichmentPriority.LOW)

        result = p.process(EnrichmentContext(event_type="TEST", data="x"))
        self.assertTrue(result.get_enrichment("stopped_here"))
        self.assertFalse(result.has_enrichment("reached"))

    def test_disabled_enricher(self):
        p = EnrichmentPipeline()

        def add_flag(ctx):
            ctx.add_enrichment("flag", True)
            return ctx

        enricher = FunctionEnricher(add_flag, name="flagger")
        enricher.disable()
        p.add(enricher)

        result = p.process(EnrichmentContext(event_type="TEST", data="x"))
        self.assertFalse(result.has_enrichment("flag"))

    def test_error_handling(self):
        p = EnrichmentPipeline()

        def bad_enricher(ctx):
            raise ValueError("boom")

        def good_enricher(ctx):
            ctx.add_enrichment("good", True)
            return ctx

        p.add_function(bad_enricher, priority=EnrichmentPriority.HIGH)
        p.add_function(good_enricher, priority=EnrichmentPriority.LOW)

        result = p.process(EnrichmentContext(event_type="TEST", data="x"))
        # Pipeline should continue after error
        self.assertTrue(result.get_enrichment("good"))

    def test_error_callback(self):
        p = EnrichmentPipeline()
        errors = []

        def bad_enricher(ctx):
            raise ValueError("test error")

        p.add_function(bad_enricher)
        p.on_error(lambda e, ctx, exc: errors.append(str(exc)))

        p.process(EnrichmentContext(event_type="TEST", data="x"))
        self.assertEqual(len(errors), 1)
        self.assertIn("test error", errors[0])

    def test_remove_enricher(self):
        p = EnrichmentPipeline()

        def fn(ctx):
            return ctx

        p.add_function(fn, name="removable")
        self.assertEqual(p.enricher_count, 1)
        self.assertTrue(p.remove("removable"))
        self.assertEqual(p.enricher_count, 0)
        self.assertFalse(p.remove("nonexistent"))

    def test_process_batch(self):
        p = EnrichmentPipeline()

        def add_len(ctx):
            ctx.add_enrichment("len", len(ctx.data))
            return ctx

        p.add_function(add_len)
        contexts = [
            EnrichmentContext(event_type="TEST", data="ab"),
            EnrichmentContext(event_type="TEST", data="abcd"),
        ]
        results = p.process_batch(contexts)
        self.assertEqual(results[0].get_enrichment("len"), 2)
        self.assertEqual(results[1].get_enrichment("len"), 4)

    def test_stats(self):
        p = EnrichmentPipeline(name="test_pipe")

        def fn(ctx):
            return ctx

        p.add_function(fn, name="test_enricher")
        p.process(EnrichmentContext(event_type="TEST", data="x"))

        stats = p.get_stats()
        self.assertEqual(stats["name"], "test_pipe")
        self.assertEqual(stats["total_processed"], 1)
        self.assertEqual(len(stats["enrichers"]), 1)
        self.assertEqual(stats["enrichers"][0]["calls"], 1)

    def test_decorator(self):
        p = EnrichmentPipeline()

        @p.enricher(name="my_enricher", event_types={"TEST"})
        def my_fn(ctx):
            ctx.add_enrichment("decorated", True)
            return ctx

        result = p.process(EnrichmentContext(event_type="TEST", data="x"))
        self.assertTrue(result.get_enrichment("decorated"))

    def test_timings_recorded(self):
        p = EnrichmentPipeline()

        def slow(ctx):
            return ctx

        p.add_function(slow, name="slow_enricher")
        result = p.process(EnrichmentContext(event_type="TEST", data="x"))
        self.assertIn("slow_enricher", result._timings)

    def test_get_enricher_names(self):
        p = EnrichmentPipeline()
        p.add_function(lambda c: c, name="a")
        p.add_function(lambda c: c, name="b")
        self.assertEqual(p.get_enricher_names(), ["a", "b"])

    def test_list_enrichers(self):
        p = EnrichmentPipeline()
        p.add_function(lambda c: c, name="test_e", event_types={"IP_ADDRESS"})
        listing = p.list_enrichers()
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["name"], "test_e")
        self.assertIn("IP_ADDRESS", listing[0]["event_types"])

    def test_thread_safety(self):
        p = EnrichmentPipeline()

        def add_ts(ctx):
            ctx.add_enrichment("processed", True)
            return ctx

        p.add_function(add_ts)
        errors = []

        def process_many():
            try:
                for _ in range(50):
                    p.process(EnrichmentContext(event_type="TEST", data="x"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=process_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(p.get_stats()["total_processed"], 200)


class TestTagEnricher(unittest.TestCase):
    def test_ip_tag(self):
        e = TagEnricher()
        ctx = e.enrich(EnrichmentContext(event_type="IP_ADDRESS", data="1.2.3.4"))
        self.assertIn("network", ctx.tags)

    def test_malicious_tag(self):
        e = TagEnricher()
        ctx = e.enrich(EnrichmentContext(event_type="MALICIOUS_IPADDR", data="x"))
        self.assertIn("threat", ctx.tags)

    def test_email_tag(self):
        e = TagEnricher()
        ctx = e.enrich(EnrichmentContext(event_type="EMAILADDR", data="a@b.com"))
        self.assertIn("identity", ctx.tags)

    def test_no_match(self):
        e = TagEnricher()
        ctx = e.enrich(EnrichmentContext(event_type="RAW_DATA", data="x"))
        self.assertEqual(len(ctx.tags), 0)


class TestDataSizeEnricher(unittest.TestCase):
    def test_data_length(self):
        e = DataSizeEnricher()
        ctx = e.enrich(EnrichmentContext(event_type="TEST", data="hello"))
        self.assertEqual(ctx.get_enrichment("data_length"), 5)
        self.assertFalse(ctx.get_enrichment("data_is_empty"))

    def test_empty_data(self):
        e = DataSizeEnricher()
        ctx = e.enrich(EnrichmentContext(event_type="TEST", data="  "))
        self.assertTrue(ctx.get_enrichment("data_is_empty"))


class TestDefaultPipeline(unittest.TestCase):
    def test_create_default(self):
        p = create_default_pipeline()
        self.assertGreaterEqual(p.enricher_count, 2)

        ctx = EnrichmentContext(event_type="IP_ADDRESS", data="1.2.3.4")
        result = p.process(ctx)
        self.assertIn("network", result.tags)
        self.assertEqual(result.get_enrichment("data_length"), 7)


if __name__ == "__main__":
    unittest.main()
