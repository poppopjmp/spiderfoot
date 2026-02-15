"""Tests for spiderfoot.event_pipeline module."""
from __future__ import annotations

import unittest

from spiderfoot.events.event_pipeline import (
    EventPipeline,
    FunctionStage,
    PipelineEvent,
    RouterStage,
    StageResult,
    TaggingStage,
    TransformStage,
    ValidatorStage,
)


class TestPipelineEvent(unittest.TestCase):
    def test_basic(self):
        e = PipelineEvent(event_type="IP_ADDRESS", data="1.2.3.4", module="sfp_dns")
        self.assertFalse(e.is_dropped)
        self.assertEqual(e.event_type, "IP_ADDRESS")

    def test_drop(self):
        e = PipelineEvent(event_type="TEST", data="x")
        e.drop("too big")
        self.assertTrue(e.is_dropped)
        self.assertEqual(e.drop_reason, "too big")

    def test_tags(self):
        e = PipelineEvent(event_type="TEST", data="x")
        e.tags.add("threat")
        self.assertIn("threat", e.tags)


class TestValidatorStage(unittest.TestCase):
    def test_allowed_types(self):
        v = ValidatorStage(allowed_types={"IP_ADDRESS"})
        e1 = PipelineEvent(event_type="IP_ADDRESS", data="1.2.3.4")
        self.assertEqual(v.process(e1), StageResult.CONTINUE)

        e2 = PipelineEvent(event_type="RAW_DATA", data="x")
        self.assertEqual(v.process(e2), StageResult.DROP)
        self.assertTrue(e2.is_dropped)

    def test_max_data_size(self):
        v = ValidatorStage(max_data_size=10)
        e1 = PipelineEvent(event_type="T", data="short")
        self.assertEqual(v.process(e1), StageResult.CONTINUE)

        e2 = PipelineEvent(event_type="T", data="x" * 100)
        self.assertEqual(v.process(e2), StageResult.DROP)


class TestTransformStage(unittest.TestCase):
    def test_transform(self):
        t = TransformStage(lambda d: d.upper())
        e = PipelineEvent(event_type="T", data="hello")
        self.assertEqual(t.process(e), StageResult.CONTINUE)
        self.assertEqual(e.data, "HELLO")

    def test_transform_error(self):
        t = TransformStage(lambda d: 1 / 0)
        e = PipelineEvent(event_type="T", data="x")
        self.assertEqual(t.process(e), StageResult.ERROR)


class TestTaggingStage(unittest.TestCase):
    def test_tagging(self):
        t = TaggingStage({"MALICIOUS": "threat", "IP_ADDRESS": "network"})
        e = PipelineEvent(event_type="IP_ADDRESS", data="1.2.3.4")
        t.process(e)
        self.assertIn("network", e.tags)

    def test_add_rule(self):
        t = TaggingStage()
        t.add_rule("secret", "sensitive")
        e = PipelineEvent(event_type="T", data="this is a secret value")
        t.process(e)
        self.assertIn("sensitive", e.tags)


class TestFunctionStage(unittest.TestCase):
    def test_function(self):
        def mark(e):
            e.metadata["seen"] = True
            return StageResult.CONTINUE

        s = FunctionStage(mark, name="marker")
        e = PipelineEvent(event_type="T", data="x")
        self.assertEqual(s.process(e), StageResult.CONTINUE)
        self.assertTrue(e.metadata["seen"])


class TestRouterStage(unittest.TestCase):
    def test_routing(self):
        r = RouterStage()
        r.add_route(lambda e: e.event_type == "IP_ADDRESS", "ip_handler")
        r.add_route(lambda e: "malicious" in e.data, "threat_handler")

        e = PipelineEvent(event_type="IP_ADDRESS", data="malicious 1.2.3.4")
        r.process(e)
        routes = e.metadata.get("_routes", [])
        self.assertIn("ip_handler", routes)
        self.assertIn("threat_handler", routes)


