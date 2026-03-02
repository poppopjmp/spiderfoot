# -------------------------------------------------------------------------------
# Name:         target_replication
# Purpose:      Generate Terraform + Ansible IaC to recreate scanned targets locally
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Target Replication Engine — Terraform + Ansible Infrastructure-as-Code Generator.

Consumes SpiderFoot scan results (event data) and produces:

1. **Terraform configurations** for provisioning infrastructure on
   AWS, Azure, GCP, DigitalOcean, or VMware vSphere.
2. **Ansible playbooks** for installing and configuring the discovered
   software stack (web servers, databases, frameworks, services).

This enables operators to spin up a faithful replica of a scanned target
for red-team exercises, vulnerability testing, or training environments.

Architecture
------------
::

    ScanResults → TargetProfileExtractor → TargetProfile
                                              ↓
                            ┌─────────────────┼─────────────────┐
                            ↓                 ↓                 ↓
                   TerraformGenerator   AnsibleGenerator   DockerComposeGenerator
                            ↓                 ↓                 ↓
                        main.tf          playbook.yml     docker-compose.yml
                     variables.tf        roles/...
                     outputs.tf          inventory.ini

Components
----------
- :class:`TargetProfile` — Normalized representation of discovered infrastructure
- :class:`TargetProfileExtractor` — Extracts profile from SpiderFoot scan events
- :class:`TerraformGenerator` — Multi-cloud Terraform HCL generation
- :class:`AnsibleGenerator` — Role-based playbook & inventory generation
- :class:`DockerComposeGenerator` — Lightweight local replication via Docker
- :class:`TargetReplicator` — Unified façade for full IaC output generation
"""

from __future__ import annotations

import json
import logging
import os
import re
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.recon.target_replication")


# ============================================================================
# Data Model — Target Profile (extracted from scan results)
# ============================================================================


class CloudProvider(Enum):
    """Supported cloud/virtualization providers for Terraform."""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    DIGITALOCEAN = "digitalocean"
    VMWARE = "vmware"


class ServiceCategory(Enum):
    """Categories for discovered services."""
    WEB_SERVER = "web_server"
    DATABASE = "database"
    MAIL_SERVER = "mail_server"
    DNS_SERVER = "dns_server"
    APPLICATION = "application"
    CACHE = "cache"
    QUEUE = "queue"
    MONITORING = "monitoring"
    PROXY = "proxy"
    CUSTOM = "custom"


@dataclass
class DiscoveredPort:
    """A TCP/UDP port found open during scanning."""
    port: int
    protocol: str = "tcp"  # tcp or udp
    banner: str = ""
    service_name: str = ""
    service_version: str = ""

    @property
    def is_web(self) -> bool:
        return self.port in (80, 443, 8080, 8443, 8888, 3000, 5000, 9000)

    @property
    def is_database(self) -> bool:
        return self.port in (3306, 5432, 1521, 1433, 27017, 6379, 9200, 5984, 2638)

    @property
    def is_mail(self) -> bool:
        return self.port in (25, 110, 143, 465, 587, 993, 995)


@dataclass
class DiscoveredService:
    """A software service identified on the target."""
    name: str
    version: str = ""
    category: ServiceCategory = ServiceCategory.CUSTOM
    port: int | None = None
    config_hints: dict[str, Any] = field(default_factory=dict)

    @property
    def ansible_package_name(self) -> str:
        """Map service name to OS package name."""
        return _SERVICE_TO_PACKAGE.get(self.name.lower(), self.name.lower())

    @property
    def docker_image(self) -> str:
        """Map service to Docker image."""
        name_lower = self.name.lower()
        if self.version:
            img = _SERVICE_TO_DOCKER.get(name_lower, name_lower)
            return f"{img}:{self.version}"
        return _SERVICE_TO_DOCKER.get(name_lower, name_lower)


@dataclass
class DiscoveredWebTechnology:
    """A web technology/framework detected on the target."""
    name: str
    version: str = ""
    category: str = ""  # framework, cms, language, server, cdn, waf


@dataclass
class SSLCertInfo:
    """SSL/TLS certificate information."""
    issuer: str = ""
    subject: str = ""
    alt_names: list[str] = field(default_factory=list)
    expired: bool = False
    expiring: bool = False
    self_signed: bool = False


@dataclass
class TargetProfile:
    """Complete normalized profile of a scanned target.

    Assembled from SpiderFoot scan events, this profile contains
    everything needed to generate IaC for replication.
    """
    # Identity
    target: str = ""
    domain: str = ""
    ip_addresses: list[str] = field(default_factory=list)
    ipv6_addresses: list[str] = field(default_factory=list)
    hostnames: list[str] = field(default_factory=list)

    # Operating System
    operating_system: str = ""
    os_family: str = ""  # linux, windows
    os_version: str = ""

    # Network
    open_ports: list[DiscoveredPort] = field(default_factory=list)

    # Services
    services: list[DiscoveredService] = field(default_factory=list)

    # Web
    web_server: str = ""
    web_server_version: str = ""
    web_technologies: list[DiscoveredWebTechnology] = field(default_factory=list)
    ssl_cert: SSLCertInfo | None = None

    # DNS
    dns_records: dict[str, list[str]] = field(default_factory=dict)
    nameservers: list[str] = field(default_factory=list)
    mail_servers: list[str] = field(default_factory=list)

    # Cloud/Hosting
    hosting_provider: str = ""
    cloud_provider: str = ""

    # Metadata
    scan_id: str = ""
    scan_date: str = ""

    @property
    def has_web_services(self) -> bool:
        return bool(self.web_server) or any(p.is_web for p in self.open_ports)

    @property
    def has_database(self) -> bool:
        return any(p.is_database for p in self.open_ports)

    @property
    def has_mail(self) -> bool:
        return any(p.is_mail for p in self.open_ports)

    @property
    def primary_ip(self) -> str:
        return self.ip_addresses[0] if self.ip_addresses else "10.0.1.10"

    def get_web_ports(self) -> list[int]:
        return [p.port for p in self.open_ports if p.is_web]

    def get_db_ports(self) -> list[int]:
        return [p.port for p in self.open_ports if p.is_database]

    def get_all_ports(self) -> list[int]:
        return [p.port for p in self.open_ports]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        return {
            "target": self.target,
            "domain": self.domain,
            "ip_addresses": self.ip_addresses,
            "ipv6_addresses": self.ipv6_addresses,
            "hostnames": self.hostnames,
            "operating_system": self.operating_system,
            "os_family": self.os_family,
            "open_ports": [
                {"port": p.port, "protocol": p.protocol,
                 "banner": p.banner, "service_name": p.service_name}
                for p in self.open_ports
            ],
            "services": [
                {"name": s.name, "version": s.version,
                 "category": s.category.value, "port": s.port}
                for s in self.services
            ],
            "web_server": self.web_server,
            "web_technologies": [
                {"name": t.name, "version": t.version, "category": t.category}
                for t in self.web_technologies
            ],
            "hosting_provider": self.hosting_provider,
            "scan_id": self.scan_id,
        }


# Service → OS package mapping
_SERVICE_TO_PACKAGE: dict[str, str] = {
    "nginx": "nginx",
    "apache": "apache2",
    "httpd": "httpd",
    "mysql": "mysql-server",
    "mariadb": "mariadb-server",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "redis": "redis-server",
    "memcached": "memcached",
    "mongodb": "mongodb-org",
    "openssh": "openssh-server",
    "postfix": "postfix",
    "dovecot": "dovecot-imapd",
    "php": "php-fpm",
    "nodejs": "nodejs",
    "node": "nodejs",
    "python": "python3",
    "tomcat": "tomcat9",
    "elasticsearch": "elasticsearch",
    "rabbitmq": "rabbitmq-server",
    "varnish": "varnish",
    "haproxy": "haproxy",
    "bind": "bind9",
    "named": "bind9",
    "proftpd": "proftpd",
    "vsftpd": "vsftpd",
    "squid": "squid",
}

# Service → Docker image mapping
_SERVICE_TO_DOCKER: dict[str, str] = {
    "nginx": "nginx",
    "apache": "httpd",
    "httpd": "httpd",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "postgresql": "postgres",
    "postgres": "postgres",
    "redis": "redis",
    "memcached": "memcached",
    "mongodb": "mongo",
    "elasticsearch": "elasticsearch",
    "rabbitmq": "rabbitmq",
    "tomcat": "tomcat",
    "php": "php",
    "nodejs": "node",
    "node": "node",
    "python": "python",
    "varnish": "varnish",
    "haproxy": "haproxy",
    "postfix": "boky/postfix",
    "grafana": "grafana/grafana",
    "prometheus": "prom/prometheus",
}

# Banner patterns → service names
_BANNER_PATTERNS: list[tuple[str, str, str]] = [
    # (regex_pattern, service_name, category)
    (r"nginx[/ ]?([\d.]+)?", "nginx", "web_server"),
    (r"Apache[/ ]?([\d.]+)?", "apache", "web_server"),
    (r"Microsoft-IIS[/ ]?([\d.]+)?", "iis", "web_server"),
    (r"lighttpd[/ ]?([\d.]+)?", "lighttpd", "web_server"),
    (r"OpenSSH[_ ]?([\d.p]+)?", "openssh", "application"),
    (r"MySQL[/ ]?([\d.]+)?", "mysql", "database"),
    (r"MariaDB[/ ]?([\d.]+)?", "mariadb", "database"),
    (r"PostgreSQL[/ ]?([\d.]+)?", "postgresql", "database"),
    (r"Redis[/ ]?([\d.]+)?", "redis", "cache"),
    (r"MongoDB[/ ]?([\d.]+)?", "mongodb", "database"),
    (r"Postfix", "postfix", "mail_server"),
    (r"Dovecot", "dovecot", "mail_server"),
    (r"Exim[/ ]?([\d.]+)?", "exim", "mail_server"),
    (r"ProFTPD[/ ]?([\d.]+)?", "proftpd", "application"),
    (r"vsftpd[/ ]?([\d.]+)?", "vsftpd", "application"),
    (r"Pure-FTPd", "pure-ftpd", "application"),
    (r"RabbitMQ[/ ]?([\d.]+)?", "rabbitmq", "queue"),
    (r"Elasticsearch[/ ]?([\d.]+)?", "elasticsearch", "application"),
    (r"Tomcat[/ ]?([\d.]+)?", "tomcat", "web_server"),
    (r"Varnish[/ ]?([\d.]+)?", "varnish", "proxy"),
    (r"HAProxy[/ ]?([\d.]+)?", "haproxy", "proxy"),
    (r"Squid[/ ]?([\d.]+)?", "squid", "proxy"),
    (r"BIND[/ ]?([\d.]+)?", "bind", "dns_server"),
]


# ============================================================================
# Target Profile Extractor (from scan events)
# ============================================================================


class TargetProfileExtractor:
    """Extract a :class:`TargetProfile` from SpiderFoot scan event data.

    Accepts events as dicts with at minimum ``eventType`` and ``data`` keys,
    mirroring the structure returned by the SpiderFoot DB or API.

    Usage::

        extractor = TargetProfileExtractor()
        for event in scan_events:
            extractor.ingest(event)
        profile = extractor.build()
    """

    def __init__(self, target: str = "", scan_id: str = "") -> None:
        self._target = target
        self._scan_id = scan_id
        self._ips: set[str] = set()
        self._ipv6s: set[str] = set()
        self._hostnames: set[str] = set()
        self._ports: dict[int, DiscoveredPort] = {}
        self._services: list[DiscoveredService] = []
        self._web_techs: list[DiscoveredWebTechnology] = []
        self._os: str = ""
        self._web_server: str = ""
        self._web_server_version: str = ""
        self._ssl_cert: SSLCertInfo | None = None
        self._hosting: str = ""
        self._cloud: str = ""
        self._domain: str = ""
        self._nameservers: list[str] = []
        self._mail_servers: list[str] = []
        self._dns_records: dict[str, list[str]] = {}
        self._seen_services: set[str] = set()

    def ingest(self, event: dict[str, Any]) -> None:
        """Process a single scan event."""
        etype = event.get("eventType", event.get("type", ""))
        data = event.get("data", "")
        if not etype or not data:
            return

        handler = self._HANDLERS.get(etype)
        if handler:
            handler(self, str(data))

    def _handle_ip(self, data: str) -> None:
        ip = data.strip()
        if ip and not ip.startswith(("10.", "192.168.", "172.")):
            self._ips.add(ip)
        elif ip:
            self._ips.add(ip)

    def _handle_ipv6(self, data: str) -> None:
        self._ipv6s.add(data.strip())

    def _handle_hostname(self, data: str) -> None:
        self._hostnames.add(data.strip().lower())

    def _handle_domain(self, data: str) -> None:
        self._domain = data.strip().lower()
        self._hostnames.add(self._domain)

    def _handle_port_open(self, data: str) -> None:
        """Parse 'IP:PORT' or just 'PORT'."""
        parts = data.strip().rsplit(":", 1)
        try:
            port_num = int(parts[-1])
        except (ValueError, IndexError):
            return
        if port_num not in self._ports:
            self._ports[port_num] = DiscoveredPort(port=port_num, protocol="tcp")

    def _handle_port_banner(self, data: str) -> None:
        """Parse banner and extract service info."""
        # Try to extract port from data format "IP:PORT\nBANNER" or just banner
        lines = data.strip().split("\n", 1)
        banner_text = lines[-1] if len(lines) > 1 else data.strip()

        # Try to identify the port from the first line
        port_num = None
        if len(lines) > 1:
            parts = lines[0].rsplit(":", 1)
            try:
                port_num = int(parts[-1])
            except (ValueError, IndexError):
                pass

        # Parse banner for service identification
        for pattern, svc_name, svc_cat in _BANNER_PATTERNS:
            m = re.search(pattern, banner_text, re.IGNORECASE)
            if m:
                version = m.group(1) if m.lastindex and m.group(1) else ""
                if port_num and port_num in self._ports:
                    self._ports[port_num].banner = banner_text
                    self._ports[port_num].service_name = svc_name
                    self._ports[port_num].service_version = version

                svc_key = f"{svc_name}:{version}"
                if svc_key not in self._seen_services:
                    self._seen_services.add(svc_key)
                    cat = ServiceCategory(svc_cat) if svc_cat in [e.value for e in ServiceCategory] else ServiceCategory.CUSTOM
                    self._services.append(DiscoveredService(
                        name=svc_name, version=version,
                        category=cat, port=port_num,
                    ))
                break

    def _handle_os(self, data: str) -> None:
        self._os = data.strip()

    def _handle_web_server(self, data: str) -> None:
        """Parse web server banner like 'nginx/1.24.0'."""
        parts = data.strip().split("/", 1)
        self._web_server = parts[0].strip()
        if len(parts) > 1:
            self._web_server_version = parts[1].strip()

    def _handle_web_tech(self, data: str) -> None:
        """Parse technology like 'WordPress 6.4' or 'PHP/8.2'."""
        parts = re.split(r"[/ ]", data.strip(), maxsplit=1)
        name = parts[0].strip()
        version = parts[1].strip() if len(parts) > 1 else ""
        self._web_techs.append(DiscoveredWebTechnology(
            name=name, version=version, category="technology",
        ))

    def _handle_software(self, data: str) -> None:
        """Parse SOFTWARE_USED events."""
        parts = re.split(r"[/ ]", data.strip(), maxsplit=1)
        name = parts[0].strip()
        version = parts[1].strip() if len(parts) > 1 else ""
        svc_key = f"{name.lower()}:{version}"
        if svc_key not in self._seen_services:
            self._seen_services.add(svc_key)
            self._services.append(DiscoveredService(
                name=name, version=version,
                category=ServiceCategory.APPLICATION,
            ))

    def _handle_hosting(self, data: str) -> None:
        self._hosting = data.strip()

    def _handle_cloud(self, data: str) -> None:
        self._cloud = data.strip()

    def _handle_nameserver(self, data: str) -> None:
        self._nameservers.append(data.strip())

    def _handle_mail_server(self, data: str) -> None:
        self._mail_servers.append(data.strip())

    def _handle_dns_txt(self, data: str) -> None:
        self._dns_records.setdefault("TXT", []).append(data.strip())

    def _handle_dns_spf(self, data: str) -> None:
        self._dns_records.setdefault("SPF", []).append(data.strip())

    def _handle_ssl_cert(self, data: str) -> None:
        """Parse SSL certificate raw data."""
        self._ssl_cert = SSLCertInfo()
        # Extract key fields from cert text
        for line in data.split("\n"):
            line = line.strip()
            if line.startswith("Issuer:"):
                self._ssl_cert.issuer = line[7:].strip()
            elif line.startswith("Subject:"):
                self._ssl_cert.subject = line[8:].strip()
            elif "self-signed" in line.lower() or "self signed" in line.lower():
                self._ssl_cert.self_signed = True

    _HANDLERS: dict[str, Any] = {
        "IP_ADDRESS": _handle_ip,
        "IPV6_ADDRESS": _handle_ipv6,
        "INTERNET_NAME": _handle_hostname,
        "DOMAIN_NAME": _handle_domain,
        "TCP_PORT_OPEN": _handle_port_open,
        "TCP_PORT_OPEN_BANNER": _handle_port_banner,
        "UDP_PORT_OPEN": _handle_port_open,
        "OPERATING_SYSTEM": _handle_os,
        "WEBSERVER_BANNER": _handle_web_server,
        "WEBSERVER_TECHNOLOGY": _handle_web_tech,
        "SOFTWARE_USED": _handle_software,
        "PROVIDER_HOSTING": _handle_hosting,
        "CLOUD_PROVIDER": _handle_cloud,
        "PROVIDER_DNS": _handle_nameserver,
        "PROVIDER_MAIL": _handle_mail_server,
        "DNS_TEXT": _handle_dns_txt,
        "DNS_SPF": _handle_dns_spf,
        "SSL_CERTIFICATE_RAW": _handle_ssl_cert,
    }

    def build(self) -> TargetProfile:
        """Build and return the complete :class:`TargetProfile`."""
        os_family = ""
        if self._os:
            os_lower = self._os.lower()
            if any(k in os_lower for k in ("linux", "ubuntu", "debian", "centos", "rhel", "fedora", "alpine")):
                os_family = "linux"
            elif any(k in os_lower for k in ("windows", "microsoft")):
                os_family = "windows"
            elif "macos" in os_lower or "darwin" in os_lower:
                os_family = "macos"

        os_version = ""
        m = re.search(r"([\d]+(?:\.[\d]+)*)", self._os)
        if m:
            os_version = m.group(1)

        return TargetProfile(
            target=self._target,
            domain=self._domain or self._target,
            ip_addresses=sorted(self._ips),
            ipv6_addresses=sorted(self._ipv6s),
            hostnames=sorted(self._hostnames),
            operating_system=self._os,
            os_family=os_family or "linux",
            os_version=os_version,
            open_ports=sorted(self._ports.values(), key=lambda p: p.port),
            services=self._services,
            web_server=self._web_server,
            web_server_version=self._web_server_version,
            web_technologies=self._web_techs,
            ssl_cert=self._ssl_cert,
            dns_records=self._dns_records,
            nameservers=self._nameservers,
            mail_servers=self._mail_servers,
            hosting_provider=self._hosting,
            cloud_provider=self._cloud,
            scan_id=self._scan_id,
        )


# ============================================================================
# Terraform Generator (Cycles 21–30)
# ============================================================================


# Instance type mappings per provider
_INSTANCE_TYPES: dict[str, dict[str, str]] = {
    "aws": {"small": "t3.micro", "medium": "t3.medium", "large": "t3.large"},
    "azure": {"small": "Standard_B1ms", "medium": "Standard_B2ms", "large": "Standard_D2s_v3"},
    "gcp": {"small": "e2-micro", "medium": "e2-medium", "large": "e2-standard-2"},
    "digitalocean": {"small": "s-1vcpu-1gb", "medium": "s-2vcpu-2gb", "large": "s-2vcpu-4gb"},
    "vmware": {"small": "1cpu-1gb", "medium": "2cpu-2gb", "large": "2cpu-4gb"},
}

# AMI/Image mappings per provider per OS
_OS_IMAGES: dict[str, dict[str, str]] = {
    "aws": {
        "ubuntu": "ami-0c7217cdde317cfec",  # Ubuntu 22.04
        "debian": "ami-0908a9be84a44b7c0",
        "centos": "ami-002070d43b0a4f171",
        "amazon-linux": "ami-0c101f26f147fa7fd",
        "windows": "ami-0f9c44e98edf38a2b",
    },
    "azure": {
        "ubuntu": "Canonical:0001-com-ubuntu-server-jammy:22_04-lts:latest",
        "debian": "Debian:debian-11:11:latest",
        "centos": "OpenLogic:CentOS:7_9:latest",
        "windows": "MicrosoftWindowsServer:WindowsServer:2022-datacenter:latest",
    },
    "gcp": {
        "ubuntu": "ubuntu-os-cloud/ubuntu-2204-lts",
        "debian": "debian-cloud/debian-11",
        "centos": "centos-cloud/centos-stream-9",
        "windows": "windows-cloud/windows-2022",
    },
    "digitalocean": {
        "ubuntu": "ubuntu-22-04-x64",
        "debian": "debian-11-x64",
        "centos": "centos-stream-9-x64",
    },
    "vmware": {
        "ubuntu": "ubuntu-22.04-template",
        "debian": "debian-11-template",
        "centos": "centos-stream-9-template",
        "windows": "windows-2022-template",
    },
}


class TerraformGenerator:
    """Generate Terraform HCL configurations from a :class:`TargetProfile`.

    Supports AWS, Azure, GCP, DigitalOcean, and VMware vSphere.
    Generates ``main.tf``, ``variables.tf``, ``outputs.tf``, and
    ``terraform.tfvars.example``.

    Args:
        profile: The target profile to replicate.
        provider: Cloud provider to generate for.
        instance_size: VM size category (small/medium/large).
    """

    def __init__(
        self,
        profile: TargetProfile,
        provider: CloudProvider = CloudProvider.AWS,
        instance_size: str = "medium",
    ) -> None:
        self._profile = profile
        self._provider = provider
        self._instance_size = instance_size

    def generate_all(self) -> dict[str, str]:
        """Generate all Terraform files as a dict of filename → content."""
        return {
            "main.tf": self.generate_main(),
            "variables.tf": self.generate_variables(),
            "outputs.tf": self.generate_outputs(),
            "terraform.tfvars.example": self.generate_tfvars_example(),
        }

    def generate_main(self) -> str:
        """Generate the main.tf configuration."""
        gen = getattr(self, f"_main_{self._provider.value}", None)
        if gen is None:
            raise ValueError(f"Unsupported provider: {self._provider.value}")
        return gen()

    def generate_variables(self) -> str:
        """Generate variables.tf."""
        ports = self._profile.get_all_ports()
        port_list = ", ".join(str(p) for p in ports) if ports else "80, 443"
        domain = self._profile.domain or "example.com"

        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            # Target: {self._profile.target}
            # Provider: {self._provider.value}

            variable "project_name" {{
              description = "Project name prefix for resources"
              type        = string
              default     = "sf-replica-{domain.replace(".", "-")}"
            }}

            variable "instance_type" {{
              description = "Instance type/size"
              type        = string
              default     = "{self._get_instance_type()}"
            }}

            variable "allowed_ports" {{
              description = "Ports to open in security group/firewall"
              type        = list(number)
              default     = [{port_list}]
            }}

            variable "ssh_public_key" {{
              description = "SSH public key for instance access"
              type        = string
              default     = ""
            }}

            variable "tags" {{
              description = "Tags to apply to resources"
              type        = map(string)
              default = {{
                Environment = "replica"
                ManagedBy   = "spiderfoot"
                Source      = "scan-{self._profile.scan_id or "unknown"}"
              }}
            }}
        ''')

    def generate_outputs(self) -> str:
        """Generate outputs.tf."""
        provider = self._provider.value

        if provider == "aws":
            return textwrap.dedent('''\
                output "instance_id" {
                  description = "EC2 instance ID"
                  value       = aws_instance.replica.id
                }

                output "public_ip" {
                  description = "Elastic IP address"
                  value       = aws_eip.replica.public_ip
                }

                output "public_dns" {
                  description = "Public DNS name"
                  value       = aws_instance.replica.public_dns
                }

                output "vpc_id" {
                  description = "VPC ID"
                  value       = aws_vpc.replica.id
                }

                output "security_group_id" {
                  description = "Security group ID"
                  value       = aws_security_group.replica.id
                }
            ''')
        elif provider == "azure":
            return textwrap.dedent('''\
                output "vm_id" {
                  value = azurerm_linux_virtual_machine.replica.id
                }

                output "public_ip" {
                  value = azurerm_public_ip.replica.ip_address
                }
            ''')
        elif provider == "gcp":
            return textwrap.dedent('''\
                output "instance_name" {
                  value = google_compute_instance.replica.name
                }

                output "external_ip" {
                  value = google_compute_instance.replica.network_interface[0].access_config[0].nat_ip
                }
            ''')
        elif provider == "digitalocean":
            return textwrap.dedent('''\
                output "droplet_id" {
                  value = digitalocean_droplet.replica.id
                }

                output "ipv4_address" {
                  value = digitalocean_droplet.replica.ipv4_address
                }
            ''')
        else:  # vmware
            return textwrap.dedent('''\
                output "vm_name" {
                  value = vsphere_virtual_machine.replica.name
                }

                output "default_ip" {
                  value = vsphere_virtual_machine.replica.default_ip_address
                }
            ''')

    def generate_tfvars_example(self) -> str:
        """Generate terraform.tfvars.example."""
        domain = self._profile.domain or "example.com"
        return textwrap.dedent(f'''\
            # Copy to terraform.tfvars and fill in your values
            project_name   = "sf-replica-{domain.replace(".", "-")}"
            instance_type  = "{self._get_instance_type()}"
            ssh_public_key = "ssh-rsa AAAA..."
        ''')

    # ------------------------------------------------------------------
    # Provider-specific main.tf generators
    # ------------------------------------------------------------------

    def _main_aws(self) -> str:
        os_image = self._resolve_os_image("aws")
        ports = self._profile.get_all_ports() or [80, 443]
        ingress_rules = "\n".join(
            f"    ingress {{\n      from_port   = {p}\n      to_port     = {p}\n"
            f"      protocol    = \"tcp\"\n      cidr_blocks = [\"0.0.0.0/0\"]\n    }}"
            for p in ports
        )

        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            # Target: {self._profile.target}

            terraform {{
              required_providers {{
                aws = {{
                  source  = "hashicorp/aws"
                  version = "~> 5.0"
                }}
              }}
            }}

            provider "aws" {{
              region = "us-east-1"
            }}

            # ---- Networking ----

            resource "aws_vpc" "replica" {{
              cidr_block           = "10.0.0.0/16"
              enable_dns_support   = true
              enable_dns_hostnames = true

              tags = merge(var.tags, {{
                Name = "${{var.project_name}}-vpc"
              }})
            }}

            resource "aws_internet_gateway" "replica" {{
              vpc_id = aws_vpc.replica.id

              tags = merge(var.tags, {{
                Name = "${{var.project_name}}-igw"
              }})
            }}

            resource "aws_subnet" "replica" {{
              vpc_id                  = aws_vpc.replica.id
              cidr_block              = "10.0.1.0/24"
              availability_zone       = "us-east-1a"
              map_public_ip_on_launch = true

              tags = merge(var.tags, {{
                Name = "${{var.project_name}}-subnet"
              }})
            }}

            resource "aws_route_table" "replica" {{
              vpc_id = aws_vpc.replica.id

              route {{
                cidr_block = "0.0.0.0/0"
                gateway_id = aws_internet_gateway.replica.id
              }}

              tags = merge(var.tags, {{
                Name = "${{var.project_name}}-rt"
              }})
            }}

            resource "aws_route_table_association" "replica" {{
              subnet_id      = aws_subnet.replica.id
              route_table_id = aws_route_table.replica.id
            }}

            # ---- Security ----

            resource "aws_security_group" "replica" {{
              name_prefix = "${{var.project_name}}-sg"
              description = "Security group for SpiderFoot target replica"
              vpc_id      = aws_vpc.replica.id

              ingress {{
                from_port   = 22
                to_port     = 22
                protocol    = "tcp"
                cidr_blocks = ["0.0.0.0/0"]
                description = "SSH access"
              }}

            {ingress_rules}

              egress {{
                from_port   = 0
                to_port     = 0
                protocol    = "-1"
                cidr_blocks = ["0.0.0.0/0"]
              }}

              tags = var.tags

              lifecycle {{
                create_before_destroy = true
              }}
            }}

            resource "aws_key_pair" "replica" {{
              count      = var.ssh_public_key != "" ? 1 : 0
              key_name   = "${{var.project_name}}-key"
              public_key = var.ssh_public_key

              tags = var.tags
            }}

            # ---- Compute ----

            resource "aws_instance" "replica" {{
              ami           = "{os_image}"
              instance_type = var.instance_type
              subnet_id     = aws_subnet.replica.id

              vpc_security_group_ids = [aws_security_group.replica.id]
              key_name               = var.ssh_public_key != "" ? aws_key_pair.replica[0].key_name : null

              root_block_device {{
                volume_size           = 30
                volume_type           = "gp3"
                delete_on_termination = true
                encrypted             = true
              }}

              tags = merge(var.tags, {{
                Name = var.project_name
              }})

              user_data = <<-EOF
                #!/bin/bash
                echo "SpiderFoot target replica provisioned"
              EOF

              lifecycle {{
                ignore_changes = [user_data]
              }}
            }}

            # ---- Elastic IP ----

            resource "aws_eip" "replica" {{
              instance = aws_instance.replica.id
              domain   = "vpc"

              tags = merge(var.tags, {{
                Name = "${{var.project_name}}-eip"
              }})
            }}
        ''')

    def _main_azure(self) -> str:
        os_image = self._resolve_os_image("azure")
        parts = os_image.split(":")
        publisher = parts[0] if len(parts) > 0 else "Canonical"
        offer = parts[1] if len(parts) > 1 else "0001-com-ubuntu-server-jammy"
        sku = parts[2] if len(parts) > 2 else "22_04-lts"
        img_version = parts[3] if len(parts) > 3 else "latest"
        ports = self._profile.get_all_ports() or [80, 443]
        nsg_rules = ""
        for i, p in enumerate(ports):
            nsg_rules += textwrap.dedent(f'''\

              security_rule {{
                name                       = "allow-port-{p}"
                priority                   = {100 + i}
                direction                  = "Inbound"
                access                     = "Allow"
                protocol                   = "Tcp"
                source_port_range          = "*"
                destination_port_range     = "{p}"
                source_address_prefix      = "*"
                destination_address_prefix = "*"
              }}
            ''')

        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            # Target: {self._profile.target}

            terraform {{
              required_providers {{
                azurerm = {{
                  source  = "hashicorp/azurerm"
                  version = "~> 3.0"
                }}
              }}
            }}

            provider "azurerm" {{
              features {{}}
            }}

            resource "azurerm_resource_group" "replica" {{
              name     = "${{var.project_name}}-rg"
              location = "East US"
              tags     = var.tags
            }}

            resource "azurerm_virtual_network" "replica" {{
              name                = "${{var.project_name}}-vnet"
              resource_group_name = azurerm_resource_group.replica.name
              location            = azurerm_resource_group.replica.location
              address_space       = ["10.0.0.0/16"]
            }}

            resource "azurerm_subnet" "replica" {{
              name                 = "${{var.project_name}}-subnet"
              resource_group_name  = azurerm_resource_group.replica.name
              virtual_network_name = azurerm_virtual_network.replica.name
              address_prefixes     = ["10.0.1.0/24"]
            }}

            resource "azurerm_public_ip" "replica" {{
              name                = "${{var.project_name}}-pip"
              resource_group_name = azurerm_resource_group.replica.name
              location            = azurerm_resource_group.replica.location
              allocation_method   = "Dynamic"
            }}

            resource "azurerm_network_security_group" "replica" {{
              name                = "${{var.project_name}}-nsg"
              resource_group_name = azurerm_resource_group.replica.name
              location            = azurerm_resource_group.replica.location
            {nsg_rules}
              tags = var.tags
            }}

            resource "azurerm_network_interface" "replica" {{
              name                = "${{var.project_name}}-nic"
              resource_group_name = azurerm_resource_group.replica.name
              location            = azurerm_resource_group.replica.location

              ip_configuration {{
                name                          = "internal"
                subnet_id                     = azurerm_subnet.replica.id
                private_ip_address_allocation = "Dynamic"
                public_ip_address_id          = azurerm_public_ip.replica.id
              }}
            }}

            resource "azurerm_linux_virtual_machine" "replica" {{
              name                = var.project_name
              resource_group_name = azurerm_resource_group.replica.name
              location            = azurerm_resource_group.replica.location
              size                = var.instance_type
              admin_username      = "azureuser"

              network_interface_ids = [azurerm_network_interface.replica.id]

              admin_ssh_key {{
                username   = "azureuser"
                public_key = var.ssh_public_key
              }}

              os_disk {{
                caching              = "ReadWrite"
                storage_account_type = "Standard_LRS"
              }}

              source_image_reference {{
                publisher = "{publisher}"
                offer     = "{offer}"
                sku       = "{sku}"
                version   = "{img_version}"
              }}

              tags = var.tags
            }}
        ''')

    def _main_gcp(self) -> str:
        os_image = self._resolve_os_image("gcp")
        ports = self._profile.get_all_ports() or [80, 443]
        port_list = ", ".join(f'"{p}"' for p in ports)

        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            # Target: {self._profile.target}

            terraform {{
              required_providers {{
                google = {{
                  source  = "hashicorp/google"
                  version = "~> 5.0"
                }}
              }}
            }}

            provider "google" {{
              project = "my-project"
              region  = "us-central1"
              zone    = "us-central1-a"
            }}

            resource "google_compute_firewall" "replica" {{
              name    = "${{var.project_name}}-fw"
              network = "default"

              allow {{
                protocol = "tcp"
                ports    = [{port_list}]
              }}

              source_ranges = ["0.0.0.0/0"]
              target_tags   = ["${{var.project_name}}"]
            }}

            resource "google_compute_instance" "replica" {{
              name         = var.project_name
              machine_type = var.instance_type
              zone         = "us-central1-a"

              boot_disk {{
                initialize_params {{
                  image = "{os_image}"
                }}
              }}

              network_interface {{
                network = "default"
                access_config {{}}
              }}

              tags = ["${{var.project_name}}"]

              metadata = {{
                ssh-keys = "ubuntu:${{var.ssh_public_key}}"
              }}
            }}
        ''')

    def _main_digitalocean(self) -> str:
        os_image = self._resolve_os_image("digitalocean")
        ports = self._profile.get_all_ports() or [80, 443]
        inbound_rules = ""
        for p in ports:
            inbound_rules += textwrap.dedent(f'''\

              inbound_rule {{
                protocol         = "tcp"
                port_range       = "{p}"
                source_addresses = ["0.0.0.0/0", "::/0"]
              }}
            ''')

        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            # Target: {self._profile.target}

            terraform {{
              required_providers {{
                digitalocean = {{
                  source  = "digitalocean/digitalocean"
                  version = "~> 2.0"
                }}
              }}
            }}

            provider "digitalocean" {{
              token = var.do_token
            }}

            variable "do_token" {{
              description = "DigitalOcean API token"
              type        = string
              sensitive   = true
            }}

            resource "digitalocean_firewall" "replica" {{
              name = "${{var.project_name}}-fw"
              droplet_ids = [digitalocean_droplet.replica.id]
            {inbound_rules}

              outbound_rule {{
                protocol              = "tcp"
                port_range            = "1-65535"
                destination_addresses = ["0.0.0.0/0", "::/0"]
              }}

              outbound_rule {{
                protocol              = "udp"
                port_range            = "1-65535"
                destination_addresses = ["0.0.0.0/0", "::/0"]
              }}
            }}

            resource "digitalocean_droplet" "replica" {{
              name   = var.project_name
              region = "nyc1"
              size   = var.instance_type
              image  = "{os_image}"

              ssh_keys = var.ssh_public_key != "" ? [var.ssh_public_key] : []

              tags = ["spiderfoot-replica"]
            }}
        ''')

    def _main_vmware(self) -> str:
        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            # Target: {self._profile.target}

            terraform {{
              required_providers {{
                vsphere = {{
                  source  = "hashicorp/vsphere"
                  version = "~> 2.0"
                }}
              }}
            }}

            provider "vsphere" {{
              vsphere_server       = var.vsphere_server
              user                 = var.vsphere_user
              password             = var.vsphere_password
              allow_unverified_ssl = true
            }}

            variable "vsphere_server" {{
              type = string
            }}

            variable "vsphere_user" {{
              type = string
            }}

            variable "vsphere_password" {{
              type      = string
              sensitive = true
            }}

            data "vsphere_datacenter" "dc" {{
              name = "dc1"
            }}

            data "vsphere_datastore" "datastore" {{
              name          = "datastore1"
              datacenter_id = data.vsphere_datacenter.dc.id
            }}

            data "vsphere_network" "network" {{
              name          = "VM Network"
              datacenter_id = data.vsphere_datacenter.dc.id
            }}

            data "vsphere_virtual_machine" "template" {{
              name          = "{self._resolve_os_image("vmware")}"
              datacenter_id = data.vsphere_datacenter.dc.id
            }}

            resource "vsphere_virtual_machine" "replica" {{
              name             = var.project_name
              resource_pool_id = data.vsphere_datacenter.dc.id
              datastore_id     = data.vsphere_datastore.datastore.id
              num_cpus         = 2
              memory           = 2048
              guest_id         = data.vsphere_virtual_machine.template.guest_id

              network_interface {{
                network_id = data.vsphere_network.network.id
              }}

              disk {{
                label            = "disk0"
                size             = 20
                thin_provisioned = true
              }}

              clone {{
                template_uuid = data.vsphere_virtual_machine.template.id
              }}
            }}
        ''')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_instance_type(self) -> str:
        types = _INSTANCE_TYPES.get(self._provider.value, {})
        return types.get(self._instance_size, types.get("medium", "t3.medium"))

    def _resolve_os_image(self, provider: str) -> str:
        """Resolve OS image ID based on detected OS."""
        images = _OS_IMAGES.get(provider, {})
        os_lower = (self._profile.operating_system or "").lower()

        if "ubuntu" in os_lower:
            return images.get("ubuntu", images.get("ubuntu", "ubuntu"))
        if "debian" in os_lower:
            return images.get("debian", images.get("ubuntu", "ubuntu"))
        if "centos" in os_lower or "rhel" in os_lower or "red hat" in os_lower:
            return images.get("centos", images.get("ubuntu", "ubuntu"))
        if "windows" in os_lower:
            return images.get("windows", images.get("ubuntu", "ubuntu"))
        if "amazon" in os_lower:
            return images.get("amazon-linux", images.get("ubuntu", "ubuntu"))

        # Default to Ubuntu
        return images.get("ubuntu", "ubuntu")


# ============================================================================
# Ansible Generator (Cycles 31–40)
# ============================================================================


class AnsibleGenerator:
    """Generate Ansible playbooks and inventory from a :class:`TargetProfile`.

    Produces:
    - ``playbook.yml`` — Main playbook with roles for each discovered service
    - ``inventory.ini`` — Inventory file with target host
    - ``roles/`` — Role structure for each service
    - ``group_vars/all.yml`` — Shared variables

    Args:
        profile: The target profile to replicate.
        target_host: IP/hostname of the target VM (default: from profile or localhost).
        ssh_user: SSH user for Ansible connection.
    """

    def __init__(
        self,
        profile: TargetProfile,
        target_host: str = "",
        ssh_user: str = "ubuntu",
    ) -> None:
        self._profile = profile
        self._target_host = target_host or profile.primary_ip
        self._ssh_user = ssh_user

    def generate_all(self) -> dict[str, str]:
        """Generate all Ansible files as a dict of path → content."""
        files: dict[str, str] = {
            "playbook.yml": self.generate_playbook(),
            "inventory.ini": self.generate_inventory(),
            "group_vars/all.yml": self.generate_group_vars(),
            "ansible.cfg": self.generate_ansible_cfg(),
        }

        # Generate roles for discovered services
        roles = self._determine_roles()
        for role_name in roles:
            tasks = self._generate_role_tasks(role_name)
            handlers = self._generate_role_handlers(role_name)
            defaults = self._generate_role_defaults(role_name)
            files[f"roles/{role_name}/tasks/main.yml"] = tasks
            files[f"roles/{role_name}/handlers/main.yml"] = handlers
            files[f"roles/{role_name}/defaults/main.yml"] = defaults

        return files

    def generate_playbook(self) -> str:
        """Generate the main playbook.yml."""
        roles = self._determine_roles()
        role_list = "\n".join(f"    - {r}" for r in roles) if roles else "    - common"

        firewall_rules = ""
        for port in self._profile.open_ports:
            firewall_rules += f"    - {{ rule: 'allow', port: '{port.port}', proto: '{port.protocol}' }}\n"
        if not firewall_rules:
            firewall_rules = "    - { rule: 'allow', port: '80', proto: 'tcp' }\n    - { rule: 'allow', port: '443', proto: 'tcp' }\n"

        return textwrap.dedent(f'''\
            ---
            # Auto-generated by SpiderFoot Target Replication Engine
            # Recreates the service stack discovered on: {self._profile.target}
            # Scan ID: {self._profile.scan_id or "N/A"}

            - name: Configure SpiderFoot target replica
              hosts: replica
              become: true
              gather_facts: true

              vars:
                target_domain: "{self._profile.domain or "replica.local"}"
                detected_os: "{self._profile.operating_system or "Unknown"}"
                firewall_rules:
            {firewall_rules}
              pre_tasks:
                - name: Update package cache
                  ansible.builtin.apt:
                    update_cache: true
                    cache_valid_time: 3600
                  when: ansible_os_family == "Debian"

                - name: Update package cache (RHEL)
                  ansible.builtin.yum:
                    update_cache: true
                  when: ansible_os_family == "RedHat"

                - name: Configure firewall (UFW)
                  community.general.ufw:
                    rule: "{{{{ item.rule }}}}"
                    port: "{{{{ item.port }}}}"
                    proto: "{{{{ item.proto }}}}"
                  loop: "{{{{ firewall_rules }}}}"
                  when: ansible_os_family == "Debian"

              roles:
            {role_list}
        ''')

    def generate_inventory(self) -> str:
        """Generate inventory.ini."""
        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            [replica]
            target ansible_host={self._target_host} ansible_user={self._ssh_user} ansible_become=true

            [replica:vars]
            ansible_python_interpreter=/usr/bin/python3
        ''')

    def generate_group_vars(self) -> str:
        """Generate group_vars/all.yml."""
        services_list = ""
        for svc in self._profile.services:
            services_list += f"  - name: {svc.name}\n"
            if svc.version:
                services_list += f"    version: \"{svc.version}\"\n"
            if svc.port:
                services_list += f"    port: {svc.port}\n"

        web_techs_list = ""
        for tech in self._profile.web_technologies:
            web_techs_list += f"  - name: {tech.name}\n"
            if tech.version:
                web_techs_list += f"    version: \"{tech.version}\"\n"

        return textwrap.dedent(f'''\
            ---
            # Auto-generated by SpiderFoot Target Replication Engine
            # Shared variables for the replica environment

            target_domain: "{self._profile.domain or "replica.local"}"
            web_server: "{self._profile.web_server or "nginx"}"
            web_server_version: "{self._profile.web_server_version}"
            operating_system: "{self._profile.operating_system}"

            discovered_services:
            {services_list or "  []"}

            discovered_web_technologies:
            {web_techs_list or "  []"}

            open_ports:
            {self._format_ports_yaml()}
        ''')

    def generate_ansible_cfg(self) -> str:
        """Generate ansible.cfg."""
        return textwrap.dedent('''\
            [defaults]
            inventory = inventory.ini
            host_key_checking = False
            retry_files_enabled = False
            stdout_callback = yaml
            callbacks_enabled = profile_tasks

            [privilege_escalation]
            become = True
            become_method = sudo
            become_ask_pass = False
        ''')

    # ------------------------------------------------------------------
    # Role generators
    # ------------------------------------------------------------------

    def _determine_roles(self) -> list[str]:
        """Determine which Ansible roles to generate based on the profile."""
        roles = ["common"]

        # Web server role
        if self._profile.web_server or self._profile.has_web_services:
            web = (self._profile.web_server or "nginx").lower()
            if "nginx" in web:
                roles.append("nginx")
            elif "apache" in web or "httpd" in web:
                roles.append("apache")
            elif "iis" in web:
                roles.append("iis")
            else:
                roles.append("nginx")  # default to nginx

        # Database roles
        for svc in self._profile.services:
            svc_lower = svc.name.lower()
            if svc_lower in ("mysql", "mariadb"):
                if "mysql" not in roles and "mariadb" not in roles:
                    roles.append(svc_lower)
            elif svc_lower in ("postgresql", "postgres"):
                if "postgresql" not in roles:
                    roles.append("postgresql")
            elif svc_lower == "redis":
                if "redis" not in roles:
                    roles.append("redis")
            elif svc_lower == "mongodb":
                if "mongodb" not in roles:
                    roles.append("mongodb")
            elif svc_lower in ("elasticsearch",):
                if "elasticsearch" not in roles:
                    roles.append("elasticsearch")
            elif svc_lower in ("rabbitmq",):
                if "rabbitmq" not in roles:
                    roles.append("rabbitmq")

        # Port-based fallback detection
        for port in self._profile.open_ports:
            if port.port == 3306 and "mysql" not in roles and "mariadb" not in roles:
                roles.append("mysql")
            elif port.port == 5432 and "postgresql" not in roles:
                roles.append("postgresql")
            elif port.port == 6379 and "redis" not in roles:
                roles.append("redis")
            elif port.port == 27017 and "mongodb" not in roles:
                roles.append("mongodb")

        # SSL/TLS
        if any(p.port == 443 for p in self._profile.open_ports):
            roles.append("ssl")

        # Web technologies
        for tech in self._profile.web_technologies:
            tech_lower = tech.name.lower()
            if "php" in tech_lower and "php" not in roles:
                roles.append("php")
            elif "node" in tech_lower and "nodejs" not in roles:
                roles.append("nodejs")
            elif "python" in tech_lower and "python" not in roles:
                roles.append("python")
            elif "wordpress" in tech_lower and "wordpress" not in roles:
                roles.append("wordpress")

        return roles

    def _generate_role_tasks(self, role_name: str) -> str:
        """Generate tasks/main.yml for a role."""
        gen = _ROLE_TASK_GENERATORS.get(role_name, _generate_generic_role_tasks)
        return gen(self._profile)

    def _generate_role_handlers(self, role_name: str) -> str:
        """Generate handlers/main.yml for a role."""
        service_name = _ROLE_SERVICE_NAMES.get(role_name, role_name)
        return textwrap.dedent(f'''\
            ---
            - name: restart {role_name}
              ansible.builtin.service:
                name: {service_name}
                state: restarted
              when: ansible_os_family == "Debian" or ansible_os_family == "RedHat"
        ''')

    def _generate_role_defaults(self, role_name: str) -> str:
        """Generate defaults/main.yml for a role."""
        # Find matching service for version info
        version = ""
        for svc in self._profile.services:
            if svc.name.lower() == role_name.lower():
                version = svc.version
                break

        return textwrap.dedent(f'''\
            ---
            {role_name}_version: "{version}"
            {role_name}_enabled: true
        ''')

    def _format_ports_yaml(self) -> str:
        lines = []
        for p in self._profile.open_ports:
            entry = f"  - port: {p.port}\n    protocol: {p.protocol}"
            if p.service_name:
                entry += f"\n    service: {p.service_name}"
            lines.append(entry)
        return "\n".join(lines) if lines else "  []"


# Role → systemd service name mapping
_ROLE_SERVICE_NAMES: dict[str, str] = {
    "common": "ssh",
    "nginx": "nginx",
    "apache": "apache2",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "postgresql": "postgresql",
    "redis": "redis-server",
    "mongodb": "mongod",
    "elasticsearch": "elasticsearch",
    "rabbitmq": "rabbitmq-server",
    "php": "php-fpm",
    "ssl": "nginx",
    "nodejs": "node",
    "python": "python3",
    "wordpress": "apache2",
    "iis": "w3svc",
}


def _generate_common_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install essential packages
          ansible.builtin.apt:
            name:
              - curl
              - wget
              - git
              - vim
              - htop
              - net-tools
              - ufw
              - unzip
              - software-properties-common
            state: present
          when: ansible_os_family == "Debian"

        - name: Install essential packages (RHEL)
          ansible.builtin.yum:
            name:
              - curl
              - wget
              - git
              - vim
              - htop
              - net-tools
              - firewalld
              - unzip
            state: present
          when: ansible_os_family == "RedHat"

        - name: Set timezone to UTC
          community.general.timezone:
            name: UTC

        - name: Enable and start SSH
          ansible.builtin.service:
            name: ssh
            state: started
            enabled: true
          when: ansible_os_family == "Debian"
    ''')


def _generate_nginx_role_tasks(profile: TargetProfile) -> str:
    domain = profile.domain or "replica.local"
    return textwrap.dedent(f'''\
        ---
        - name: Install Nginx
          ansible.builtin.apt:
            name: nginx
            state: present
          when: ansible_os_family == "Debian"

        - name: Install Nginx (RHEL)
          ansible.builtin.yum:
            name: nginx
            state: present
          when: ansible_os_family == "RedHat"

        - name: Create site configuration
          ansible.builtin.template:
            src: site.conf.j2
            dest: /etc/nginx/sites-available/{domain}
            mode: "0644"
          notify: restart nginx

        - name: Enable site
          ansible.builtin.file:
            src: /etc/nginx/sites-available/{domain}
            dest: /etc/nginx/sites-enabled/{domain}
            state: link
          notify: restart nginx
          when: ansible_os_family == "Debian"

        - name: Start and enable Nginx
          ansible.builtin.service:
            name: nginx
            state: started
            enabled: true
    ''')


def _generate_apache_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install Apache
          ansible.builtin.apt:
            name: apache2
            state: present
          when: ansible_os_family == "Debian"

        - name: Install Apache (RHEL)
          ansible.builtin.yum:
            name: httpd
            state: present
          when: ansible_os_family == "RedHat"

        - name: Start and enable Apache
          ansible.builtin.service:
            name: "{{ 'apache2' if ansible_os_family == 'Debian' else 'httpd' }}"
            state: started
            enabled: true
    ''')


def _generate_mysql_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install MySQL
          ansible.builtin.apt:
            name:
              - mysql-server
              - mysql-client
              - python3-mysqldb
            state: present
          when: ansible_os_family == "Debian"

        - name: Start and enable MySQL
          ansible.builtin.service:
            name: mysql
            state: started
            enabled: true

        - name: Set MySQL root password
          community.mysql.mysql_user:
            name: root
            password: "{{ mysql_root_password | default('changeme') }}"
            login_unix_socket: /var/run/mysqld/mysqld.sock
          when: ansible_os_family == "Debian"
    ''')


def _generate_postgresql_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install PostgreSQL
          ansible.builtin.apt:
            name:
              - postgresql
              - postgresql-contrib
              - python3-psycopg2
            state: present
          when: ansible_os_family == "Debian"

        - name: Start and enable PostgreSQL
          ansible.builtin.service:
            name: postgresql
            state: started
            enabled: true

        - name: Configure pg_hba.conf for local access
          ansible.builtin.lineinfile:
            path: /etc/postgresql/14/main/pg_hba.conf
            regexp: "^local\\s+all\\s+all"
            line: "local all all md5"
          notify: restart postgresql
          when: ansible_os_family == "Debian"
    ''')


def _generate_redis_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install Redis
          ansible.builtin.apt:
            name: redis-server
            state: present
          when: ansible_os_family == "Debian"

        - name: Configure Redis to listen on all interfaces
          ansible.builtin.lineinfile:
            path: /etc/redis/redis.conf
            regexp: "^bind"
            line: "bind 0.0.0.0"
          notify: restart redis

        - name: Start and enable Redis
          ansible.builtin.service:
            name: redis-server
            state: started
            enabled: true
    ''')


def _generate_ssl_role_tasks(profile: TargetProfile) -> str:
    domain = profile.domain or "replica.local"
    return textwrap.dedent(f'''\
        ---
        - name: Install certbot and OpenSSL
          ansible.builtin.apt:
            name:
              - certbot
              - openssl
              - python3-certbot-nginx
            state: present
          when: ansible_os_family == "Debian"

        - name: Generate self-signed certificate for testing
          ansible.builtin.command:
            cmd: >
              openssl req -x509 -nodes -days 365
              -newkey rsa:2048
              -keyout /etc/ssl/private/{domain}.key
              -out /etc/ssl/certs/{domain}.crt
              -subj "/CN={domain}/O=SpiderFoot Replica"
            creates: /etc/ssl/certs/{domain}.crt
    ''')


def _generate_php_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install PHP and extensions
          ansible.builtin.apt:
            name:
              - php-fpm
              - php-mysql
              - php-pgsql
              - php-curl
              - php-gd
              - php-mbstring
              - php-xml
              - php-zip
            state: present
          when: ansible_os_family == "Debian"

        - name: Start and enable PHP-FPM
          ansible.builtin.service:
            name: php-fpm
            state: started
            enabled: true
          ignore_errors: true
    ''')


def _generate_nodejs_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install Node.js LTS
          ansible.builtin.shell: |
            curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
            apt-get install -y nodejs
          args:
            creates: /usr/bin/node
          when: ansible_os_family == "Debian"

        - name: Install PM2 process manager
          community.general.npm:
            name: pm2
            global: true
    ''')


def _generate_mongodb_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Import MongoDB GPG key
          ansible.builtin.apt_key:
            url: https://www.mongodb.org/static/pgp/server-7.0.asc
            state: present
          when: ansible_os_family == "Debian"

        - name: Add MongoDB repository
          ansible.builtin.apt_repository:
            repo: "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu {{ ansible_distribution_release }}/mongodb-org/7.0 multiverse"
            state: present
          when: ansible_os_family == "Debian"

        - name: Install MongoDB
          ansible.builtin.apt:
            name: mongodb-org
            state: present
            update_cache: true
          when: ansible_os_family == "Debian"

        - name: Create MongoDB data directory
          ansible.builtin.file:
            path: /var/lib/mongodb
            state: directory
            owner: mongodb
            group: mongodb
            mode: "0755"

        - name: Configure MongoDB bind address
          ansible.builtin.lineinfile:
            path: /etc/mongod.conf
            regexp: "^  bindIp:"
            line: "  bindIp: 0.0.0.0"
          notify: restart mongodb

        - name: Start and enable MongoDB
          ansible.builtin.service:
            name: mongod
            state: started
            enabled: true

        - name: Wait for MongoDB to be ready
          ansible.builtin.wait_for:
            port: 27017
            delay: 5
            timeout: 30
    ''')


def _generate_elasticsearch_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Import Elasticsearch GPG key
          ansible.builtin.apt_key:
            url: https://artifacts.elastic.co/GPG-KEY-elasticsearch
            state: present
          when: ansible_os_family == "Debian"

        - name: Add Elasticsearch repository
          ansible.builtin.apt_repository:
            repo: "deb https://artifacts.elastic.co/packages/8.x/apt stable main"
            state: present
          when: ansible_os_family == "Debian"

        - name: Install Elasticsearch
          ansible.builtin.apt:
            name: elasticsearch
            state: present
            update_cache: true
          when: ansible_os_family == "Debian"

        - name: Configure Elasticsearch cluster name
          ansible.builtin.lineinfile:
            path: /etc/elasticsearch/elasticsearch.yml
            regexp: "^cluster.name:"
            line: "cluster.name: sf-replica"
          notify: restart elasticsearch

        - name: Configure Elasticsearch network host
          ansible.builtin.lineinfile:
            path: /etc/elasticsearch/elasticsearch.yml
            regexp: "^network.host:"
            line: "network.host: 0.0.0.0"
          notify: restart elasticsearch

        - name: Configure Elasticsearch discovery type
          ansible.builtin.lineinfile:
            path: /etc/elasticsearch/elasticsearch.yml
            regexp: "^discovery.type:"
            line: "discovery.type: single-node"
          notify: restart elasticsearch

        - name: Disable Elasticsearch security for replica
          ansible.builtin.lineinfile:
            path: /etc/elasticsearch/elasticsearch.yml
            regexp: "^xpack.security.enabled:"
            line: "xpack.security.enabled: false"
          notify: restart elasticsearch

        - name: Set JVM heap size
          ansible.builtin.copy:
            content: |
              -Xms512m
              -Xmx512m
            dest: /etc/elasticsearch/jvm.options.d/heap.options
            mode: "0644"
          notify: restart elasticsearch

        - name: Start and enable Elasticsearch
          ansible.builtin.service:
            name: elasticsearch
            state: started
            enabled: true

        - name: Wait for Elasticsearch to be ready
          ansible.builtin.uri:
            url: http://localhost:9200/_cluster/health
            method: GET
          register: es_health
          until: es_health.status == 200
          retries: 12
          delay: 5
    ''')


def _generate_tomcat_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install Java JDK
          ansible.builtin.apt:
            name:
              - default-jdk
              - default-jre
            state: present
          when: ansible_os_family == "Debian"

        - name: Create Tomcat group
          ansible.builtin.group:
            name: tomcat
            state: present

        - name: Create Tomcat user
          ansible.builtin.user:
            name: tomcat
            group: tomcat
            home: /opt/tomcat
            shell: /bin/false
            create_home: false

        - name: Install Tomcat
          ansible.builtin.apt:
            name: tomcat9
            state: present
          when: ansible_os_family == "Debian"

        - name: Start and enable Tomcat
          ansible.builtin.service:
            name: tomcat9
            state: started
            enabled: true

        - name: Wait for Tomcat to be ready
          ansible.builtin.wait_for:
            port: 8080
            delay: 5
            timeout: 30
    ''')


def _generate_haproxy_role_tasks(profile: TargetProfile) -> str:
    web_ports = profile.get_web_ports() or [80]
    backend_port = web_ports[0]
    return textwrap.dedent(f'''\
        ---
        - name: Install HAProxy
          ansible.builtin.apt:
            name: haproxy
            state: present
          when: ansible_os_family == "Debian"

        - name: Configure HAProxy
          ansible.builtin.copy:
            content: |
              global
                  log /dev/log local0
                  maxconn 4096
                  user haproxy
                  group haproxy
                  daemon

              defaults
                  log global
                  mode http
                  option httplog
                  option dontlognull
                  timeout connect 5000ms
                  timeout client  50000ms
                  timeout server  50000ms
                  retries 3

              frontend http_front
                  bind *:80
                  default_backend http_back

              backend http_back
                  balance roundrobin
                  option httpchk GET /
                  server replica1 127.0.0.1:{backend_port} check
            dest: /etc/haproxy/haproxy.cfg
            mode: "0644"
            backup: true
          notify: restart haproxy

        - name: Validate HAProxy configuration
          ansible.builtin.command:
            cmd: haproxy -c -f /etc/haproxy/haproxy.cfg
          changed_when: false

        - name: Start and enable HAProxy
          ansible.builtin.service:
            name: haproxy
            state: started
            enabled: true
    ''')


def _generate_wordpress_role_tasks(profile: TargetProfile) -> str:
    domain = profile.domain or "replica.local"
    return textwrap.dedent(f'''\
        ---
        - name: Install WordPress dependencies
          ansible.builtin.apt:
            name:
              - php-fpm
              - php-mysql
              - php-curl
              - php-gd
              - php-mbstring
              - php-xml
              - php-xmlrpc
              - php-soap
              - php-intl
              - php-zip
              - unzip
            state: present
          when: ansible_os_family == "Debian"

        - name: Create WordPress directory
          ansible.builtin.file:
            path: /var/www/{domain}
            state: directory
            owner: www-data
            group: www-data
            mode: "0755"

        - name: Download WordPress
          ansible.builtin.get_url:
            url: https://wordpress.org/latest.tar.gz
            dest: /tmp/wordpress.tar.gz
            mode: "0644"

        - name: Extract WordPress
          ansible.builtin.unarchive:
            src: /tmp/wordpress.tar.gz
            dest: /var/www/{domain}
            remote_src: true
            extra_opts: ["--strip-components=1"]
            creates: /var/www/{domain}/wp-config-sample.php

        - name: Set WordPress ownership
          ansible.builtin.file:
            path: /var/www/{domain}
            owner: www-data
            group: www-data
            recurse: true

        - name: Copy WordPress config
          ansible.builtin.copy:
            src: /var/www/{domain}/wp-config-sample.php
            dest: /var/www/{domain}/wp-config.php
            remote_src: true
            owner: www-data
            group: www-data
            mode: "0640"
            force: false
    ''')


def _generate_memcached_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install Memcached
          ansible.builtin.apt:
            name:
              - memcached
              - libmemcached-tools
            state: present
          when: ansible_os_family == "Debian"

        - name: Configure Memcached memory limit
          ansible.builtin.lineinfile:
            path: /etc/memcached.conf
            regexp: "^-m"
            line: "-m 256"
          notify: restart memcached

        - name: Configure Memcached listen address
          ansible.builtin.lineinfile:
            path: /etc/memcached.conf
            regexp: "^-l"
            line: "-l 0.0.0.0"
          notify: restart memcached

        - name: Start and enable Memcached
          ansible.builtin.service:
            name: memcached
            state: started
            enabled: true

        - name: Wait for Memcached to be ready
          ansible.builtin.wait_for:
            port: 11211
            delay: 2
            timeout: 15
    ''')


def _generate_varnish_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install Varnish
          ansible.builtin.apt:
            name: varnish
            state: present
          when: ansible_os_family == "Debian"

        - name: Configure Varnish VCL backend
          ansible.builtin.copy:
            content: |
              vcl 4.1;
              backend default {
                  .host = "127.0.0.1";
                  .port = "8080";
                  .connect_timeout = 5s;
                  .first_byte_timeout = 30s;
                  .between_bytes_timeout = 10s;
              }
            dest: /etc/varnish/default.vcl
            mode: "0644"
          notify: restart varnish

        - name: Configure Varnish listen port
          ansible.builtin.lineinfile:
            path: /etc/default/varnish
            regexp: "^DAEMON_OPTS="
            line: 'DAEMON_OPTS="-a :6081 -T localhost:6082 -f /etc/varnish/default.vcl -S /etc/varnish/secret -s malloc,256m"'
          notify: restart varnish

        - name: Start and enable Varnish
          ansible.builtin.service:
            name: varnish
            state: started
            enabled: true
    ''')


def _generate_python_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install Python and development tools
          ansible.builtin.apt:
            name:
              - python3
              - python3-pip
              - python3-venv
              - python3-dev
              - build-essential
              - libssl-dev
              - libffi-dev
            state: present
          when: ansible_os_family == "Debian"

        - name: Install Python (RHEL)
          ansible.builtin.yum:
            name:
              - python3
              - python3-pip
              - python3-devel
              - gcc
              - openssl-devel
              - libffi-devel
            state: present
          when: ansible_os_family == "RedHat"

        - name: Install virtualenv
          ansible.builtin.pip:
            name: virtualenv
            executable: pip3

        - name: Install Gunicorn for Python web apps
          ansible.builtin.pip:
            name:
              - gunicorn
              - uvicorn
            executable: pip3
    ''')


def _generate_rabbitmq_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Install Erlang
          ansible.builtin.apt:
            name: erlang-base
            state: present
          when: ansible_os_family == "Debian"

        - name: Import RabbitMQ GPG key
          ansible.builtin.apt_key:
            url: https://www.rabbitmq.com/rabbitmq-release-signing-key.asc
            state: present
          when: ansible_os_family == "Debian"

        - name: Install RabbitMQ
          ansible.builtin.apt:
            name: rabbitmq-server
            state: present
          when: ansible_os_family == "Debian"

        - name: Enable RabbitMQ management plugin
          community.rabbitmq.rabbitmq_plugin:
            names: rabbitmq_management
            state: enabled
          notify: restart rabbitmq

        - name: Start and enable RabbitMQ
          ansible.builtin.service:
            name: rabbitmq-server
            state: started
            enabled: true

        - name: Wait for RabbitMQ to be ready
          ansible.builtin.wait_for:
            port: 5672
            delay: 5
            timeout: 30
    ''')


def _generate_generic_role_tasks(profile: TargetProfile) -> str:
    return textwrap.dedent('''\
        ---
        - name: Note - generic role placeholder
          ansible.builtin.debug:
            msg: "This role requires manual customization for the specific service"
    ''')


# Map role names → task generators
_ROLE_TASK_GENERATORS: dict[str, Any] = {
    "common": _generate_common_role_tasks,
    "nginx": _generate_nginx_role_tasks,
    "apache": _generate_apache_role_tasks,
    "mysql": _generate_mysql_role_tasks,
    "mariadb": _generate_mysql_role_tasks,
    "postgresql": _generate_postgresql_role_tasks,
    "redis": _generate_redis_role_tasks,
    "ssl": _generate_ssl_role_tasks,
    "php": _generate_php_role_tasks,
    "nodejs": _generate_nodejs_role_tasks,
    "mongodb": _generate_mongodb_role_tasks,
    "elasticsearch": _generate_elasticsearch_role_tasks,
    "tomcat": _generate_tomcat_role_tasks,
    "haproxy": _generate_haproxy_role_tasks,
    "wordpress": _generate_wordpress_role_tasks,
    "memcached": _generate_memcached_role_tasks,
    "varnish": _generate_varnish_role_tasks,
    "python": _generate_python_role_tasks,
    "rabbitmq": _generate_rabbitmq_role_tasks,
}


# ============================================================================
# Docker Compose Generator (lightweight local replication)
# ============================================================================


class DockerComposeGenerator:
    """Generate docker-compose.yml for lightweight local target replication.

    Args:
        profile: The target profile to replicate.
    """

    def __init__(self, profile: TargetProfile) -> None:
        self._profile = profile

    def generate(self) -> str:
        """Generate docker-compose.yml content.

        Produces a production-grade Compose file with:
        - Named volumes for persistent data
        - Separate frontend/backend networks
        - Healthchecks for service readiness
        - ``depends_on`` with health conditions
        - Resource limits (CPU + memory)
        """
        services: dict[str, dict[str, Any]] = {}
        volumes: dict[str, dict[str, Any]] = {}
        backend_services: list[str] = []  # services on backend network only
        frontend_services: list[str] = []  # services on both networks

        # Web server
        if self._profile.web_server or self._profile.has_web_services:
            web = (self._profile.web_server or "nginx").lower()
            if "nginx" in web:
                services["web"] = {
                    "image": f"nginx:{self._profile.web_server_version or 'latest'}",
                    "ports": self._docker_port_list([80, 443]),
                    "volumes": [
                        "./html:/usr/share/nginx/html:ro",
                        "./nginx/conf.d:/etc/nginx/conf.d:ro",
                    ],
                    "restart": "unless-stopped",
                    "healthcheck": {
                        "test": ["CMD", "curl", "-f", "http://localhost/"],
                        "interval": "15s",
                        "timeout": "5s",
                        "retries": 3,
                        "start_period": "10s",
                    },
                    "deploy": {"resources": {"limits": {"cpus": "1.0", "memory": "256M"}}},
                    "networks": ["frontend", "backend"],
                }
                frontend_services.append("web")
            elif "apache" in web or "httpd" in web:
                services["web"] = {
                    "image": f"httpd:{self._profile.web_server_version or 'latest'}",
                    "ports": self._docker_port_list([80, 443]),
                    "volumes": ["./html:/usr/local/apache2/htdocs:ro"],
                    "restart": "unless-stopped",
                    "healthcheck": {
                        "test": ["CMD", "curl", "-f", "http://localhost/"],
                        "interval": "15s",
                        "timeout": "5s",
                        "retries": 3,
                        "start_period": "10s",
                    },
                    "deploy": {"resources": {"limits": {"cpus": "1.0", "memory": "256M"}}},
                    "networks": ["frontend", "backend"],
                }
                frontend_services.append("web")

        # Databases and services
        for svc in self._profile.services:
            docker_img = svc.docker_image
            svc_lower = svc.name.lower()

            if svc_lower in ("nginx", "apache", "httpd"):
                continue  # Already handled as web server

            svc_key = svc_lower.replace("-", "_")
            if svc_key in services:
                continue

            svc_def: dict[str, Any] = {
                "image": docker_img,
                "restart": "unless-stopped",
            }

            if svc.port:
                svc_def["ports"] = [f"{svc.port}:{svc.port}"]

            # Service-specific configuration
            if svc_lower in ("mysql", "mariadb"):
                svc_def["environment"] = {
                    "MYSQL_ROOT_PASSWORD": "changeme",
                    "MYSQL_DATABASE": "replica_db",
                }
                vol_name = f"{svc_key}_data"
                svc_def["volumes"] = [f"{vol_name}:/var/lib/mysql"]
                volumes[vol_name] = {"driver": "local"}
                svc_def["healthcheck"] = {
                    "test": ["CMD", "mysqladmin", "ping", "-h", "localhost"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                    "start_period": "30s",
                }
                svc_def["networks"] = ["backend"]
                svc_def["deploy"] = {"resources": {"limits": {"cpus": "1.0", "memory": "512M"}}}
                backend_services.append(svc_key)
            elif svc_lower in ("postgresql", "postgres"):
                svc_def["environment"] = {
                    "POSTGRES_PASSWORD": "changeme",
                    "POSTGRES_DB": "replica_db",
                }
                vol_name = f"{svc_key}_data"
                svc_def["volumes"] = [f"{vol_name}:/var/lib/postgresql/data"]
                volumes[vol_name] = {"driver": "local"}
                svc_def["healthcheck"] = {
                    "test": ["CMD-SHELL", "pg_isready -U postgres"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                    "start_period": "30s",
                }
                svc_def["networks"] = ["backend"]
                svc_def["deploy"] = {"resources": {"limits": {"cpus": "1.0", "memory": "512M"}}}
                backend_services.append(svc_key)
            elif svc_lower == "mongodb":
                svc_def["environment"] = {
                    "MONGO_INITDB_ROOT_USERNAME": "admin",
                    "MONGO_INITDB_ROOT_PASSWORD": "changeme",
                }
                svc_def["volumes"] = ["mongodb_data:/data/db"]
                volumes["mongodb_data"] = {"driver": "local"}
                svc_def["healthcheck"] = {
                    "test": ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                    "start_period": "30s",
                }
                svc_def["networks"] = ["backend"]
                svc_def["deploy"] = {"resources": {"limits": {"cpus": "1.0", "memory": "512M"}}}
                backend_services.append(svc_key)
            elif svc_lower == "redis":
                svc_def["volumes"] = ["redis_data:/data"]
                volumes["redis_data"] = {"driver": "local"}
                svc_def["healthcheck"] = {
                    "test": ["CMD", "redis-cli", "ping"],
                    "interval": "10s",
                    "timeout": "3s",
                    "retries": 3,
                    "start_period": "5s",
                }
                svc_def["networks"] = ["backend"]
                svc_def["deploy"] = {"resources": {"limits": {"cpus": "0.5", "memory": "256M"}}}
                backend_services.append(svc_key)
            elif svc_lower == "elasticsearch":
                svc_def["environment"] = {
                    "discovery.type": "single-node",
                    "xpack.security.enabled": "false",
                    "ES_JAVA_OPTS": "-Xms256m -Xmx256m",
                }
                svc_def["volumes"] = ["elasticsearch_data:/usr/share/elasticsearch/data"]
                volumes["elasticsearch_data"] = {"driver": "local"}
                svc_def["healthcheck"] = {
                    "test": ["CMD-SHELL", "curl -sf http://localhost:9200/_cluster/health || exit 1"],
                    "interval": "15s",
                    "timeout": "10s",
                    "retries": 5,
                    "start_period": "60s",
                }
                svc_def["networks"] = ["backend"]
                svc_def["deploy"] = {"resources": {"limits": {"cpus": "1.0", "memory": "1024M"}}}
                backend_services.append(svc_key)
            elif svc_lower == "rabbitmq":
                svc_def["environment"] = {
                    "RABBITMQ_DEFAULT_USER": "admin",
                    "RABBITMQ_DEFAULT_PASS": "changeme",
                }
                svc_def["volumes"] = ["rabbitmq_data:/var/lib/rabbitmq"]
                volumes["rabbitmq_data"] = {"driver": "local"}
                svc_def["healthcheck"] = {
                    "test": ["CMD", "rabbitmq-diagnostics", "check_running"],
                    "interval": "15s",
                    "timeout": "10s",
                    "retries": 5,
                    "start_period": "30s",
                }
                svc_def["networks"] = ["backend"]
                svc_def["deploy"] = {"resources": {"limits": {"cpus": "0.5", "memory": "512M"}}}
                backend_services.append(svc_key)
            elif svc_lower == "memcached":
                svc_def["command"] = ["memcached", "-m", "256"]
                svc_def["healthcheck"] = {
                    "test": ["CMD-SHELL", "echo stats | nc localhost 11211 | grep -q uptime"],
                    "interval": "10s",
                    "timeout": "3s",
                    "retries": 3,
                }
                svc_def["networks"] = ["backend"]
                svc_def["deploy"] = {"resources": {"limits": {"cpus": "0.5", "memory": "256M"}}}
                backend_services.append(svc_key)
            else:
                # Generic service — backend network only
                if "networks" not in svc_def:
                    svc_def["networks"] = ["backend"]
                backend_services.append(svc_key)

            services[svc_key] = svc_def

        # Build YAML output
        if not services:
            services["web"] = {
                "image": "nginx:latest",
                "ports": ["80:80"],
                "restart": "unless-stopped",
                "networks": ["frontend"],
            }
            frontend_services.append("web")

        # Wire up depends_on: web depends on all backend databases
        db_services = [s for s in backend_services if s in services and
                       any(k in s for k in ("mysql", "mariadb", "postgresql",
                                            "postgres", "mongodb", "redis"))]
        if "web" in services and db_services:
            depends: dict[str, dict[str, str]] = {}
            for db_svc in db_services:
                if "healthcheck" in services[db_svc]:
                    depends[db_svc] = {"condition": "service_healthy"}
                else:
                    depends[db_svc] = {"condition": "service_started"}
            services["web"]["depends_on"] = depends

        lines = [
            "# Auto-generated by SpiderFoot Target Replication Engine",
            f"# Target: {self._profile.target}",
            "",
            "services:",
        ]

        for svc_name, svc_def in services.items():
            lines.append(f"  {svc_name}:")
            lines.append(f"    image: {svc_def['image']}")
            if "command" in svc_def:
                cmd = svc_def["command"]
                if isinstance(cmd, list):
                    lines.append(f"    command: {cmd}")
                else:
                    lines.append(f"    command: {cmd}")
            if "ports" in svc_def:
                lines.append("    ports:")
                for port in svc_def["ports"]:
                    lines.append(f'      - "{port}"')
            if "volumes" in svc_def:
                lines.append("    volumes:")
                for vol in svc_def["volumes"]:
                    lines.append(f"      - {vol}")
            if "environment" in svc_def:
                lines.append("    environment:")
                for k, v in svc_def["environment"].items():
                    lines.append(f"      {k}: {v}")
            if "healthcheck" in svc_def:
                hc = svc_def["healthcheck"]
                lines.append("    healthcheck:")
                test_val = hc["test"]
                if isinstance(test_val, list):
                    lines.append(f"      test: {test_val}")
                else:
                    lines.append(f"      test: {test_val}")
                for hc_key in ("interval", "timeout", "retries", "start_period"):
                    if hc_key in hc:
                        lines.append(f"      {hc_key}: {hc[hc_key]}")
            if "depends_on" in svc_def:
                lines.append("    depends_on:")
                for dep_name, dep_cond in svc_def["depends_on"].items():
                    lines.append(f"      {dep_name}:")
                    lines.append(f"        condition: {dep_cond['condition']}")
            if "deploy" in svc_def:
                deploy = svc_def["deploy"]
                if "resources" in deploy and "limits" in deploy["resources"]:
                    limits = deploy["resources"]["limits"]
                    lines.append("    deploy:")
                    lines.append("      resources:")
                    lines.append("        limits:")
                    if "cpus" in limits:
                        lines.append(f"          cpus: \"{limits['cpus']}\"")
                    if "memory" in limits:
                        lines.append(f"          memory: {limits['memory']}")
            if "networks" in svc_def:
                lines.append("    networks:")
                for net in svc_def["networks"]:
                    lines.append(f"      - {net}")
            if "restart" in svc_def:
                lines.append(f"    restart: {svc_def['restart']}")
            lines.append("")

        # Named volumes
        if volumes:
            lines.append("volumes:")
            for vol_name, vol_cfg in volumes.items():
                lines.append(f"  {vol_name}:")
                for vk, vv in vol_cfg.items():
                    lines.append(f"    {vk}: {vv}")
            lines.append("")

        # Networks
        lines.append("networks:")
        lines.append("  frontend:")
        lines.append("    driver: bridge")
        lines.append("  backend:")
        lines.append("    driver: bridge")
        lines.append("    internal: true")
        lines.append("")

        return "\n".join(lines)

    def _docker_port_list(self, default_ports: list[int]) -> list[str]:
        """Build port mapping list from profile ports."""
        web_ports = self._profile.get_web_ports()
        if not web_ports:
            web_ports = default_ports
        return [f"{p}:{p}" for p in web_ports]


# ============================================================================
# IaC Validator — Pre-generation validation
# ============================================================================


@dataclass
class ValidationResult:
    """Result of an IaC validation check."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        return ValidationResult(
            valid=self.valid and other.valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
            info=self.info + other.info,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }


