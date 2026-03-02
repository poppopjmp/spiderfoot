"""Tests for spiderfoot.research.privacy_monitoring (Phase 8b, Cycles 701-800)."""

import pytest
from spiderfoot.research.privacy_monitoring import (
    PrivacyStat,
    LaplaceMechanism,
    PrivacyBudgetTracker,
    PrivateScanStatistics,
    AggregationContribution,
    SecureAggregator,
    AlertSeverity,
    MonitoringAlert,
    MonitorTarget,
    AssetBaseline,
    PassiveMonitor,
)


# ── LaplaceMechanism ─────────────────────────────────────────────────


class TestLaplaceMechanism:
    def test_add_noise(self):
        noisy = LaplaceMechanism.add_noise(100.0, 1.0, 1.0)
        assert isinstance(noisy, float)

    def test_zero_epsilon_raises(self):
        with pytest.raises(ValueError):
            LaplaceMechanism.add_noise(100.0, 1.0, 0.0)

    def test_noise_magnitude(self):
        """Higher epsilon → less noise on average."""
        diffs_high_eps = []
        diffs_low_eps = []
        for _ in range(100):
            diffs_high_eps.append(
                abs(LaplaceMechanism.add_noise(100.0, 1.0, 10.0) - 100.0)
            )
            diffs_low_eps.append(
                abs(LaplaceMechanism.add_noise(100.0, 1.0, 0.1) - 100.0)
            )
        assert sum(diffs_high_eps) / 100 < sum(diffs_low_eps) / 100

    def test_required_epsilon(self):
        eps = LaplaceMechanism.required_epsilon(10.0, 1.0, 0.95)
        assert eps > 0

    def test_required_epsilon_invalid(self):
        with pytest.raises(ValueError):
            LaplaceMechanism.required_epsilon(0.0, 1.0)


# ── PrivacyBudgetTracker ─────────────────────────────────────────────


class TestPrivacyBudgetTracker:
    def test_initial_state(self):
        t = PrivacyBudgetTracker(10.0)
        assert t.remaining == 10.0
        assert t.spent == 0.0

    def test_spend(self):
        t = PrivacyBudgetTracker(10.0)
        assert t.spend(3.0, "q1") is True
        assert t.remaining == 7.0
        assert t.query_count == 1

    def test_overspend(self):
        t = PrivacyBudgetTracker(5.0)
        t.spend(4.0)
        assert t.spend(2.0) is False
        assert t.remaining == 1.0

    def test_negative_epsilon_raises(self):
        t = PrivacyBudgetTracker()
        with pytest.raises(ValueError):
            t.spend(-1.0)

    def test_history(self):
        t = PrivacyBudgetTracker()
        t.spend(1.0, "q1")
        t.spend(2.0, "q2")
        history = t.get_history()
        assert len(history) == 2
        assert history[0]["query"] == "q1"

    def test_reset(self):
        t = PrivacyBudgetTracker(10.0)
        t.spend(5.0)
        t.reset()
        assert t.remaining == 10.0
        assert t.query_count == 0


# ── PrivateScanStatistics ────────────────────────────────────────────


class TestPrivateScanStatistics:
    def test_privatize_count(self):
        pss = PrivateScanStatistics(epsilon=1.0)
        stat = pss.privatize_count("total_findings", 100)
        assert stat is not None
        assert stat.noisy_value >= 0

    def test_privatize_mean(self):
        pss = PrivateScanStatistics(epsilon=1.0)
        stat = pss.privatize_mean(
            "avg_risk_score", 75.0, value_range=(0.0, 100.0)
        )
        assert stat is not None
        assert 0.0 <= stat.noisy_value <= 100.0

    def test_budget_exhaustion(self):
        tracker = PrivacyBudgetTracker(total_budget=2.0)
        pss = PrivateScanStatistics(epsilon=1.0, budget_tracker=tracker)
        assert pss.privatize_count("a", 10) is not None
        assert pss.privatize_count("b", 20) is not None
        assert pss.privatize_count("c", 30) is None  # budget exhausted

    def test_generate_report(self):
        pss = PrivateScanStatistics()
        pss.privatize_count("total_findings", 100)
        report = pss.generate_report()
        assert report["stat_count"] == 1
        assert "privacy_budget" in report

    def test_non_negative_counts(self):
        pss = PrivateScanStatistics(epsilon=0.01)  # Very noisy
        for _ in range(20):
            stat = pss.privatize_count("total_findings", 5)
            if stat:
                assert stat.noisy_value >= 0


