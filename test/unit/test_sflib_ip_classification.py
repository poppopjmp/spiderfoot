"""Adversarial tests for SpiderFoot's IP scope/SSRF classification helpers.

isValidLocalOrLoopbackIp and isPublicIpAddress determine scan scope and whether
an address is publicly routable — bugs here are silent and security-relevant
(scope creep / SSRF). Two real defects were fixed and are guarded here:

  * isValidLocalOrLoopbackIp probed a `is_private` attribute removed in
    netaddr 1.x, so it returned False for *every* RFC1918 private address
    (only loopback was detected) — private IPs leaked through as public.
  * isPublicIpAddress did not exclude link-local addresses, so 169.254.169.254
    (the cloud metadata endpoint) and fe80::/10 were classified as public.
"""
from __future__ import annotations

import pytest

from spiderfoot.sflib.helpers import (
    isValidLocalOrLoopbackIp,
    isPublicIpAddress,
)


class TestIsValidLocalOrLoopbackIp:
    @pytest.mark.parametrize("ip", [
        "10.0.0.1", "10.255.255.255",
        "192.168.0.1", "192.168.1.254",
        "172.16.0.1", "172.31.255.255",
        "127.0.0.1", "::1",
        "169.254.0.1", "169.254.169.254",  # link-local incl. cloud metadata
        "fd00::1",                          # IPv6 unique-local
        "fe80::1",                          # IPv6 link-local
    ])
    def test_local_addresses_are_local(self, ip):
        assert isValidLocalOrLoopbackIp(ip) is True

    @pytest.mark.parametrize("ip", [
        "8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:2800:220:1::1",
    ])
    def test_public_addresses_are_not_local(self, ip):
        assert isValidLocalOrLoopbackIp(ip) is False

    @pytest.mark.parametrize("bad", ["", "not-an-ip", "999.999.999.999", "example.com"])
    def test_invalid_input_is_false(self, bad):
        assert isValidLocalOrLoopbackIp(bad) is False

    def test_172_16_boundary_private_vs_public(self):
        # 172.16/12 is private; 172.32.x is public.
        assert isValidLocalOrLoopbackIp("172.16.5.5") is True
        assert isValidLocalOrLoopbackIp("172.32.5.5") is False


class TestIsPublicIpAddress:
    @pytest.mark.parametrize("ip", [
        "8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:2800:220:1::1",
    ])
    def test_public_addresses(self, ip):
        assert isPublicIpAddress(ip) is True

    @pytest.mark.parametrize("ip", [
        "10.0.0.1", "192.168.1.1", "172.16.0.1",   # private
        "127.0.0.1", "::1",                          # loopback
        "169.254.169.254", "169.254.0.1",            # IPv4 link-local (metadata)
        "fe80::1",                                   # IPv6 link-local
        "fd00::1",                                   # IPv6 unique-local
        "224.0.0.1",                                 # multicast
        "0.0.0.0",                                   # unspecified/reserved
    ])
    def test_non_public_addresses(self, ip):
        assert isPublicIpAddress(ip) is False

    def test_cloud_metadata_endpoint_is_not_public(self):
        # Regression: this SSRF-relevant address must never be "public".
        assert isPublicIpAddress("169.254.169.254") is False

    @pytest.mark.parametrize("bad", ["", "not-an-ip", None, 12345])
    def test_invalid_input_is_false(self, bad):
        assert isPublicIpAddress(bad) is False
