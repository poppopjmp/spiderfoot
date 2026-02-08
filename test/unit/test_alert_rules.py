"""Tests for spiderfoot.alert_rules."""

import time
import pytest
from spiderfoot.alert_rules import (
    AlertSeverity,
    AlertConditionType,
    AlertCondition,
    Alert,
    AlertRule,
    AlertEngine,
)


class TestAlertCondition:
    def test_event_type_match(self):
        c = AlertCondition(AlertConditionType.EVENT_TYPE, "IP_ADDRESS")
        assert c.evaluate({"event_type": "IP_ADDRESS"})
        assert not c.evaluate({"event_type": "DOMAIN"})

    def test_pattern_match(self):
        c = AlertCondition(AlertConditionType.PATTERN, r"\d+\.\d+\.\d+\.\d+")
        assert c.evaluate({"data": "Found 192.168.1.1"})
        assert not c.evaluate({"data": "no ip here"})

    def test_severity_gte(self):
        c = AlertCondition(AlertConditionType.SEVERITY, 70, operator="gte")
        assert c.evaluate({"risk_score": 80})
        assert not c.evaluate({"risk_score": 50})

    def test_severity_eq(self):
        c = AlertCondition(AlertConditionType.SEVERITY, 50, operator="eq")
        assert c.evaluate({"risk_score": 50})
        assert not c.evaluate({"risk_score": 51})

    def test_count_threshold(self):
        c = AlertCondition(AlertConditionType.COUNT, 10, operator="gte")
        assert c.evaluate({"count": 15})
        assert not c.evaluate({"count": 5})

    def test_rate_threshold(self):
        c = AlertCondition(AlertConditionType.RATE, 5.0, operator="gt")
        assert c.evaluate({"rate": 6.0})
        assert not c.evaluate({"rate": 5.0})

    def test_custom_callable(self):
        c = AlertCondition(AlertConditionType.CUSTOM, lambda ctx: ctx.get("x") > 0)
        assert c.evaluate({"x": 1})
        assert not c.evaluate({"x": -1})

    def test_to_dict(self):
        c = AlertCondition(AlertConditionType.EVENT_TYPE, "IP_ADDRESS")
        d = c.to_dict()
        assert d["condition_type"] == "event_type"
        assert d["value"] == "IP_ADDRESS"


class TestAlert:
    def test_defaults(self):
        a = Alert(rule_name="test", severity=AlertSeverity.HIGH, message="msg")
        assert a.rule_name == "test"
        assert not a.acknowledged

    def test_acknowledge(self):
        a = Alert(rule_name="test", severity=AlertSeverity.LOW, message="msg")
        a.acknowledge()
        assert a.acknowledged

    def test_to_dict(self):
        a = Alert(rule_name="r", severity=AlertSeverity.CRITICAL, message="m")
        d = a.to_dict()
        assert d["severity"] == "critical"
        assert d["rule_name"] == "r"


class TestAlertRule:
    def test_basic_trigger(self):
        rule = AlertRule("test_rule", severity=AlertSeverity.HIGH)
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 70))
        alert = rule.evaluate({"risk_score": 80})
        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH

    def test_no_trigger(self):
        rule = AlertRule("test_rule")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 70))
        alert = rule.evaluate({"risk_score": 50})
        assert alert is None

    def test_disabled_rule(self):
        rule = AlertRule("test_rule", enabled=False)
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        assert rule.evaluate({"risk_score": 100}) is None

    def test_match_any(self):
        rule = AlertRule("test_rule", match_any=True)
        rule.add_condition(AlertCondition(AlertConditionType.EVENT_TYPE, "IP_ADDRESS"))
        rule.add_condition(AlertCondition(AlertConditionType.EVENT_TYPE, "DOMAIN"))
        assert rule.evaluate({"event_type": "IP_ADDRESS"}) is not None
        rule.reset()
        assert rule.evaluate({"event_type": "OTHER"}) is None

    def test_match_all(self):
        rule = AlertRule("test_rule", match_any=False)
        rule.add_condition(AlertCondition(AlertConditionType.EVENT_TYPE, "IP_ADDRESS"))
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 50))
        # Both match
        assert rule.evaluate({"event_type": "IP_ADDRESS", "risk_score": 60}) is not None
        rule.reset()
        # Only one matches
        assert rule.evaluate({"event_type": "IP_ADDRESS", "risk_score": 30}) is None

    def test_max_alerts(self):
        rule = AlertRule("test_rule", max_alerts=2)
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        rule.evaluate({"risk_score": 50})
        rule.evaluate({"risk_score": 50})
        assert rule.evaluate({"risk_score": 50}) is None
        assert rule.alert_count == 2

    def test_cooldown(self):
        rule = AlertRule("test_rule", cooldown_seconds=1.0)
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        assert rule.evaluate({"risk_score": 50}) is not None
        assert rule.evaluate({"risk_score": 50}) is None  # cooldown

    def test_message_template(self):
        rule = AlertRule("test", message_template="Found {event_type} with score {risk_score}")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        alert = rule.evaluate({"event_type": "IP", "risk_score": 80})
        assert "Found IP" in alert.message
        assert "80" in alert.message

    def test_chaining(self):
        rule = AlertRule("test")
        result = rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        assert result is rule

    def test_reset(self):
        rule = AlertRule("test")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        rule.evaluate({"risk_score": 50})
        rule.reset()
        assert rule.alert_count == 0

    def test_to_dict(self):
        rule = AlertRule("test", severity=AlertSeverity.CRITICAL)
        d = rule.to_dict()
        assert d["name"] == "test"
        assert d["severity"] == "critical"

    def test_no_conditions(self):
        rule = AlertRule("test")
        assert rule.evaluate({"risk_score": 100}) is None


