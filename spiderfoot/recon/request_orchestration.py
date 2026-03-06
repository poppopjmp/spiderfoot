# -------------------------------------------------------------------------------
# Name:         request_orchestration
# Purpose:      Request-order randomization & timing profile enforcement
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Request Orchestration — SOTA S-004 (Cycles 61–80).

Advanced request ordering and timing control to defeat traffic-analysis
based detection systems. While S-001/S-002 handled per-request jitter
and domain throttling, S-004 provides scan-level orchestration:

- :class:`RequestRecord` — Immutable record of a pending or completed request
  with priority, domain, timing, and dependency metadata.
- :class:`RequestPriorityQueue` — Thread-safe priority queue with domain-aware
  scheduling that prevents request bursts to any single domain.
- :class:`TimingProfile` — Configurable human-realistic timing patterns
  (browsing, research, crawler, burst, paranoid) with per-phase timing
  parameters matching real user behavior analytics.
- :class:`RequestOrderRandomizer` — Shuffles request order with constraints
  (domain spread, priority preservation, dependency respect) to prevent
  pattern detection in request sequences.
- :class:`SessionSimulator` — Simulates realistic browsing sessions with
  page-views, think-time, tab-switching, and idle periods.
- :class:`RequestOrchestrator` — Unified orchestrator combining all components
  to schedule, order, and time requests across a full scan lifecycle.

Usage::

    from spiderfoot.recon.request_orchestration import (
        RequestOrchestrator,
        TimingProfile,
    )

    orch = RequestOrchestrator(
        timing=TimingProfile.RESEARCH,
        max_concurrent=5,
    )
    orch.enqueue("https://example.com/page1", priority=1)
    orch.enqueue("https://example.com/page2", priority=2)

    # Get next request with appropriate delay
    req, delay = orch.next_request()
    time.sleep(delay)
    # ... make request ...
    orch.complete(req.request_id, status_code=200)
"""

from __future__ import annotations

import hashlib
import heapq
import logging
import random
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger("spiderfoot.recon.request_orchestration")


# ============================================================================
# Request Record (Cycle 61)
# ============================================================================


class RequestStatus(Enum):
    """Status of a request in the orchestration pipeline."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_FLIGHT = "in_flight"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(order=True)
