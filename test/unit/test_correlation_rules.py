"""Tests for spiderfoot.correlation_rules module."""

import time
import unittest

from spiderfoot.correlation_rules import (
    Condition,
    ConditionOp,
    CorrelationEngine,
    CorrelationMatch,
    CorrelationRule,
    MatchMode,
)


class TestCondition(unittest.TestCase):
    def test_equals(self):
        c = Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS")
        self.assertTrue(c.evaluate({"event_type": "IP_ADDRESS"}))
        self.assertFalse(c.evaluate({"event_type": "DOMAIN"}))

    def test_not_equals(self):
        c = Condition("event_type", ConditionOp.NOT_EQUALS, "RAW_DATA")
        self.assertTrue(c.evaluate({"event_type": "IP_ADDRESS"}))
        self.assertFalse(c.evaluate({"event_type": "RAW_DATA"}))

    def test_contains(self):
        c = Condition("data", ConditionOp.CONTAINS, "password")
        self.assertTrue(c.evaluate({"data": "user password leaked"}))
        self.assertFalse(c.evaluate({"data": "safe data"}))

    def test_matches_regex(self):
        c = Condition("data", ConditionOp.MATCHES, r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        self.assertTrue(c.evaluate({"data": "server at 192.168.1.1"}))
        self.assertFalse(c.evaluate({"data": "no ip here"}))

    def test_greater_than(self):
        c = Condition("risk", ConditionOp.GREATER_THAN, 50)
        self.assertTrue(c.evaluate({"risk": 80}))
        self.assertFalse(c.evaluate({"risk": 30}))

    def test_less_than(self):
        c = Condition("risk", ConditionOp.LESS_THAN, 50)
        self.assertTrue(c.evaluate({"risk": 30}))
        self.assertFalse(c.evaluate({"risk": 80}))

    def test_in(self):
        c = Condition("event_type", ConditionOp.IN, {"IP_ADDRESS", "DOMAIN_NAME"})
        self.assertTrue(c.evaluate({"event_type": "IP_ADDRESS"}))
        self.assertFalse(c.evaluate({"event_type": "RAW_DATA"}))

    def test_not_in(self):
        c = Condition("event_type", ConditionOp.NOT_IN, {"RAW_DATA"})
        self.assertTrue(c.evaluate({"event_type": "IP_ADDRESS"}))
        self.assertFalse(c.evaluate({"event_type": "RAW_DATA"}))

    def test_exists(self):
        c = Condition("module", ConditionOp.EXISTS)
        self.assertTrue(c.evaluate({"module": "sfp_dns"}))
        self.assertFalse(c.evaluate({"data": "no module key"}))

    def test_missing_field(self):
        c = Condition("nonexistent", ConditionOp.EQUALS, "x")
        self.assertFalse(c.evaluate({"data": "test"}))


class TestCorrelationRule(unittest.TestCase):
    def test_basic_match(self):
        rule = CorrelationRule("test")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        self.assertTrue(rule.evaluate({"event_type": "IP_ADDRESS"}))
        self.assertFalse(rule.evaluate({"event_type": "DOMAIN"}))

    def test_all_mode(self):
        rule = CorrelationRule("test", mode=MatchMode.ALL)
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        rule.add_condition(Condition("risk", ConditionOp.GREATER_THAN, 50))
        self.assertTrue(rule.evaluate({"event_type": "IP_ADDRESS", "risk": 80}))
        self.assertFalse(rule.evaluate({"event_type": "IP_ADDRESS", "risk": 30}))

    def test_any_mode(self):
        rule = CorrelationRule("test", mode=MatchMode.ANY)
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        rule.add_condition(Condition("risk", ConditionOp.GREATER_THAN, 50))
        self.assertTrue(rule.evaluate({"event_type": "IP_ADDRESS", "risk": 10}))
        self.assertTrue(rule.evaluate({"event_type": "DOMAIN", "risk": 80}))
        self.assertFalse(rule.evaluate({"event_type": "DOMAIN", "risk": 10}))

    def test_threshold(self):
        rule = CorrelationRule("test")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        rule.set_threshold(count=3)

        e = {"event_type": "IP_ADDRESS", "data": "1.2.3.4"}
        self.assertIsNone(rule.process(e))
        self.assertIsNone(rule.process(e))
        match = rule.process(e)
        self.assertIsNotNone(match)
        self.assertEqual(len(match.events), 3)
        self.assertEqual(rule.fire_count, 1)

    def test_group_by(self):
        rule = CorrelationRule("test")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        rule.set_threshold(count=2)
        rule.set_group_by("module")

        self.assertIsNone(rule.process({"event_type": "IP_ADDRESS", "module": "sfp_dns"}))
        self.assertIsNone(rule.process({"event_type": "IP_ADDRESS", "module": "sfp_ssl"}))
        # Second event from sfp_dns triggers for that group
        match = rule.process({"event_type": "IP_ADDRESS", "module": "sfp_dns"})
        self.assertIsNotNone(match)
        self.assertEqual(match.metadata["group_key"], "sfp_dns")

    def test_disabled_rule(self):
        rule = CorrelationRule("test", enabled=False)
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        self.assertFalse(rule.evaluate({"event_type": "IP_ADDRESS"}))
        self.assertIsNone(rule.process({"event_type": "IP_ADDRESS"}))

    def test_enable_disable(self):
        rule = CorrelationRule("test")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "X"))
        rule.disable()
        self.assertFalse(rule.is_enabled)
        rule.enable()
        self.assertTrue(rule.is_enabled)

    def test_reset(self):
        rule = CorrelationRule("test")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        rule.set_threshold(count=2)
        rule.process({"event_type": "IP_ADDRESS"})
        rule.reset()
        self.assertEqual(rule.fire_count, 0)

    def test_chaining(self):
        rule = (
            CorrelationRule("test")
            .add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
            .set_threshold(count=2)
            .set_group_by("module")
        )
        self.assertEqual(rule.name, "test")

    def test_to_dict(self):
        rule = CorrelationRule("test", description="desc", priority=5)
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP"))
        d = rule.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertEqual(d["priority"], 5)
        self.assertEqual(d["conditions"], 1)