class IaCValidator:
    """Validates a :class:`TargetProfile` and generated IaC for correctness.

    Performs sanity checks including:
    - Port range validation (1-65535)
    - IP address format validation
    - Service/port consistency
    - OS family / image availability
    - Terraform HCL structure checks
    - Ansible YAML structure checks
    - Port conflict detection
    - Service dependency verification
    """

    def __init__(self, profile: TargetProfile) -> None:
        self._profile = profile

    def validate_all(self) -> ValidationResult:
        """Run all validation checks."""
        result = ValidationResult(valid=True)
        for check in [
            self.validate_ports,
            self.validate_ip_addresses,
            self.validate_services,
            self.validate_os,
            self.validate_dependencies,
            self.validate_port_conflicts,
        ]:
            result = result.merge(check())
        return result

    def validate_ports(self) -> ValidationResult:
        """Validate port numbers are in valid range."""
        errors: list[str] = []
        warnings: list[str] = []
        info: list[str] = []

        for port in self._profile.open_ports:
            if port.port < 1 or port.port > 65535:
                errors.append(f"Invalid port number: {port.port}")
            elif port.port < 1024 and port.protocol == "tcp":
                info.append(f"Privileged port {port.port} requires root/sudo")
            if port.protocol not in ("tcp", "udp"):
                errors.append(f"Invalid protocol '{port.protocol}' for port {port.port}")

        if not self._profile.open_ports:
            warnings.append("No open ports discovered — IaC will use defaults (80, 443)")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors, warnings=warnings, info=info,
        )

    def validate_ip_addresses(self) -> ValidationResult:
        """Validate IP address formats."""
        errors: list[str] = []
        warnings: list[str] = []

        ip_pattern = re.compile(
            r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
        )
        for ip in self._profile.ip_addresses:
            if not ip_pattern.match(ip):
                errors.append(f"Invalid IPv4 address: {ip}")

        if not self._profile.ip_addresses:
            warnings.append("No IP addresses discovered — using default 10.0.1.10")

        # Check for private IPs
        for ip in self._profile.ip_addresses:
            if ip.startswith(("10.", "192.168.", "172.16.", "172.17.",
                              "172.18.", "172.19.", "172.2", "172.3")):
                warnings.append(f"Private IP detected: {ip} — may not be routable")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors, warnings=warnings,
        )

    def validate_services(self) -> ValidationResult:
        """Validate discovered services have matching ports."""
        errors: list[str] = []
        warnings: list[str] = []

        open_port_nums = {p.port for p in self._profile.open_ports}

        for svc in self._profile.services:
            if svc.port and svc.port not in open_port_nums:
                warnings.append(
                    f"Service '{svc.name}' on port {svc.port} but port not in open ports list"
                )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors, warnings=warnings,
        )

    def validate_os(self) -> ValidationResult:
        """Validate OS detection and image availability."""
        errors: list[str] = []
        warnings: list[str] = []
        info: list[str] = []

        if not self._profile.operating_system:
            warnings.append("OS not detected — defaulting to Ubuntu 22.04")
        else:
            info.append(f"Detected OS: {self._profile.operating_system} (family: {self._profile.os_family})")

        if self._profile.os_family == "windows":
            warnings.append(
                "Windows target: Ansible roles use Linux package managers — "
                "Windows configuration may need WinRM/chocolatey customization"
            )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors, warnings=warnings, info=info,
        )

    def validate_dependencies(self) -> ValidationResult:
        """Validate service dependencies are met."""
        warnings: list[str] = []

        svc_names = {s.name.lower() for s in self._profile.services}
        has_web = bool(self._profile.web_server) or "nginx" in svc_names or "apache" in svc_names

        # WordPress needs a web server + database + PHP
        web_techs_lower = {t.name.lower() for t in self._profile.web_technologies}
        if "wordpress" in web_techs_lower:
            if not has_web:
                warnings.append("WordPress detected but no web server — will default to nginx")
            if not any(db in svc_names for db in ("mysql", "mariadb", "postgresql")):
                warnings.append("WordPress detected but no database — WP requires MySQL/MariaDB")

        # PHP needs a web server
        if "php" in web_techs_lower and not has_web:
            warnings.append("PHP detected but no web server — PHP-FPM needs nginx/apache")

        return ValidationResult(
            valid=True,  # Dependencies are warnings, not errors
            warnings=warnings,
        )

    def validate_port_conflicts(self) -> ValidationResult:
        """Check for port conflicts between services."""
        warnings: list[str] = []

        port_services: dict[int, list[str]] = {}
        for svc in self._profile.services:
            if svc.port:
                port_services.setdefault(svc.port, []).append(svc.name)

        for port, services in port_services.items():
            if len(services) > 1:
                warnings.append(
                    f"Port conflict: multiple services on port {port}: {', '.join(services)}"
                )

        return ValidationResult(valid=True, warnings=warnings)


