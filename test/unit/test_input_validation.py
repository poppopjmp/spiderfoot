"""
Tests for Cycle 44 — Input Validation for Scan Targets

Validates that ValidationUtils correctly accepts well-formed target values
and rejects malformed / malicious inputs for all 11 target types.
"""

import pytest
from spiderfoot.core.validation import ValidationUtils


# ---------------------------------------------------------------------------
# validate_target_type
# ---------------------------------------------------------------------------

class TestValidateTargetType:
    """Tests for validate_target_type()."""

    @pytest.mark.parametrize("tt", [
        "IP_ADDRESS", "IPV6_ADDRESS", "NETBLOCK_OWNER", "NETBLOCKV6_OWNER",
        "INTERNET_NAME", "EMAILADDR", "HUMAN_NAME", "BGP_AS_OWNER",
        "PHONE_NUMBER", "USERNAME", "BITCOIN_ADDRESS",
    ])
    def test_valid_target_types(self, tt):
        assert ValidationUtils.validate_target_type(tt) == tt

    def test_invalid_target_type(self):
        with pytest.raises(ValueError, match="Invalid target type"):
            ValidationUtils.validate_target_type("NOT_A_TYPE")

    def test_empty_target_type(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            ValidationUtils.validate_target_type("")

    def test_none_target_type(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            ValidationUtils.validate_target_type(None)

    def test_strips_whitespace(self):
        assert ValidationUtils.validate_target_type("  IP_ADDRESS  ") == "IP_ADDRESS"


# ---------------------------------------------------------------------------
# validate_target_value — IP_ADDRESS
# ---------------------------------------------------------------------------

class TestValidateIPAddress:
    """Tests for IP_ADDRESS validation."""

    @pytest.mark.parametrize("ip", [
        "1.2.3.4", "10.0.0.1", "192.168.1.1", "255.255.255.255", "0.0.0.0",
    ])
    def test_valid_ipv4(self, ip):
        assert ValidationUtils.validate_target_value(ip, "IP_ADDRESS") == ip

    def test_rejects_ipv6_as_ipv4(self):
        with pytest.raises(ValueError, match="IPv6"):
            ValidationUtils.validate_target_value("::1", "IP_ADDRESS")

    @pytest.mark.parametrize("bad", [
        "999.999.999.999", "abc", "1.2.3", "1.2.3.4.5", "",
    ])
    def test_rejects_invalid_ipv4(self, bad):
        with pytest.raises(ValueError):
            ValidationUtils.validate_target_value(bad, "IP_ADDRESS")


# ---------------------------------------------------------------------------
# validate_target_value — IPV6_ADDRESS
# ---------------------------------------------------------------------------

class TestValidateIPv6Address:
    """Tests for IPV6_ADDRESS validation."""

    @pytest.mark.parametrize("ip", [
        "::1", "fe80::1", "2001:db8::1", "::ffff:192.0.2.1",
    ])
    def test_valid_ipv6(self, ip):
        assert ValidationUtils.validate_target_value(ip, "IPV6_ADDRESS") == ip

    def test_rejects_ipv4_as_ipv6(self):
        with pytest.raises(ValueError, match="not an IPv6"):
            ValidationUtils.validate_target_value("1.2.3.4", "IPV6_ADDRESS")


# ---------------------------------------------------------------------------
# validate_target_value — NETBLOCK_OWNER
# ---------------------------------------------------------------------------

class TestValidateNetblock:
    """Tests for NETBLOCK_OWNER validation."""

    @pytest.mark.parametrize("net", [
        "192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12",
    ])
    def test_valid_netblock(self, net):
        assert ValidationUtils.validate_target_value(net, "NETBLOCK_OWNER") == net

    def test_rejects_ipv6_netblock(self):
        with pytest.raises(ValueError, match="IPv6"):
            ValidationUtils.validate_target_value("2001:db8::/32", "NETBLOCK_OWNER")

    def test_rejects_garbage(self):
        with pytest.raises(ValueError, match="Invalid network"):
            ValidationUtils.validate_target_value("not-a-cidr", "NETBLOCK_OWNER")


# ---------------------------------------------------------------------------
# validate_target_value — NETBLOCKV6_OWNER
# ---------------------------------------------------------------------------

class TestValidateNetblockV6:
    """Tests for NETBLOCKV6_OWNER validation."""

    def test_valid_ipv6_netblock(self):
        result = ValidationUtils.validate_target_value("2001:db8::/32", "NETBLOCKV6_OWNER")
        assert result == "2001:db8::/32"

    def test_rejects_ipv4_netblock(self):
        with pytest.raises(ValueError, match="not an IPv6"):
            ValidationUtils.validate_target_value("10.0.0.0/8", "NETBLOCKV6_OWNER")


# ---------------------------------------------------------------------------
# validate_target_value — INTERNET_NAME
# ---------------------------------------------------------------------------

class TestValidateInternetName:
    """Tests for INTERNET_NAME validation."""

    @pytest.mark.parametrize("domain", [
        "example.com", "sub.example.com", "my-domain.org", "a.b.c.d.e.com",
        "localhost",
    ])
    def test_valid_domains(self, domain):
        assert ValidationUtils.validate_target_value(domain, "INTERNET_NAME") == domain

    @pytest.mark.parametrize("bad", [
        "-bad.com", "bad-.com", ".bad", "bad domain.com",
    ])
    def test_rejects_invalid_domains(self, bad):
        with pytest.raises(ValueError, match="Invalid domain"):
            ValidationUtils.validate_target_value(bad, "INTERNET_NAME")

    def test_rejects_overlong_domain(self):
        domain = "a" * 254 + ".com"
        with pytest.raises(ValueError, match="too long"):
            ValidationUtils.validate_target_value(domain, "INTERNET_NAME")


# ---------------------------------------------------------------------------
# validate_target_value — EMAILADDR
# ---------------------------------------------------------------------------

class TestValidateEmail:
    """Tests for EMAILADDR validation."""

    @pytest.mark.parametrize("email", [
        "user@example.com", "test.user@sub.domain.org", "a+b@c.io",
    ])
    def test_valid_emails(self, email):
        assert ValidationUtils.validate_target_value(email, "EMAILADDR") == email

    @pytest.mark.parametrize("bad", [
        "not-an-email", "@missing.com", "user@", "user@.com",
    ])
    def test_rejects_bad_emails(self, bad):
        with pytest.raises(ValueError, match="Invalid email"):
            ValidationUtils.validate_target_value(bad, "EMAILADDR")


# ---------------------------------------------------------------------------
# validate_target_value — PHONE_NUMBER
# ---------------------------------------------------------------------------

class TestValidatePhoneNumber:
    """Tests for PHONE_NUMBER validation."""

    @pytest.mark.parametrize("phone", [
        "+12125551234", "+44 20 7946 0958", "212-555-1234", "2125551234",
    ])
    def test_valid_phone_numbers(self, phone):
        assert ValidationUtils.validate_target_value(phone, "PHONE_NUMBER") == phone

    def test_rejects_too_short(self):
        with pytest.raises(ValueError, match="Invalid phone"):
            ValidationUtils.validate_target_value("123", "PHONE_NUMBER")


# ---------------------------------------------------------------------------
# validate_target_value — BGP_AS_OWNER
# ---------------------------------------------------------------------------

class TestValidateBGPAS:
    """Tests for BGP_AS_OWNER validation."""

    @pytest.mark.parametrize("asn", ["15169", "1", "396982"])
    def test_valid_asn(self, asn):
        assert ValidationUtils.validate_target_value(asn, "BGP_AS_OWNER") == asn

    @pytest.mark.parametrize("bad", ["notanumber", "-1", "12345678901"])
    def test_rejects_invalid_asn(self, bad):
        with pytest.raises(ValueError, match="Invalid BGP"):
            ValidationUtils.validate_target_value(bad, "BGP_AS_OWNER")


# ---------------------------------------------------------------------------
# validate_target_value — BITCOIN_ADDRESS
# ---------------------------------------------------------------------------

class TestValidateBitcoin:
    """Tests for BITCOIN_ADDRESS validation."""

    @pytest.mark.parametrize("addr", [
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
    ])
    def test_valid_bitcoin(self, addr):
        assert ValidationUtils.validate_target_value(addr, "BITCOIN_ADDRESS") == addr

    @pytest.mark.parametrize("bad", ["2xxxxx", "bc1", "not-a-btc-address"])
    def test_rejects_invalid_bitcoin(self, bad):
        with pytest.raises(ValueError, match="Invalid Bitcoin"):
            ValidationUtils.validate_target_value(bad, "BITCOIN_ADDRESS")


# ---------------------------------------------------------------------------
# validate_target_value — USERNAME
# ---------------------------------------------------------------------------

class TestValidateUsername:
    """Tests for USERNAME validation."""

    def test_valid_username(self):
        ValidationUtils.validate_target_value("johndoe", "USERNAME")

    def test_rejects_path_separators(self):
        with pytest.raises(ValueError, match="path separators"):
            ValidationUtils.validate_target_value("../../etc/passwd", "USERNAME")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            ValidationUtils.validate_target_value("", "USERNAME")


# ---------------------------------------------------------------------------
# validate_target_value — HUMAN_NAME
# ---------------------------------------------------------------------------

class TestValidateHumanName:
    """Tests for HUMAN_NAME validation."""

    @pytest.mark.parametrize("name", [
        "John Doe", "Mary-Jane Watson", "O'Brien", "J. Smith",
    ])
    def test_valid_names(self, name):
        assert ValidationUtils.validate_target_value(name, "HUMAN_NAME") == name

    def test_rejects_numeric_name(self):
        with pytest.raises(ValueError, match="Invalid human name"):
            ValidationUtils.validate_target_value("12345", "HUMAN_NAME")


# ---------------------------------------------------------------------------
# Cross-cutting security: shell metacharacters & null bytes
# ---------------------------------------------------------------------------

class TestSecurityGuards:
    """Ensure dangerous characters are blocked regardless of target type."""

    @pytest.mark.parametrize("value", [
        "1.2.3.4\x00 extra",
        "1.2.3.4; rm -rf /",
        "1.2.3.4 | cat /etc/passwd",
        "$(whoami).evil.com",
        "foo`id`bar",
        "test{one,two}",
    ])
    def test_rejects_injection_in_ip(self, value):
        with pytest.raises(ValueError):
            ValidationUtils.validate_target_value(value, "IP_ADDRESS")

    def test_null_byte_in_domain(self):
        with pytest.raises(ValueError, match="null bytes"):
            ValidationUtils.validate_target_value("example\x00.com", "INTERNET_NAME")

    def test_pipe_in_email(self):
        with pytest.raises(ValueError, match="metacharacters"):
            ValidationUtils.validate_target_value("user|bad@evil.com", "EMAILADDR")


# ---------------------------------------------------------------------------
# validate_target (original basic checks)
# ---------------------------------------------------------------------------

class TestValidateTarget:
    """Existing validate_target should still work."""

    def test_strips_whitespace(self):
        assert ValidationUtils.validate_target("  example.com  ") == "example.com"

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            ValidationUtils.validate_target("")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            ValidationUtils.validate_target("a" * 501)