class TestAlertEngine:
    def test_add_and_process(self):
        engine = AlertEngine()
        rule = AlertRule("r1")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 70))
        engine.add_rule(rule)
        alerts = engine.process_event({"risk_score": 80})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "r1"

    def test_no_trigger(self):
        engine = AlertEngine()
        rule = AlertRule("r1")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 70))
        engine.add_rule(rule)
        alerts = engine.process_event({"risk_score": 50})
        assert len(alerts) == 0

    def test_multiple_rules(self):
        engine = AlertEngine()
        r1 = AlertRule("r1")
        r1.add_condition(AlertCondition(AlertConditionType.SEVERITY, 70))
        r2 = AlertRule("r2")
        r2.add_condition(AlertCondition(AlertConditionType.EVENT_TYPE, "IP_ADDRESS"))
        engine.add_rule(r1).add_rule(r2)
        alerts = engine.process_event({"risk_score": 80, "event_type": "IP_ADDRESS"})
        assert len(alerts) == 2

    def test_handler_called(self):
        received = []
        engine = AlertEngine()
        engine.add_handler(lambda a: received.append(a))
        rule = AlertRule("r1")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        engine.add_rule(rule)
        engine.process_event({"risk_score": 50})
        assert len(received) == 1

    def test_handler_error_isolated(self):
        def bad_handler(a):
            raise ValueError("boom")
        engine = AlertEngine()
        engine.add_handler(bad_handler)
        rule = AlertRule("r1")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        engine.add_rule(rule)
        # Should not raise
        alerts = engine.process_event({"risk_score": 50})
        assert len(alerts) == 1

    def test_remove_rule(self):
        engine = AlertEngine()
        engine.add_rule(AlertRule("r1"))
        assert engine.remove_rule("r1") is True
        assert engine.remove_rule("r1") is False

    def test_get_rule(self):
        engine = AlertEngine()
        rule = AlertRule("r1")
        engine.add_rule(rule)
        assert engine.get_rule("r1") is rule
        assert engine.get_rule("missing") is None

    def test_alerts_by_severity(self):
        engine = AlertEngine()
        r1 = AlertRule("r1", severity=AlertSeverity.CRITICAL)
        r1.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        r2 = AlertRule("r2", severity=AlertSeverity.LOW)
        r2.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        engine.add_rule(r1).add_rule(r2)
        engine.process_event({"risk_score": 50})
        assert len(engine.get_alerts_by_severity(AlertSeverity.CRITICAL)) == 1
        assert len(engine.get_alerts_by_severity(AlertSeverity.LOW)) == 1

    def test_acknowledge_all(self):
        engine = AlertEngine()
        rule = AlertRule("r1")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        engine.add_rule(rule)
        engine.process_event({"risk_score": 50})
        assert len(engine.get_unacknowledged()) == 1
        engine.acknowledge_all()
        assert len(engine.get_unacknowledged()) == 0

    def test_clear_alerts(self):
        engine = AlertEngine()
        rule = AlertRule("r1")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        engine.add_rule(rule)
        engine.process_event({"risk_score": 50})
        engine.clear_alerts()
        assert len(engine.alerts) == 0

    def test_reset(self):
        engine = AlertEngine()
        rule = AlertRule("r1")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        engine.add_rule(rule)
        engine.process_event({"risk_score": 50})
        engine.reset()
        assert len(engine.alerts) == 0
        assert rule.alert_count == 0

    def test_summary(self):
        engine = AlertEngine()
        rule = AlertRule("r1", severity=AlertSeverity.HIGH)
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        engine.add_rule(rule)
        engine.process_event({"risk_score": 50})
        s = engine.summary()
        assert s["total_rules"] == 1
        assert s["total_alerts"] == 1
        assert s["by_severity"]["high"] == 1

    def test_to_dict(self):
        engine = AlertEngine()
        engine.add_rule(AlertRule("r1"))
        d = engine.to_dict()
        assert "rules" in d
        assert "summary" in d

    def test_history_limit(self):
        engine = AlertEngine(max_history=3)
        rule = AlertRule("r1")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 0))
        engine.add_rule(rule)
        for _ in range(5):
            engine.process_event({"risk_score": 50})
        assert len(engine.alerts) == 3