class RequestRecord:
    """Immutable record of a request in the orchestration queue.

    Attributes:
        priority: Lower number = higher priority (0 = critical).
        url: Target URL.
        domain: Extracted domain from URL.
        request_id: Unique identifier.
        created_at: Timestamp when request was created.
        scheduled_at: Timestamp when request was scheduled.
        completed_at: Timestamp when request completed.
        status: Current status.
        depends_on: Set of request_ids this depends on.
        metadata: Arbitrary metadata dict.
    """
    priority: int
    url: str = field(compare=False)
    domain: str = field(compare=False, default="")
    request_id: str = field(compare=False, default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(compare=False, default_factory=time.time)
    scheduled_at: float = field(compare=False, default=0.0)
    completed_at: float = field(compare=False, default=0.0)
    status: RequestStatus = field(compare=False, default=RequestStatus.PENDING)
    depends_on: set[str] = field(compare=False, default_factory=set)
    metadata: dict[str, Any] = field(compare=False, default_factory=dict)
    status_code: int = field(compare=False, default=0)

    def __post_init__(self) -> None:
        if not self.domain and self.url:
            try:
                parsed = urlparse(self.url)
                self.domain = parsed.hostname or ""
            except Exception:
                self.domain = ""


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""


# ============================================================================
# Timing Profiles (Cycles 62–65)
# ============================================================================


class TimingProfileType(Enum):
    """Pre-defined timing profile types."""
    FAST = "fast"
    BROWSING = "browsing"
    RESEARCH = "research"
    CAUTIOUS = "cautious"
    PARANOID = "paranoid"
    CUSTOM = "custom"


@dataclass
class TimingProfile:
    """Configurable timing profile for request scheduling.

    Models realistic user behavior timing patterns to evade
    traffic-analysis based detection. Each profile defines ranges
    for different timing parameters.

    Attributes:
        name: Profile type identifier.
        min_delay: Minimum inter-request delay (seconds).
        max_delay: Maximum inter-request delay (seconds).
        mean_delay: Mean inter-request delay for normal distribution.
        domain_min_interval: Minimum interval between requests to same domain.
        think_time_range: Range for human "think time" pauses (min, max).
        page_load_time: Simulated page load time range.
        session_duration: Max session duration before a long pause.
        session_break_range: Range for breaks between sessions.
        burst_probability: Probability of a short burst of rapid requests.
        burst_size: Number of requests in a burst.
        idle_probability: Probability of an idle period.
        idle_duration_range: Duration range for idle periods.
    """
    name: TimingProfileType = TimingProfileType.RESEARCH
    min_delay: float = 1.0
    max_delay: float = 5.0
    mean_delay: float = 2.5
    domain_min_interval: float = 3.0
    think_time_range: tuple[float, float] = (0.5, 3.0)
    page_load_time: tuple[float, float] = (0.3, 1.5)
    session_duration: float = 300.0
    session_break_range: tuple[float, float] = (30.0, 120.0)
    burst_probability: float = 0.05
    burst_size: int = 3
    idle_probability: float = 0.1
    idle_duration_range: tuple[float, float] = (5.0, 30.0)

    def compute_delay(self, *, same_domain: bool = False) -> float:
        """Compute a delay before the next request.

        Uses a log-normal distribution to model realistic human timing.

        Args:
            same_domain: If True, enforce domain minimum interval.

        Returns:
            Delay in seconds.
        """
        # Check for burst mode
        if random.random() < self.burst_probability:
            delay = max(self.min_delay * 0.3, random.uniform(0.1, 0.5))
            if same_domain:
                delay = max(delay, self.domain_min_interval)
            return delay

        # Check for idle period
        if random.random() < self.idle_probability:
            delay = random.uniform(*self.idle_duration_range)
            if same_domain:
                delay = max(delay, self.domain_min_interval)
            return delay

        # Normal delay with log-normal distribution
        import math
        mu = math.log(self.mean_delay)
        sigma = 0.5
        delay = random.lognormvariate(mu, sigma)
        delay = max(self.min_delay, min(self.max_delay, delay))

        # Apply domain minimum interval
        if same_domain:
            delay = max(delay, self.domain_min_interval)

        return delay

    def compute_think_time(self) -> float:
        """Compute human think-time pause."""
        return random.uniform(*self.think_time_range)

    def compute_session_break(self) -> float:
        """Compute a session break duration."""
        return random.uniform(*self.session_break_range)

    def should_take_break(self, session_elapsed: float) -> bool:
        """Check if a session break should be taken."""
        if session_elapsed >= self.session_duration:
            return True
        # Small random chance of early break
        if session_elapsed > self.session_duration * 0.7:
            return random.random() < 0.1
        return False


# Pre-built timing profiles
TIMING_PROFILES: dict[TimingProfileType, TimingProfile] = {
    TimingProfileType.FAST: TimingProfile(
        name=TimingProfileType.FAST,
        min_delay=0.1,
        max_delay=1.0,
        mean_delay=0.3,
        domain_min_interval=0.5,
        think_time_range=(0.1, 0.5),
        page_load_time=(0.1, 0.5),
        session_duration=600.0,
        session_break_range=(5.0, 15.0),
        burst_probability=0.2,
        burst_size=5,
        idle_probability=0.02,
        idle_duration_range=(1.0, 5.0),
    ),
    TimingProfileType.BROWSING: TimingProfile(
        name=TimingProfileType.BROWSING,
        min_delay=0.5,
        max_delay=4.0,
        mean_delay=1.5,
        domain_min_interval=2.0,
        think_time_range=(1.0, 5.0),
        page_load_time=(0.5, 2.0),
        session_duration=300.0,
        session_break_range=(30.0, 120.0),
        burst_probability=0.1,
        burst_size=3,
        idle_probability=0.1,
        idle_duration_range=(5.0, 20.0),
    ),
    TimingProfileType.RESEARCH: TimingProfile(
        name=TimingProfileType.RESEARCH,
        min_delay=1.0,
        max_delay=5.0,
        mean_delay=2.5,
        domain_min_interval=3.0,
        think_time_range=(2.0, 8.0),
        page_load_time=(0.5, 2.0),
        session_duration=300.0,
        session_break_range=(30.0, 120.0),
        burst_probability=0.05,
        burst_size=3,
        idle_probability=0.1,
        idle_duration_range=(5.0, 30.0),
    ),
    TimingProfileType.CAUTIOUS: TimingProfile(
        name=TimingProfileType.CAUTIOUS,
        min_delay=3.0,
        max_delay=15.0,
        mean_delay=7.0,
        domain_min_interval=10.0,
        think_time_range=(3.0, 15.0),
        page_load_time=(1.0, 3.0),
        session_duration=180.0,
        session_break_range=(60.0, 300.0),
        burst_probability=0.01,
        burst_size=2,
        idle_probability=0.15,
        idle_duration_range=(10.0, 60.0),
    ),
    TimingProfileType.PARANOID: TimingProfile(
        name=TimingProfileType.PARANOID,
        min_delay=10.0,
        max_delay=60.0,
        mean_delay=25.0,
        domain_min_interval=30.0,
        think_time_range=(10.0, 45.0),
        page_load_time=(2.0, 5.0),
        session_duration=120.0,
        session_break_range=(120.0, 600.0),
        burst_probability=0.0,
        burst_size=1,
        idle_probability=0.2,
        idle_duration_range=(30.0, 120.0),
    ),
}


def get_timing_profile(name: TimingProfileType | str) -> TimingProfile:
    """Get a pre-built timing profile by name."""
    if isinstance(name, str):
        name = TimingProfileType(name)
    return TIMING_PROFILES.get(name, TIMING_PROFILES[TimingProfileType.RESEARCH])


# ============================================================================
# Request Priority Queue (Cycles 66–68)
# ============================================================================


class RequestPriorityQueue:
    """Thread-safe priority queue with domain-aware scheduling.

    Prevents request bursts to any single domain by tracking
    per-domain last-request times and enforcing minimum intervals.

    Features:
    - Priority-based ordering (lower number = higher priority)
    - Domain-aware dequeue (skips domains on cooldown)
    - Dependency tracking (won't dequeue until deps complete)
    - Queue statistics and monitoring
    """

    def __init__(
        self,
        domain_min_interval: float = 3.0,
        max_size: int = 10000,
    ) -> None:
        self._heap: list[RequestRecord] = []
        self._domain_last_request: dict[str, float] = {}
        self._completed_ids: set[str] = set()
        self._pending_count = 0
        self._domain_min_interval = domain_min_interval
        self._max_size = max_size
        self._lock = threading.Lock()

    def enqueue(self, record: RequestRecord) -> bool:
        """Add a request to the queue.

        Returns:
            True if enqueued, False if queue is full.
        """
        with self._lock:
            if self._pending_count >= self._max_size:
                return False
            heapq.heappush(self._heap, record)
            self._pending_count += 1
            return True

    def dequeue(self) -> RequestRecord | None:
        """Get the next request respecting domain cooldowns and deps.

        Returns:
            Next RequestRecord, or None if nothing is ready.
        """
        with self._lock:
            now = time.time()
            skipped: list[RequestRecord] = []
            result: RequestRecord | None = None

            while self._heap:
                record = heapq.heappop(self._heap)

                # Check dependencies
                if record.depends_on and not record.depends_on.issubset(self._completed_ids):
                    skipped.append(record)
                    continue

                # Check domain cooldown
                last_time = self._domain_last_request.get(record.domain, 0.0)
                if now - last_time < self._domain_min_interval:
                    skipped.append(record)
                    continue

                # This record is ready
                record.status = RequestStatus.SCHEDULED
                record.scheduled_at = now
                self._domain_last_request[record.domain] = now
                self._pending_count -= 1
                result = record
                break

            # Put skipped items back
            for s in skipped:
                heapq.heappush(self._heap, s)

            return result

    def mark_completed(self, request_id: str) -> None:
        """Mark a request as completed (for dependency tracking)."""
        with self._lock:
            self._completed_ids.add(request_id)

    def peek_next_domain_delay(self) -> float:
        """Return the minimum time until any domain is available.

        Returns 0 if something is immediately available.
        """
        with self._lock:
            if not self._heap:
                return 0.0
            now = time.time()
            min_delay = float("inf")
            for record in self._heap:
                last_time = self._domain_last_request.get(record.domain, 0.0)
                remaining = self._domain_min_interval - (now - last_time)
                if remaining <= 0:
                    return 0.0
                min_delay = min(min_delay, remaining)
            return min_delay if min_delay != float("inf") else 0.0

    @property
    def size(self) -> int:
        with self._lock:
            return self._pending_count

    @property
    def is_empty(self) -> bool:
        with self._lock:
            return self._pending_count == 0

    @property
    def domain_count(self) -> int:
        """Number of unique domains in the queue."""
        with self._lock:
            domains = {r.domain for r in self._heap}
            return len(domains)

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            domain_counts: dict[str, int] = {}
            for r in self._heap:
                domain_counts[r.domain] = domain_counts.get(r.domain, 0) + 1
            return {
                "pending": self._pending_count,
                "completed_deps": len(self._completed_ids),
                "domains_in_queue": len(domain_counts),
                "domain_distribution": domain_counts,
                "heap_size": len(self._heap),
            }

    def clear(self) -> None:
        with self._lock:
            self._heap.clear()
            self._completed_ids.clear()
            self._domain_last_request.clear()
            self._pending_count = 0


# ============================================================================
# Request Order Randomizer (Cycles 69–72)
# ============================================================================


class RandomizationStrategy(Enum):
    """How to randomize request order."""
    SHUFFLE = "shuffle"           # Pure random shuffle
    DOMAIN_SPREAD = "domain_spread"  # Maximize domain diversity
    PRIORITY_AWARE = "priority_aware"  # Shuffle within priority bands
    INTERLEAVED = "interleaved"    # Alternate between domains


class RequestOrderRandomizer:
    """Randomize request order with configurable constraints.

    Prevents sequential pattern detection by shuffling request
    order while respecting priority and domain constraints.
    """

    def __init__(
        self,
        strategy: RandomizationStrategy = RandomizationStrategy.DOMAIN_SPREAD,
        priority_band_size: int = 5,
    ) -> None:
        self._strategy = strategy
        self._priority_band_size = priority_band_size

    @property
    def strategy(self) -> RandomizationStrategy:
        return self._strategy

    def randomize(self, requests: list[RequestRecord]) -> list[RequestRecord]:
        """Randomize request order.

        Args:
            requests: List of RequestRecords to reorder.

        Returns:
            New list in randomized order.
        """
        if not requests or len(requests) <= 1:
            return list(requests)

        if self._strategy == RandomizationStrategy.SHUFFLE:
            return self._shuffle(requests)
        elif self._strategy == RandomizationStrategy.DOMAIN_SPREAD:
            return self._domain_spread(requests)
        elif self._strategy == RandomizationStrategy.PRIORITY_AWARE:
            return self._priority_aware(requests)
        elif self._strategy == RandomizationStrategy.INTERLEAVED:
            return self._interleaved(requests)
        return list(requests)

    def _shuffle(self, requests: list[RequestRecord]) -> list[RequestRecord]:
        """Pure random shuffle."""
        result = list(requests)
        random.shuffle(result)
        return result

    def _domain_spread(self, requests: list[RequestRecord]) -> list[RequestRecord]:
        """Maximize domain diversity in request order.

        Ensures requests to the same domain are spread as far apart
        as possible in the sequence.
        """
        # Group by domain
        domain_queues: dict[str, deque[RequestRecord]] = defaultdict(deque)
        for r in requests:
            domain_queues[r.domain].append(r)

        # Shuffle within each domain
        for dq in domain_queues.values():
            items = list(dq)
            random.shuffle(items)
            dq.clear()
            dq.extend(items)

        # Interleave domains in round-robin fashion
        result: list[RequestRecord] = []
        domains = list(domain_queues.keys())
        random.shuffle(domains)

        while any(domain_queues[d] for d in domains):
            for d in domains:
                if domain_queues[d]:
                    result.append(domain_queues[d].popleft())

        return result

    def _priority_aware(self, requests: list[RequestRecord]) -> list[RequestRecord]:
        """Shuffle within priority bands.

        Groups requests by priority bands and shuffles within each
        band, maintaining the overall priority ordering.
        """
        # Sort by priority
        sorted_reqs = sorted(requests, key=lambda r: r.priority)

        # Group into bands
        bands: list[list[RequestRecord]] = []
        for i in range(0, len(sorted_reqs), self._priority_band_size):
            band = sorted_reqs[i:i + self._priority_band_size]
            random.shuffle(band)
            bands.append(band)

        # Flatten
        return [r for band in bands for r in band]

    def _interleaved(self, requests: list[RequestRecord]) -> list[RequestRecord]:
        """Alternate between domains.

        Strictly alternates between different domains to maximize
        the minimum gap between requests to the same domain.
        """
        domain_queues: dict[str, deque[RequestRecord]] = defaultdict(deque)
        for r in requests:
            domain_queues[r.domain].append(r)

        result: list[RequestRecord] = []
        domains = list(domain_queues.keys())

        while domains:
            random.shuffle(domains)
            exhausted = []
            for d in domains:
                if domain_queues[d]:
                    result.append(domain_queues[d].popleft())
                else:
                    exhausted.append(d)
            for d in exhausted:
                domains.remove(d)

        return result


# ============================================================================
# Session Simulator (Cycles 73–75)
# ============================================================================


class SessionPhase(Enum):
    """Phase within a browsing session."""
    ACTIVE = "active"
    THINKING = "thinking"
    IDLE = "idle"
    BREAK = "break"


@dataclass
class SessionState:
    """State of the simulated browsing session.

    Tracks where we are in the current session lifecycle
    to generate appropriate timing signals.
    """
    phase: SessionPhase = SessionPhase.ACTIVE
    session_start: float = field(default_factory=time.time)
    phase_start: float = field(default_factory=time.time)
    requests_in_session: int = 0
    requests_in_phase: int = 0
    total_requests: int = 0
    total_sessions: int = 1
    burst_remaining: int = 0

    @property
    def session_elapsed(self) -> float:
        return time.time() - self.session_start

    @property
    def phase_elapsed(self) -> float:
        return time.time() - self.phase_start


class SessionSimulator:
    """Simulate realistic browsing sessions.

    Models human browsing behavior with:
    - Active browsing phases (clicking links, reading pages)
    - Thinking pauses (reading content before next click)
    - Idle periods (alt-tabbing, checking phone)
    - Session breaks (lunch, meetings, etc.)

    The simulator produces timing signals that should be used
    as delays between requests.
    """

    def __init__(self, timing: TimingProfile | None = None) -> None:
        self._timing = timing or TIMING_PROFILES[TimingProfileType.RESEARCH]
        self._state = SessionState()
        self._lock = threading.Lock()

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def timing(self) -> TimingProfile:
        return self._timing

    def next_delay(self, *, same_domain: bool = False) -> float:
        """Compute the next inter-request delay.

        Takes into account the current session phase and transitions
        between phases as needed.

        Args:
            same_domain: True if next request is to the same domain.

        Returns:
            Delay in seconds before making the next request.
        """
        with self._lock:
            return self._compute_delay(same_domain)

    def _compute_delay(self, same_domain: bool) -> float:
        """Internal delay computation with phase transitions."""
        state = self._state

        # Check if we should take a session break
        if self._timing.should_take_break(state.session_elapsed):
            self._transition(SessionPhase.BREAK)
            break_delay = self._timing.compute_session_break()
            return break_delay

        # Check for burst mode
        if state.burst_remaining > 0:
            state.burst_remaining -= 1
            return max(self._timing.min_delay * 0.3, random.uniform(0.05, 0.3))

        # Maybe start a burst
        if random.random() < self._timing.burst_probability:
            state.burst_remaining = self._timing.burst_size - 1
            return self._timing.min_delay * 0.5

        # Normal phase transitions
        phase = state.phase
        if phase == SessionPhase.BREAK:
            self._transition(SessionPhase.ACTIVE)
            state.total_sessions += 1

        # Possibly transition to thinking
        if state.requests_in_phase > 0 and random.random() < 0.3:
            self._transition(SessionPhase.THINKING)
            return self._timing.compute_think_time()

        # Possibly enter idle
        if random.random() < self._timing.idle_probability:
            self._transition(SessionPhase.IDLE)
            return random.uniform(*self._timing.idle_duration_range)

        # Regular active delay
        state.requests_in_phase += 1
        state.requests_in_session += 1
        state.total_requests += 1
        return self._timing.compute_delay(same_domain=same_domain)

    def _transition(self, new_phase: SessionPhase) -> None:
        """Transition to a new session phase."""
        self._state.phase = new_phase
        self._state.phase_start = time.time()
        self._state.requests_in_phase = 0
        if new_phase == SessionPhase.BREAK:
            # Reset session on break
            self._state.requests_in_session = 0

    def new_session(self) -> None:
        """Start a fresh browsing session."""
        with self._lock:
            self._state = SessionState()

    def get_stats(self) -> dict[str, Any]:
        """Get session simulation statistics."""
        with self._lock:
            return {
                "phase": self._state.phase.value,
                "session_elapsed": round(self._state.session_elapsed, 1),
                "requests_in_session": self._state.requests_in_session,
                "requests_in_phase": self._state.requests_in_phase,
                "total_requests": self._state.total_requests,
                "total_sessions": self._state.total_sessions,
                "burst_remaining": self._state.burst_remaining,
            }


# ============================================================================
# Request Orchestrator (Cycles 76–80)
# ============================================================================


@dataclass
class OrchestratorStats:
    """Statistics from the request orchestrator."""
    total_enqueued: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_cancelled: int = 0
    current_queue_size: int = 0
    unique_domains: int = 0
    avg_delay: float = 0.0
    total_delay_time: float = 0.0


class RequestOrchestrator:
    """Unified request orchestrator combining priority queue,
    order randomization, timing profiles, and session simulation.

    This is the top-level component that modules interact with
    to schedule and time their requests.

    Args:
        timing: Timing profile (or TimingProfileType name).
        strategy: Request ordering strategy.
        max_concurrent: Maximum concurrent requests.
        max_queue_size: Maximum queue size.
        domain_min_interval: Minimum interval between same-domain requests.
    """

    def __init__(
        self,
        timing: TimingProfile | TimingProfileType | str | None = None,
        strategy: RandomizationStrategy = RandomizationStrategy.DOMAIN_SPREAD,
        max_concurrent: int = 5,
        max_queue_size: int = 10000,
        domain_min_interval: float | None = None,
    ) -> None:
        # Resolve timing profile
        if timing is None:
            self._timing = TIMING_PROFILES[TimingProfileType.RESEARCH]
        elif isinstance(timing, TimingProfile):
            self._timing = timing
        elif isinstance(timing, str):
            self._timing = get_timing_profile(timing)
        else:
            self._timing = get_timing_profile(timing)

        interval = domain_min_interval or self._timing.domain_min_interval

        self._queue = RequestPriorityQueue(
            domain_min_interval=interval,
            max_size=max_queue_size,
        )
        self._randomizer = RequestOrderRandomizer(strategy=strategy)
        self._session = SessionSimulator(timing=self._timing)
        self._max_concurrent = max_concurrent
        self._in_flight: dict[str, RequestRecord] = {}
        self._completed: list[RequestRecord] = []
        self._all_records: dict[str, RequestRecord] = {}
        self._last_domain: str = ""
        self._lock = threading.Lock()
        self._stats = OrchestratorStats()
        self._delay_history: list[float] = []

    @property
    def timing(self) -> TimingProfile:
        return self._timing

    @property
    def queue_size(self) -> int:
        return self._queue.size

    @property
    def in_flight_count(self) -> int:
        with self._lock:
            return len(self._in_flight)

    @property
    def completed_count(self) -> int:
        with self._lock:
            return len(self._completed)

    def enqueue(
        self,
        url: str,
        *,
        priority: int = 5,
        depends_on: set[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Enqueue a URL for scheduled fetching.

        Args:
            url: Target URL.
            priority: Priority (0=highest, 10=lowest).
            depends_on: Request IDs this depends on.
            metadata: Arbitrary request metadata.

        Returns:
            Request ID for tracking.
        """
        record = RequestRecord(
            priority=priority,
            url=url,
            depends_on=depends_on or set(),
            metadata=metadata or {},
        )

        if not self._queue.enqueue(record):
            log.warning("Queue full, dropping request: %s", url)
            return ""

        with self._lock:
            self._all_records[record.request_id] = record
            self._stats.total_enqueued += 1

        return record.request_id

    def enqueue_batch(
        self,
        urls: list[str],
        *,
        priority: int = 5,
        randomize: bool = True,
    ) -> list[str]:
        """Enqueue a batch of URLs with optional randomization.

        Args:
            urls: List of target URLs.
            priority: Priority for all requests.
            randomize: Whether to randomize order before enqueuing.

        Returns:
            List of request IDs.
        """
        records = [
            RequestRecord(priority=priority, url=url)
            for url in urls
        ]

        if randomize:
            records = self._randomizer.randomize(records)

        ids = []
        for record in records:
            if self._queue.enqueue(record):
                with self._lock:
                    self._all_records[record.request_id] = record
                    self._stats.total_enqueued += 1
                ids.append(record.request_id)

        return ids

    def next_request(self) -> tuple[RequestRecord | None, float]:
        """Get the next request and recommended delay.

        Returns:
            Tuple of (RequestRecord or None, delay in seconds).
            If None, the queue is empty or all are on cooldown.
        """
        with self._lock:
            if len(self._in_flight) >= self._max_concurrent:
                delay = self._queue.peek_next_domain_delay()
                return None, max(delay, 0.5)

        record = self._queue.dequeue()
        if record is None:
            delay = self._queue.peek_next_domain_delay()
            return None, max(delay, 0.1)

        # Compute delay
        same_domain = record.domain == self._last_domain
        delay = self._session.next_delay(same_domain=same_domain)

        with self._lock:
            record.status = RequestStatus.IN_FLIGHT
            self._in_flight[record.request_id] = record
            self._last_domain = record.domain
            self._delay_history.append(delay)
            self._stats.total_delay_time += delay

        return record, delay

    def complete(
        self,
        request_id: str,
        *,
        status_code: int = 200,
        success: bool = True,
    ) -> None:
        """Mark a request as completed.

        Args:
            request_id: ID returned by enqueue().
            status_code: HTTP response status code.
            success: Whether the request succeeded.
        """
        with self._lock:
            record = self._in_flight.pop(request_id, None)
            if record is None:
                return
            record.completed_at = time.time()
            record.status_code = status_code
            if success:
                record.status = RequestStatus.COMPLETED
                self._stats.total_completed += 1
            else:
                record.status = RequestStatus.FAILED
                self._stats.total_failed += 1
            self._completed.append(record)

        # Notify queue for dependency tracking
        self._queue.mark_completed(request_id)

    def cancel(self, request_id: str) -> None:
        """Cancel a pending request."""
        with self._lock:
            record = self._all_records.get(request_id)
            if record and record.status in (RequestStatus.PENDING, RequestStatus.SCHEDULED):
                record.status = RequestStatus.CANCELLED
                self._stats.total_cancelled += 1

    def get_request(self, request_id: str) -> RequestRecord | None:
        """Get a request record by ID."""
        with self._lock:
            return self._all_records.get(request_id)

    def get_stats(self) -> dict[str, Any]:
        """Get orchestrator statistics."""
        with self._lock:
            avg_delay = 0.0
            if self._delay_history:
                avg_delay = sum(self._delay_history) / len(self._delay_history)
            return {
                "total_enqueued": self._stats.total_enqueued,
                "total_completed": self._stats.total_completed,
                "total_failed": self._stats.total_failed,
                "total_cancelled": self._stats.total_cancelled,
                "queue_size": self._queue.size,
                "in_flight": len(self._in_flight),
                "unique_domains": self._queue.domain_count,
                "avg_delay": round(avg_delay, 3),
                "total_delay_time": round(self._stats.total_delay_time, 3),
                "session": self._session.get_stats(),
                "queue": self._queue.get_stats(),
            }

    def reset(self) -> None:
        """Reset all state."""
        with self._lock:
            self._queue.clear()
            self._in_flight.clear()
            self._completed.clear()
            self._all_records.clear()
            self._delay_history.clear()
            self._stats = OrchestratorStats()
            self._session.new_session()
            self._last_domain = ""
