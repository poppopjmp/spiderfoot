"""Tests for spiderfoot.module_sandbox."""
from __future__ import annotations

import time
import threading
import pytest
from spiderfoot.module_sandbox import (
    SandboxState,
    ResourceLimits,
    SandboxResult,
    ResourceTracker,
    ModuleSandbox,
    SandboxManager,
)


# --- ResourceLimits ---

class TestResourceLimits:
    def test_defaults(self):
        lim = ResourceLimits()
        assert lim.max_execution_seconds == 300.0
        assert lim.max_events == 10000
        assert lim.max_errors == 100
        assert lim.max_http_requests == 1000

    def test_custom(self):
        lim = ResourceLimits(max_execution_seconds=60, max_events=500)
        assert lim.max_execution_seconds == 60
        assert lim.max_events == 500


# --- SandboxResult ---

class TestSandboxResult:
    def test_success(self):
        r = SandboxResult(module_name="m", state=SandboxState.COMPLETED, events_produced=5)
        assert r.success is True
        d = r.to_dict()
        assert d["success"] is True
        assert d["events_produced"] == 5

    def test_failure(self):
        r = SandboxResult(module_name="m", state=SandboxState.FAILED, exception="err")
        assert r.success is False
        assert r.to_dict()["exception"] == "err"

    def test_timeout(self):
        r = SandboxResult(module_name="m", state=SandboxState.TIMED_OUT)
        assert r.success is False
        assert r.to_dict()["state"] == "timed_out"


# --- ResourceTracker ---

class TestResourceTracker:
    def test_event_limit(self):
        t = ResourceTracker(ResourceLimits(max_events=3))
        t.start()
        assert t.record_event() is True
        assert t.record_event() is True
        assert t.record_event() is True
        assert t.record_event() is False

    def test_error_limit(self):
        t = ResourceTracker(ResourceLimits(max_errors=2))
        t.start()
        assert t.record_error() is True
        assert t.record_error() is True
        assert t.record_error() is False

    def test_http_limit(self):
        t = ResourceTracker(ResourceLimits(max_http_requests=1))
        t.start()
        assert t.record_http_request() is True
        assert t.record_http_request() is False

    def test_timeout_check(self):
        t = ResourceTracker(ResourceLimits(max_execution_seconds=0.01))
        t.start()
        time.sleep(0.05)
        assert t.check_timeout() is True

    def test_no_timeout(self):
        t = ResourceTracker(ResourceLimits(max_execution_seconds=60))
        t.start()
        assert t.check_timeout() is False

    def test_check_limits_ok(self):
        t = ResourceTracker(ResourceLimits())
        t.start()
        assert t.check_limits() is None

    def test_check_limits_event_exceeded(self):
        t = ResourceTracker(ResourceLimits(max_events=1))
        t.start()
        t.record_event()
        t.record_event()
        msg = t.check_limits()
        assert msg is not None
        assert "Event limit" in msg

    def test_get_usage(self):
        t = ResourceTracker(ResourceLimits())
        t.start()
        t.record_event()
        t.record_event()
        t.record_error()
        t.record_http_request()
        u = t.get_usage()
        assert u["events"] == 2
        assert u["errors"] == 1
        assert u["http_requests"] == 1
        assert u["elapsed_seconds"] >= 0

    def test_elapsed_before_start(self):
        t = ResourceTracker(ResourceLimits())
        assert t.elapsed == 0.0


# --- ModuleSandbox ---

