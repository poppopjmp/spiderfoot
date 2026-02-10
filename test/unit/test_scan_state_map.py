"""Tests for scan_state_map — unified state mapping."""
from __future__ import annotations

import pytest

from spiderfoot.scan_state import ScanState
from spiderfoot.scan_state_map import (
    db_status_to_state,
    state_to_db_status,
    proto_to_state,
    state_to_proto,
    db_status_to_proto,
    proto_to_db_status,
)


class TestDbStatusToState:
    """DB status string -> ScanState."""

    def test_finished_maps_to_completed(self):
        assert db_status_to_state("FINISHED") == ScanState.COMPLETED

    def test_aborted_maps_to_cancelled(self):
        assert db_status_to_state("ABORTED") == ScanState.CANCELLED

    def test_error_failed_maps_to_failed(self):
        assert db_status_to_state("ERROR-FAILED") == ScanState.FAILED

    def test_abort_requested_maps_to_stopping(self):
        assert db_status_to_state("ABORT-REQUESTED") == ScanState.STOPPING

    def test_running_identity(self):
        assert db_status_to_state("RUNNING") == ScanState.RUNNING

    def test_started_alias(self):
        assert db_status_to_state("STARTED") == ScanState.RUNNING

    def test_unknown_defaults_to_created(self):
        assert db_status_to_state("NONSENSE") == ScanState.CREATED

    def test_case_insensitive(self):
        assert db_status_to_state("finished") == ScanState.COMPLETED


class TestStateToDbStatus:
    """ScanState -> DB status string."""

    def test_completed_to_finished(self):
        assert state_to_db_status(ScanState.COMPLETED) == "FINISHED"

    def test_cancelled_to_aborted(self):
        assert state_to_db_status(ScanState.CANCELLED) == "ABORTED"

    def test_failed_to_error_failed(self):
        assert state_to_db_status(ScanState.FAILED) == "ERROR-FAILED"

    def test_stopping_to_abort_requested(self):
        assert state_to_db_status(ScanState.STOPPING) == "ABORT-REQUESTED"

    def test_roundtrip_all_states(self):
        for state in ScanState:
            db_str = state_to_db_status(state)
            back = db_status_to_state(db_str)
            assert back == state, f"Roundtrip failed: {state} -> {db_str} -> {back}"


class TestProtoMapping:
    """Proto integer <-> ScanState."""

    def test_proto_running(self):
        assert proto_to_state(3) == ScanState.RUNNING

    def test_proto_finished(self):
        assert proto_to_state(7) == ScanState.COMPLETED

    def test_proto_error(self):
        assert proto_to_state(8) == ScanState.FAILED

    def test_state_to_proto_running(self):
        assert state_to_proto(ScanState.RUNNING) == 3

    def test_state_to_proto_completed(self):
        assert state_to_proto(ScanState.COMPLETED) == 7

    def test_unknown_proto_defaults(self):
        assert proto_to_state(999) == ScanState.CREATED


class TestCrossMapping:
    """DB -> Proto and Proto -> DB convenience functions."""

    def test_db_to_proto_finished(self):
        assert db_status_to_proto("FINISHED") == 7

    def test_proto_to_db_running(self):
        assert proto_to_db_status(3) == "RUNNING"

    def test_proto_to_db_finished(self):
        assert proto_to_db_status(7) == "FINISHED"
