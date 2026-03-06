"""Tests for network.getSession() thread-local session reuse — Cycle 16.

Validates that getSession() returns a cached session per-thread,
closeSession() clears it, and fetchUrl() uses the session correctly.
"""
from __future__ import annotations

import threading
import unittest

from spiderfoot.sflib.network import getSession, closeSession, fetchUrl


class TestGetSessionReuse(unittest.TestCase):
    """getSession() must return the same session within one thread."""

    def tearDown(self):
        closeSession()

    def test_same_session_reused(self):
        s1 = getSession()
        s2 = getSession()
        self.assertIs(s1, s2)

    def test_session_has_adapters(self):
        s = getSession()
        adapters = s.adapters
        self.assertIn("http://", adapters)
        self.assertIn("https://", adapters)

    def test_close_session_clears_cache(self):
        s1 = getSession()
        closeSession()
        s2 = getSession()
        self.assertIsNot(s1, s2)


class TestGetSessionThreadIsolation(unittest.TestCase):
    """Each thread must get its own session instance."""

    def test_different_threads_get_different_sessions(self):
        sessions = {}
        barrier = threading.Barrier(2)

        def worker(name):
            s = getSession()
            sessions[name] = id(s)
            barrier.wait()
            closeSession()

        t1 = threading.Thread(target=worker, args=("a",))
        t2 = threading.Thread(target=worker, args=("b",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertNotEqual(sessions["a"], sessions["b"])


class TestFetchUrl(unittest.TestCase):
    """fetchUrl() basic validation (no network calls)."""

    def tearDown(self):
        closeSession()

    def test_invalid_scheme_returns_none(self):
        result = fetchUrl("ftp://example.com/file.txt")
        self.assertIsNone(result)

    def test_empty_url_returns_none(self):
        result = fetchUrl("")
        self.assertIsNone(result)

    def test_non_string_returns_none(self):
        result = fetchUrl(123)
        self.assertIsNone(result)

    def test_valid_url_returns_dict_with_keys(self):
        """fetchUrl with a real URL returns a dict with standard keys.

        This hits the network — the request may fail, but the dict
        structure should still be returned.
        """
        result = fetchUrl("https://httpbin.org/status/200", timeout=5)
        self.assertIsInstance(result, dict)
        self.assertIn("code", result)
        self.assertIn("content", result)
        self.assertIn("headers", result)
        self.assertIn("realurl", result)

    def test_fetchUrl_reuses_session(self):
        """Two consecutive fetchUrl calls should use the same session."""
        s_before = getSession()
        fetchUrl("https://httpbin.org/status/200", timeout=5)
        s_after = getSession()
        self.assertIs(s_before, s_after)


if __name__ == "__main__":
    unittest.main()
