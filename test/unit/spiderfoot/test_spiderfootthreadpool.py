import unittest
from unittest.mock import MagicMock, patch
from spiderfoot.threadpool import SpiderFootThreadPool, ThreadPoolWorker
import queue
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestSpiderFootThreadPool(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        self.pool = SpiderFootThreadPool(threads=5, qsize=10, name='test_pool')
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def test_init(self):
        self.assertEqual(self.pool.threads, 5)
        self.assertEqual(self.pool.qsize, 10)
        self.assertEqual(self.pool.name, 'test_pool')
        self.assertEqual(len(self.pool.pool), 5)
        self.assertIsNone(self.pool.inputThread)
        self.assertFalse(self.pool._stop)

    def test_start(self):
        with patch('spiderfoot.threadpool.ThreadPoolWorker') as mock_worker:
            self.pool.start()
            self.assertEqual(len(self.pool.pool), 5)
            # Check that ThreadPoolWorker was called 5 times (once for each thread)
            self.assertEqual(mock_worker.call_count, 5)

    def test_stop_setter(self):
        with patch('spiderfoot.threadpool.ThreadPoolWorker'):
            self.pool.start()
            self.pool.stop = True
            self.assertTrue(self.pool.stop)
            self.assertTrue(all(t.stop for t in self.pool.pool))

    def test_shutdown(self):
        with patch('spiderfoot.threadpool.ThreadPoolWorker'), \
             patch.object(self.pool, 'results', return_value=[]) as mock_results:
            self.pool.start()
            # Set stop to True to make finished property return True
            self.pool._stop = True
            results = self.pool.shutdown()
            self.assertIsInstance(results, dict)
            self.assertTrue(self.pool.stop)

    def test_submit(self):
        callback = MagicMock()
        callback.__name__ = 'test_callback'
        self.pool.submit(callback, 'arg1', taskName='test_task')
        self.assertEqual(self.pool.countQueuedTasks('test_task'), 1)

    def test_countQueuedTasks(self):
        callback = MagicMock()
        callback.__name__ = 'test_callback'
        self.pool.submit(callback, 'arg1', taskName='test_task')
        self.assertEqual(self.pool.countQueuedTasks('test_task'), 1)

    def test_inputQueue(self):
        queue = self.pool.inputQueue('test_task')
        self.assertIsNotNone(queue)
        self.assertEqual(self.pool.inputQueues['test_task'], queue)

    def test_outputQueue(self):
        queue = self.pool.outputQueue('test_task')
        self.assertIsNotNone(queue)
        self.assertEqual(self.pool.outputQueues['test_task'], queue)

    def test_map(self):
        callback = MagicMock()
        callback.__name__ = 'test_callback'
        iterable = ['a', 'b', 'c']
        
        # Mock threading and other components to avoid daemon thread issues
        with patch('spiderfoot.threadpool.threading.Thread') as mock_thread, \
             patch.object(self.pool, 'start'), \
             patch.object(self.pool, 'feedQueue'), \
             patch.object(self.pool, 'results', return_value=iter(iterable)):
            
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            results = list(self.pool.map(callback, iterable))
            self.assertEqual(results, iterable)
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()

    def test_results(self):
        callback = MagicMock()
        callback.__name__ = 'test_callback'
        
        # Mock the submit method to avoid actually submitting tasks
        with patch.object(self.pool, 'submit'), \
             patch.object(self.pool, 'countQueuedTasks', return_value=0), \
             patch.object(self.pool, 'outputQueue', return_value=MagicMock(get_nowait=MagicMock(side_effect=['result', queue.Empty]))):
            results = list(self.pool.results('test_task', wait=True))
            self.assertEqual(results, ['result'])

    def test_feedQueue(self):
        callback = MagicMock()
        callback.__name__ = 'test_callback'
        iterable = ['a', 'b', 'c']
        self.pool.feedQueue(callback, iterable, (), {})
        self.assertEqual(self.pool.countQueuedTasks('default'), 3)

    def test_finished(self):
        self.pool._stop = True
        self.assertTrue(self.pool.finished)

    def test_enter_exit(self):
        with patch.object(self.pool, 'shutdown') as mock_shutdown:
            with self.pool as p:
                self.assertEqual(p, self.pool)
            mock_shutdown.assert_called_once()


class TestThreadPoolWorker(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        self.pool = MagicMock()
        self.worker = ThreadPoolWorker(pool=self.pool, name='test_worker')
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def test_init(self):
        self.assertEqual(self.worker.pool, self.pool)
        self.assertEqual(self.worker.taskName, "")
        self.assertFalse(self.worker.busy)
        self.assertFalse(self.worker.stop)

    def test_run(self):
        callback = MagicMock()
        mock_queue = MagicMock()
        # First call returns a task, second call raises Empty 
        mock_queue.get_nowait.side_effect = [(callback, (), {}), queue.Empty()]
        self.pool.inputQueues.values.return_value = [mock_queue]
        
        # Use a side effect to stop the worker after one iteration
        original_stop = self.worker.stop
        def stop_after_task():
            self.worker.stop = True
            return callback.return_value
        callback.side_effect = stop_after_task
        
        self.worker.run()
        callback.assert_called_once()

    def test_run_with_exception(self):
        def callback_with_exception(*args, **kwargs):
            # Stop the worker after raising the exception
            self.worker.stop = True
            raise Exception('test exception')
            
        callback = MagicMock(side_effect=callback_with_exception)
        mock_queue = MagicMock()
        # First call returns a task that will raise exception
        mock_queue.get_nowait.side_effect = [(callback, (), {}), queue.Empty()]
        self.pool.inputQueues.values.return_value = [mock_queue]
        
        # Mock the worker's logger directly since it's created in __init__
        mock_logger = MagicMock()
        self.worker.log = mock_logger
        
        self.worker.run()
        # The worker should have logged an error
        mock_logger.error.assert_called_once()

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
