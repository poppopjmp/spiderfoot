"""
DnsService — Standalone DNS resolution service.

Extracted from the SpiderFoot god object (core.py + network.py) to provide
a clean, injectable DNS resolution service for modules.

Handles forward/reverse lookups, wildcard detection, and DNS-over-HTTPS.
"""

import logging
import random
import socket
import string
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    import dns.resolver
    import dns.reversename
    import dns.rdatatype
    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False

try:
    import netaddr
    HAS_NETADDR = True
except ImportError:
    HAS_NETADDR = False

log = logging.getLogger("spiderfoot.dns_service")


@dataclass
class DnsServiceConfig:
    """Configuration for the DNS service.
    
    Attributes:
        nameservers: Custom nameservers (empty = system default)
        timeout: Per-query timeout in seconds
        lifetime: Total resolution lifetime in seconds
        cache_enabled: Enable local DNS cache
        cache_ttl: Cache TTL in seconds
        doh_enabled: Use DNS-over-HTTPS
        doh_url: DoH resolver URL
    """
    nameservers: List[str] = field(default_factory=list)
    timeout: float = 5.0
    lifetime: float = 10.0
    cache_enabled: bool = True
    cache_ttl: int = 300
    doh_enabled: bool = False
    doh_url: str = "https://cloudflare-dns.com/dns-query"
    
    @classmethod
    def from_sf_config(cls, opts: Dict[str, Any]) -> "DnsServiceConfig":
        """Create config from SpiderFoot options dict."""
        nameservers = []
        ns_str = opts.get("_dnsserver", "")
        if ns_str:
            nameservers = [s.strip() for s in ns_str.split(",") if s.strip()]
        
        return cls(
            nameservers=nameservers,
            timeout=float(opts.get("_dnstimeout", 5.0)),
        )


