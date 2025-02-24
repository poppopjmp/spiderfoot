import unittest
from unittest.mock import MagicMock, patch
from spiderfoot.threadpool import SpiderFootThreadPool, ThreadPoolWorker


class TestSpiderFootThreadPool(unittest.TestCase):

    def setUp(self):
        self.pool = SpiderFootThreadPool(threads=5, qsize=10, name='test_pool')

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
            self.assertTrue(all(isinstance(t, mock_worker) for t in self.pool.pool))

    def test_stop_setter(self):
        with patch('spiderfoot.threadpool.ThreadPoolWorker') as mock_worker:
            self.pool.start()
            self.pool.stop = True
            self.assertTrue(self.pool.stop)
            self.assertTrue(all(t.stop for t in self.pool.pool))

    def test_shutdown(self):
        with patch('spiderfoot.threadpool.ThreadPoolWorker') as mock_worker:
            self.pool.start()
            results = self.pool.shutdown()
            self.assertIsInstance(results, dict)
            self.assertTrue(self.pool.stop)

    def test_submit(self):
        callback = MagicMock()
        self.pool.submit(callback, 'arg1', taskName='test_task')
        self.assertEqual(self.pool.countQueuedTasks('test_task'), 1)

    def test_countQueuedTasks(self):
        callback = MagicMock()
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
        iterable = ['a', 'b', 'c']
        with patch.object(self.pool, 'results', return_value=iter(iterable)):
            results = list(self.pool.map(callback, iterable))
            self.assertEqual(results, iterable)

    def test_results(self):
        callback = MagicMock()
        self.pool.submit(callback, 'arg1', taskName='test_task')
        with patch.object(self.pool, 'outputQueue', return_value=MagicMock(get_nowait=MagicMock(side_effect=['result', queue.Empty]))):
            results = list(self.pool.results('test_task', wait=True))
            self.assertEqual(results, ['result'])

    def test_feedQueue(self):
        callback = MagicMock()
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


class TestThreadPoolWorker(unittest.TestCase):

    def setUp(self):
        self.pool = MagicMock()
        self.worker = ThreadPoolWorker(pool=self.pool, name='test_worker')

    def test_init(self):
        self.assertEqual(self.worker.pool, self.pool)
        self.assertEqual(self.worker.taskName, "")
        self.assertFalse(self.worker.busy)
        self.assertFalse(self.worker.stop)

    def test_run(self):
        callback = MagicMock()
        self.pool.inputQueues.values.return_value = [MagicMock(get_nowait=MagicMock(side_effect=[(callback, (), {}), queue.Empty]))]
        self.worker.run()
        callback.assert_called_once()

    def test_run_with_exception(self):
        callback = MagicMock(side_effect=Exception('test exception'))
        self.pool.inputQueues.values.return_value = [MagicMock(get_nowait=MagicMock(side_effect=[(callback, (), {}), queue.Empty]))]
        with patch('spiderfoot.threadpool.logging.getLogger') as mock_logger:
            self.worker.run()
            mock_logger.return_value.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
