"""Scan state machine for SpiderFoot.

Provides a formal state machine for scan lifecycle management:
- Defined states: CREATED, QUEUED, STARTING, RUNNING, PAUSED,
  STOPPING, COMPLETED, FAILED, CANCELLED
- Valid transition enforcement
- State change hooks/callbacks
- Transition history with timestamps
- Thread-safe state management

Usage::

    from spiderfoot.scan_state import ScanStateMachine, ScanState

    sm = ScanStateMachine(scan_id="scan-001")
    sm.on_transition(lambda old, new, sid: print(f"{old} -> {new}"))

    sm.transition(ScanState.QUEUED)
    sm.transition(ScanState.STARTING)
    sm.transition(ScanState.RUNNING)
    sm.transition(ScanState.COMPLETED)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.scan_state")


class ScanState(Enum):
    """Possible scan states."""
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        """Whether this is a terminal (final) state."""
        return self in (ScanState.COMPLETED, ScanState.FAILED,
                        ScanState.CANCELLED)

    @property
    def is_active(self) -> bool:
        """Whether the scan is actively running or starting."""
        return self in (ScanState.STARTING, ScanState.RUNNING)


# Valid state transitions: from_state -> set of allowed to_states
VALID_TRANSITIONS: dict[ScanState, set[ScanState]] = {
    ScanState.CREATED: {ScanState.QUEUED, ScanState.CANCELLED},
    ScanState.QUEUED: {ScanState.STARTING, ScanState.CANCELLED},
    ScanState.STARTING: {ScanState.RUNNING, ScanState.FAILED,
                         ScanState.CANCELLED},
    ScanState.RUNNING: {ScanState.PAUSED, ScanState.STOPPING,
                        ScanState.COMPLETED, ScanState.FAILED},
    ScanState.PAUSED: {ScanState.RUNNING, ScanState.STOPPING,
                       ScanState.CANCELLED},
    ScanState.STOPPING: {ScanState.COMPLETED, ScanState.FAILED,
                         ScanState.CANCELLED},
    ScanState.COMPLETED: set(),  # terminal
    ScanState.FAILED: set(),     # terminal
    ScanState.CANCELLED: set(),  # terminal
}


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: ScanState
    to_state: ScanState
    timestamp: float
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_state.value,
            "to": self.to_state.value,
            "timestamp": self.timestamp,
            "reason": self.reason,
        }


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, from_state: ScanState, to_state: ScanState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        allowed = VALID_TRANSITIONS.get(from_state, set())
        super().__init__(
            f"Invalid transition: {from_state.value} -> {to_state.value}. "
            f"Allowed: {[s.value for s in allowed]}"
        )


# Callback type: (old_state, new_state, scan_id) -> None
TransitionCallback = Callable[[ScanState, ScanState, str], None]


class ScanStateMachine:
    """Thread-safe scan state machine with transition validation.

    Enforces valid state transitions and maintains history.
    """

    def __init__(self, scan_id: str,
                 initial_state: ScanState = ScanState.CREATED) -> None:
        self.scan_id = scan_id
        self._state = initial_state
        self._lock = threading.Lock()
        self._history: list[StateTransition] = []
        self._callbacks: list[TransitionCallback] = []
        self._created_at = time.time()

    @property
    def state(self) -> ScanState:
        """Current state."""
        with self._lock:
            return self._state

    @property
    def is_terminal(self) -> bool:
        """Whether the scan is in a terminal state."""
        return self.state.is_terminal

    @property
    def is_active(self) -> bool:
        """Whether the scan is actively running."""
        return self.state.is_active

    @property
    def history(self) -> list[StateTransition]:
        """Get transition history."""
        with self._lock:
            return list(self._history)

    @property
    def duration(self) -> float:
        """Total elapsed time since creation."""
        return time.time() - self._created_at

    def can_transition(self, to_state: ScanState) -> bool:
        """Check if a transition to the given state is valid."""
        with self._lock:
            allowed = VALID_TRANSITIONS.get(self._state, set())
            return to_state in allowed

    def transition(self, to_state: ScanState,
                   reason: str = "") -> ScanState:
        """Transition to a new state.

        Args:
            to_state: Target state
            reason: Optional reason for the transition

        Returns:
            The new state

        Raises:
            InvalidTransitionError: If the transition is not valid
        """
        with self._lock:
            old_state = self._state
            allowed = VALID_TRANSITIONS.get(old_state, set())

            if to_state not in allowed:
                raise InvalidTransitionError(old_state, to_state)

            self._state = to_state
            transition = StateTransition(
                from_state=old_state,
                to_state=to_state,
                timestamp=time.time(),
                reason=reason,
            )
            self._history.append(transition)

        # Fire callbacks outside lock
        log.info("Scan %s: %s -> %s%s",
                 self.scan_id, old_state.value, to_state.value,
                 f" ({reason})" if reason else "")

        for cb in self._callbacks:
            try:
                cb(old_state, to_state, self.scan_id)
            except Exception as e:
                log.error("Callback error during transition: %s", e)

        return to_state

    def on_transition(self, callback: TransitionCallback) -> None:
        """Register a callback for state transitions.

        Args:
            callback: Function(old_state, new_state, scan_id)
        """
        self._callbacks.append(callback)

    def get_time_in_state(self, state: ScanState) -> float:
        """Calculate total time spent in a given state (seconds)."""
        with self._lock:
            total = 0.0
            entries = [(h.to_state, h.timestamp) for h in self._history]
            # Add current state
            now = time.time()

            for i, (st, ts) in enumerate(entries):
                if st == state:
                    # Time until next transition or now
                    if i + 1 < len(entries):
                        total += entries[i + 1][1] - ts
                    elif self._state == state:
                        total += now - ts

            return total

    def to_dict(self) -> dict[str, Any]:
        """Export state machine as dict."""
        with self._lock:
            return {
                "scan_id": self.scan_id,
                "state": self._state.value,
                "is_terminal": self._state.is_terminal,
                "is_active": self._state.is_active,
                "duration_s": round(self.duration, 3),
                "transitions": len(self._history),
                "history": [h.to_dict() for h in self._history],
            }