# ── SecureAggregator ─────────────────────────────────────────────────


class TestSecureAggregator:
    def test_hash_indicator(self):
        h1 = SecureAggregator.hash_indicator("1.2.3.4")
        h2 = SecureAggregator.hash_indicator("1.2.3.4")
        h3 = SecureAggregator.hash_indicator("5.6.7.8")
        assert h1 == h2
        assert h1 != h3

    def test_hash_with_salt(self):
        h1 = SecureAggregator.hash_indicator("1.2.3.4", "salt1")
        h2 = SecureAggregator.hash_indicator("1.2.3.4", "salt2")
        assert h1 != h2

    def test_min_contributors(self):
        agg = SecureAggregator(min_contributors=3)
        agg.submit(AggregationContribution("org1", ["hash1"]))
        agg.submit(AggregationContribution("org2", ["hash1"]))
        assert agg.aggregate_indicators() == {}  # below threshold

    def test_aggregate_indicators(self):
        agg = SecureAggregator(min_contributors=2)
        agg.submit(AggregationContribution("org1", ["hash1", "hash2"]))
        agg.submit(AggregationContribution("org2", ["hash1", "hash3"]))
        result = agg.aggregate_indicators()
        assert result["hash1"] == 2
        assert result.get("hash2", 0) == 1

    def test_aggregate_counts(self):
        agg = SecureAggregator(min_contributors=2)
        agg.submit(AggregationContribution(
            "org1", counts={"domains": 100, "ips": 50}
        ))
        agg.submit(AggregationContribution(
            "org2", counts={"domains": 200, "ips": 80}
        ))
        result = agg.aggregate_counts(epsilon=10.0)
        assert "domains" in result
        assert result["domains"] > 0

    def test_meets_threshold(self):
        agg = SecureAggregator(min_contributors=3)
        agg.submit(AggregationContribution("org1"))
        assert agg.meets_threshold() is False
        agg.submit(AggregationContribution("org2"))
        agg.submit(AggregationContribution("org3"))
        assert agg.meets_threshold() is True


# ── AssetBaseline ─────────────────────────────────────────────────────


class TestAssetBaseline:
    def test_set_and_get(self):
        b = AssetBaseline()
        b.set_baseline("t1", "subdomain", {"a.com", "b.com"})
        assert b.get_baseline("t1", "subdomain") == {"a.com", "b.com"}

    def test_empty_baseline(self):
        b = AssetBaseline()
        assert b.get_baseline("t1", "subdomain") == set()

    def test_detect_changes_new(self):
        b = AssetBaseline()
        b.set_baseline("t1", "subdomain", {"a.com"})
        changes = b.detect_changes("t1", "subdomain", {"a.com", "b.com"})
        assert changes["added"] == {"b.com"}
        assert changes["removed"] == set()

    def test_detect_changes_removed(self):
        b = AssetBaseline()
        b.set_baseline("t1", "subdomain", {"a.com", "b.com"})
        changes = b.detect_changes("t1", "subdomain", {"a.com"})
        assert changes["removed"] == {"b.com"}

    def test_detect_no_baseline(self):
        b = AssetBaseline()
        changes = b.detect_changes("t1", "subdomain", {"a.com"})
        assert changes["added"] == {"a.com"}

    def test_has_baseline(self):
        b = AssetBaseline()
        assert b.has_baseline("t1") is False
        b.set_baseline("t1", "subdomain", set())
        assert b.has_baseline("t1") is True


# ── PassiveMonitor ────────────────────────────────────────────────────


