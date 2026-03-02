"""
Validation Utilities for SpiderFoot

This module provides validation and utility functions shared across
CLI, API, and WebUI components.
"""

from __future__ import annotations

import ipaddress
import os
import sys
import logging
import re
from typing import Any
from spiderfoot.config.constants import DEFAULT_WEB_PORT


class ValidationUtils:
    """Validation and utility functions for SpiderFoot."""

    def __init__(self) -> None:
        """Initialize validation utilities."""
        self.log = logging.getLogger(f"spiderfoot.{__name__}")

    @staticmethod
    def validate_python_version(min_version: tuple[int, int] = (3, 9)) -> None:
        """
        Validate Python version meets minimum requirements.

        Args:
            min_version: Minimum required Python version as tuple

        Raises:
            SystemExit: If Python version is too old
        """
        if sys.version_info < min_version:
            version_str = ".".join(map(str, min_version))
            sys.stderr.write(f"SpiderFoot requires Python {version_str} or higher.\n")
            sys.exit(-1)

    @staticmethod
    def validate_directory_exists(directory: str, name: str = "Directory") -> bool:
        """
        Validate that a directory exists.

        Args:
            directory: Path to directory
            name: Human-readable name for error messages

        Returns:
            True if directory exists, False otherwise
        """
        if not os.path.isdir(directory):
            logging.getLogger("spiderfoot.validation").error(f"{name} not found: {directory}")
            return False
        return True

    @staticmethod
    def validate_file_exists(file_path: str, name: str = "File") -> bool:
        """
        Validate that a file exists.

        Args:
            file_path: Path to file
            name: Human-readable name for error messages

        Returns:
            True if file exists, False otherwise
        """
        if not os.path.isfile(file_path):
            logging.getLogger("spiderfoot.validation").error(f"{name} not found: {file_path}")
            return False
        return True

    @staticmethod
    def parse_host_port(host_port: str, default_host: str = '127.0.0.1',
                       default_port: int = DEFAULT_WEB_PORT) -> tuple[str, int]:
        """
        Parse host:port string into components.

        Args:
            host_port: String in format "host:port"
            default_host: Default host if not specified
            default_port: Default port if not specified

        Returns:
            Tuple of (host, port)

        Raises:
            ValueError: If format is invalid
        """
        if not host_port:
            return default_host, default_port

        if ':' not in host_port:
            raise ValueError(f"Invalid host:port format: {host_port}")

        try:
            host, port_str = host_port.split(':', 1)
            port = int(port_str)

            if port < 1 or port > 65535:
                raise ValueError(f"Port must be between 1 and 65535, got: {port}")

            return host, port

        except ValueError as e:
            raise ValueError(f"Invalid host:port format '{host_port}': {e}")

    @staticmethod
    def validate_scan_name(scan_name: str) -> str:
        """
        Validate and sanitize scan name.

        Args:
            scan_name: Raw scan name

        Returns:
            Sanitized scan name

        Raises:
            ValueError: If scan name is invalid
        """
        if not scan_name or not scan_name.strip():
            raise ValueError("Scan name cannot be empty")

        # Remove dangerous characters but allow spaces and common punctuation
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', scan_name.strip())

        if not sanitized:
            raise ValueError("Scan name contains only invalid characters")

        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100]

        return sanitized

    @staticmethod
    def validate_target(target: str) -> str:
        """
        Validate and sanitize scan target.

        Args:
            target: Raw target string

        Returns:
            Sanitized target

        Raises:
            ValueError: If target is invalid
        """
        if not target or not target.strip():
            raise ValueError("Target cannot be empty")

        sanitized = target.strip()

        # Basic length check
        if len(sanitized) > 500:
            raise ValueError("Target too long (max 500 characters)")

        return sanitized

    # Valid target types accepted by SpiderFootTarget
    _VALID_TARGET_TYPES = frozenset({
        "IP_ADDRESS", "IPV6_ADDRESS", "NETBLOCK_OWNER", "NETBLOCKV6_OWNER",
        "INTERNET_NAME", "EMAILADDR", "HUMAN_NAME", "BGP_AS_OWNER",
        "PHONE_NUMBER", "USERNAME", "BITCOIN_ADDRESS",
    })

    @classmethod
    def validate_target_type(cls, target_type: str) -> str:
        """
        Validate that target_type is one of the accepted scan target types.

        Args:
            target_type: Target type string

        Returns:
            Validated target type

        Raises:
            ValueError: If target type is invalid
        """
        if not target_type or not isinstance(target_type, str):
            raise ValueError("Target type cannot be empty")

        target_type = target_type.strip()

        if target_type not in cls._VALID_TARGET_TYPES:
            raise ValueError(
                f"Invalid target type '{target_type}'. "
                f"Valid types: {sorted(cls._VALID_TARGET_TYPES)}"
            )

        return target_type

    @staticmethod
    def validate_target_value(target_value: str, target_type: str) -> str:
        """
        Validate that a target value is well-formed for its declared type.

        Prevents malformed or dangerous inputs from reaching the module system.

        Args:
            target_value: The target value to validate
            target_type: The declared target type

        Returns:
            Sanitized target value

        Raises:
            ValueError: If target value doesn't match the expected format
        """
        import ipaddress

        if not target_value or not isinstance(target_value, str):
            raise ValueError("Target value cannot be empty")

        value = target_value.strip()

        # Block null bytes and shell metacharacters in ALL target types
        if '\x00' in value:
            raise ValueError("Target value contains null bytes")
        if any(c in value for c in ['|', ';', '`', '$', '{', '}']):
            raise ValueError("Target value contains disallowed shell metacharacters")

        if target_type == "IP_ADDRESS":
            try:
                ip = ipaddress.ip_address(value)
                if isinstance(ip, ipaddress.IPv6Address):
                    raise ValueError(
                        f"Value '{value}' is an IPv6 address, use target type IPV6_ADDRESS"
                    )
            except ValueError as e:
                if "IPv6" in str(e):
                    raise
                raise ValueError(f"Invalid IP address: '{value}'") from None

        elif target_type == "IPV6_ADDRESS":
            try:
                ip = ipaddress.ip_address(value)
                if not isinstance(ip, ipaddress.IPv6Address):
                    raise ValueError(
                        f"Value '{value}' is not an IPv6 address"
                    )
            except ValueError as e:
                if "not an IPv6" in str(e):
                    raise
                raise ValueError(f"Invalid IPv6 address: '{value}'") from None

        elif target_type == "NETBLOCK_OWNER":
            try:
                net = ipaddress.ip_network(value, strict=False)
            except ValueError:
                raise ValueError(f"Invalid network block: '{value}'") from None
            if isinstance(net, ipaddress.IPv6Network):
                raise ValueError(
                    f"Value '{value}' is an IPv6 network, use target type NETBLOCKV6_OWNER"
                )

        elif target_type == "NETBLOCKV6_OWNER":
            try:
                net = ipaddress.ip_network(value, strict=False)
            except ValueError:
                raise ValueError(f"Invalid IPv6 network: '{value}'") from None
            if not isinstance(net, ipaddress.IPv6Network):
                raise ValueError(
                    f"Value '{value}' is not an IPv6 network"
                )

        elif target_type == "INTERNET_NAME":
            # Domain name / hostname validation (RFC 1035)
            stripped = value.strip('"\'')
            if len(stripped) > 253:
                raise ValueError("Domain name too long (max 253 characters)")
            if not re.match(
                r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
                r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$',
                stripped,
            ):
                raise ValueError(f"Invalid domain/hostname: '{stripped}'")

        elif target_type == "EMAILADDR":
            if not re.match(
                r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$',
                value,
            ):
                raise ValueError(f"Invalid email address: '{value}'")

        elif target_type == "PHONE_NUMBER":
            if not re.match(r'^\+?[\d\s\-\(\)]{7,15}$', value):
                raise ValueError(f"Invalid phone number: '{value}'")

        elif target_type == "BGP_AS_OWNER":
            stripped = value.strip()
            if not re.match(r'^\d+$', stripped) or len(stripped) > 10:
                raise ValueError(f"Invalid BGP AS number: '{value}'")

        elif target_type == "BITCOIN_ADDRESS":
            if not re.match(
                r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$',
                value,
            ):
                raise ValueError(f"Invalid Bitcoin address: '{value}'")

        elif target_type == "USERNAME":
            # Usernames: alphanumeric, underscores, dots, at-sign; no paths
            stripped = value.strip('"\'@')
            if not stripped:
                raise ValueError("Username cannot be empty")
            if '/' in stripped or '\\' in stripped:
                raise ValueError(f"Username contains path separators: '{value}'")

        elif target_type == "HUMAN_NAME":
            stripped = value.strip('"\'')
            if not stripped:
                raise ValueError("Human name cannot be empty")
            if not re.match(r'^[a-zA-Z\s\.\-\']+$', stripped):
                raise ValueError(f"Invalid human name: '{value}'")

        return value

    @staticmethod
    def validate_module_list(modules: str | list[str]) -> list[str]:
        """
        Validate and parse module list.

        Args:
            modules: Comma-separated string or list of module names

        Returns:
            List of valid module names
        """
        if isinstance(modules, str):
            module_list = [m.strip() for m in modules.split(',') if m.strip()]
        elif isinstance(modules, list):
            module_list = [str(m).strip() for m in modules if str(m).strip()]
        else:
            return []

        # Filter out empty strings and validate names
        valid_modules = []
        for module in module_list:
            if re.match(r'^[a-zA-Z0-9_]+$', module):
                valid_modules.append(module)
            else:
                logging.getLogger("spiderfoot.validation").warning(f"Invalid module name: {module}")

        return valid_modules

    @staticmethod
    def validate_event_types(event_types: str | list[str]) -> list[str]:
        """
        Validate and parse event types list.

        Args:
            event_types: Comma-separated string or list of event types

        Returns:
            List of valid event types
        """
        if isinstance(event_types, str):
            types_list = [t.strip() for t in event_types.split(',') if t.strip()]
        elif isinstance(event_types, list):
            types_list = [str(t).strip() for t in event_types if str(t).strip()]
        else:
            return []

        # Filter out empty strings and validate format
        valid_types = []
        for event_type in types_list:
            if re.match(r'^[A-Z_][A-Z0-9_]*$', event_type):
                valid_types.append(event_type)
            else:
                logging.getLogger("spiderfoot.validation").warning(f"Invalid event type: {event_type}")

        return valid_types

    @staticmethod
    def validate_output_format(output_format: str) -> str:
        """
        Validate output format.

        Args:
            output_format: Output format string

        Returns:
            Validated output format

        Raises:
            ValueError: If format is invalid
        """
        valid_formats = ['tab', 'csv', 'json', 'xlsx', 'gexf']

        if output_format.lower() not in valid_formats:
            raise ValueError(f"Invalid output format '{output_format}'. Valid formats: {', '.join(valid_formats)}")

        return output_format.lower()

    @staticmethod
    def validate_scan_id(scan_id: str) -> str:
        """
        Validate scan ID format.

        Args:
            scan_id: Scan ID string

        Returns:
            Validated scan ID

        Raises:
            ValueError: If scan ID is invalid
        """
        if not scan_id or not scan_id.strip():
            raise ValueError("Scan ID cannot be empty")

        # Scan IDs should be alphanumeric with possible hyphens/underscores
        sanitized = scan_id.strip()
        if not re.match(r'^[a-zA-Z0-9_-]+$', sanitized):
            raise ValueError(f"Invalid scan ID format: {scan_id}")

        return sanitized

    @staticmethod
    def clean_user_input(input_data: str | list[str]) -> str | list[str]:
        """
        Clean user input by escaping HTML and removing dangerous characters.

        Args:
            input_data: String or list of strings to clean

        Returns:
            Cleaned input data
        """
        import html

        if isinstance(input_data, str):
            cleaned = html.escape(input_data, True)
            cleaned = cleaned.replace("&amp;", "&").replace("&quot;", "\"")
            return cleaned

        elif isinstance(input_data, list):
            cleaned_list = []
            for item in input_data:
                if item:
                    cleaned = html.escape(str(item), True)
                    cleaned = cleaned.replace("&amp;", "&").replace("&quot;", "\"")
                    cleaned_list.append(cleaned)
                else:
                    cleaned_list.append("")
            return cleaned_list

        return input_data

    @staticmethod
    def validate_config_option(key: str, value: Any, config_descriptions: dict[str, str]) -> bool:
        """
        Validate a configuration option.

        Args:
            key: Configuration key
            value: Configuration value
            config_descriptions: Dictionary of valid configuration keys

        Returns:
            True if valid, False otherwise
        """
        if key not in config_descriptions:
            logging.getLogger("spiderfoot.validation").warning(f"Unknown configuration key: {key}")
            return False

        # Basic type validation based on key patterns
        if key.startswith('_') and key.endswith('timeout'):
            try:
                timeout_val = int(value)
                if timeout_val < 0:
                    return False
            except (ValueError, TypeError):
                return False

        elif key.startswith('_') and 'thread' in key:
            try:
                thread_val = int(value)
                if thread_val < 1 or thread_val > 100:
                    return False
            except (ValueError, TypeError):
                return False

        return True

    # ── SSRF-safe URL validation ─────────────────────────────────────

    # Private / link-local / loopback networks that must never be targets
    _PRIVATE_NETWORKS = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),       # link-local
        ipaddress.ip_network("0.0.0.0/8"),             # "this" network
        ipaddress.ip_network("::1/128"),               # IPv6 loopback
        ipaddress.ip_network("fc00::/7"),               # IPv6 ULA
        ipaddress.ip_network("fe80::/10"),             # IPv6 link-local
    ]

    # Allowed URL schemes for outbound webhooks
    _ALLOWED_SCHEMES = {"https", "http"}

    @classmethod
    def validate_url_no_ssrf(
        cls,
        url: str,
        *,
        allow_private: bool = False,
        allowed_schemes: set[str] | None = None,
    ) -> str:
        """
        Validate a URL for safe outbound use (webhooks, callbacks).

        Prevents SSRF by:
        - Restricting to http/https schemes
        - Blocking private/loopback/link-local IP addresses
        - Blocking hostnames that resolve to private IPs
        - Rejecting URLs with credentials embedded
        - Rejecting URLs targeting common cloud metadata endpoints

        Args:
            url: The URL to validate
            allow_private: If True, skip the private-IP check (for testing)
            allowed_schemes: Override the default set of allowed schemes

        Returns:
            The validated URL

        Raises:
            ValueError: If the URL is unsafe
        """
        from urllib.parse import urlparse

        if not url or not isinstance(url, str):
            raise ValueError("URL cannot be empty")

        url = url.strip()

        try:
            parsed = urlparse(url)
        except Exception:
            raise ValueError(f"Malformed URL: '{url}'") from None

        # --- Scheme check ---
        schemes = allowed_schemes or cls._ALLOWED_SCHEMES
        if parsed.scheme not in schemes:
            raise ValueError(
                f"URL scheme '{parsed.scheme}' not allowed. "
                f"Use one of: {sorted(schemes)}"
            )

        # --- Hostname required ---
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL must include a hostname")

        # --- Block embedded credentials ---
        if parsed.username or parsed.password:
            raise ValueError("URL must not contain embedded credentials")

        # --- Block cloud metadata endpoints ---
        _metadata_hosts = {"169.254.169.254", "metadata.google.internal"}
        if hostname.lower() in _metadata_hosts:
            raise ValueError("URL must not target cloud metadata endpoints")

        # --- Resolve hostname and check for private IPs ---
        if not allow_private:
            try:
                ip = ipaddress.ip_address(hostname)
            except ValueError:
                # It's a hostname, not an IP literal — resolve it
                import socket
                try:
                    results = socket.getaddrinfo(hostname, None)
                    ips = {ipaddress.ip_address(r[4][0]) for r in results}
                except (socket.gaierror, OSError):
                    # Cannot resolve — let it through (will fail at connect time)
                    ips = set()
                for ip in ips:
                    if any(ip in net for net in cls._PRIVATE_NETWORKS):
                        raise ValueError(
                            f"URL hostname '{hostname}' resolves to a private IP address"
                        )
            else:
                if any(ip in net for net in cls._PRIVATE_NETWORKS):
                    raise ValueError(
                        f"URL must not target private/loopback address '{hostname}'"
                    )

        return url