class TestModuleSandbox:
    def test_simple_execution(self):
        sb = ModuleSandbox("test_mod")

        def func(tracker):
            tracker.record_event()
            return 1

        result = sb.execute(func)
        assert result.success is True
        assert result.events_produced == 1
        assert sb.state == SandboxState.COMPLETED

    def test_exception(self):
        sb = ModuleSandbox("test_mod")

        def func(tracker):
            raise ValueError("boom")

        result = sb.execute(func)
        assert result.success is False
        assert result.state == SandboxState.FAILED
        assert "ValueError" in result.exception

    def test_event_limit_violation(self):
        sb = ModuleSandbox("test_mod", ResourceLimits(max_events=2))

        def func(tracker):
            for _ in range(5):
                tracker.record_event()
            return 5

        result = sb.execute(func)
        assert result.success is False
        assert "Event limit" in result.exception

    def test_timeout_violation(self):
        sb = ModuleSandbox("test_mod", ResourceLimits(max_execution_seconds=0.01))

        def func(tracker):
            time.sleep(0.05)
            return 0

        result = sb.execute(func)
        assert result.state == SandboxState.TIMED_OUT

    def test_callback(self):
        sb = ModuleSandbox("test_mod")
        results_seen = []
        sb.on_complete(lambda r: results_seen.append(r))

        def func(tracker):
            return 2

        sb.execute(func)
        assert len(results_seen) == 1
        assert results_seen[0].events_produced == 2

    def test_callback_error_isolated(self):
        sb = ModuleSandbox("test_mod")
        sb.on_complete(lambda r: (_ for _ in ()).throw(RuntimeError("cb fail")))

        def func(tracker):
            return 0

        # Should not raise
        result = sb.execute(func)
        assert result.success is True

    def test_reset(self):
        sb = ModuleSandbox("test_mod")
        sb.execute(lambda t: 0)
        assert sb.state == SandboxState.COMPLETED
        sb.reset()
        assert sb.state == SandboxState.IDLE

    def test_to_dict(self):
        sb = ModuleSandbox("test_mod", ResourceLimits(max_events=500))
        d = sb.to_dict()
        assert d["module"] == "test_mod"
        assert d["limits"]["max_events"] == 500

    def test_execute_with_timeout_success(self):
        sb = ModuleSandbox("test_mod", ResourceLimits(max_execution_seconds=5))

        def func(tracker):
            return 3

        result = sb.execute_with_timeout(func)
        assert result.success is True
        assert result.events_produced == 3

    def test_execute_with_timeout_exceeded(self):
        sb = ModuleSandbox("test_mod", ResourceLimits(max_execution_seconds=0.1))

        def func(tracker):
            time.sleep(5)
            return 0

        result = sb.execute_with_timeout(func)
        assert result.state == SandboxState.TIMED_OUT

    def test_kwargs_passed(self):
        sb = ModuleSandbox("test_mod")
        captured = {}

        def func(tracker, target=None):
            captured["target"] = target
            return 0

        sb.execute(func, target="example.com")
        assert captured["target"] == "example.com"


# --- SandboxManager ---

class TestSandboxManager:
    def test_get_sandbox(self):
        mgr = SandboxManager()
        sb = mgr.get_sandbox("mod_a")
        assert isinstance(sb, ModuleSandbox)
        assert sb.module_name == "mod_a"

    def test_get_sandbox_cached(self):
        mgr = SandboxManager()
        sb1 = mgr.get_sandbox("mod_a")
        sb2 = mgr.get_sandbox("mod_a")
        assert sb1 is sb2

    def test_custom_limits(self):
        lim = ResourceLimits(max_events=42)
        mgr = SandboxManager()
        sb = mgr.get_sandbox("mod_a", limits=lim)
        assert sb.limits.max_events == 42

    def test_default_limits(self):
        default = ResourceLimits(max_execution_seconds=30)
        mgr = SandboxManager(default_limits=default)
        sb = mgr.get_sandbox("mod_a")
        assert sb.limits.max_execution_seconds == 30

    def test_remove_sandbox(self):
        mgr = SandboxManager()
        mgr.get_sandbox("mod_a")
        assert mgr.remove_sandbox("mod_a") is True
        assert mgr.remove_sandbox("mod_a") is False

    def test_sandbox_count(self):
        mgr = SandboxManager()
        mgr.get_sandbox("a")
        mgr.get_sandbox("b")
        assert mgr.sandbox_count == 2

    def test_module_names(self):
        mgr = SandboxManager()
        mgr.get_sandbox("b")
        mgr.get_sandbox("a")
        assert mgr.module_names == ["a", "b"]

    def test_record_and_get_results(self):
        mgr = SandboxManager()
        r = SandboxResult(module_name="m", state=SandboxState.COMPLETED)
        mgr.record_result(r)
        assert len(mgr.get_results()) == 1
        assert len(mgr.get_results("m")) == 1
        assert len(mgr.get_results("other")) == 0

    def test_failed_modules(self):
        mgr = SandboxManager()
        sb = mgr.get_sandbox("fail_mod")
        sb.execute(lambda t: (_ for _ in ()).throw(RuntimeError("x")))
        assert "fail_mod" in mgr.get_failed_modules()

    def test_summary(self):
        mgr = SandboxManager()
        sb = mgr.get_sandbox("m1")
        sb.execute(lambda t: 0)
        s = mgr.summary()
        assert s["total_sandboxes"] == 1
        assert "completed" in s["states"]

    def test_to_dict(self):
        mgr = SandboxManager()
        mgr.get_sandbox("m1")
        d = mgr.to_dict()
        assert "sandboxes" in d
        assert "summary" in d