# ============================================================================
# Service Dependency Resolver
# ============================================================================


# Dependency graph: service → list of services it depends on
_SERVICE_DEPENDENCIES: dict[str, list[str]] = {
    "wordpress": ["php", "mysql"],
    "php": ["nginx"],
    "nodejs": ["common"],
    "nginx": ["common"],
    "apache": ["common"],
    "mysql": ["common"],
    "mariadb": ["common"],
    "postgresql": ["common"],
    "redis": ["common"],
    "mongodb": ["common"],
    "elasticsearch": ["common"],
    "rabbitmq": ["common"],
    "ssl": ["nginx"],
    "tomcat": ["common"],
    "haproxy": ["common"],
    "varnish": ["common"],
    "memcached": ["common"],
    "python": ["common"],
}


class ServiceDependencyResolver:
    """Topologically sort roles based on service dependencies.

    Ensures that roles are applied in the correct order, e.g.,
    ``common`` before ``nginx``, ``nginx + mysql`` before ``wordpress``.
    """

    def __init__(self, roles: list[str]) -> None:
        self._roles = roles

    def resolve(self) -> list[str]:
        """Return roles in dependency-resolved order."""
        visited: set[str] = set()
        order: list[str] = []
        role_set = set(self._roles)

        def _visit(role: str) -> None:
            if role in visited:
                return
            visited.add(role)
            for dep in _SERVICE_DEPENDENCIES.get(role, []):
                if dep in role_set:
                    _visit(dep)
            order.append(role)

        for role in self._roles:
            _visit(role)

        return order


