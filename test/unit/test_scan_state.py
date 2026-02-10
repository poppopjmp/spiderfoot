"""Tests for spiderfoot.scan_state."""
from __future__ import annotations

import time
import threading
import unittest

from spiderfoot.scan_state import (
    InvalidTransitionError,
    ScanState,
    ScanStateMachine,
    StateTransition,
    VALID_TRANSITIONS,
)


class TestScanState(unittest.TestCase):
    """Tests for ScanState enum."""

    def test_terminal_states(self):
        self.assertTrue(ScanState.COMPLETED.is_terminal)
        self.assertTrue(ScanState.FAILED.is_terminal)
        self.assertTrue(ScanState.CANCELLED.is_terminal)
        self.assertFalse(ScanState.RUNNING.is_terminal)

    def test_active_states(self):
        self.assertTrue(ScanState.RUNNING.is_active)
        self.assertTrue(ScanState.STARTING.is_active)
        self.assertFalse(ScanState.PAUSED.is_active)
        self.assertFalse(ScanState.COMPLETED.is_active)

    def test_values(self):
        self.assertEqual(ScanState.CREATED.value, "CREATED")
        self.assertEqual(ScanState.RUNNING.value, "RUNNING")


class TestStateTransition(unittest.TestCase):
    """Tests for StateTransition."""

    def test_to_dict(self):
        t = StateTransition(
            from_state=ScanState.CREATED,
            to_state=ScanState.QUEUED,
            timestamp=1234567890.0,
            reason="User started scan",
        )
        d = t.to_dict()
        self.assertEqual(d["from"], "CREATED")
        self.assertEqual(d["to"], "QUEUED")
        self.assertEqual(d["reason"], "User started scan")


class TestValidTransitions(unittest.TestCase):
    """Tests for transition table."""

    def test_terminal_states_have_no_transitions(self):
        for state in (ScanState.COMPLETED, ScanState.FAILED,
                      ScanState.CANCELLED):
            self.assertEqual(VALID_TRANSITIONS[state], set())

    def test_created_can_queue_or_cancel(self):
        allowed = VALID_TRANSITIONS[ScanState.CREATED]
        self.assertIn(ScanState.QUEUED, allowed)
        self.assertIn(ScanState.CANCELLED, allowed)

    def test_running_can_pause_stop_complete_fail(self):
        allowed = VALID_TRANSITIONS[ScanState.RUNNING]
        self.assertIn(ScanState.PAUSED, allowed)
        self.assertIn(ScanState.STOPPING, allowed)
        self.assertIn(ScanState.COMPLETED, allowed)
        self.assertIn(ScanState.FAILED, allowed)

    def test_paused_can_resume_stop_cancel(self):
        allowed = VALID_TRANSITIONS[ScanState.PAUSED]
        self.assertIn(ScanState.RUNNING, allowed)
        self.assertIn(ScanState.STOPPING, allowed)
        self.assertIn(ScanState.CANCELLED, allowed)


