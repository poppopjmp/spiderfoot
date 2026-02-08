"""Tests for spiderfoot.scan_queue."""

import threading
import time
import unittest

from spiderfoot.scan_queue import (
    BackpressureAction,
    PressureLevel,
    Priority,
    QueueItem,
    ScanQueue,
)


class TestQueueItem(unittest.TestCase):
    def test_ordering(self):
        high = QueueItem(payload="a", priority=Priority.HIGH)
        low = QueueItem(payload="b", priority=Priority.LOW)
        self.assertTrue(high < low)

    def test_same_priority_fifo(self):
        a = QueueItem(payload="a", priority=Priority.NORMAL, enqueued_at=1.0)
        b = QueueItem(payload="b", priority=Priority.NORMAL, enqueued_at=2.0)
        self.assertTrue(a < b)


class TestScanQueue(unittest.TestCase):
    def test_put_get(self):
        q: ScanQueue[str] = ScanQueue(capacity=10)
        q.put("hello")
        item = q.get(timeout=1.0)
        self.assertIsNotNone(item)
        self.assertEqual(item.payload, "hello")

    def test_priority_order(self):
        q: ScanQueue[str] = ScanQueue(capacity=100)
        q.put("low", priority=Priority.LOW)
        q.put("high", priority=Priority.HIGH)
        q.put("normal", priority=Priority.NORMAL)

        items = [q.get(timeout=1.0).payload for _ in range(3)]
        self.assertEqual(items, ["high", "normal", "low"])

    def test_fifo_within_priority(self):
        q: ScanQueue[int] = ScanQueue(capacity=100)
        for i in range(5):
            q.put(i, priority=Priority.NORMAL)
        results = [q.get(timeout=1.0).payload for _ in range(5)]
        self.assertEqual(results, [0, 1, 2, 3, 4])

    def test_depth_tracking(self):
        q: ScanQueue[str] = ScanQueue(capacity=10)
        self.assertEqual(q.depth, 0)
        q.put("a")
        q.put("b")
        self.assertEqual(q.depth, 2)
        q.get(timeout=1.0)
        self.assertEqual(q.depth, 1)

    def test_is_empty_is_full(self):
        q: ScanQueue[int] = ScanQueue(capacity=2)
        self.assertTrue(q.is_empty)
        q.put(1)
        q.put(2)
        self.assertTrue(q.is_full)

    def test_reject_when_full(self):
        q: ScanQueue[int] = ScanQueue(
            capacity=2,
            backpressure_action=BackpressureAction.REJECT,
        )
        self.assertTrue(q.put(1))
        self.assertTrue(q.put(2))
        self.assertFalse(q.put(3))

    def test_drop_oldest_when_full(self):
        q: ScanQueue[str] = ScanQueue(
            capacity=2,
            backpressure_action=BackpressureAction.DROP_OLDEST,
        )
        q.put("a", priority=Priority.LOW)
        q.put("b", priority=Priority.LOW)
        # Should drop "a" and enqueue "c"
        self.assertTrue(q.put("c", priority=Priority.NORMAL))
        self.assertEqual(q.depth, 2)

    def test_block_timeout(self):
        q: ScanQueue[int] = ScanQueue(
            capacity=1,
            backpressure_action=BackpressureAction.BLOCK,
        )
        q.put(1)
        # Should timeout
        self.assertFalse(q.put(2, timeout=0.05))

    def test_block_then_unblock(self):
        q: ScanQueue[int] = ScanQueue(
            capacity=1,
            backpressure_action=BackpressureAction.BLOCK,
        )
        q.put(1)

        result = [None]

        def producer():
            result[0] = q.put(2, timeout=2.0)

        t = threading.Thread(target=producer)
        t.start()
        time.sleep(0.05)
        q.get(timeout=1.0)
        t.join(timeout=2.0)
        self.assertTrue(result[0])

    def test_get_timeout_empty(self):
        q: ScanQueue[int] = ScanQueue(capacity=10)
        item = q.get(timeout=0.05)
        self.assertIsNone(item)

    def test_get_batch(self):
        q: ScanQueue[int] = ScanQueue(capacity=100)
        for i in range(5):
            q.put(i)
        batch = q.get_batch(max_items=3, timeout=1.0)
        self.assertEqual(len(batch), 3)
        self.assertEqual(q.depth, 2)

    def test_get_batch_priority(self):
        q: ScanQueue[str] = ScanQueue(capacity=100)
        q.put("low", priority=Priority.LOW)
        q.put("high", priority=Priority.HIGH)
        q.put("normal", priority=Priority.NORMAL)
        batch = q.get_batch(max_items=3, timeout=1.0)
        payloads = [it.payload for it in batch]
        self.assertEqual(payloads, ["high", "normal", "low"])

    def test_requeue(self):
        q: ScanQueue[str] = ScanQueue(capacity=10)
        q.put("task")
        item = q.get(timeout=1.0)
        self.assertTrue(q.requeue(item))
        self.assertEqual(q.depth, 1)
        item2 = q.get(timeout=1.0)
        self.assertEqual(item2.retries, 1)

    def test_requeue_to_dlq(self):
        q: ScanQueue[str] = ScanQueue(capacity=10)
        q.put("task", max_retries=1)
        item = q.get(timeout=1.0)
        q.requeue(item)  # retry 1
        item = q.get(timeout=1.0)
        result = q.requeue(item)  # retry 2 > max_retries=1
        self.assertFalse(result)
        self.assertEqual(q.dlq_depth, 1)

    def test_drain_dlq(self):
        q: ScanQueue[str] = ScanQueue(capacity=10)
        q.put("task", max_retries=0)
        item = q.get(timeout=1.0)
        q.requeue(item)
        items = q.drain_dlq()
        self.assertEqual(len(items), 1)
        self.assertEqual(q.dlq_depth, 0)

    def test_peek_dlq(self):
        q: ScanQueue[str] = ScanQueue(capacity=10)
        q.put("task", max_retries=0)
        item = q.get(timeout=1.0)
        q.requeue(item)
        peeked = q.peek_dlq()
        self.assertEqual(len(peeked), 1)
        self.assertEqual(q.dlq_depth, 1)  # still there

    def test_clear(self):
        q: ScanQueue[int] = ScanQueue(capacity=100)
        for i in range(10):
            q.put(i)
        removed = q.clear()
        self.assertEqual(removed, 10)
        self.assertTrue(q.is_empty)

    def test_clear_dlq(self):
        q: ScanQueue[str] = ScanQueue(capacity=10)
        q.put("a", max_retries=0)
        item = q.get(timeout=1.0)
        q.requeue(item)
        n = q.clear_dlq()
        self.assertEqual(n, 1)
        self.assertEqual(q.dlq_depth, 0)

    def test_pressure(self):
        q: ScanQueue[int] = ScanQueue(capacity=10)
        self.assertAlmostEqual(q.pressure, 0.0)
        for i in range(5):
            q.put(i)
        self.assertAlmostEqual(q.pressure, 0.5)

    def test_pressure_level(self):
        q: ScanQueue[int] = ScanQueue(capacity=10)
        self.assertEqual(q.pressure_level, PressureLevel.NONE)
        for i in range(9):
            q.put(i)
        # 90% = CRITICAL
        self.assertEqual(q.pressure_level, PressureLevel.CRITICAL)

    def test_pressure_callback(self):
        levels = []
        q: ScanQueue[int] = ScanQueue(capacity=4)
        q.on_pressure_change(lambda lvl: levels.append(lvl))
        q.put(1)  # 25% → LOW
        q.put(2)  # 50% → MEDIUM
        q.put(3)  # 75% → HIGH
        self.assertTrue(len(levels) > 0)

    def test_depth_by_priority(self):
        q: ScanQueue[str] = ScanQueue(capacity=100)
        q.put("a", priority=Priority.HIGH)
        q.put("b", priority=Priority.LOW)
        q.put("c", priority=Priority.LOW)
        by_pri = q.depth_by_priority()
        self.assertEqual(by_pri["HIGH"], 1)
        self.assertEqual(by_pri["LOW"], 2)

    def test_stats(self):
        q: ScanQueue[int] = ScanQueue(capacity=10)
        q.put(1)
        q.put(2)
        q.get(timeout=1.0)
        s = q.stats()
        self.assertEqual(s.depth, 1)
        self.assertEqual(s.capacity, 10)
        self.assertEqual(s.enqueued_total, 2)
        self.assertEqual(s.dequeued_total, 1)
        d = s.to_dict()
        self.assertIn("utilization", d)

    def test_item_id(self):
        q: ScanQueue[str] = ScanQueue(capacity=10)
        q.put("task", item_id="t-001")
        item = q.get(timeout=1.0)
        self.assertEqual(item.item_id, "t-001")

    def test_metadata(self):
        q: ScanQueue[str] = ScanQueue(capacity=10)
        q.put("task", metadata={"scan": "s1"})
        item = q.get(timeout=1.0)
        self.assertEqual(item.metadata["scan"], "s1")

    def test_concurrent_producers(self):
        q: ScanQueue[int] = ScanQueue(capacity=1000)
        n = 100

        def producer(start):
            for i in range(n):
                q.put(start + i)

        threads = [threading.Thread(target=producer, args=(i * n,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(q.depth, 500)


if __name__ == "__main__":
    unittest.main()