class TestEventPipeline(unittest.TestCase):
    def test_empty_pipeline(self):
        p = EventPipeline()
        e = PipelineEvent(event_type="T", data="x")
        self.assertEqual(p.execute(e), StageResult.CONTINUE)

    def test_single_stage(self):
        p = EventPipeline()
        p.add_stage(ValidatorStage(allowed_types={"IP_ADDRESS"}))
        e1 = PipelineEvent(event_type="IP_ADDRESS", data="1.2.3.4")
        self.assertEqual(p.execute(e1), StageResult.CONTINUE)

        e2 = PipelineEvent(event_type="RAW_DATA", data="x")
        self.assertEqual(p.execute(e2), StageResult.DROP)

    def test_multi_stage(self):
        p = EventPipeline()
        p.add_stage(ValidatorStage(allowed_types={"IP_ADDRESS"}))
        p.add_stage(TaggingStage({"IP": "network"}))
        p.add_stage(TransformStage(lambda d: d.strip()))

        e = PipelineEvent(event_type="IP_ADDRESS", data="  1.2.3.4  ")
        self.assertEqual(p.execute(e), StageResult.CONTINUE)
        self.assertEqual(e.data, "1.2.3.4")
        self.assertIn("network", e.tags)

    def test_drop_stops_pipeline(self):
        p = EventPipeline()
        p.add_stage(ValidatorStage(allowed_types={"IP_ADDRESS"}, name="v1"))
        p.add_stage(TaggingStage({"x": "tag"}, name="t1"))

        e = PipelineEvent(event_type="RAW_DATA", data="x")
        self.assertEqual(p.execute(e), StageResult.DROP)
        # Tagging stage should not have processed
        self.assertEqual(p.get_stats()["stage_stats"][1]["processed"], 0)

    def test_error_continues(self):
        p = EventPipeline()
        p.add_stage(TransformStage(lambda d: 1 / 0, name="bad"))
        p.add_stage(TaggingStage({"x": "tag"}, name="tagger"))

        e = PipelineEvent(event_type="T", data="x")
        result = p.execute(e)
        self.assertEqual(result, StageResult.CONTINUE)

    def test_chaining(self):
        p = (
            EventPipeline("test")
            .add_stage(ValidatorStage(name="v"))
            .add_stage(TaggingStage(name="t"))
        )
        self.assertEqual(p.stage_count, 2)

    def test_remove_stage(self):
        p = EventPipeline()
        p.add_stage(ValidatorStage(name="v1"))
        self.assertTrue(p.remove_stage("v1"))
        self.assertEqual(p.stage_count, 0)
        self.assertFalse(p.remove_stage("nonexistent"))

    def test_disabled_stage_skipped(self):
        p = EventPipeline()
        v = ValidatorStage(allowed_types={"IP_ADDRESS"}, name="v")
        v.disable()
        p.add_stage(v)

        e = PipelineEvent(event_type="RAW_DATA", data="x")
        self.assertEqual(p.execute(e), StageResult.CONTINUE)

    def test_stage_names(self):
        p = EventPipeline()
        p.add_stage(ValidatorStage(name="v"))
        p.add_stage(TaggingStage(name="t"))
        self.assertEqual(p.get_stage_names(), ["v", "t"])

    def test_stats(self):
        p = EventPipeline("test")
        p.add_stage(ValidatorStage(allowed_types={"IP_ADDRESS"}, name="v"))
        p.execute(PipelineEvent(event_type="IP_ADDRESS", data="1.2.3.4"))
        p.execute(PipelineEvent(event_type="RAW_DATA", data="x"))

        stats = p.get_stats()
        self.assertEqual(stats["total_processed"], 2)
        self.assertEqual(stats["total_passed"], 1)
        self.assertEqual(stats["total_dropped"], 1)

    def test_reset_stats(self):
        p = EventPipeline()
        p.add_stage(ValidatorStage(name="v"))
        p.execute(PipelineEvent(event_type="T", data="x"))
        p.reset_stats()
        self.assertEqual(p.get_stats()["total_processed"], 0)

    def test_batch(self):
        p = EventPipeline()
        p.add_stage(ValidatorStage(allowed_types={"IP_ADDRESS"}))
        events = [
            PipelineEvent(event_type="IP_ADDRESS", data="1.1.1.1"),
            PipelineEvent(event_type="RAW_DATA", data="x"),
        ]
        results = p.execute_batch(events)
        self.assertEqual(results[0][1], StageResult.CONTINUE)
        self.assertEqual(results[1][1], StageResult.DROP)

    def test_error_handler(self):
        errors = []
        p = EventPipeline()
        p.add_stage(FunctionStage(lambda e: 1 / 0, name="bad"))
        p.on_error(lambda e, s, ex: errors.append((s.name, str(ex))))
        p.execute(PipelineEvent(event_type="T", data="x"))
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], "bad")

    def test_to_dict(self):
        p = EventPipeline("test")
        p.add_stage(ValidatorStage(name="v"))
        d = p.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertIn("stage_stats", d)


if __name__ == "__main__":
    unittest.main()