class TestScanStateMachine(unittest.TestCase):
    """Tests for ScanStateMachine."""

    def setUp(self):
        self.sm = ScanStateMachine(scan_id="test-001")

    def test_initial_state(self):
        self.assertEqual(self.sm.state, ScanState.CREATED)
        self.assertFalse(self.sm.is_terminal)
        self.assertFalse(self.sm.is_active)

    def test_valid_transition(self):
        result = self.sm.transition(ScanState.QUEUED)
        self.assertEqual(result, ScanState.QUEUED)
        self.assertEqual(self.sm.state, ScanState.QUEUED)

    def test_invalid_transition(self):
        with self.assertRaises(InvalidTransitionError) as ctx:
            self.sm.transition(ScanState.RUNNING)
        self.assertIn("CREATED", str(ctx.exception))
        self.assertIn("RUNNING", str(ctx.exception))

    def test_full_lifecycle(self):
        self.sm.transition(ScanState.QUEUED)
        self.sm.transition(ScanState.STARTING)
        self.sm.transition(ScanState.RUNNING)
        self.assertTrue(self.sm.is_active)
        self.sm.transition(ScanState.COMPLETED, reason="All modules done")
        self.assertTrue(self.sm.is_terminal)

    def test_pause_resume(self):
        self.sm.transition(ScanState.QUEUED)
        self.sm.transition(ScanState.STARTING)
        self.sm.transition(ScanState.RUNNING)
        self.sm.transition(ScanState.PAUSED, reason="User paused")
        self.assertFalse(self.sm.is_active)
        self.sm.transition(ScanState.RUNNING, reason="Resumed")
        self.assertTrue(self.sm.is_active)

    def test_cancel_from_created(self):
        self.sm.transition(ScanState.CANCELLED)
        self.assertTrue(self.sm.is_terminal)

    def test_fail_from_running(self):
        self.sm.transition(ScanState.QUEUED)
        self.sm.transition(ScanState.STARTING)
        self.sm.transition(ScanState.RUNNING)
        self.sm.transition(ScanState.FAILED, reason="Module crashed")
        self.assertTrue(self.sm.is_terminal)

    def test_no_transition_from_terminal(self):
        self.sm.transition(ScanState.CANCELLED)
        with self.assertRaises(InvalidTransitionError):
            self.sm.transition(ScanState.RUNNING)

    def test_can_transition(self):
        self.assertTrue(self.sm.can_transition(ScanState.QUEUED))
        self.assertFalse(self.sm.can_transition(ScanState.COMPLETED))

    def test_history(self):
        self.sm.transition(ScanState.QUEUED)
        self.sm.transition(ScanState.STARTING)
        history = self.sm.history
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].from_state, ScanState.CREATED)
        self.assertEqual(history[0].to_state, ScanState.QUEUED)

    def test_callback(self):
        transitions = []
        self.sm.on_transition(
            lambda old, new, sid: transitions.append((old, new, sid))
        )
        self.sm.transition(ScanState.QUEUED)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0],
                        (ScanState.CREATED, ScanState.QUEUED, "test-001"))

    def test_callback_error_does_not_break(self):
        def bad_cb(old, new, sid):
            raise RuntimeError("callback error")

        self.sm.on_transition(bad_cb)
        # Should not raise
        self.sm.transition(ScanState.QUEUED)
        self.assertEqual(self.sm.state, ScanState.QUEUED)

    def test_duration(self):
        self.assertGreater(self.sm.duration, 0)

    def test_to_dict(self):
        self.sm.transition(ScanState.QUEUED)
        d = self.sm.to_dict()
        self.assertEqual(d["scan_id"], "test-001")
        self.assertEqual(d["state"], "QUEUED")
        self.assertFalse(d["is_terminal"])
        self.assertEqual(d["transitions"], 1)
        self.assertEqual(len(d["history"]), 1)

    def test_thread_safety(self):
        """Concurrent transitions should not corrupt state."""
        errors = []
        sm = ScanStateMachine("thread-test")
        sm.transition(ScanState.QUEUED)
        sm.transition(ScanState.STARTING)
        sm.transition(ScanState.RUNNING)

        def pause_resume(n):
            try:
                for _ in range(n):
                    try:
                        sm.transition(ScanState.PAUSED)
                        sm.transition(ScanState.RUNNING)
                    except InvalidTransitionError:
                        pass  # Expected due to race
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=pause_resume, args=(10,))
                   for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        # State should be valid
        self.assertIn(sm.state,
                     (ScanState.RUNNING, ScanState.PAUSED))

    def test_transition_with_reason(self):
        self.sm.transition(ScanState.QUEUED, reason="Scheduled")
        history = self.sm.history
        self.assertEqual(history[0].reason, "Scheduled")

    def test_custom_initial_state(self):
        sm = ScanStateMachine("test", initial_state=ScanState.QUEUED)
        self.assertEqual(sm.state, ScanState.QUEUED)

    def test_stopping_workflow(self):
        self.sm.transition(ScanState.QUEUED)
        self.sm.transition(ScanState.STARTING)
        self.sm.transition(ScanState.RUNNING)
        self.sm.transition(ScanState.STOPPING, reason="User abort")
        self.sm.transition(ScanState.COMPLETED, reason="Graceful stop")
        self.assertTrue(self.sm.is_terminal)


class TestInvalidTransitionError(unittest.TestCase):
    """Tests for InvalidTransitionError."""

    def test_message(self):
        err = InvalidTransitionError(ScanState.CREATED, ScanState.RUNNING)
        self.assertIn("CREATED", str(err))
        self.assertIn("RUNNING", str(err))
        self.assertIn("Allowed", str(err))

    def test_attributes(self):
        err = InvalidTransitionError(ScanState.CREATED, ScanState.RUNNING)
        self.assertEqual(err.from_state, ScanState.CREATED)
        self.assertEqual(err.to_state, ScanState.RUNNING)


if __name__ == "__main__":
    unittest.main()
