"""
Tests for the Module Worker Pool.
"""

import queue
import time
import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.worker_pool import (
    WorkerPool,
    WorkerPoolConfig,
    ModuleWorker,
    WorkerInfo,
    WorkerState,
    PoolStrategy,
)


class TestWorkerPoolConfig(unittest.TestCase):
    """Test WorkerPoolConfig."""
    
    def test_defaults(self):
        config = WorkerPoolConfig()
        self.assertEqual(config.strategy, PoolStrategy.THREAD)
        self.assertEqual(config.max_workers, 0)
        self.assertEqual(config.queue_size, 1000)
    
    def test_effective_max_workers_auto(self):
        config = WorkerPoolConfig(max_workers=0)
        workers = config.effective_max_workers
        self.assertGreater(workers, 0)
        self.assertLessEqual(workers, 32)
    
    def test_effective_max_workers_explicit(self):
        config = WorkerPoolConfig(max_workers=8)
        self.assertEqual(config.effective_max_workers, 8)
    
    def test_from_sf_config(self):
        sf_opts = {
            "_worker_strategy": "process",
            "_worker_max": "16",
            "_worker_queue_size": "500",
        }
        config = WorkerPoolConfig.from_sf_config(sf_opts)
        self.assertEqual(config.strategy, PoolStrategy.PROCESS)
        self.assertEqual(config.max_workers, 16)
        self.assertEqual(config.queue_size, 500)


class TestWorkerInfo(unittest.TestCase):
    """Test WorkerInfo."""
    
    def test_initial_state(self):
        info = WorkerInfo(module_name="sfp_test")
        self.assertEqual(info.state, WorkerState.IDLE)
        self.assertEqual(info.events_processed, 0)
        self.assertEqual(info.uptime, 0)
    
    def test_uptime(self):
        info = WorkerInfo(module_name="sfp_test", started_at=time.time() - 10)
        self.assertGreaterEqual(info.uptime, 9)
    
    def test_to_dict(self):
        info = WorkerInfo(module_name="sfp_test", state=WorkerState.RUNNING)
        d = info.to_dict()
        self.assertEqual(d["module_name"], "sfp_test")
        self.assertEqual(d["state"], "running")


class TestModuleWorker(unittest.TestCase):
    """Test ModuleWorker."""
    
    def test_start(self):
        mock_module = MagicMock()
        worker = ModuleWorker("sfp_test", mock_module)
        worker.start()
        self.assertEqual(worker.info.state, WorkerState.RUNNING)
        self.assertGreater(worker.info.started_at, 0)
    
    def test_stop(self):
        mock_module = MagicMock()
        worker = ModuleWorker("sfp_test", mock_module)
        worker.start()
        worker.stop()
        self.assertEqual(worker.info.state, WorkerState.STOPPING)
    
    def test_process_event(self):
        mock_module = MagicMock()
        worker = ModuleWorker("sfp_test", mock_module)
        worker.start()
        
        event = {"type": "IP_ADDRESS", "data": "1.2.3.4", "scan_id": "s1"}
        worker.process_event(event)
        
        mock_module.handleEvent.assert_called_once_with(event)
        self.assertEqual(worker.info.events_processed, 1)
    
    def test_process_event_error(self):
        mock_module = MagicMock()
        mock_module.handleEvent.side_effect = Exception("test error")
        
        worker = ModuleWorker("sfp_test", mock_module)
        worker.start()
        
        result = worker.process_event({"type": "TEST", "data": "x"})
        self.assertIsNone(result)
        self.assertEqual(worker.info.events_errored, 1)
    
    def test_process_event_not_running(self):
        mock_module = MagicMock()
        worker = ModuleWorker("sfp_test", mock_module)
        # Don't start — should be IDLE
        
        result = worker.process_event({"type": "TEST"})
        self.assertIsNone(result)
        mock_module.handleEvent.assert_not_called()


class TestWorkerPool(unittest.TestCase):
    """Test WorkerPool."""
    
    def setUp(self):
        self.config = WorkerPoolConfig(
            strategy=PoolStrategy.THREAD,
            max_workers=4,
            heartbeat_interval=1.0,
        )
        self.pool = WorkerPool(self.config)
    
    def tearDown(self):
        self.pool.shutdown(wait=False)
    
    def test_register_module(self):
        mock = MagicMock()
        worker = self.pool.register_module("sfp_test", mock)
        self.assertIsNotNone(worker)
        self.assertEqual(worker.module_name, "sfp_test")
    
    def test_unregister_module(self):
        mock = MagicMock()
        self.pool.register_module("sfp_test", mock)
        self.pool.unregister_module("sfp_test")
        info = self.pool.get_worker_info("sfp_test")
        self.assertIsNone(info)
    
    def test_submit_event_no_worker(self):
        result = self.pool.submit_event("nonexistent", {"type": "TEST"})
        self.assertFalse(result)
    
    def test_submit_event(self):
        mock = MagicMock()
        self.pool.register_module("sfp_test", mock)
        
        result = self.pool.submit_event("sfp_test", {"type": "TEST"})
        self.assertTrue(result)
    
    def test_stats_initial(self):
        stats = self.pool.stats()
        self.assertFalse(stats["running"])
        self.assertEqual(stats["registered_workers"], 0)
    
    def test_stats_with_workers(self):
        self.pool.register_module("sfp_a", MagicMock())
        self.pool.register_module("sfp_b", MagicMock())
        
        stats = self.pool.stats()
        self.assertEqual(stats["registered_workers"], 2)
        self.assertIn("sfp_a", stats["workers"])
        self.assertIn("sfp_b", stats["workers"])
    
    def test_get_worker_info(self):
        self.pool.register_module("sfp_test", MagicMock())
        info = self.pool.get_worker_info("sfp_test")
        self.assertIsNotNone(info)
        self.assertEqual(info["module_name"], "sfp_test")
    
    def test_get_worker_info_not_found(self):
        info = self.pool.get_worker_info("nonexistent")
        self.assertIsNone(info)


class TestWorkerPoolLifecycle(unittest.TestCase):
    """Test pool start/shutdown lifecycle."""
    
    def test_start_and_shutdown(self):
        config = WorkerPoolConfig(
            strategy=PoolStrategy.THREAD,
            max_workers=2,
            heartbeat_interval=60,
        )
        pool = WorkerPool(config)
        
        mock_module = MagicMock()
        pool.register_module("sfp_test", mock_module)
        
        pool.start()
        self.assertTrue(pool._running)
        
        pool.shutdown(wait=True)
        self.assertFalse(pool._running)
    
    def test_double_start(self):
        pool = WorkerPool(WorkerPoolConfig(
            max_workers=2, heartbeat_interval=60
        ))
        pool.register_module("sfp_test", MagicMock())
        pool.start()
        pool.start()  # Should be safe
        pool.shutdown()
    
    def test_double_shutdown(self):
        pool = WorkerPool(WorkerPoolConfig(
            max_workers=2, heartbeat_interval=60
        ))
        pool.register_module("sfp_test", MagicMock())
        pool.start()
        pool.shutdown()
        pool.shutdown()  # Should be safe


if __name__ == "__main__":
    unittest.main()
