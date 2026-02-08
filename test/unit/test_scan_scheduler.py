"""
Tests for the Scan Scheduler Service.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.scan_scheduler import (
    ScanScheduler,
    SchedulerConfig,
    ScanRequest,
    ScanStatus,
    ScanState,
    ScanPriority,
)


class TestScanRequest(unittest.TestCase):
    """Test ScanRequest."""
    
    def test_auto_id(self):
        req = ScanRequest(scan_name="Test", target="example.com")
        self.assertTrue(len(req.scan_id) > 0)
    
    def test_explicit_id(self):
        req = ScanRequest(
            scan_name="Test", target="example.com", scan_id="my-id"
        )
        self.assertEqual(req.scan_id, "my-id")
    
    def test_default_priority(self):
        req = ScanRequest(scan_name="Test", target="example.com")
        self.assertEqual(req.priority, ScanPriority.NORMAL)


class TestScanStatus(unittest.TestCase):
    """Test ScanStatus."""
    
    def test_to_dict(self):
        status = ScanStatus(
            scan_id="s1",
            scan_name="Test",
            target="example.com",
            state=ScanState.RUNNING,
            started_at=time.time() - 10,
        )
        d = status.to_dict()
        self.assertEqual(d["scan_id"], "s1")
        self.assertEqual(d["state"], "RUNNING")
        self.assertGreater(d["duration"], 9)
    
    def test_duration_not_started(self):
        status = ScanStatus(
            scan_id="s1", scan_name="T", target="t",
            state=ScanState.CREATED
        )
        self.assertEqual(status.duration, 0)


class TestSchedulerConfig(unittest.TestCase):
    """Test SchedulerConfig."""
    
    def test_defaults(self):
        config = SchedulerConfig()
        self.assertEqual(config.max_concurrent_scans, 3)
        self.assertTrue(config.enable_auto_correlations)
    
    def test_from_sf_config(self):
        config = SchedulerConfig.from_sf_config({
            "_scheduler_max_scans": "5",
            "_scheduler_poll_interval": "10",
        })
        self.assertEqual(config.max_concurrent_scans, 5)
        self.assertEqual(config.scan_poll_interval, 10.0)


class TestScanScheduler(unittest.TestCase):
    """Test ScanScheduler."""
    
    def setUp(self):
        self.config = SchedulerConfig(
            max_concurrent_scans=2,
            scan_poll_interval=0.1,
        )
        self.scheduler = ScanScheduler(self.config)
    
    def tearDown(self):
        self.scheduler.shutdown()
    
    def test_submit_scan(self):
        scan_id = self.scheduler.submit_scan(ScanRequest(
            scan_name="Test", target="example.com"
        ))
        self.assertTrue(len(scan_id) > 0)
        self.assertEqual(self.scheduler.pending_count, 1)
    
    def test_submit_multiple(self):
        self.scheduler.submit_scan(ScanRequest(scan_name="S1", target="t1.com"))
        self.scheduler.submit_scan(ScanRequest(scan_name="S2", target="t2.com"))
        self.assertEqual(self.scheduler.pending_count, 2)
    
    def test_priority_ordering(self):
        self.scheduler.submit_scan(ScanRequest(
            scan_name="Low", target="low.com",
            priority=ScanPriority.LOW,
        ))
        self.scheduler.submit_scan(ScanRequest(
            scan_name="Critical", target="crit.com",
            priority=ScanPriority.CRITICAL,
        ))
        self.scheduler.submit_scan(ScanRequest(
            scan_name="High", target="high.com",
            priority=ScanPriority.HIGH,
        ))
        
        # Critical should be first
        self.assertEqual(self.scheduler._pending[0].scan_name, "Critical")
    
    def test_abort_pending(self):
        scan_id = self.scheduler.submit_scan(ScanRequest(
            scan_name="Test", target="example.com"
        ))
        result = self.scheduler.abort_scan(scan_id)
        self.assertTrue(result)
        self.assertEqual(self.scheduler.pending_count, 0)
    
    def test_abort_nonexistent(self):
        result = self.scheduler.abort_scan("nonexistent")
        self.assertFalse(result)
    
    def test_get_scan_status_pending(self):
        scan_id = self.scheduler.submit_scan(ScanRequest(
            scan_name="Test", target="example.com",
            modules=["sfp_a", "sfp_b"],
        ))
        status = self.scheduler.get_scan_status(scan_id)
        self.assertIsNotNone(status)
        self.assertEqual(status["state"], "CREATED")
        self.assertEqual(status["modules_total"], 2)
    
    def test_get_scan_status_not_found(self):
        status = self.scheduler.get_scan_status("nonexistent")
        self.assertIsNone(status)
    
    def test_list_scans(self):
        self.scheduler.submit_scan(ScanRequest(scan_name="S1", target="t1"))
        scans = self.scheduler.list_scans()
        self.assertEqual(len(scans), 1)
        self.assertEqual(scans[0]["scan_name"], "S1")
    
    def test_list_scans_filter(self):
        self.scheduler.submit_scan(ScanRequest(scan_name="S1", target="t1"))
        scans = self.scheduler.list_scans(state=ScanState.RUNNING)
        self.assertEqual(len(scans), 0)
    
    def test_complete_scan(self):
        # Manually add to active
        status = ScanStatus(
            scan_id="s1", scan_name="T", target="t",
            state=ScanState.RUNNING, started_at=time.time()
        )
        self.scheduler._active["s1"] = status
        
        self.scheduler.complete_scan("s1")
        self.assertEqual(self.scheduler.active_count, 0)
        completed = self.scheduler.get_scan_status("s1")
        self.assertEqual(completed["state"], "FINISHED")
    
    def test_error_scan(self):
        status = ScanStatus(
            scan_id="s1", scan_name="T", target="t",
            state=ScanState.RUNNING, started_at=time.time()
        )
        self.scheduler._active["s1"] = status
        
        self.scheduler.error_scan("s1", "Something broke")
        completed = self.scheduler.get_scan_status("s1")
        self.assertEqual(completed["state"], "ERROR")
        self.assertEqual(completed["error_message"], "Something broke")
    
    def test_update_progress(self):
        status = ScanStatus(
            scan_id="s1", scan_name="T", target="t",
            state=ScanState.RUNNING, modules_total=10,
        )
        self.scheduler._active["s1"] = status
        
        self.scheduler.update_scan_progress(
            "s1", events_produced=50,
            modules_running=3, modules_finished=5
        )
        
        result = self.scheduler.get_scan_status("s1")
        self.assertEqual(result["events_produced"], 50)
        self.assertEqual(result["progress"], 50.0)
    
    def test_pause_resume(self):
        status = ScanStatus(
            scan_id="s1", scan_name="T", target="t",
            state=ScanState.RUNNING,
        )
        self.scheduler._active["s1"] = status
        
        self.assertTrue(self.scheduler.pause_scan("s1"))
        self.assertEqual(status.state, ScanState.PAUSED)
        
        self.assertTrue(self.scheduler.resume_scan("s1"))
        self.assertEqual(status.state, ScanState.RUNNING)
    
    def test_stats(self):
        self.scheduler.submit_scan(ScanRequest(scan_name="S1", target="t1"))
        stats = self.scheduler.stats()
        self.assertEqual(stats["pending_scans"], 1)
        self.assertEqual(stats["active_scans"], 0)
        self.assertEqual(stats["max_concurrent"], 2)
    
    def test_callbacks(self):
        on_complete = MagicMock()
        self.scheduler.on_scan_complete(on_complete)
        
        status = ScanStatus(
            scan_id="s1", scan_name="T", target="t",
            state=ScanState.RUNNING, started_at=time.time()
        )
        self.scheduler._active["s1"] = status
        
        self.scheduler.complete_scan("s1")
        on_complete.assert_called_once()


class TestSchedulerTimeout(unittest.TestCase):
    """Test scan timeout handling."""
    
    def test_check_timeouts(self):
        config = SchedulerConfig(default_max_duration=1)
        scheduler = ScanScheduler(config)
        
        # Add an active scan that started 10 seconds ago
        status = ScanStatus(
            scan_id="s1", scan_name="T", target="t",
            state=ScanState.RUNNING,
            started_at=time.time() - 10,
        )
        scheduler._active["s1"] = status
        
        scheduler._check_timeouts()
        
        # Should be aborted
        result = scheduler.get_scan_status("s1")
        self.assertEqual(result["state"], "ABORTED")
        scheduler.shutdown()


if __name__ == "__main__":
    unittest.main()
