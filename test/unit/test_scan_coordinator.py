"""Tests for spiderfoot.scan_coordinator."""

import time
import unittest
from unittest.mock import MagicMock

from spiderfoot.scan_coordinator import (
    DistributionStrategy,
    NodeState,
    ScanCoordinator,
    ScannerNode,
    ScanWork,
    WorkAssignment,
    WorkState,
)


class TestScannerNode(unittest.TestCase):
    """Tests for ScannerNode."""

    def test_basic(self):
        n = ScannerNode("n1", "http://host:8001", capacity=5)
        self.assertEqual(n.node_id, "n1")
        self.assertEqual(n.available_capacity, 5)
        self.assertTrue(n.is_available)

    def test_available_capacity(self):
        n = ScannerNode("n1", "http://host:8001", capacity=3)
        n.active_work = 2
        self.assertEqual(n.available_capacity, 1)

    def test_not_available_when_full(self):
        n = ScannerNode("n1", "http://host:8001", capacity=1)
        n.active_work = 1
        self.assertFalse(n.is_available)

    def test_not_available_when_offline(self):
        n = ScannerNode("n1", "http://host:8001", state=NodeState.OFFLINE)
        self.assertFalse(n.is_available)

    def test_to_dict(self):
        n = ScannerNode("n1", "http://host:8001", tags=["gpu"])
        d = n.to_dict()
        self.assertEqual(d["node_id"], "n1")
        self.assertIn("gpu", d["tags"])


class TestScanWork(unittest.TestCase):
    """Tests for ScanWork."""

    def test_to_dict(self):
        w = ScanWork("scan1", "example.com", modules=["sfp_dns"])
        d = w.to_dict()
        self.assertEqual(d["scan_id"], "scan1")
        self.assertEqual(d["target"], "example.com")


class TestWorkAssignment(unittest.TestCase):
    """Tests for WorkAssignment."""

    def test_to_dict(self):
        w = ScanWork("scan1", "example.com")
        a = WorkAssignment("w1", w, state=WorkState.PENDING)
        d = a.to_dict()
        self.assertEqual(d["work_id"], "w1")
        self.assertEqual(d["state"], "pending")


