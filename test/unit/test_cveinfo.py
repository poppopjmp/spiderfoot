"""Unit tests for SpiderFoot.cveInfo() — Cycle 17.

Tests CIRCL and NIST parsing logic, CVSS scoring, source fallback,
and error handling using mocked fetchUrl responses.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock

from spiderfoot.sflib.core import SpiderFoot


def _sf():
    return SpiderFoot({"__logging": False, "_debug": False})


# --- CIRCL response fixtures ---

CIRCL_CRITICAL = {
    "id": "CVE-2021-44228",
    "cvss": 10.0,
    "summary": "Apache Log4j2 RCE via JNDI lookup",
}

CIRCL_HIGH = {
    "id": "CVE-2023-12345",
    "cvss": 8.5,
    "summary": "Buffer overflow in libfoo",
}

CIRCL_MEDIUM = {
    "id": "CVE-2022-9999",
    "cvss": 5.5,
    "summary": "Information disclosure via timing attack",
}

CIRCL_LOW = {
    "id": "CVE-2020-1111",
    "cvss": 2.0,
    "summary": "Minor info leak in debug endpoint",
}

CIRCL_NO_SCORE = {
    "id": "CVE-2019-0001",
    "summary": "No CVSS score available",
}

# --- NIST response fixtures ---

NIST_RESPONSE_V31 = {
    "vulnerabilities": [{
        "cve": {
            "id": "CVE-2023-44487",
            "metrics": {
                "cvssMetricV31": [{
                    "cvssData": {"baseScore": 7.5}
                }]
            },
            "descriptions": [
                {"lang": "en", "value": "HTTP/2 Rapid Reset Attack"},
                {"lang": "es", "value": "Ataque de reinicio rapido HTTP/2"},
            ],
        }
    }]
}

NIST_RESPONSE_V2_ONLY = {
    "vulnerabilities": [{
        "cve": {
            "id": "CVE-2014-0160",
            "metrics": {
                "cvssMetricV2": [{
                    "cvssData": {"baseScore": 5.0}
                }]
            },
            "descriptions": [
                {"lang": "en", "value": "Heartbleed - TLS heartbeat extension"},
            ],
        }
    }]
}

NIST_EMPTY = {"vulnerabilities": []}


class TestCveInfoCircl(unittest.TestCase):
    """Test cveInfo with CIRCL source."""

    def _mock_fetch(self, response_data, code="200"):
        """Return a mock fetchUrl that returns the given data."""
        return lambda *a, **kw: {
            "code": code,
            "content": json.dumps(response_data),
        }

    @patch.object(SpiderFoot, "fetchUrl")
    def test_circl_critical_score(self, mock_fetch):
        mock_fetch.return_value = {"code": "200", "content": json.dumps(CIRCL_CRITICAL)}
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-2021-44228", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_CRITICAL")
        self.assertIn("CVE-2021-44228", text)
        self.assertIn("10.0", text)
        self.assertIn("Log4j2", text)

    @patch.object(SpiderFoot, "fetchUrl")
    def test_circl_high_score(self, mock_fetch):
        mock_fetch.return_value = {"code": "200", "content": json.dumps(CIRCL_HIGH)}
        sf = _sf()
        event_type, _ = sf.cveInfo("CVE-2023-12345", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_HIGH")

    @patch.object(SpiderFoot, "fetchUrl")
    def test_circl_medium_score(self, mock_fetch):
        mock_fetch.return_value = {"code": "200", "content": json.dumps(CIRCL_MEDIUM)}
        sf = _sf()
        event_type, _ = sf.cveInfo("CVE-2022-9999", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_MEDIUM")

    @patch.object(SpiderFoot, "fetchUrl")
    def test_circl_low_score(self, mock_fetch):
        mock_fetch.return_value = {"code": "200", "content": json.dumps(CIRCL_LOW)}
        sf = _sf()
        event_type, _ = sf.cveInfo("CVE-2020-1111", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_LOW")

    @patch.object(SpiderFoot, "fetchUrl")
    def test_circl_no_cvss_returns_general(self, mock_fetch):
        mock_fetch.return_value = {"code": "200", "content": json.dumps(CIRCL_NO_SCORE)}
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-2019-0001", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_GENERAL")
        self.assertIn("CVE-2019-0001", text)

    @patch.object(SpiderFoot, "fetchUrl")
    def test_circl_http_error_falls_through(self, mock_fetch):
        mock_fetch.return_value = {"code": "404", "content": ""}
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-9999-0000", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_GENERAL")
        self.assertIn("Unknown", text)

    @patch.object(SpiderFoot, "fetchUrl")
    def test_circl_exception_falls_through(self, mock_fetch):
        mock_fetch.side_effect = ConnectionError("timeout")
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-9999-0000", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_GENERAL")
        self.assertIn("Unknown", text)


class TestCveInfoNist(unittest.TestCase):
    """Test cveInfo with NIST source."""

    @patch.object(SpiderFoot, "fetchUrl")
    def test_nist_v31_high_score(self, mock_fetch):
        mock_fetch.return_value = {"code": "200", "content": json.dumps(NIST_RESPONSE_V31)}
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-2023-44487", sources="nist")
        self.assertEqual(event_type, "VULNERABILITY_CVE_HIGH")
        self.assertIn("Rapid Reset", text)

    @patch.object(SpiderFoot, "fetchUrl")
    def test_nist_v2_fallback(self, mock_fetch):
        mock_fetch.return_value = {"code": "200", "content": json.dumps(NIST_RESPONSE_V2_ONLY)}
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-2014-0160", sources="nist")
        self.assertEqual(event_type, "VULNERABILITY_CVE_MEDIUM")
        self.assertIn("Heartbleed", text)

    @patch.object(SpiderFoot, "fetchUrl")
    def test_nist_empty_vulns_falls_through(self, mock_fetch):
        mock_fetch.return_value = {"code": "200", "content": json.dumps(NIST_EMPTY)}
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-0000-0000", sources="nist")
        self.assertEqual(event_type, "VULNERABILITY_GENERAL")
        self.assertIn("Unknown", text)

    @patch.object(SpiderFoot, "fetchUrl")
    def test_nist_http_error_falls_through(self, mock_fetch):
        mock_fetch.return_value = {"code": "503", "content": ""}
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-0000-0000", sources="nist")
        self.assertEqual(event_type, "VULNERABILITY_GENERAL")


class TestCveInfoFallback(unittest.TestCase):
    """Test source fallback behavior."""

    @patch.object(SpiderFoot, "fetchUrl")
    def test_circl_fails_nist_succeeds(self, mock_fetch):
        """When CIRCL returns error, falls through to NIST."""
        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            if "circl" in url:
                return {"code": "500", "content": ""}
            else:
                return {"code": "200", "content": json.dumps(NIST_RESPONSE_V31)}

        mock_fetch.side_effect = side_effect
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-2023-44487", sources="circl,nist")
        self.assertEqual(event_type, "VULNERABILITY_CVE_HIGH")
        self.assertEqual(call_count[0], 2)

    @patch.object(SpiderFoot, "fetchUrl")
    def test_all_sources_fail(self, mock_fetch):
        mock_fetch.return_value = {"code": "500", "content": ""}
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-0000-0000", sources="circl,nist")
        self.assertEqual(event_type, "VULNERABILITY_GENERAL")
        self.assertIn("Unknown", text)

    @patch.object(SpiderFoot, "fetchUrl")
    def test_unknown_source_ignored(self, mock_fetch):
        mock_fetch.return_value = {"code": "500", "content": ""}
        sf = _sf()
        event_type, text = sf.cveInfo("CVE-0000-0000", sources="invalid_source")
        self.assertEqual(event_type, "VULNERABILITY_GENERAL")
        mock_fetch.assert_not_called()

    @patch.object(SpiderFoot, "fetchUrl")
    def test_nist_only_source(self, mock_fetch):
        mock_fetch.return_value = {"code": "200", "content": json.dumps(NIST_RESPONSE_V31)}
        sf = _sf()
        event_type, _ = sf.cveInfo("CVE-2023-44487", sources="nist")
        self.assertEqual(event_type, "VULNERABILITY_CVE_HIGH")
        # Should only call fetchUrl once (NIST only)
        self.assertEqual(mock_fetch.call_count, 1)


class TestCveRatingBoundaries(unittest.TestCase):
    """Test CVSS score boundary values via cveInfo."""

    def _circl_response(self, score):
        return {"code": "200", "content": json.dumps({
            "cvss": score, "summary": "test"
        })}

    @patch.object(SpiderFoot, "fetchUrl")
    def test_score_0_is_low(self, mock_fetch):
        mock_fetch.return_value = self._circl_response(0.0)
        event_type, _ = _sf().cveInfo("CVE-0000-0001", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_LOW")

    @patch.object(SpiderFoot, "fetchUrl")
    def test_score_3_9_is_low(self, mock_fetch):
        mock_fetch.return_value = self._circl_response(3.9)
        event_type, _ = _sf().cveInfo("CVE-0000-0002", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_LOW")

    @patch.object(SpiderFoot, "fetchUrl")
    def test_score_4_0_is_medium(self, mock_fetch):
        mock_fetch.return_value = self._circl_response(4.0)
        event_type, _ = _sf().cveInfo("CVE-0000-0003", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_MEDIUM")

    @patch.object(SpiderFoot, "fetchUrl")
    def test_score_6_9_is_medium(self, mock_fetch):
        mock_fetch.return_value = self._circl_response(6.9)
        event_type, _ = _sf().cveInfo("CVE-0000-0004", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_MEDIUM")

    @patch.object(SpiderFoot, "fetchUrl")
    def test_score_7_0_is_high(self, mock_fetch):
        mock_fetch.return_value = self._circl_response(7.0)
        event_type, _ = _sf().cveInfo("CVE-0000-0005", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_HIGH")

    @patch.object(SpiderFoot, "fetchUrl")
    def test_score_8_9_is_high(self, mock_fetch):
        mock_fetch.return_value = self._circl_response(8.9)
        event_type, _ = _sf().cveInfo("CVE-0000-0006", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_HIGH")

    @patch.object(SpiderFoot, "fetchUrl")
    def test_score_9_0_is_critical(self, mock_fetch):
        mock_fetch.return_value = self._circl_response(9.0)
        event_type, _ = _sf().cveInfo("CVE-0000-0007", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_CRITICAL")

    @patch.object(SpiderFoot, "fetchUrl")
    def test_score_10_is_critical(self, mock_fetch):
        mock_fetch.return_value = self._circl_response(10.0)
        event_type, _ = _sf().cveInfo("CVE-0000-0008", sources="circl")
        self.assertEqual(event_type, "VULNERABILITY_CVE_CRITICAL")


if __name__ == "__main__":
    unittest.main()