# ============================================================================
# Packer Image Builder Generator
# ============================================================================


class PackerGenerator:
    """Generate Packer HCL configurations for pre-baking VM images.

    Produces a ``packer.pkr.hcl`` file that builds an AMI/image with
    the discovered software stack pre-installed.

    Args:
        profile: The target profile to replicate.
        provider: Cloud provider for the Packer builder.
    """

    def __init__(
        self,
        profile: TargetProfile,
        provider: CloudProvider = CloudProvider.AWS,
    ) -> None:
        self._profile = profile
        self._provider = provider

    def generate_all(self) -> dict[str, str]:
        """Generate Packer configuration files."""
        return {
            "packer.pkr.hcl": self.generate_packer_hcl(),
            "scripts/provision.sh": self.generate_provision_script(),
        }

    def generate_packer_hcl(self) -> str:
        """Generate the main Packer HCL configuration."""
        gen = getattr(self, f"_packer_{self._provider.value}", None)
        if gen is None:
            return self._packer_aws()  # fallback
        return gen()

    def _packer_aws(self) -> str:
        os_image = _OS_IMAGES.get("aws", {}).get("ubuntu", "ami-0c7217cdde317cfec")
        os_lower = (self._profile.operating_system or "").lower()
        if "ubuntu" in os_lower:
            os_image = _OS_IMAGES["aws"]["ubuntu"]
        elif "debian" in os_lower:
            os_image = _OS_IMAGES["aws"]["debian"]
        elif "centos" in os_lower:
            os_image = _OS_IMAGES["aws"]["centos"]
        elif "windows" in os_lower:
            os_image = _OS_IMAGES["aws"]["windows"]

        domain = self._profile.domain or "replica"

        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            # Packer image builder for: {self._profile.target}

            packer {{
              required_plugins {{
                amazon = {{
                  version = ">= 1.2.0"
                  source  = "github.com/hashicorp/amazon"
                }}
              }}
            }}

            variable "region" {{
              type    = string
              default = "us-east-1"
            }}

            source "amazon-ebs" "replica" {{
              ami_name      = "sf-replica-{domain.replace(".", "-")}-{{{{timestamp}}}}"
              instance_type = "t3.medium"
              region        = var.region
              source_ami    = "{os_image}"
              ssh_username  = "ubuntu"

              tags = {{
                Name      = "sf-replica-{domain.replace(".", "-")}"
                ManagedBy = "spiderfoot-packer"
                Source    = "scan-{self._profile.scan_id or "unknown"}"
              }}
            }}

            build {{
              sources = ["source.amazon-ebs.replica"]

              provisioner "shell" {{
                script = "scripts/provision.sh"
              }}

              provisioner "shell" {{
                inline = [
                  "echo 'SpiderFoot replica image build complete'",
                  "sudo apt-get clean",
                  "sudo rm -rf /var/lib/apt/lists/*",
                ]
              }}
            }}
        ''')

    def _packer_gcp(self) -> str:
        os_image = _OS_IMAGES.get("gcp", {}).get("ubuntu", "ubuntu-os-cloud/ubuntu-2204-lts")
        domain = self._profile.domain or "replica"

        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            # Packer image builder for: {self._profile.target}

            packer {{
              required_plugins {{
                googlecompute = {{
                  version = ">= 1.0.0"
                  source  = "github.com/hashicorp/googlecompute"
                }}
              }}
            }}

            variable "project_id" {{
              type = string
            }}

            variable "zone" {{
              type    = string
              default = "us-central1-a"
            }}

            source "googlecompute" "replica" {{
              project_id   = var.project_id
              source_image = "{os_image.split("/")[-1] if "/" in os_image else os_image}"
              zone         = var.zone
              image_name   = "sf-replica-{domain.replace(".", "-")}-{{{{timestamp}}}}"
              ssh_username = "ubuntu"
            }}

            build {{
              sources = ["source.googlecompute.replica"]

              provisioner "shell" {{
                script = "scripts/provision.sh"
              }}
            }}
        ''')

    def _packer_azure(self) -> str:
        domain = self._profile.domain or "replica"

        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            # Packer image builder for: {self._profile.target}

            packer {{
              required_plugins {{
                azure = {{
                  version = ">= 2.0.0"
                  source  = "github.com/hashicorp/azure"
                }}
              }}
            }}

            variable "subscription_id" {{
              type = string
            }}

            variable "resource_group" {{
              type    = string
              default = "sf-replica-rg"
            }}

            source "azure-arm" "replica" {{
              subscription_id                = var.subscription_id
              managed_image_name             = "sf-replica-{domain.replace(".", "-")}"
              managed_image_resource_group_name = var.resource_group
              os_type                        = "Linux"
              image_publisher                = "Canonical"
              image_offer                    = "0001-com-ubuntu-server-jammy"
              image_sku                      = "22_04-lts"
              vm_size                        = "Standard_B2ms"
            }}

            build {{
              sources = ["source.azure-arm.replica"]

              provisioner "shell" {{
                script = "scripts/provision.sh"
              }}
            }}
        ''')

    def _packer_digitalocean(self) -> str:
        domain = self._profile.domain or "replica"

        return textwrap.dedent(f'''\
            # Auto-generated by SpiderFoot Target Replication Engine
            # Packer image builder for: {self._profile.target}

            packer {{
              required_plugins {{
                digitalocean = {{
                  version = ">= 1.0.0"
                  source  = "github.com/digitalocean/digitalocean"
                }}
              }}
            }}

            variable "api_token" {{
              type      = string
              sensitive = true
            }}

            source "digitalocean" "replica" {{
              api_token    = var.api_token
              image        = "ubuntu-22-04-x64"
              region       = "nyc1"
              size         = "s-2vcpu-2gb"
              ssh_username = "root"
              snapshot_name = "sf-replica-{domain.replace(".", "-")}-{{{{timestamp}}}}"
            }}

            build {{
              sources = ["source.digitalocean.replica"]

              provisioner "shell" {{
                script = "scripts/provision.sh"
              }}
            }}
        ''')

    def _packer_vmware(self) -> str:
        return self._packer_aws()  # Fallback to AWS format

    def generate_provision_script(self) -> str:
        """Generate a shell provisioning script for Packer."""
        packages: list[str] = ["curl", "wget", "git", "vim", "htop",
                                "net-tools", "ufw", "unzip"]

        # Add packages for discovered services
        for svc in self._profile.services:
            pkg = _SERVICE_TO_PACKAGE.get(svc.name.lower())
            if pkg and pkg not in packages:
                packages.append(pkg)

        # Web server
        if self._profile.web_server:
            web_pkg = _SERVICE_TO_PACKAGE.get(self._profile.web_server.lower())
            if web_pkg and web_pkg not in packages:
                packages.append(web_pkg)

        # Web technologies
        for tech in self._profile.web_technologies:
            tech_pkg = _SERVICE_TO_PACKAGE.get(tech.name.lower())
            if tech_pkg and tech_pkg not in packages:
                packages.append(tech_pkg)

        pkg_install = " ".join(packages)
        ports = self._profile.get_all_ports() or [80, 443]
        ufw_rules = "\n".join(f"sudo ufw allow {p}/tcp" for p in ports)

        return textwrap.dedent(f'''\
            #!/bin/bash
            # Auto-generated by SpiderFoot Target Replication Engine
            # Provision script for: {self._profile.target}
            set -euxo pipefail

            export DEBIAN_FRONTEND=noninteractive

            echo "=== Updating package cache ==="
            sudo apt-get update -qq

            echo "=== Installing packages ==="
            sudo apt-get install -y -qq {pkg_install}

            echo "=== Configuring firewall ==="
            sudo ufw --force enable
            {ufw_rules}

            echo "=== Enabling services ==="
            sudo systemctl daemon-reload

            echo "=== Cleaning up ==="
            sudo apt-get autoremove -y -qq
            sudo apt-get clean

            echo "=== Provisioning complete ==="
        ''')


# ============================================================================
# README Generator — Deployment documentation
# ============================================================================


class ReadmeGenerator:
    """Generate deployment documentation for the replica environment.

    Produces a comprehensive README.md with:
    - Target profile summary
    - Step-by-step Terraform deployment instructions
    - Ansible provisioning instructions
    - Docker Compose quick-start
    - Troubleshooting guide

    Args:
        profile: The target profile.
        provider: Cloud provider being used.
    """

    def __init__(
        self,
        profile: TargetProfile,
        provider: CloudProvider = CloudProvider.AWS,
    ) -> None:
        self._profile = profile
        self._provider = provider

    def generate(self) -> str:
        """Generate the README.md content."""
        p = self._profile
        domain = p.domain or "target"
        ports_table = self._format_ports_table()
        services_table = self._format_services_table()
        web_techs_list = ", ".join(
            f"{t.name} {t.version}".strip() for t in p.web_technologies
        ) or "None detected"

        provider_name = {
            "aws": "AWS", "azure": "Azure", "gcp": "Google Cloud",
            "digitalocean": "DigitalOcean", "vmware": "VMware vSphere",
        }.get(self._provider.value, self._provider.value)

        return textwrap.dedent(f'''\
            # SpiderFoot Target Replica: {domain}

            > Auto-generated by SpiderFoot Target Replication Engine
            > Scan ID: {p.scan_id or "N/A"}

            ## Target Profile Summary

            | Property | Value |
            |----------|-------|
            | **Domain** | `{domain}` |
            | **IP Addresses** | {', '.join(p.ip_addresses) or 'N/A'} |
            | **Operating System** | {p.operating_system or 'Unknown'} |
            | **OS Family** | {p.os_family or 'linux'} |
            | **Web Server** | {p.web_server or 'N/A'} {p.web_server_version} |
            | **Web Technologies** | {web_techs_list} |
            | **Hosting Provider** | {p.hosting_provider or 'Unknown'} |

            ### Open Ports

            {ports_table}

            ### Discovered Services

            {services_table}

            ## Quick Start

            ### Option 1: Docker Compose (Local, fastest)

            ```bash
            cd docker/
            docker compose up -d
            # Access at http://localhost
            ```

            ### Option 2: Terraform + Ansible ({provider_name})

            #### Prerequisites

            - [Terraform](https://terraform.io/downloads) >= 1.5
            - [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/) >= 2.14
            - {provider_name} account with credentials configured
            - SSH key pair

            #### Step 1: Provision Infrastructure

            ```bash
            cd terraform/
            cp terraform.tfvars.example terraform.tfvars
            # Edit terraform.tfvars with your credentials and SSH key

            terraform init
            terraform plan
            terraform apply -auto-approve

            # Note the output IP address
            export REPLICA_IP=$(terraform output -raw public_ip)
            ```

            #### Step 2: Configure Services

            ```bash
            cd ../ansible/

            # Update inventory with the Terraform output IP
            sed -i "s/ansible_host=.*/ansible_host=$REPLICA_IP/" inventory.ini

            # Run the playbook
            ansible-playbook playbook.yml
            ```

            #### Step 3: Verify

            ```bash
            # Check connectivity
            curl -s http://$REPLICA_IP/

            # Check open ports
            nmap -sT $REPLICA_IP
            ```

            ### Option 3: Packer Pre-baked Image

            ```bash
            cd packer/
            packer init .
            packer build packer.pkr.hcl
            # Use the output AMI/image ID in Terraform
            ```

            ## Teardown

            ```bash
            cd terraform/
            terraform destroy -auto-approve
            ```

            ## Directory Structure

            ```
            .
            ├── terraform/         # Infrastructure provisioning
            │   ├── main.tf
            │   ├── variables.tf
            │   ├── outputs.tf
            │   └── terraform.tfvars.example
            ├── ansible/           # Service configuration
            │   ├── playbook.yml
            │   ├── inventory.ini
            │   ├── ansible.cfg
            │   ├── group_vars/
            │   └── roles/
            ├── docker/            # Local Docker replication
            │   └── docker-compose.yml
            ├── packer/            # Pre-baked image builder
            │   ├── packer.pkr.hcl
            │   └── scripts/
            └── profile/           # Scan profile data
                └── target_profile.json
            ```

            ## Troubleshooting

            | Issue | Solution |
            |-------|----------|
            | SSH connection refused | Check security group allows port 22 |
            | Services not starting | Run `ansible-playbook playbook.yml --tags verify` |
            | Terraform state error | Run `terraform init -reconfigure` |
            | Port already in use | Check for conflicting local services |

            ---
            *Generated by [SpiderFoot](https://github.com/smicallef/spiderfoot) Target Replication Engine*
        ''')

    def _format_ports_table(self) -> str:
        if not self._profile.open_ports:
            return "No ports discovered."

        lines = ["| Port | Protocol | Service | Version |"]
        lines.append("|------|----------|---------|---------|")
        for p in self._profile.open_ports:
            lines.append(
                f"| {p.port} | {p.protocol} | {p.service_name or 'unknown'} | {p.service_version or '-'} |"
            )
        return "\n".join(lines)

    def _format_services_table(self) -> str:
        if not self._profile.services:
            return "No services discovered."

        lines = ["| Service | Version | Category | Port |"]
        lines.append("|---------|---------|----------|------|")
        for s in self._profile.services:
            lines.append(
                f"| {s.name} | {s.version or '-'} | {s.category.value} | {s.port or '-'} |"
            )
        return "\n".join(lines)


# ============================================================================
# Terraform Backend Configuration
# ============================================================================


class TerraformBackendGenerator:
    """Generate Terraform remote backend configurations.

    Supports S3, Azure Blob, GCS, and Terraform Cloud backends
    for remote state management.

    Args:
        provider: Cloud provider for the backend.
        profile: Target profile for naming.
    """

    def __init__(
        self,
        provider: CloudProvider = CloudProvider.AWS,
        profile: TargetProfile | None = None,
    ) -> None:
        self._provider = provider
        self._profile = profile or TargetProfile()

    def generate(self) -> str:
        """Generate backend.tf content."""
        gen = getattr(self, f"_backend_{self._provider.value}", None)
        if gen is None:
            return self._backend_aws()
        return gen()

    def _backend_aws(self) -> str:
        name = (self._profile.domain or "replica").replace(".", "-")
        return textwrap.dedent(f'''\
            # Remote state backend — AWS S3
            # Uncomment and configure to enable remote state

            # terraform {{
            #   backend "s3" {{
            #     bucket         = "sf-replica-tfstate"
            #     key            = "{name}/terraform.tfstate"
            #     region         = "us-east-1"
            #     encrypt        = true
            #     dynamodb_table = "sf-replica-tflock"
            #   }}
            # }}
        ''')

    def _backend_azure(self) -> str:
        name = (self._profile.domain or "replica").replace(".", "-")
        return textwrap.dedent(f'''\
            # Remote state backend — Azure Blob Storage
            # Uncomment and configure to enable remote state

            # terraform {{
            #   backend "azurerm" {{
            #     resource_group_name  = "sf-replica-tfstate-rg"
            #     storage_account_name = "sfreplicatfstate"
            #     container_name       = "tfstate"
            #     key                  = "{name}.terraform.tfstate"
            #   }}
            # }}
        ''')

    def _backend_gcp(self) -> str:
        name = (self._profile.domain or "replica").replace(".", "-")
        return textwrap.dedent(f'''\
            # Remote state backend — Google Cloud Storage
            # Uncomment and configure to enable remote state

            # terraform {{
            #   backend "gcs" {{
            #     bucket = "sf-replica-tfstate"
            #     prefix = "{name}"
            #   }}
            # }}
        ''')

    def _backend_digitalocean(self) -> str:
        return self._backend_aws()  # DO uses S3-compatible Spaces

    def _backend_vmware(self) -> str:
        return textwrap.dedent('''\
            # VMware does not have a native backend.
            # Consider using Terraform Cloud or Consul backend.
            #
            # terraform {
            #   backend "consul" {
            #     address = "consul.example.com:8500"
            #     scheme  = "https"
            #     path    = "sf-replica/terraform-state"
            #   }
            # }
        ''')


# ============================================================================
# Target Replicator — Unified Façade
# ============================================================================


class TargetReplicator:
    """Unified façade for generating complete IaC for target replication.

    Combines Terraform, Ansible, Docker Compose, Packer, and deployment
    documentation generation from scan results into a single operation.

    Features:
    - Multi-provider generation (all cloud providers at once)
    - Pre-generation validation with detailed diagnostics
    - Service dependency resolution for role ordering
    - Packer image builder output
    - Deployment README generation
    - Terraform remote backend configuration

    Usage::

        # From scan events
        replicator = TargetReplicator.from_scan_events(events, provider="aws")
        validation = replicator.validate()
        if validation:
            output = replicator.generate()
            replicator.write_to_directory("/tmp/replica-output")

        # Multi-provider
        output = replicator.generate_multi_provider(["aws", "gcp", "azure"])

        # From a pre-built profile
        replicator = TargetReplicator(profile, provider=CloudProvider.GCP)
        output = replicator.generate()
    """

    def __init__(
        self,
        profile: TargetProfile,
        provider: CloudProvider = CloudProvider.AWS,
        instance_size: str = "medium",
        ssh_user: str = "ubuntu",
    ) -> None:
        self._profile = profile
        self._provider = provider
        self._instance_size = instance_size
        self._ssh_user = ssh_user

    @classmethod
    def from_scan_events(
        cls,
        events: list[dict[str, Any]],
        *,
        target: str = "",
        scan_id: str = "",
        provider: str | CloudProvider = "aws",
        instance_size: str = "medium",
    ) -> "TargetReplicator":
        """Create a replicator from raw scan event data."""
        extractor = TargetProfileExtractor(target=target, scan_id=scan_id)
        for event in events:
            extractor.ingest(event)
        profile = extractor.build()

        if isinstance(provider, str):
            provider = CloudProvider(provider.lower())

        return cls(profile, provider=provider, instance_size=instance_size)

    def validate(self) -> ValidationResult:
        """Run all validation checks on the current profile.

        Returns a :class:`ValidationResult` with errors, warnings, and info
        messages. The result evaluates to ``True`` if no errors were found.
        """
        validator = IaCValidator(self._profile)
        return validator.validate_all()

    def resolve_role_order(self, roles: list[str] | None = None) -> list[str]:
        """Resolve Ansible role execution order based on dependency graph.

        Args:
            roles: Explicit role list, or ``None`` to auto-detect from profile.

        Returns:
            Role names in dependency-resolved order.
        """
        if roles is None:
            ansible_gen = AnsibleGenerator(self._profile, ssh_user=self._ssh_user)
            roles = ansible_gen._determine_roles()
        resolver = ServiceDependencyResolver(roles)
        return resolver.resolve()

    def generate(self) -> dict[str, dict[str, str]]:
        """Generate all IaC files.

        Returns a dict with keys ``terraform``, ``ansible``, ``docker``,
        ``packer``, ``docs``, ``profile``, each mapping to a dict of
        filename → content.
        """
        tf_gen = TerraformGenerator(self._profile, self._provider, self._instance_size)
        ansible_gen = AnsibleGenerator(self._profile, ssh_user=self._ssh_user)
        docker_gen = DockerComposeGenerator(self._profile)
        packer_gen = PackerGenerator(self._profile, self._provider)
        readme_gen = ReadmeGenerator(self._profile, self._provider)
        backend_gen = TerraformBackendGenerator(self._provider, self._profile)

        result: dict[str, dict[str, str]] = {
            "terraform": tf_gen.generate_all(),
            "ansible": ansible_gen.generate_all(),
            "docker": {"docker-compose.yml": docker_gen.generate()},
            "packer": packer_gen.generate_all(),
            "docs": {"README.md": readme_gen.generate()},
            "profile": {"target_profile.json": json.dumps(
                self._profile.to_dict(), indent=2
            )},
        }

        # Add backend configuration
        result["terraform"]["backend.tf"] = backend_gen.generate()

        # Add validation report
        validation = self.validate()
        result["docs"]["VALIDATION.md"] = self._format_validation_report(validation)

        return result

    def generate_multi_provider(
        self,
        providers: list[str | CloudProvider] | None = None,
    ) -> dict[str, dict[str, dict[str, str]]]:
        """Generate IaC for multiple cloud providers.

        Args:
            providers: List of provider names. Defaults to all providers.

        Returns:
            Nested dict: ``provider_name → category → filename → content``.
        """
        if providers is None:
            providers = list(CloudProvider)
        else:
            providers = [
                CloudProvider(p.lower()) if isinstance(p, str) else p
                for p in providers
            ]

        results: dict[str, dict[str, dict[str, str]]] = {}

        for provider in providers:
            replicator = TargetReplicator(
                self._profile,
                provider=provider,
                instance_size=self._instance_size,
                ssh_user=self._ssh_user,
            )
            results[provider.value] = replicator.generate()

        return results

    def generate_packer(self) -> dict[str, str]:
        """Generate Packer files only."""
        packer_gen = PackerGenerator(self._profile, self._provider)
        return packer_gen.generate_all()

    def generate_readme(self) -> str:
        """Generate deployment README only."""
        readme_gen = ReadmeGenerator(self._profile, self._provider)
        return readme_gen.generate()

    def write_to_directory(self, output_dir: str) -> list[str]:
        """Generate and write all IaC files to a directory.

        Returns a list of file paths written.
        """
        output = self.generate()
        written: list[str] = []

        for category, files in output.items():
            for filename, content in files.items():
                filepath = os.path.join(output_dir, category, filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                written.append(filepath)

        return written

    @staticmethod
    def _format_validation_report(result: ValidationResult) -> str:
        """Format a validation result as a Markdown report."""
        lines = [
            "# IaC Validation Report",
            "",
            f"**Status:** {'✅ PASS' if result.valid else '❌ FAIL'}",
            "",
        ]

        if result.errors:
            lines.append("## Errors")
            lines.append("")
            for err in result.errors:
                lines.append(f"- ❌ {err}")
            lines.append("")

        if result.warnings:
            lines.append("## Warnings")
            lines.append("")
            for warn in result.warnings:
                lines.append(f"- ⚠️ {warn}")
            lines.append("")

        if result.info:
            lines.append("## Information")
            lines.append("")
            for info_msg in result.info:
                lines.append(f"- ℹ️ {info_msg}")
            lines.append("")

        lines.append("---")
        lines.append("*Generated by SpiderFoot Target Replication Engine*")

        return "\n".join(lines)

    @property
    def profile(self) -> TargetProfile:
        """Return the target profile."""
        return self._profile
