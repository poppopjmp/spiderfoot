"""
Entity and IOC extractor — finds security-relevant entities in text.

Extracts:
  - IP addresses (v4/v6)
  - Domain names
  - Email addresses
  - URLs
  - File hashes (MD5, SHA1, SHA256)
  - Phone numbers
  - Cryptocurrency addresses (Bitcoin, Ethereum)
  - Credit card numbers
  - AWS keys
  - CVE identifiers
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set

logger = logging.getLogger("sf.enrichment.extractor")


@dataclass
class ExtractionResult:
    """Container for all extracted entities from text."""

    ip_v4: List[str] = field(default_factory=list)
    ip_v6: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    md5_hashes: List[str] = field(default_factory=list)
    sha1_hashes: List[str] = field(default_factory=list)
    sha256_hashes: List[str] = field(default_factory=list)
    phone_numbers: List[str] = field(default_factory=list)
    cve_ids: List[str] = field(default_factory=list)
    bitcoin_addresses: List[str] = field(default_factory=list)
    ethereum_addresses: List[str] = field(default_factory=list)
    aws_keys: List[str] = field(default_factory=list)
    credit_cards: List[str] = field(default_factory=list)
    custom: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def total_entities(self) -> int:
        return sum(
            len(v)
            for v in [
                self.ip_v4, self.ip_v6, self.domains, self.emails,
                self.urls, self.md5_hashes, self.sha1_hashes,
                self.sha256_hashes, self.phone_numbers, self.cve_ids,
                self.bitcoin_addresses, self.ethereum_addresses,
                self.aws_keys, self.credit_cards,
            ]
        ) + sum(len(v) for v in self.custom.values())

    def to_dict(self) -> Dict:
        """Convert to dictionary, excluding empty lists."""
        result = {}
        for key, val in self.__dict__.items():
            if isinstance(val, list) and val:
                result[key] = val
            elif isinstance(val, dict) and val:
                result[key] = val
        return result


# Pre-compiled regex patterns
_PATTERNS = {
    "ip_v4": re.compile(
        r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
    ),
    "ip_v6": re.compile(
        r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'
        r'|\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b'
        r'|\b::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}\b'
    ),
    "email": re.compile(
        r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
    ),
    "url": re.compile(
        r'https?://[^\s<>"\')\]]+', re.IGNORECASE
    ),
    "domain": re.compile(
        r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+(?:com|net|org|io|dev|co|uk|de|fr|ru|cn|info|biz|gov|edu|mil|int)\b',
        re.IGNORECASE,
    ),
    "md5": re.compile(r'\b[0-9a-fA-F]{32}\b'),
    "sha1": re.compile(r'\b[0-9a-fA-F]{40}\b'),
    "sha256": re.compile(r'\b[0-9a-fA-F]{64}\b'),
    "phone": re.compile(
        r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b'
    ),
    "cve": re.compile(r'\bCVE-\d{4}-\d{4,7}\b', re.IGNORECASE),
    "bitcoin": re.compile(r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b'),
    "ethereum": re.compile(r'\b0x[0-9a-fA-F]{40}\b'),
    "aws_key": re.compile(r'\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b'),
    "credit_card": re.compile(
        r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'
    ),
}

# Common false-positive domains to skip
_DOMAIN_SKIPLIST = {
    "example.com", "example.org", "example.net",
    "localhost", "test.com", "test.local",
}

# Common IPs to skip
_IP_SKIPLIST = {"127.0.0.1", "0.0.0.0", "255.255.255.255"}


class EntityExtractor:
    """Extracts security-relevant entities from text using regex patterns."""

    def __init__(self, skip_private_ips: bool = True):
        self.skip_private_ips = skip_private_ips

    def extract(self, text: str) -> ExtractionResult:
        """
        Extract all entities from the given text.

        Args:
            text: Input text to scan

        Returns:
            ExtractionResult with all found entities
        """
        result = ExtractionResult()

        if not text:
            return result

        # Extract SHA-256 first (longest hash), then SHA-1, then MD5
        # to avoid false matches between hash types
        sha256_matches = set(_PATTERNS["sha256"].findall(text))
        sha1_matches = set(_PATTERNS["sha1"].findall(text)) - sha256_matches
        # MD5 candidates minus those that are prefixes of longer hashes
        md5_candidates = set(_PATTERNS["md5"].findall(text))
        md5_matches = set()
        for m in md5_candidates:
            if not any(m in s for s in sha1_matches | sha256_matches):
                md5_matches.add(m)

        result.sha256_hashes = sorted(sha256_matches)
        result.sha1_hashes = sorted(sha1_matches)
        result.md5_hashes = sorted(md5_matches)

        # URLs
        result.urls = sorted(set(_PATTERNS["url"].findall(text)))

        # Emails
        result.emails = sorted(set(_PATTERNS["email"].findall(text)))

        # IPs
        ipv4_matches = set(_PATTERNS["ip_v4"].findall(text)) - _IP_SKIPLIST
        if self.skip_private_ips:
            ipv4_matches = {
                ip for ip in ipv4_matches if not self._is_private_ip(ip)
            }
        result.ip_v4 = sorted(ipv4_matches)
        result.ip_v6 = sorted(set(_PATTERNS["ip_v6"].findall(text)))

        # Domains (filter out emails and known false positives)
        email_domains = {e.split("@")[1].lower() for e in result.emails}
        domains = set()
        for d in _PATTERNS["domain"].findall(text):
            dl = d.lower()
            if dl not in _DOMAIN_SKIPLIST and dl not in email_domains:
                domains.add(dl)
        result.domains = sorted(domains)

        # CVEs
        result.cve_ids = sorted(set(m.upper() for m in _PATTERNS["cve"].findall(text)))

        # Phone numbers (basic, may have false positives)
        phones = _PATTERNS["phone"].findall(text)
        result.phone_numbers = sorted(set(p.strip() for p in phones if len(p.strip()) >= 7))

        # Crypto
        result.bitcoin_addresses = sorted(set(_PATTERNS["bitcoin"].findall(text)))
        result.ethereum_addresses = sorted(set(_PATTERNS["ethereum"].findall(text)))

        # AWS keys
        result.aws_keys = sorted(set(_PATTERNS["aws_key"].findall(text)))

        # Credit cards
        result.credit_cards = sorted(set(_PATTERNS["credit_card"].findall(text)))

        return result

    @staticmethod
    def _is_private_ip(ip: str) -> bool:
        """Check if IPv4 address is in a private range."""
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            a, b = int(parts[0]), int(parts[1])
        except ValueError:
            return False

        # 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16
        return (
            a == 10
            or (a == 172 and 16 <= b <= 31)
            or (a == 192 and b == 168)
            or (a == 169 and b == 254)
        )