class DnsService:
    """DNS resolution service.
    
    Provides DNS lookups decoupled from the core SpiderFoot object.
    
    Usage:
        dns_svc = DnsService(config)
        ips = dns_svc.resolve("example.com")
        hostnames = dns_svc.reverse_resolve("93.184.216.34")
    """
    
    def __init__(self, config: Optional[DnsServiceConfig] = None):
        self.config = config or DnsServiceConfig()
        self.log = logging.getLogger("spiderfoot.dns_service")
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._query_count = 0
        self._cache_hits = 0
        
        # Configure resolver
        self._resolver = None
        if HAS_DNSPYTHON:
            self._resolver = dns.resolver.Resolver()
            if self.config.nameservers:
                self._resolver.nameservers = self.config.nameservers
            self._resolver.timeout = self.config.timeout
            self._resolver.lifetime = self.config.lifetime
    
    def _cache_get(self, key: str) -> Optional[Any]:
        """Get value from DNS cache."""
        if not self.config.cache_enabled:
            return None
        
        entry = self._cache.get(key)
        if entry is None:
            return None
        
        cached_time, value = entry
        if time.time() - cached_time > self.config.cache_ttl:
            del self._cache[key]
            return None
        
        self._cache_hits += 1
        return value
    
    def _cache_set(self, key: str, value: Any):
        """Store value in DNS cache."""
        if not self.config.cache_enabled:
            return
        self._cache[key] = (time.time(), value)
    
    # --- Forward DNS ---
    
    def resolve(self, hostname: str, rdtype: str = "A") -> List[str]:
        """Resolve a hostname to IP addresses.
        
        Args:
            hostname: Hostname to resolve
            rdtype: DNS record type (A, AAAA, MX, TXT, etc.)
            
        Returns:
            List of resolved values
        """
        cache_key = f"resolve:{hostname}:{rdtype}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        
        self._query_count += 1
        results = []
        
        if HAS_DNSPYTHON and self._resolver:
            try:
                answers = self._resolver.resolve(hostname, rdtype)
                results = [str(rdata) for rdata in answers]
            except dns.resolver.NXDOMAIN:
                self.log.debug(f"NXDOMAIN: {hostname}")
            except dns.resolver.NoAnswer:
                self.log.debug(f"No {rdtype} records: {hostname}")
            except dns.resolver.NoNameservers:
                self.log.warning(f"No nameservers available for {hostname}")
            except dns.exception.Timeout:
                self.log.warning(f"DNS timeout resolving {hostname}")
            except Exception as e:
                self.log.warning(f"DNS resolve error for {hostname}: {e}")
        else:
            # Fallback to socket
            try:
                if rdtype == "A":
                    _, _, addrs = socket.gethostbyname_ex(hostname)
                    results = list(addrs)
                elif rdtype == "AAAA":
                    infos = socket.getaddrinfo(hostname, None, socket.AF_INET6)
                    results = list(set(info[4][0] for info in infos))
                else:
                    self.log.warning(
                        f"Record type {rdtype} requires dnspython; falling back to A"
                    )
                    _, _, addrs = socket.gethostbyname_ex(hostname)
                    results = list(addrs)
            except socket.gaierror as e:
                self.log.debug(f"Socket resolve failed for {hostname}: {e}")
            except Exception as e:
                self.log.warning(f"Socket resolve error for {hostname}: {e}")
        
        self._cache_set(cache_key, results)
        return results
    
    def resolve_host(self, hostname: str) -> List[str]:
        """Resolve a hostname to IPv4 addresses (convenience method).
        
        Args:
            hostname: Hostname to resolve
            
        Returns:
            List of IPv4 addresses
        """
        return self.resolve(hostname, "A")
    
    def resolve_host6(self, hostname: str) -> List[str]:
        """Resolve a hostname to IPv6 addresses.
        
        Args:
            hostname: Hostname to resolve
            
        Returns:
            List of IPv6 addresses
        """
        return self.resolve(hostname, "AAAA")
    
    # --- Reverse DNS ---
    
    def reverse_resolve(self, ip_address: str) -> List[str]:
        """Reverse-resolve an IP address to hostnames.
        
        Args:
            ip_address: IP address to reverse-resolve
            
        Returns:
            List of hostnames
        """
        cache_key = f"reverse:{ip_address}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        
        self._query_count += 1
        results = []
        
        if HAS_DNSPYTHON and self._resolver:
            try:
                rev_name = dns.reversename.from_address(ip_address)
                answers = self._resolver.resolve(rev_name, "PTR")
                results = [str(rdata).rstrip(".") for rdata in answers]
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                self.log.debug(f"No PTR for {ip_address}")
            except dns.exception.Timeout:
                self.log.warning(f"DNS timeout reverse-resolving {ip_address}")
            except Exception as e:
                self.log.warning(f"Reverse DNS error for {ip_address}: {e}")
        else:
            try:
                hostname, _, _ = socket.gethostbyaddr(ip_address)
                results = [hostname]
            except socket.herror:
                self.log.debug(f"No reverse DNS for {ip_address}")
            except Exception as e:
                self.log.warning(f"Socket reverse DNS error for {ip_address}: {e}")
        
        self._cache_set(cache_key, results)
        return results
    
    # --- Record Type Queries ---
    
    def resolve_mx(self, domain: str) -> List[Dict[str, Any]]:
        """Resolve MX records for a domain.
        
        Args:
            domain: Domain name
            
        Returns:
            List of dicts with 'priority' and 'host' keys
        """
        if not HAS_DNSPYTHON or not self._resolver:
            self.log.warning("MX resolution requires dnspython")
            return []
        
        cache_key = f"mx:{domain}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        
        self._query_count += 1
        results = []
        
        try:
            answers = self._resolver.resolve(domain, "MX")
            for rdata in answers:
                results.append({
                    "priority": rdata.preference,
                    "host": str(rdata.exchange).rstrip("."),
                })
            results.sort(key=lambda x: x["priority"])
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            pass
        except Exception as e:
            self.log.warning(f"MX resolve error for {domain}: {e}")
        
        self._cache_set(cache_key, results)
        return results
    
    def resolve_txt(self, domain: str) -> List[str]:
        """Resolve TXT records for a domain.
        
        Args:
            domain: Domain name
            
        Returns:
            List of TXT record strings
        """
        return self.resolve(domain, "TXT")
    
    def resolve_ns(self, domain: str) -> List[str]:
        """Resolve NS records for a domain.
        
        Args:
            domain: Domain name
            
        Returns:
            List of nameserver hostnames
        """
        results = self.resolve(domain, "NS")
        return [r.rstrip(".") for r in results]
    
    def resolve_cname(self, hostname: str) -> List[str]:
        """Resolve CNAME records for a hostname.
        
        Args:
            hostname: Hostname to check
            
        Returns:
            List of CNAME targets
        """
        results = self.resolve(hostname, "CNAME")
        return [r.rstrip(".") for r in results]
    
    def resolve_soa(self, domain: str) -> Optional[Dict[str, Any]]:
        """Resolve SOA record for a domain.
        
        Args:
            domain: Domain name
            
        Returns:
            Dict with mname, rname, serial, etc. or None
        """
        if not HAS_DNSPYTHON or not self._resolver:
            return None
        
        cache_key = f"soa:{domain}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        
        self._query_count += 1
        
        try:
            answers = self._resolver.resolve(domain, "SOA")
            for rdata in answers:
                result = {
                    "mname": str(rdata.mname).rstrip("."),
                    "rname": str(rdata.rname).rstrip("."),
                    "serial": rdata.serial,
                    "refresh": rdata.refresh,
                    "retry": rdata.retry,
                    "expire": rdata.expire,
                    "minimum": rdata.minimum,
                }
                self._cache_set(cache_key, result)
                return result
        except Exception as e:
            self.log.debug(f"SOA resolve error for {domain}: {e}")
        
        return None
    
    # --- Validation & Detection ---
    
    def validate_ip(self, hostname: str, ip: str) -> bool:
        """Check if a hostname resolves to a specific IP.
        
        Args:
            hostname: Hostname to resolve
            ip: Expected IP address
            
        Returns:
            True if hostname resolves to the given IP
        """
        resolved_ips = self.resolve_host(hostname) + self.resolve_host6(hostname)
        return ip in resolved_ips
    
    def check_wildcard(self, domain: str) -> bool:
        """Check if a domain has wildcard DNS configured.
        
        Generates a random subdomain and checks if it resolves.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if wildcard DNS is detected
        """
        random_sub = ''.join(random.choices(string.ascii_lowercase, k=12))
        test_domain = f"{random_sub}.{domain}"
        
        results = self.resolve_host(test_domain)
        return len(results) > 0
    
    def check_zone_transfer(self, domain: str) -> Optional[List[Dict[str, str]]]:
        """Attempt a DNS zone transfer (AXFR).
        
        Args:
            domain: Domain to attempt zone transfer on
            
        Returns:
            List of records if transfer succeeds, None if fails
        """
        if not HAS_DNSPYTHON:
            self.log.warning("Zone transfer requires dnspython")
            return None
        
        import dns.zone
        import dns.query
        
        # Get nameservers first
        nameservers = self.resolve_ns(domain)
        if not nameservers:
            return None
        
        for ns in nameservers:
            ns_ips = self.resolve_host(ns)
            for ns_ip in ns_ips:
                try:
                    zone = dns.zone.from_xfr(
                        dns.query.xfr(ns_ip, domain, timeout=self.config.timeout)
                    )
                    records = []
                    for name, node in zone.nodes.items():
                        for rdataset in node.rdatasets:
                            for rdata in rdataset:
                                records.append({
                                    "name": str(name),
                                    "type": dns.rdatatype.to_text(rdataset.rdtype),
                                    "data": str(rdata),
                                })
                    return records
                except Exception:
                    continue
        
        return None
    
    # --- Cache Management ---
    
    def cache_clear(self):
        """Clear the DNS cache."""
        self._cache.clear()
    
    def cache_size(self) -> int:
        """Get the number of cached entries."""
        return len(self._cache)
    
    # --- Metrics ---
    
    def stats(self) -> Dict[str, Any]:
        """Get service statistics.
        
        Returns:
            Dict with query counts, cache stats, etc.
        """
        return {
            "query_count": self._query_count,
            "cache_hits": self._cache_hits,
            "cache_size": self.cache_size(),
            "cache_enabled": self.config.cache_enabled,
            "has_dnspython": HAS_DNSPYTHON,
            "nameservers": self.config.nameservers or ["system default"],
        }
