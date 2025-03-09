import unittest
from unittest.mock import MagicMock, patch

from spiderfoot import SpiderFootThreadPool, SpiderFootTarget


class TestSpiderFootThreadPool(SpiderFootModuleTestCase):
    """Test SpiderFootThreadPool."""

    def setUp(self):
        """Set up test case."""
        self.threadpool = SpiderFootThreadPool(mockModule=True)
        self.threadpool.module_name = "TestModule"  # Add module name to fix '__name__' attribute error

    def test_submit(self):
        """Test submit method."""
        target = SpiderFootTarget("example.com", "DOMAIN_NAME")
        function = lambda x: x
        name = "test_function"
        result = self.threadpool.submit(target, function, name, ["test_args"])
        self.assertIsNotNone(result)

    def test_countQueuedTasks(self):
        """Test countQueuedTasks method."""
        self.assertEqual(self.threadpool.countQueuedTasks(), 0)

    def test_feedQueue(self):
        """Test feedQueue method."""
        # Setup a return value for the queue.unfinished_tasks attribute access
        self.threadpool.queue = MagicMock()
        self.threadpool.queue.unfinished_tasks = 1
        result = self.threadpool.feedQueue()
        self.assertEqual(result, 1)

    def test_results(self):
        """Test results method."""
        result = self.threadpool.results()
        self.assertIsInstance(result, list)
        
    # ... other test methods ...


class TestThreadPoolWorker(SpiderFootModuleTestCase):
    """Test ThreadPoolWorker."""

    def setUp(self):
        """Set up test case."""
        self.threadpool = MagicMock()
        self.mock_queue = MagicMock()
        self.threadpool.queue = self.mock_queue
        
        from spiderfoot import ThreadPoolWorker
        self.worker = ThreadPoolWorker(self.threadpool)
        
    def test_run(self):
        """Test run method."""
        # Setup mock queue to return a task and then raise StopIteration
        task = MagicMock()
        self.mock_queue.get.side_effect = [task, StopIteration]
        task.fn = MagicMock()
        
        # Patch the sleep function to avoid actual sleeping
        with patch('time.sleep'):
            try:
                self.worker.run()
            except StopIteration:
                # This is expected when the queue is empty
                pass
                
    def test_run_with_exception(self):
        """Test run method with an exception."""
        task = MagicMock()
        task.fn.side_effect = Exception("Test exception")
        self.mock_queue.get.side_effect = [task, StopIteration]
        
        # Patch the sleep function to avoid actual sleeping
        with patch('time.sleep'):
            try:
                self.worker.run()
            except StopIteration:
                # This is expected when the queue is empty
                pass


if __name__ == "__main__":
    unittest.main()