class TestCorrelationEngine(unittest.TestCase):
    def test_add_remove(self):
        engine = CorrelationEngine()
        engine.add_rule(CorrelationRule("r1"))
        self.assertEqual(engine.rule_count, 1)
        self.assertTrue(engine.remove_rule("r1"))
        self.assertEqual(engine.rule_count, 0)
        self.assertFalse(engine.remove_rule("nonexistent"))

    def test_get_rule(self):
        engine = CorrelationEngine()
        r = CorrelationRule("test")
        engine.add_rule(r)
        self.assertIs(engine.get_rule("test"), r)
        self.assertIsNone(engine.get_rule("missing"))

    def test_process_single(self):
        engine = CorrelationEngine()
        rule = CorrelationRule("ip_detect")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        engine.add_rule(rule)

        matches = engine.process({"event_type": "IP_ADDRESS", "data": "1.2.3.4"})
        self.assertEqual(len(matches), 1)
        self.assertEqual(engine.events_processed, 1)

    def test_process_no_match(self):
        engine = CorrelationEngine()
        rule = CorrelationRule("ip_detect")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        engine.add_rule(rule)

        matches = engine.process({"event_type": "DOMAIN_NAME", "data": "example.com"})
        self.assertEqual(len(matches), 0)

    def test_callback(self):
        engine = CorrelationEngine()
        rule = CorrelationRule("test")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        engine.add_rule(rule)

        received = []
        engine.on_match(lambda m: received.append(m))
        engine.process({"event_type": "IP_ADDRESS"})
        self.assertEqual(len(received), 1)

    def test_callback_error_handled(self):
        engine = CorrelationEngine()
        rule = CorrelationRule("test")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        engine.add_rule(rule)

        engine.on_match(lambda m: 1 / 0)
        # Should not raise despite callback error
        matches = engine.process({"event_type": "IP_ADDRESS"})
        self.assertEqual(len(matches), 1)

    def test_process_batch(self):
        engine = CorrelationEngine()
        rule = CorrelationRule("test")
        rule.add_condition(Condition("event_type", ConditionOp.EQUALS, "IP_ADDRESS"))
        engine.add_rule(rule)

        events = [
            {"event_type": "IP_ADDRESS", "data": "1.1.1.1"},
            {"event_type": "DOMAIN_NAME", "data": "example.com"},
            {"event_type": "IP_ADDRESS", "data": "2.2.2.2"},
        ]
        matches = engine.process_batch(events)
        self.assertEqual(len(matches), 2)
        self.assertEqual(engine.events_processed, 3)

    def test_priority_ordering(self):
        engine = CorrelationEngine()
        fired_order = []

        r1 = CorrelationRule("low", priority=1)
        r1.add_condition(Condition("event_type", ConditionOp.EQUALS, "X"))
        r2 = CorrelationRule("high", priority=10)
        r2.add_condition(Condition("event_type", ConditionOp.EQUALS, "X"))

        engine.add_rule(r1).add_rule(r2)
        engine.on_match(lambda m: fired_order.append(m.rule_name))
        engine.process({"event_type": "X"})

        self.assertEqual(fired_order, ["high", "low"])

    def test_get_matches(self):
        engine = CorrelationEngine()
        r1 = CorrelationRule("a")
        r1.add_condition(Condition("event_type", ConditionOp.EQUALS, "X"))
        r2 = CorrelationRule("b")
        r2.add_condition(Condition("event_type", ConditionOp.EQUALS, "X"))
        engine.add_rule(r1).add_rule(r2)

        engine.process({"event_type": "X"})
        self.assertEqual(len(engine.get_matches()), 2)
        self.assertEqual(len(engine.get_matches("a")), 1)
        self.assertEqual(engine.total_matches, 2)

    def test_reset(self):
        engine = CorrelationEngine()
        r = CorrelationRule("test")
        r.add_condition(Condition("event_type", ConditionOp.EQUALS, "X"))
        engine.add_rule(r)
        engine.process({"event_type": "X"})
        engine.reset()
        self.assertEqual(engine.events_processed, 0)
        self.assertEqual(engine.total_matches, 0)

    def test_rule_names(self):
        engine = CorrelationEngine()
        engine.add_rule(CorrelationRule("b"))
        engine.add_rule(CorrelationRule("a"))
        self.assertEqual(engine.rule_names, ["a", "b"])

    def test_to_dict(self):
        engine = CorrelationEngine()
        engine.add_rule(CorrelationRule("test"))
        d = engine.to_dict()
        self.assertIn("rules", d)
        self.assertIn("test", d["rules"])
        self.assertIn("events_processed", d)

    def test_chaining(self):
        engine = CorrelationEngine()
        result = engine.add_rule(CorrelationRule("a"))
        self.assertIs(result, engine)


if __name__ == "__main__":
    unittest.main()