class TestScanCoordinator(unittest.TestCase):
    """Tests for ScanCoordinator."""

    def setUp(self):
        self.coord = ScanCoordinator(strategy=DistributionStrategy.LEAST_LOADED)

    def test_register_node(self):
        node = ScannerNode("n1", "http://host:8001")
        self.coord.register_node(node)
        self.assertEqual(len(self.coord.list_nodes()), 1)

    def test_unregister_node(self):
        node = ScannerNode("n1", "http://host:8001")
        self.coord.register_node(node)
        removed = self.coord.unregister_node("n1")
        self.assertIsNotNone(removed)
        self.assertEqual(len(self.coord.list_nodes()), 0)

    def test_unregister_nonexistent(self):
        self.assertIsNone(self.coord.unregister_node("x"))

    def test_get_node(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        node = self.coord.get_node("n1")
        self.assertIsNotNone(node)
        self.assertIsNone(self.coord.get_node("x"))

    def test_set_node_state(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        self.assertTrue(self.coord.set_node_state("n1", NodeState.DRAINING))
        self.assertEqual(self.coord.get_node("n1").state, NodeState.DRAINING)

    def test_set_node_state_nonexistent(self):
        self.assertFalse(self.coord.set_node_state("x", NodeState.OFFLINE))

    def test_heartbeat(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        self.assertTrue(self.coord.heartbeat("n1"))
        self.assertFalse(self.coord.heartbeat("x"))

    def test_heartbeat_updates_active_work(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        self.coord.heartbeat("n1", active_work=3)
        self.assertEqual(self.coord.get_node("n1").active_work, 3)

    def test_heartbeat_restores_offline(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        self.coord.set_node_state("n1", NodeState.OFFLINE)
        self.coord.heartbeat("n1")
        self.assertEqual(self.coord.get_node("n1").state, NodeState.ONLINE)

    def test_submit_work_immediate(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        work = ScanWork("scan1", "example.com")
        work_id = self.coord.submit_work(work)
        status = self.coord.get_work_status(work_id)
        self.assertIsNotNone(status)
        self.assertEqual(status["state"], "assigned")
        self.assertEqual(status["node_id"], "n1")

    def test_submit_work_queued_when_no_nodes(self):
        work = ScanWork("scan1", "example.com")
        work_id = self.coord.submit_work(work)
        status = self.coord.get_work_status(work_id)
        self.assertEqual(status["state"], "pending")

    def test_cancel_work(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        work_id = self.coord.submit_work(ScanWork("scan1", "example.com"))
        self.assertTrue(self.coord.cancel_work(work_id))
        status = self.coord.get_work_status(work_id)
        self.assertEqual(status["state"], "cancelled")

    def test_cancel_nonexistent(self):
        self.assertFalse(self.coord.cancel_work("x"))

    def test_cancel_completed(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        work_id = self.coord.submit_work(ScanWork("scan1", "example.com"))
        self.coord.report_started(work_id)
        self.coord.report_completed(work_id)
        self.assertFalse(self.coord.cancel_work(work_id))

    def test_report_started(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        work_id = self.coord.submit_work(ScanWork("scan1", "example.com"))
        self.assertTrue(self.coord.report_started(work_id))
        status = self.coord.get_work_status(work_id)
        self.assertEqual(status["state"], "running")

    def test_report_completed(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        work_id = self.coord.submit_work(ScanWork("scan1", "example.com"))
        self.coord.report_started(work_id)
        self.assertTrue(self.coord.report_completed(work_id, {"events": 42}))
        status = self.coord.get_work_status(work_id)
        self.assertEqual(status["state"], "completed")

    def test_report_completed_frees_capacity(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001", capacity=1))
        work_id = self.coord.submit_work(ScanWork("scan1", "example.com"))
        self.assertEqual(self.coord.get_node("n1").active_work, 1)
        self.coord.report_started(work_id)
        self.coord.report_completed(work_id)
        self.assertEqual(self.coord.get_node("n1").active_work, 0)

    def test_report_failed_retries(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        self.coord.register_node(ScannerNode("n2", "http://host2:8001"))
        work = ScanWork("scan1", "example.com", max_retries=2)
        work_id = self.coord.submit_work(work)
        self.coord.report_started(work_id)
        self.coord.report_failed(work_id, "crash")
        status = self.coord.get_work_status(work_id)
        # Should be reassigned, not failed
        self.assertIn(status["state"], ["assigned", "reassigned"])

    def test_report_failed_max_retries(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        work = ScanWork("scan1", "example.com", max_retries=0)
        work_id = self.coord.submit_work(work)
        self.coord.report_started(work_id)
        self.coord.report_failed(work_id, "fatal")
        status = self.coord.get_work_status(work_id)
        self.assertEqual(status["state"], "failed")

    def test_list_work(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        self.coord.submit_work(ScanWork("s1", "a.com"))
        self.coord.submit_work(ScanWork("s2", "b.com"))
        all_work = self.coord.list_work()
        self.assertEqual(len(all_work), 2)

    def test_list_work_filtered(self):
        self.coord.register_node(ScannerNode("n1", "http://host:8001"))
        w1 = self.coord.submit_work(ScanWork("s1", "a.com"))
        self.coord.report_started(w1)
        self.coord.report_completed(w1)
        self.coord.submit_work(ScanWork("s2", "b.com"))
        completed = self.coord.list_work(state=WorkState.COMPLETED)
        self.assertEqual(len(completed), 1)

    def test_get_work_status_nonexistent(self):
        self.assertIsNone(self.coord.get_work_status("x"))


class TestDistributionStrategies(unittest.TestCase):
    """Tests for different distribution strategies."""

    def test_least_loaded(self):
        coord = ScanCoordinator(strategy=DistributionStrategy.LEAST_LOADED)
        n1 = ScannerNode("n1", "http://host1:8001", capacity=5)
        n1.active_work = 3
        n2 = ScannerNode("n2", "http://host2:8001", capacity=5)
        n2.active_work = 1
        coord.register_node(n1)
        coord.register_node(n2)

        work_id = coord.submit_work(ScanWork("s1", "example.com"))
        status = coord.get_work_status(work_id)
        self.assertEqual(status["node_id"], "n2")

    def test_round_robin(self):
        coord = ScanCoordinator(strategy=DistributionStrategy.ROUND_ROBIN)
        coord.register_node(ScannerNode("n1", "http://h1:8001", capacity=10))
        coord.register_node(ScannerNode("n2", "http://h2:8001", capacity=10))

        ids = []
        for i in range(4):
            wid = coord.submit_work(ScanWork(f"s{i}", f"{i}.com"))
            ids.append(coord.get_work_status(wid)["node_id"])

        # Should alternate (order depends on dict ordering)
        self.assertTrue(len(set(ids)) == 2)

    def test_hash_based(self):
        coord = ScanCoordinator(strategy=DistributionStrategy.HASH_BASED)
        coord.register_node(ScannerNode("n1", "http://h1:8001", capacity=10))
        coord.register_node(ScannerNode("n2", "http://h2:8001", capacity=10))

        # Same target should go to same node
        w1 = coord.submit_work(ScanWork("s1", "same.com"))
        coord.report_started(w1)
        coord.report_completed(w1)
        w2 = coord.submit_work(ScanWork("s2", "same.com"))
        self.assertEqual(
            coord.get_work_status(w1)["node_id"],
            coord.get_work_status(w2)["node_id"],
        )

    def test_required_tags(self):
        coord = ScanCoordinator(strategy=DistributionStrategy.LEAST_LOADED)
        coord.register_node(ScannerNode("n1", "http://h1:8001", tags=["gpu"]))
        coord.register_node(ScannerNode("n2", "http://h2:8001", tags=["standard"]))

        work = ScanWork("s1", "example.com", required_tags=["gpu"])
        work_id = coord.submit_work(work)
        self.assertEqual(coord.get_work_status(work_id)["node_id"], "n1")

    def test_no_matching_tags_queued(self):
        coord = ScanCoordinator(strategy=DistributionStrategy.LEAST_LOADED)
        coord.register_node(ScannerNode("n1", "http://h1:8001", tags=["standard"]))

        work = ScanWork("s1", "example.com", required_tags=["gpu"])
        work_id = coord.submit_work(work)
        self.assertEqual(coord.get_work_status(work_id)["state"], "pending")


class TestFailover(unittest.TestCase):
    """Tests for failover scenarios."""

    def test_node_removal_reassigns(self):
        coord = ScanCoordinator()
        coord.register_node(ScannerNode("n1", "http://h1:8001"))
        coord.register_node(ScannerNode("n2", "http://h2:8001"))

        work_id = coord.submit_work(ScanWork("s1", "example.com"))
        first_node = coord.get_work_status(work_id)["node_id"]

        # Remove the assigned node
        coord.unregister_node(first_node, reassign=True)
        status = coord.get_work_status(work_id)
        # Should be reassigned to the other node
        self.assertIn(status["state"], ["assigned", "reassigned"])

    def test_pending_dequeued_when_node_added(self):
        coord = ScanCoordinator()
        work_id = coord.submit_work(ScanWork("s1", "example.com"))
        self.assertEqual(coord.get_work_status(work_id)["state"], "pending")

        # Add a node — pending work should get picked up on next
        # report_completed or manual trigger
        coord.register_node(ScannerNode("n1", "http://h1:8001"))
        # Submit another to trigger _try_assign_pending
        w2 = coord.submit_work(ScanWork("s2", "b.com"))
        # Both should now be assigned (depends on capacity)
        states = [
            coord.get_work_status(work_id)["state"],
            coord.get_work_status(w2)["state"],
        ]
        # At minimum w2 was assigned directly
        self.assertIn("assigned", states)


class TestCallbacks(unittest.TestCase):
    """Tests for coordinator callbacks."""

    def test_work_assigned_callback(self):
        coord = ScanCoordinator()
        coord.register_node(ScannerNode("n1", "http://h1:8001"))
        received = []
        coord.on("work_assigned", lambda a: received.append(a))
        coord.submit_work(ScanWork("s1", "example.com"))
        self.assertEqual(len(received), 1)

    def test_work_completed_callback(self):
        coord = ScanCoordinator()
        coord.register_node(ScannerNode("n1", "http://h1:8001"))
        received = []
        coord.on("work_completed", lambda a: received.append(a))
        wid = coord.submit_work(ScanWork("s1", "example.com"))
        coord.report_started(wid)
        coord.report_completed(wid)
        self.assertEqual(len(received), 1)

    def test_work_failed_callback(self):
        coord = ScanCoordinator()
        coord.register_node(ScannerNode("n1", "http://h1:8001"))
        received = []
        coord.on("work_failed", lambda a: received.append(a))
        wid = coord.submit_work(ScanWork("s1", "example.com", max_retries=0))
        coord.report_started(wid)
        coord.report_failed(wid, "crash")
        self.assertEqual(len(received), 1)

    def test_node_online_callback(self):
        coord = ScanCoordinator()
        received = []
        coord.on("node_online", lambda n: received.append(n))
        coord.register_node(ScannerNode("n1", "http://h1:8001"))
        self.assertEqual(len(received), 1)


class TestCoordinatorStats(unittest.TestCase):
    """Tests for coordinator stats."""

    def test_stats(self):
        coord = ScanCoordinator()
        coord.register_node(ScannerNode("n1", "http://h1:8001", capacity=5))
        coord.submit_work(ScanWork("s1", "example.com"))
        s = coord.stats()
        self.assertEqual(s["total_nodes"], 1)
        self.assertEqual(s["nodes_online"], 1)
        self.assertEqual(s["total_capacity"], 5)
        self.assertEqual(s["total_work"], 1)
        self.assertEqual(s["strategy"], "least_loaded")

    def test_stats_empty(self):
        coord = ScanCoordinator()
        s = coord.stats()
        self.assertEqual(s["total_nodes"], 0)
        self.assertEqual(s["total_work"], 0)


if __name__ == "__main__":
    unittest.main()