class TestPassiveMonitor:
    def _monitor(self) -> PassiveMonitor:
        m = PassiveMonitor()
        m.add_target(MonitorTarget(
            target_id="t1",
            target_value="example.com",
            check_interval_seconds=0,  # Always due
        ))
        return m

    def test_add_target(self):
        m = PassiveMonitor()
        m.add_target(MonitorTarget("t1", "example.com"))
        assert m.target_count == 1

    def test_remove_target(self):
        m = self._monitor()
        assert m.remove_target("t1") is True
        assert m.remove_target("t1") is False

    def test_due_targets(self):
        m = self._monitor()
        due = m.get_due_targets()
        assert len(due) == 1

    def test_check_new_assets(self):
        m = self._monitor()
        m.set_baseline("t1", "subdomain", {"a.com"})
        alerts = m.check_for_changes("t1", "subdomain", {"a.com", "b.com"})
        assert len(alerts) == 1
        assert "b.com" in alerts[0].description

    def test_check_removed_assets(self):
        m = self._monitor()
        m.set_baseline("t1", "subdomain", {"a.com", "b.com"})
        alerts = m.check_for_changes("t1", "subdomain", {"a.com"})
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.INFO

    def test_severity_mapping(self):
        m = self._monitor()
        m.set_baseline("t1", "open_port", set())
        alerts = m.check_for_changes("t1", "open_port", {"443"})
        assert alerts[0].severity == AlertSeverity.HIGH

    def test_acknowledge_alert(self):
        m = self._monitor()
        m.set_baseline("t1", "subdomain", set())
        alerts = m.check_for_changes("t1", "subdomain", {"new.com"})
        assert m.acknowledge_alert(alerts[0].alert_id) is True
        assert m.get_alerts(unacknowledged_only=True) == []

    def test_filter_by_severity(self):
        m = self._monitor()
        m.set_baseline("t1", "subdomain", set())
        m.check_for_changes("t1", "subdomain", {"new.com"})
        high = m.get_alerts(severity=AlertSeverity.HIGH)
        assert len(high) == 0

    def test_callback(self):
        m = self._monitor()
        received = []
        m.register_callback(lambda a: received.append(a))
        m.set_baseline("t1", "subdomain", set())
        m.check_for_changes("t1", "subdomain", {"new.com"})
        assert len(received) == 1

    def test_status(self):
        m = self._monitor()
        status = m.get_status()
        assert status["total_targets"] == 1
        assert status["active_targets"] == 1

    def test_nonexistent_target(self):
        m = PassiveMonitor()
        alerts = m.check_for_changes("none", "subdomain", {"x.com"})
        assert alerts == []

    def test_baseline_updates_after_check(self):
        m = self._monitor()
        m.set_baseline("t1", "subdomain", set())
        m.check_for_changes("t1", "subdomain", {"a.com"})
        # Second check with no changes
        alerts = m.check_for_changes("t1", "subdomain", {"a.com"})
        assert len(alerts) == 0


# ── Integration Tests ─────────────────────────────────────────────────


class TestIntegration:
    def test_privacy_lifecycle(self):
        """Full privacy-preserving statistics lifecycle."""
        tracker = PrivacyBudgetTracker(total_budget=5.0)
        pss = PrivateScanStatistics(epsilon=1.0, budget_tracker=tracker)

        pss.privatize_count("total_findings", 150)
        pss.privatize_count("unique_domains", 25)
        pss.privatize_mean("avg_risk_score", 72.5)

        report = pss.generate_report()
        assert report["stat_count"] == 3
        assert report["privacy_budget"]["spent"] == 3.0

    def test_aggregation_with_privacy(self):
        """Aggregate across orgs with privacy guarantees."""
        agg = SecureAggregator(min_contributors=2)
        for org in ("org1", "org2", "org3"):
            indicators = [
                SecureAggregator.hash_indicator(f"{org}-{i}")
                for i in range(5)
            ]
            agg.submit(AggregationContribution(
                org,
                hashed_indicators=indicators,
                counts={"scans": 10},
            ))

        assert agg.meets_threshold()
        summary = agg.aggregate_indicators()
        assert len(summary) > 0

    def test_monitoring_lifecycle(self):
        """Full monitoring lifecycle: add → baseline → detect → alert."""
        m = PassiveMonitor()
        m.add_target(MonitorTarget(
            "t1", "example.com", check_interval_seconds=0,
        ))
        m.set_baseline("t1", "subdomain", {"www.example.com"})

        alerts = m.check_for_changes(
            "t1", "subdomain",
            {"www.example.com", "mail.example.com"},
        )
        assert len(alerts) == 1
        assert "mail.example.com" in alerts[0].new_value

        # No new alerts on repeat
        alerts2 = m.check_for_changes(
            "t1", "subdomain",
            {"www.example.com", "mail.example.com"},
        )
        assert len(alerts2) == 0
