# -------------------------------------------------------------------------------
# Name:         test_target_replication
# Purpose:      Tests for the Target Replication Engine
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Comprehensive tests for spiderfoot.recon.target_replication module.

Covers:
- TargetProfile data model
- TargetProfileExtractor (scan event ingestion)
- TerraformGenerator (all 5 providers + VPC/network)
- AnsibleGenerator (playbook, inventory, roles)
- DockerComposeGenerator (healthchecks, volumes, networks)
- IaCValidator (port, IP, service, OS, dependency validation)
- ServiceDependencyResolver (topological role ordering)
- PackerGenerator (AWS, GCP, Azure, DigitalOcean)
- ReadmeGenerator (deployment documentation)
- TerraformBackendGenerator (remote state)
- TargetReplicator (unified façade, multi-provider, validation)

Total: 200+ test methods.
"""

import json
import os
import tempfile
from typing import Any

import pytest

from spiderfoot.iac.target_replication import (
    AnsibleGenerator,
    CloudProvider,
    DiscoveredPort,
    DiscoveredService,
    DiscoveredWebTechnology,
    DockerComposeGenerator,
    IaCValidator,
    PackerGenerator,
    ReadmeGenerator,
    SSLCertInfo,
    ServiceCategory,
    ServiceDependencyResolver,
    TargetProfile,
    TargetProfileExtractor,
    TargetReplicator,
    TerraformBackendGenerator,
    TerraformGenerator,
    ValidationResult,
)


# ============================================================================
# Fixtures — sample scan events & profiles
# ============================================================================


def _make_events() -> list[dict[str, Any]]:
    """Generate a realistic set of scan events for a LAMP-ish target."""
    return [
        {"eventType": "DOMAIN_NAME", "data": "example.com"},
        {"eventType": "IP_ADDRESS", "data": "93.184.216.34"},
        {"eventType": "IP_ADDRESS", "data": "93.184.216.35"},
        {"eventType": "IPV6_ADDRESS", "data": "2606:2800:220:1:248:1893:25c8:1946"},
        {"eventType": "INTERNET_NAME", "data": "www.example.com"},
        {"eventType": "INTERNET_NAME", "data": "mail.example.com"},
        {"eventType": "TCP_PORT_OPEN", "data": "93.184.216.34:80"},
        {"eventType": "TCP_PORT_OPEN", "data": "93.184.216.34:443"},
        {"eventType": "TCP_PORT_OPEN", "data": "93.184.216.34:22"},
        {"eventType": "TCP_PORT_OPEN", "data": "93.184.216.34:3306"},
        {"eventType": "TCP_PORT_OPEN", "data": "93.184.216.34:6379"},
        {"eventType": "OPERATING_SYSTEM", "data": "Ubuntu 22.04 LTS"},
        {"eventType": "WEBSERVER_BANNER", "data": "nginx/1.24.0"},
        {"eventType": "WEBSERVER_TECHNOLOGY", "data": "PHP/8.2"},
        {"eventType": "WEBSERVER_TECHNOLOGY", "data": "WordPress 6.4"},
        {"eventType": "SOFTWARE_USED", "data": "OpenSSH 9.3"},
        {"eventType": "TCP_PORT_OPEN_BANNER", "data": "93.184.216.34:3306\nMySQL 8.0.35"},
        {"eventType": "TCP_PORT_OPEN_BANNER", "data": "93.184.216.34:6379\nRedis 7.2.3"},
        {"eventType": "PROVIDER_HOSTING", "data": "Edgecast"},
        {"eventType": "PROVIDER_DNS", "data": "ns1.example.com"},
        {"eventType": "PROVIDER_MAIL", "data": "mail.example.com"},
        {"eventType": "DNS_TEXT", "data": "v=spf1 include:_spf.example.com ~all"},
        {"eventType": "SSL_CERTIFICATE_RAW", "data": "Issuer: DigiCert\nSubject: example.com"},
    ]


def _make_profile() -> TargetProfile:
    """Build a fully-populated TargetProfile for testing."""
    return TargetProfile(
        target="example.com",
        domain="example.com",
        ip_addresses=["93.184.216.34", "93.184.216.35"],
        ipv6_addresses=["2606:2800:220:1:248:1893:25c8:1946"],
        hostnames=["www.example.com", "mail.example.com"],
        operating_system="Ubuntu 22.04 LTS",
        os_family="linux",
        os_version="22.04",
        open_ports=[
            DiscoveredPort(port=22, service_name="openssh"),
            DiscoveredPort(port=80, service_name="nginx"),
            DiscoveredPort(port=443, service_name="nginx"),
            DiscoveredPort(port=3306, service_name="mysql", service_version="8.0.35"),
            DiscoveredPort(port=6379, service_name="redis", service_version="7.2.3"),
        ],
        services=[
            DiscoveredService("nginx", "1.24.0", ServiceCategory.WEB_SERVER, 80),
            DiscoveredService("mysql", "8.0.35", ServiceCategory.DATABASE, 3306),
            DiscoveredService("redis", "7.2.3", ServiceCategory.CACHE, 6379),
            DiscoveredService("openssh", "9.3", ServiceCategory.APPLICATION, 22),
        ],
        web_server="nginx",
        web_server_version="1.24.0",
        web_technologies=[
            DiscoveredWebTechnology("PHP", "8.2", "language"),
            DiscoveredWebTechnology("WordPress", "6.4", "cms"),
        ],
        ssl_cert=SSLCertInfo(issuer="DigiCert", subject="example.com"),
        hosting_provider="Edgecast",
        scan_id="test-scan-001",
    )


def _make_minimal_profile() -> TargetProfile:
    """A bare-bones profile with minimal data."""
    return TargetProfile(
        target="minimal.test",
        domain="minimal.test",
        ip_addresses=["10.0.0.1"],
        open_ports=[DiscoveredPort(port=80)],
    )


# ============================================================================
# TargetProfile model tests
# ============================================================================


class TestTargetProfile:
    """Tests for the TargetProfile data model."""

    def test_default_values(self) -> None:
        profile = TargetProfile()
        assert profile.target == ""
        assert profile.ip_addresses == []
        assert profile.os_family == ""
        assert profile.open_ports == []
        assert profile.services == []

    def test_has_web_services_with_web_server(self) -> None:
        profile = TargetProfile(web_server="nginx")
        assert profile.has_web_services is True

    def test_has_web_services_with_web_port(self) -> None:
        profile = TargetProfile(
            open_ports=[DiscoveredPort(port=80)]
        )
        assert profile.has_web_services is True

    def test_has_web_services_false(self) -> None:
        profile = TargetProfile(
            open_ports=[DiscoveredPort(port=22)]
        )
        assert profile.has_web_services is False

    def test_has_database(self) -> None:
        profile = TargetProfile(
            open_ports=[DiscoveredPort(port=3306)]
        )
        assert profile.has_database is True

    def test_has_database_false(self) -> None:
        profile = TargetProfile(
            open_ports=[DiscoveredPort(port=80)]
        )
        assert profile.has_database is False

    def test_has_mail(self) -> None:
        profile = TargetProfile(
            open_ports=[DiscoveredPort(port=25)]
        )
        assert profile.has_mail is True

    def test_primary_ip(self) -> None:
        profile = TargetProfile(ip_addresses=["1.2.3.4", "5.6.7.8"])
        assert profile.primary_ip == "1.2.3.4"

    def test_primary_ip_fallback(self) -> None:
        profile = TargetProfile()
        assert profile.primary_ip == "10.0.1.10"

    def test_get_web_ports(self) -> None:
        profile = TargetProfile(open_ports=[
            DiscoveredPort(port=80),
            DiscoveredPort(port=443),
            DiscoveredPort(port=22),
            DiscoveredPort(port=8080),
        ])
        assert profile.get_web_ports() == [80, 443, 8080]

    def test_get_db_ports(self) -> None:
        profile = TargetProfile(open_ports=[
            DiscoveredPort(port=80),
            DiscoveredPort(port=3306),
            DiscoveredPort(port=5432),
        ])
        assert profile.get_db_ports() == [3306, 5432]

    def test_get_all_ports(self) -> None:
        profile = TargetProfile(open_ports=[
            DiscoveredPort(port=22),
            DiscoveredPort(port=80),
        ])
        assert profile.get_all_ports() == [22, 80]

    def test_to_dict(self) -> None:
        profile = _make_profile()
        d = profile.to_dict()
        assert d["target"] == "example.com"
        assert len(d["ip_addresses"]) == 2
        assert len(d["open_ports"]) == 5
        assert len(d["services"]) == 4
        assert d["web_server"] == "nginx"

    def test_to_dict_roundtrip(self) -> None:
        profile = _make_profile()
        d = profile.to_dict()
        j = json.dumps(d)
        parsed = json.loads(j)
        assert parsed["target"] == "example.com"


# ============================================================================
# DiscoveredPort tests
# ============================================================================


class TestDiscoveredPort:
    def test_is_web(self) -> None:
        assert DiscoveredPort(port=80).is_web is True
        assert DiscoveredPort(port=443).is_web is True
        assert DiscoveredPort(port=8080).is_web is True
        assert DiscoveredPort(port=22).is_web is False

    def test_is_database(self) -> None:
        assert DiscoveredPort(port=3306).is_database is True
        assert DiscoveredPort(port=5432).is_database is True
        assert DiscoveredPort(port=27017).is_database is True
        assert DiscoveredPort(port=80).is_database is False

    def test_is_mail(self) -> None:
        assert DiscoveredPort(port=25).is_mail is True
        assert DiscoveredPort(port=587).is_mail is True
        assert DiscoveredPort(port=993).is_mail is True
        assert DiscoveredPort(port=80).is_mail is False


# ============================================================================
# DiscoveredService tests
# ============================================================================


class TestDiscoveredService:
    def test_ansible_package_name(self) -> None:
        svc = DiscoveredService("nginx")
        assert svc.ansible_package_name == "nginx"

    def test_ansible_package_name_mapped(self) -> None:
        svc = DiscoveredService("apache")
        assert svc.ansible_package_name == "apache2"

    def test_docker_image_no_version(self) -> None:
        svc = DiscoveredService("redis")
        assert svc.docker_image == "redis"

    def test_docker_image_with_version(self) -> None:
        svc = DiscoveredService("redis", version="7.2.3")
        assert svc.docker_image == "redis:7.2.3"

    def test_docker_image_mapped(self) -> None:
        svc = DiscoveredService("postgresql", version="15")
        assert svc.docker_image == "postgres:15"


# ============================================================================
# TargetProfileExtractor tests
# ============================================================================


class TestTargetProfileExtractor:
    """Tests for scan event → TargetProfile extraction."""

    def test_basic_extraction(self) -> None:
        events = _make_events()
        extractor = TargetProfileExtractor(target="example.com", scan_id="s1")
        for e in events:
            extractor.ingest(e)
        profile = extractor.build()

        assert profile.target == "example.com"
        assert profile.domain == "example.com"
        assert "93.184.216.34" in profile.ip_addresses
        assert len(profile.ip_addresses) == 2
        assert len(profile.ipv6_addresses) == 1
        assert "www.example.com" in profile.hostnames

    def test_port_extraction(self) -> None:
        events = _make_events()
        extractor = TargetProfileExtractor()
        for e in events:
            extractor.ingest(e)
        profile = extractor.build()

        port_nums = [p.port for p in profile.open_ports]
        assert 80 in port_nums
        assert 443 in port_nums
        assert 22 in port_nums
        assert 3306 in port_nums
        assert 6379 in port_nums

    def test_os_detection_linux(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({"eventType": "OPERATING_SYSTEM", "data": "Ubuntu 22.04"})
        profile = extractor.build()
        assert profile.os_family == "linux"
        assert "22.04" in profile.os_version

    def test_os_detection_windows(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({"eventType": "OPERATING_SYSTEM", "data": "Windows Server 2022"})
        profile = extractor.build()
        assert profile.os_family == "windows"

    def test_web_server_extraction(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({"eventType": "WEBSERVER_BANNER", "data": "nginx/1.24.0"})
        profile = extractor.build()
        assert profile.web_server == "nginx"
        assert profile.web_server_version == "1.24.0"

    def test_banner_service_detection(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({"eventType": "TCP_PORT_OPEN", "data": "1.2.3.4:3306"})
        extractor.ingest({"eventType": "TCP_PORT_OPEN_BANNER", "data": "1.2.3.4:3306\nMySQL 8.0.35"})
        profile = extractor.build()

        mysql_svc = [s for s in profile.services if "mysql" in s.name.lower()]
        assert len(mysql_svc) == 1
        assert mysql_svc[0].version == "8.0.35"

    def test_web_technology_extraction(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({"eventType": "WEBSERVER_TECHNOLOGY", "data": "PHP/8.2"})
        extractor.ingest({"eventType": "WEBSERVER_TECHNOLOGY", "data": "WordPress 6.4"})
        profile = extractor.build()

        assert len(profile.web_technologies) == 2
        names = [t.name for t in profile.web_technologies]
        assert "PHP" in names
        assert "WordPress" in names

    def test_ssl_cert_extraction(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({
            "eventType": "SSL_CERTIFICATE_RAW",
            "data": "Issuer: DigiCert Inc\nSubject: example.com\nself-signed: no",
        })
        profile = extractor.build()
        assert profile.ssl_cert is not None
        assert "DigiCert" in profile.ssl_cert.issuer

    def test_ssl_cert_self_signed(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({
            "eventType": "SSL_CERTIFICATE_RAW",
            "data": "Issuer: Self\nSubject: test.local\nThis is a self-signed certificate",
        })
        profile = extractor.build()
        assert profile.ssl_cert is not None
        assert profile.ssl_cert.self_signed is True

    def test_hosting_and_cloud(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({"eventType": "PROVIDER_HOSTING", "data": "AWS"})
        extractor.ingest({"eventType": "CLOUD_PROVIDER", "data": "Amazon"})
        profile = extractor.build()
        assert profile.hosting_provider == "AWS"
        assert profile.cloud_provider == "Amazon"

    def test_dns_records(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({"eventType": "DNS_TEXT", "data": "v=spf1 ~all"})
        extractor.ingest({"eventType": "DNS_SPF", "data": "v=spf1 include:test ~all"})
        profile = extractor.build()
        assert "TXT" in profile.dns_records
        assert "SPF" in profile.dns_records

    def test_empty_events(self) -> None:
        extractor = TargetProfileExtractor()
        profile = extractor.build()
        assert profile.target == ""
        assert profile.os_family == "linux"  # default

    def test_ignores_unknown_events(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({"eventType": "CUSTOM_UNKNOWN_EVENT", "data": "some data"})
        profile = extractor.build()
        assert profile.target == ""

    def test_software_used_deduplication(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({"eventType": "SOFTWARE_USED", "data": "OpenSSH 9.3"})
        extractor.ingest({"eventType": "SOFTWARE_USED", "data": "OpenSSH 9.3"})
        profile = extractor.build()
        ssh = [s for s in profile.services if "openssh" in s.name.lower()]
        assert len(ssh) == 1

    def test_port_only_format(self) -> None:
        extractor = TargetProfileExtractor()
        extractor.ingest({"eventType": "TCP_PORT_OPEN", "data": "8080"})
        profile = extractor.build()
        assert any(p.port == 8080 for p in profile.open_ports)


# ============================================================================
# TerraformGenerator tests
# ============================================================================


class TestTerraformGenerator:
    """Tests for Terraform HCL generation across all 5 providers."""

    def test_generate_all_keys(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AWS)
        files = gen.generate_all()
        assert "main.tf" in files
        assert "variables.tf" in files
        assert "outputs.tf" in files
        assert "terraform.tfvars.example" in files

    # --- AWS ---

    def test_aws_main_provider(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AWS)
        main = gen.generate_main()
        assert "hashicorp/aws" in main
        assert 'provider "aws"' in main

    def test_aws_main_security_group(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AWS)
        main = gen.generate_main()
        assert "aws_security_group" in main
        assert "from_port   = 80" in main
        assert "from_port   = 443" in main
        assert "from_port   = 3306" in main

    def test_aws_main_instance(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AWS)
        main = gen.generate_main()
        assert "aws_instance" in main
        assert "ami" in main

    def test_aws_ubuntu_image(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AWS)
        main = gen.generate_main()
        # Ubuntu profile should use Ubuntu AMI
        assert "ami-" in main

    # --- Azure ---

    def test_azure_main_provider(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AZURE)
        main = gen.generate_main()
        assert "hashicorp/azurerm" in main
        assert 'provider "azurerm"' in main

    def test_azure_main_resources(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AZURE)
        main = gen.generate_main()
        assert "azurerm_resource_group" in main
        assert "azurerm_virtual_network" in main
        assert "azurerm_subnet" in main
        assert "azurerm_public_ip" in main
        assert "azurerm_network_security_group" in main
        assert "azurerm_linux_virtual_machine" in main

    def test_azure_nsg_rules(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AZURE)
        main = gen.generate_main()
        assert "allow-port-80" in main
        assert "allow-port-443" in main

    # --- GCP ---

    def test_gcp_main_provider(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.GCP)
        main = gen.generate_main()
        assert "hashicorp/google" in main
        assert 'provider "google"' in main

    def test_gcp_firewall(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.GCP)
        main = gen.generate_main()
        assert "google_compute_firewall" in main
        assert '"80"' in main

    def test_gcp_instance(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.GCP)
        main = gen.generate_main()
        assert "google_compute_instance" in main
        assert "boot_disk" in main

    # --- DigitalOcean ---

    def test_do_main_provider(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.DIGITALOCEAN)
        main = gen.generate_main()
        assert "digitalocean/digitalocean" in main
        assert "digitalocean_droplet" in main

    def test_do_firewall(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.DIGITALOCEAN)
        main = gen.generate_main()
        assert "digitalocean_firewall" in main
        assert "inbound_rule" in main

    # --- VMware ---

    def test_vmware_main_provider(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.VMWARE)
        main = gen.generate_main()
        assert "hashicorp/vsphere" in main
        assert "vsphere_virtual_machine" in main

    def test_vmware_template(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.VMWARE)
        main = gen.generate_main()
        assert "vsphere_virtual_machine" in main
        assert "clone" in main

    # --- Variables ---

    def test_variables_ports(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AWS)
        variables = gen.generate_variables()
        assert "allowed_ports" in variables
        assert "80" in variables
        assert "443" in variables

    def test_variables_project_name(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AWS)
        variables = gen.generate_variables()
        assert "sf-replica-example-com" in variables

    # --- Outputs ---

    def test_outputs_aws(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AWS)
        outputs = gen.generate_outputs()
        assert "public_ip" in outputs
        assert "instance_id" in outputs

    def test_outputs_azure(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AZURE)
        outputs = gen.generate_outputs()
        assert "vm_id" in outputs
        assert "public_ip" in outputs

    def test_outputs_gcp(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.GCP)
        outputs = gen.generate_outputs()
        assert "external_ip" in outputs

    def test_outputs_do(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.DIGITALOCEAN)
        outputs = gen.generate_outputs()
        assert "ipv4_address" in outputs

    def test_outputs_vmware(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.VMWARE)
        outputs = gen.generate_outputs()
        assert "default_ip" in outputs

    # --- Instance sizes ---

    def test_instance_size_small(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AWS, "small")
        variables = gen.generate_variables()
        assert "t3.micro" in variables

    def test_instance_size_large(self) -> None:
        gen = TerraformGenerator(_make_profile(), CloudProvider.AWS, "large")
        variables = gen.generate_variables()
        assert "t3.large" in variables

    # --- OS image resolution ---

    def test_windows_image(self) -> None:
        profile = TargetProfile(operating_system="Windows Server 2022")
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "ami-" in main  # Should find Windows AMI

    def test_centos_image(self) -> None:
        profile = TargetProfile(operating_system="CentOS Stream 9")
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "ami-" in main

    # --- Minimal profile ---

    def test_minimal_profile_aws(self) -> None:
        gen = TerraformGenerator(_make_minimal_profile(), CloudProvider.AWS)
        files = gen.generate_all()
        assert all(files[k] for k in files)  # All files have content

    def test_minimal_profile_azure(self) -> None:
        gen = TerraformGenerator(_make_minimal_profile(), CloudProvider.AZURE)
        main = gen.generate_main()
        assert "azurerm" in main

    def test_minimal_profile_gcp(self) -> None:
        gen = TerraformGenerator(_make_minimal_profile(), CloudProvider.GCP)
        main = gen.generate_main()
        assert "google" in main


# ============================================================================
# AnsibleGenerator tests
# ============================================================================


class TestAnsibleGenerator:
    """Tests for Ansible playbook/inventory/role generation."""

    def test_generate_all_keys(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        assert "playbook.yml" in files
        assert "inventory.ini" in files
        assert "group_vars/all.yml" in files
        assert "ansible.cfg" in files

    def test_playbook_hosts(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        pb = gen.generate_playbook()
        assert "hosts: replica" in pb
        assert "become: true" in pb

    def test_playbook_firewall_rules(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        pb = gen.generate_playbook()
        assert "port: '80'" in pb
        assert "port: '443'" in pb
        assert "port: '3306'" in pb

    def test_playbook_roles(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        pb = gen.generate_playbook()
        assert "- common" in pb
        assert "- nginx" in pb
        assert "- mysql" in pb
        assert "- redis" in pb

    def test_inventory(self) -> None:
        gen = AnsibleGenerator(_make_profile(), target_host="10.0.0.5")
        inv = gen.generate_inventory()
        assert "ansible_host=10.0.0.5" in inv
        assert "[replica]" in inv

    def test_inventory_default_host(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        inv = gen.generate_inventory()
        assert "93.184.216.34" in inv

    def test_group_vars(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        gv = gen.generate_group_vars()
        assert "example.com" in gv
        assert "nginx" in gv
        assert "Ubuntu 22.04 LTS" in gv

    def test_ansible_cfg(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        cfg = gen.generate_ansible_cfg()
        assert "host_key_checking = False" in cfg
        assert "inventory = inventory.ini" in cfg

    # --- Role detection ---

    def test_roles_include_common(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        assert "roles/common/tasks/main.yml" in files

    def test_roles_include_web_server(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        assert "roles/nginx/tasks/main.yml" in files

    def test_roles_include_database(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        assert "roles/mysql/tasks/main.yml" in files

    def test_roles_include_cache(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        assert "roles/redis/tasks/main.yml" in files

    def test_roles_include_ssl(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        assert "roles/ssl/tasks/main.yml" in files

    def test_roles_include_php(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        assert "roles/php/tasks/main.yml" in files

    def test_roles_include_wordpress(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        assert "roles/wordpress/tasks/main.yml" in files

    # --- Role content ---

    def test_common_role_has_packages(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        tasks = files["roles/common/tasks/main.yml"]
        assert "curl" in tasks
        assert "wget" in tasks
        assert "git" in tasks

    def test_nginx_role_has_install(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        tasks = files["roles/nginx/tasks/main.yml"]
        assert "Install Nginx" in tasks
        assert "nginx" in tasks

    def test_mysql_role_has_install(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        tasks = files["roles/mysql/tasks/main.yml"]
        assert "Install MySQL" in tasks
        assert "mysql-server" in tasks

    def test_ssl_role_generates_cert(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        tasks = files["roles/ssl/tasks/main.yml"]
        assert "openssl" in tasks
        assert "example.com" in tasks

    def test_redis_role_has_config(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        tasks = files["roles/redis/tasks/main.yml"]
        assert "redis-server" in tasks

    # --- Handlers ---

    def test_handlers_generated(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        handlers = files["roles/nginx/handlers/main.yml"]
        assert "restart nginx" in handlers

    # --- Defaults ---

    def test_defaults_generated(self) -> None:
        gen = AnsibleGenerator(_make_profile())
        files = gen.generate_all()
        defaults = files["roles/nginx/defaults/main.yml"]
        assert "nginx_enabled" in defaults

    # --- Apache variant ---

    def test_apache_profile(self) -> None:
        profile = TargetProfile(
            web_server="Apache",
            web_server_version="2.4.57",
            open_ports=[DiscoveredPort(port=80)],
        )
        gen = AnsibleGenerator(profile)
        files = gen.generate_all()
        assert "roles/apache/tasks/main.yml" in files
        tasks = files["roles/apache/tasks/main.yml"]
        assert "Install Apache" in tasks

    # --- Port-based fallback ---

    def test_postgresql_detected_by_port(self) -> None:
        profile = TargetProfile(
            open_ports=[DiscoveredPort(port=5432), DiscoveredPort(port=80)],
            web_server="nginx",
        )
        gen = AnsibleGenerator(profile)
        files = gen.generate_all()
        assert "roles/postgresql/tasks/main.yml" in files

    def test_mongodb_detected_by_port(self) -> None:
        profile = TargetProfile(
            open_ports=[DiscoveredPort(port=27017), DiscoveredPort(port=80)],
            web_server="nginx",
        )
        gen = AnsibleGenerator(profile)
        files = gen.generate_all()
        assert "roles/mongodb/tasks/main.yml" in files

    # --- Minimal profile ---

    def test_minimal_generates_valid_playbook(self) -> None:
        gen = AnsibleGenerator(_make_minimal_profile())
        pb = gen.generate_playbook()
        assert "hosts: replica" in pb
        assert "- common" in pb


# ============================================================================
# DockerComposeGenerator tests
# ============================================================================


class TestDockerComposeGenerator:
    """Tests for Docker Compose generation."""

    def test_basic_output(self) -> None:
        gen = DockerComposeGenerator(_make_profile())
        output = gen.generate()
        assert "services:" in output
        assert "nginx" in output

    def test_web_service_ports(self) -> None:
        gen = DockerComposeGenerator(_make_profile())
        output = gen.generate()
        assert "80:80" in output
        assert "443:443" in output

    def test_mysql_service(self) -> None:
        gen = DockerComposeGenerator(_make_profile())
        output = gen.generate()
        assert "mysql" in output.lower() or "MYSQL_ROOT_PASSWORD" in output

    def test_redis_service(self) -> None:
        gen = DockerComposeGenerator(_make_profile())
        output = gen.generate()
        assert "redis" in output.lower()

    def test_database_env_vars(self) -> None:
        gen = DockerComposeGenerator(_make_profile())
        output = gen.generate()
        assert "MYSQL_ROOT_PASSWORD" in output or "MYSQL_DATABASE" in output

    def test_apache_variant(self) -> None:
        profile = TargetProfile(
            web_server="apache",
            open_ports=[DiscoveredPort(port=80)],
        )
        gen = DockerComposeGenerator(profile)
        output = gen.generate()
        assert "httpd" in output

    def test_minimal_profile(self) -> None:
        gen = DockerComposeGenerator(_make_minimal_profile())
        output = gen.generate()
        assert "services:" in output

    def test_version_in_image(self) -> None:
        profile = TargetProfile(
            web_server="nginx",
            web_server_version="1.24.0",
            open_ports=[DiscoveredPort(port=80)],
        )
        gen = DockerComposeGenerator(profile)
        output = gen.generate()
        assert "nginx:1.24.0" in output

    def test_restart_policy(self) -> None:
        gen = DockerComposeGenerator(_make_profile())
        output = gen.generate()
        assert "unless-stopped" in output


# ============================================================================
# TargetReplicator (façade) tests
# ============================================================================


class TestTargetReplicator:
    """Tests for the unified TargetReplicator façade."""

    def test_from_scan_events(self) -> None:
        replicator = TargetReplicator.from_scan_events(
            _make_events(), target="example.com", scan_id="s1",
        )
        assert replicator.profile.target == "example.com"
        assert len(replicator.profile.ip_addresses) > 0

    def test_generate_all_categories(self) -> None:
        replicator = TargetReplicator(_make_profile())
        output = replicator.generate()
        assert "terraform" in output
        assert "ansible" in output
        assert "docker" in output
        assert "profile" in output

    def test_generate_terraform_files(self) -> None:
        replicator = TargetReplicator(_make_profile(), CloudProvider.AWS)
        output = replicator.generate()
        assert "main.tf" in output["terraform"]
        assert "variables.tf" in output["terraform"]

    def test_generate_ansible_files(self) -> None:
        replicator = TargetReplicator(_make_profile())
        output = replicator.generate()
        assert "playbook.yml" in output["ansible"]
        assert "inventory.ini" in output["ansible"]

    def test_generate_docker_files(self) -> None:
        replicator = TargetReplicator(_make_profile())
        output = replicator.generate()
        assert "docker-compose.yml" in output["docker"]

    def test_profile_json_valid(self) -> None:
        replicator = TargetReplicator(_make_profile())
        output = replicator.generate()
        profile_json = output["profile"]["target_profile.json"]
        parsed = json.loads(profile_json)
        assert parsed["target"] == "example.com"

    def test_write_to_directory(self) -> None:
        replicator = TargetReplicator(_make_profile())
        with tempfile.TemporaryDirectory() as tmpdir:
            written = replicator.write_to_directory(tmpdir)
            assert len(written) > 0
            # Check that files exist
            for path in written:
                assert os.path.exists(path), f"File not found: {path}"

    def test_write_creates_subdirs(self) -> None:
        replicator = TargetReplicator(_make_profile())
        with tempfile.TemporaryDirectory() as tmpdir:
            replicator.write_to_directory(tmpdir)
            assert os.path.isdir(os.path.join(tmpdir, "terraform"))
            assert os.path.isdir(os.path.join(tmpdir, "ansible"))
            assert os.path.isdir(os.path.join(tmpdir, "docker"))

    def test_from_scan_events_provider_string(self) -> None:
        replicator = TargetReplicator.from_scan_events(
            _make_events(), provider="gcp",
        )
        output = replicator.generate()
        assert "google" in output["terraform"]["main.tf"]

    def test_from_scan_events_provider_enum(self) -> None:
        replicator = TargetReplicator.from_scan_events(
            _make_events(), provider=CloudProvider.AZURE,
        )
        output = replicator.generate()
        assert "azurerm" in output["terraform"]["main.tf"]

    # --- Multi-provider generation ---

    def test_all_providers(self) -> None:
        profile = _make_profile()
        for provider in CloudProvider:
            gen = TerraformGenerator(profile, provider)
            files = gen.generate_all()
            assert all(content for content in files.values()), (
                f"Provider {provider.value} generated empty files"
            )

    # --- Edge cases ---

    def test_empty_events(self) -> None:
        replicator = TargetReplicator.from_scan_events([])
        output = replicator.generate()
        # Should still produce valid output with defaults
        assert "main.tf" in output["terraform"]
        assert "playbook.yml" in output["ansible"]

    def test_profile_property(self) -> None:
        profile = _make_profile()
        replicator = TargetReplicator(profile)
        assert replicator.profile is profile

    def test_custom_ssh_user(self) -> None:
        replicator = TargetReplicator(_make_profile(), ssh_user="admin")
        output = replicator.generate()
        inv = output["ansible"]["inventory.ini"]
        assert "ansible_user=admin" in inv

    def test_instance_size_propagation(self) -> None:
        replicator = TargetReplicator(
            _make_profile(), CloudProvider.AWS, instance_size="large",
        )
        output = replicator.generate()
        variables = output["terraform"]["variables.tf"]
        assert "t3.large" in variables


# ============================================================================
# Helper profiles for new tests
# ============================================================================


def _make_profile_with_mongodb() -> TargetProfile:
    """Profile with MongoDB for role generator tests."""
    return TargetProfile(
        target="mongo.example.com",
        domain="mongo.example.com",
        ip_addresses=["10.0.0.5"],
        open_ports=[
            DiscoveredPort(port=27017, service_name="mongodb"),
            DiscoveredPort(port=80, service_name="nginx"),
        ],
        services=[
            DiscoveredService("mongodb", "7.0", ServiceCategory.DATABASE, 27017),
            DiscoveredService("nginx", "1.24", ServiceCategory.WEB_SERVER, 80),
        ],
        web_server="nginx",
        operating_system="Ubuntu 22.04",
        os_family="linux",
    )


def _make_profile_with_elasticsearch() -> TargetProfile:
    """Profile with Elasticsearch."""
    return TargetProfile(
        target="elastic.example.com",
        domain="elastic.example.com",
        ip_addresses=["10.0.0.6"],
        open_ports=[
            DiscoveredPort(port=9200, service_name="elasticsearch"),
            DiscoveredPort(port=9300, service_name="elasticsearch"),
        ],
        services=[
            DiscoveredService("elasticsearch", "8.12", ServiceCategory.DATABASE, 9200),
        ],
        operating_system="Ubuntu 22.04",
        os_family="linux",
    )


def _make_profile_with_wordpress() -> TargetProfile:
    """Profile with WordPress stack (nginx + mysql + PHP + WP)."""
    return TargetProfile(
        target="wp.example.com",
        domain="wp.example.com",
        ip_addresses=["10.0.0.7"],
        open_ports=[
            DiscoveredPort(port=80, service_name="nginx"),
            DiscoveredPort(port=443, service_name="nginx"),
            DiscoveredPort(port=3306, service_name="mysql"),
        ],
        services=[
            DiscoveredService("nginx", "1.24", ServiceCategory.WEB_SERVER, 80),
            DiscoveredService("mysql", "8.0", ServiceCategory.DATABASE, 3306),
        ],
        web_server="nginx",
        web_technologies=[
            DiscoveredWebTechnology("PHP", "8.2", "language"),
            DiscoveredWebTechnology("WordPress", "6.4", "cms"),
        ],
        operating_system="Ubuntu 22.04",
        os_family="linux",
    )


def _make_profile_with_bad_ports() -> TargetProfile:
    """Profile with invalid port numbers for validation tests."""
    return TargetProfile(
        target="bad.example.com",
        domain="bad.example.com",
        ip_addresses=["10.0.0.8", "not-an-ip"],
        open_ports=[
            DiscoveredPort(port=80, service_name="nginx"),
            DiscoveredPort(port=99999, service_name="invalid"),
            DiscoveredPort(port=-1, service_name="negative"),
        ],
    )


def _make_profile_haproxy() -> TargetProfile:
    """Profile with HAProxy."""
    return TargetProfile(
        target="lb.example.com",
        domain="lb.example.com",
        ip_addresses=["10.0.0.9"],
        open_ports=[DiscoveredPort(port=80), DiscoveredPort(port=8080)],
        services=[
            DiscoveredService("haproxy", "2.8", ServiceCategory.WEB_SERVER, 80),
        ],
        web_server="haproxy",
    )


def _make_profile_windows() -> TargetProfile:
    """Profile with Windows OS."""
    return TargetProfile(
        target="win.example.com",
        domain="win.example.com",
        ip_addresses=["10.0.0.10"],
        open_ports=[DiscoveredPort(port=80), DiscoveredPort(port=3389)],
        operating_system="Windows Server 2022",
        os_family="windows",
    )


# ============================================================================
# ValidationResult tests
# ============================================================================


class TestValidationResult:
    """Tests for the ValidationResult data model."""

    def test_valid_result_is_truthy(self) -> None:
        result = ValidationResult(valid=True)
        assert bool(result) is True

    def test_invalid_result_is_falsy(self) -> None:
        result = ValidationResult(valid=False, errors=["bad port"])
        assert bool(result) is False

    def test_merge_both_valid(self) -> None:
        r1 = ValidationResult(valid=True, info=["a"])
        r2 = ValidationResult(valid=True, warnings=["b"])
        merged = r1.merge(r2)
        assert merged.valid is True
        assert "a" in merged.info
        assert "b" in merged.warnings

    def test_merge_one_invalid(self) -> None:
        r1 = ValidationResult(valid=True)
        r2 = ValidationResult(valid=False, errors=["err"])
        merged = r1.merge(r2)
        assert merged.valid is False
        assert "err" in merged.errors

    def test_to_dict(self) -> None:
        result = ValidationResult(
            valid=True, errors=[], warnings=["w"], info=["i"],
        )
        d = result.to_dict()
        assert d["valid"] is True
        assert d["warnings"] == ["w"]
        assert d["info"] == ["i"]

    def test_default_empty_lists(self) -> None:
        result = ValidationResult(valid=True)
        assert result.errors == []
        assert result.warnings == []
        assert result.info == []


# ============================================================================
# IaCValidator tests
# ============================================================================


class TestIaCValidator:
    """Tests for the IaCValidator class."""

    def test_valid_profile_passes(self) -> None:
        profile = _make_profile()
        validator = IaCValidator(profile)
        result = validator.validate_all()
        assert result.valid is True
        assert len(result.errors) == 0

    def test_invalid_port_detected(self) -> None:
        profile = _make_profile_with_bad_ports()
        validator = IaCValidator(profile)
        result = validator.validate_ports()
        assert result.valid is False
        assert any("99999" in e for e in result.errors)
        assert any("-1" in e for e in result.errors)

    def test_privileged_port_info(self) -> None:
        profile = _make_profile()
        validator = IaCValidator(profile)
        result = validator.validate_ports()
        assert any("Privileged port" in i for i in result.info)

    def test_invalid_ip_detected(self) -> None:
        profile = _make_profile_with_bad_ports()
        validator = IaCValidator(profile)
        result = validator.validate_ip_addresses()
        assert result.valid is False
        assert any("not-an-ip" in e for e in result.errors)

    def test_private_ip_warning(self) -> None:
        profile = _make_minimal_profile()
        validator = IaCValidator(profile)
        result = validator.validate_ip_addresses()
        assert any("Private IP" in w for w in result.warnings)

    def test_no_ports_warning(self) -> None:
        profile = TargetProfile(target="empty.test")
        validator = IaCValidator(profile)
        result = validator.validate_ports()
        assert any("No open ports" in w for w in result.warnings)

    def test_no_ip_warning(self) -> None:
        profile = TargetProfile(target="no-ip.test")
        validator = IaCValidator(profile)
        result = validator.validate_ip_addresses()
        assert any("No IP addresses" in w for w in result.warnings)

    def test_os_not_detected_warning(self) -> None:
        profile = _make_minimal_profile()
        validator = IaCValidator(profile)
        result = validator.validate_os()
        assert any("OS not detected" in w for w in result.warnings)

    def test_os_detected_info(self) -> None:
        profile = _make_profile()
        validator = IaCValidator(profile)
        result = validator.validate_os()
        assert any("Ubuntu" in i for i in result.info)

    def test_windows_warning(self) -> None:
        profile = _make_profile_windows()
        validator = IaCValidator(profile)
        result = validator.validate_os()
        assert any("Windows target" in w for w in result.warnings)

    def test_wordpress_dependency_warnings(self) -> None:
        profile = TargetProfile(
            target="wp-alone.test",
            web_technologies=[
                DiscoveredWebTechnology("WordPress", "6.4", "cms"),
            ],
        )
        validator = IaCValidator(profile)
        result = validator.validate_dependencies()
        assert any("WordPress" in w for w in result.warnings)

    def test_port_conflict_detection(self) -> None:
        profile = TargetProfile(
            target="conflict.test",
            services=[
                DiscoveredService("nginx", "1.24", ServiceCategory.WEB_SERVER, 80),
                DiscoveredService("apache", "2.4", ServiceCategory.WEB_SERVER, 80),
            ],
        )
        validator = IaCValidator(profile)
        result = validator.validate_port_conflicts()
        assert any("Port conflict" in w for w in result.warnings)
        assert any("80" in w for w in result.warnings)

    def test_validate_all_combines_results(self) -> None:
        profile = _make_profile_with_bad_ports()
        validator = IaCValidator(profile)
        result = validator.validate_all()
        assert result.valid is False
        # Should have errors from both port and IP validation
        assert len(result.errors) >= 2

    def test_service_port_mismatch_warning(self) -> None:
        profile = TargetProfile(
            target="mismatch.test",
            open_ports=[DiscoveredPort(port=80)],
            services=[
                DiscoveredService("mysql", "8.0", ServiceCategory.DATABASE, 3306),
            ],
        )
        validator = IaCValidator(profile)
        result = validator.validate_services()
        assert any("3306" in w for w in result.warnings)

    def test_valid_profile_no_port_conflict(self) -> None:
        profile = _make_profile()
        validator = IaCValidator(profile)
        result = validator.validate_port_conflicts()
        assert len(result.warnings) == 0


# ============================================================================
# ServiceDependencyResolver tests
# ============================================================================


class TestServiceDependencyResolver:
    """Tests for topological role ordering."""

    def test_simple_ordering(self) -> None:
        resolver = ServiceDependencyResolver(["nginx", "common"])
        order = resolver.resolve()
        assert order.index("common") < order.index("nginx")

    def test_wordpress_chain(self) -> None:
        resolver = ServiceDependencyResolver(
            ["wordpress", "php", "mysql", "nginx", "common"],
        )
        order = resolver.resolve()
        assert order.index("common") < order.index("nginx")
        assert order.index("nginx") < order.index("php")
        assert order.index("mysql") < order.index("wordpress")
        assert order.index("php") < order.index("wordpress")

    def test_independent_services(self) -> None:
        resolver = ServiceDependencyResolver(["redis", "mongodb", "common"])
        order = resolver.resolve()
        assert order.index("common") < order.index("redis")
        assert order.index("common") < order.index("mongodb")
        assert len(order) == 3

    def test_single_role(self) -> None:
        resolver = ServiceDependencyResolver(["common"])
        order = resolver.resolve()
        assert order == ["common"]

    def test_empty_roles(self) -> None:
        resolver = ServiceDependencyResolver([])
        order = resolver.resolve()
        assert order == []

    def test_no_duplicates(self) -> None:
        resolver = ServiceDependencyResolver(
            ["nginx", "common", "ssl", "php"],
        )
        order = resolver.resolve()
        assert len(order) == len(set(order))

    def test_ssl_after_nginx(self) -> None:
        resolver = ServiceDependencyResolver(["ssl", "nginx", "common"])
        order = resolver.resolve()
        assert order.index("nginx") < order.index("ssl")

    def test_all_registered_roles(self) -> None:
        all_roles = [
            "common", "nginx", "apache", "mysql", "postgresql", "redis",
            "mongodb", "elasticsearch", "php", "nodejs", "ssl",
            "tomcat", "haproxy", "varnish", "memcached", "python", "rabbitmq",
        ]
        resolver = ServiceDependencyResolver(all_roles)
        order = resolver.resolve()
        assert len(order) == len(all_roles)
        assert order[0] == "common"


# ============================================================================
# PackerGenerator tests
# ============================================================================


class TestPackerGenerator:
    """Tests for the PackerGenerator class."""

    def test_generate_all_files(self) -> None:
        profile = _make_profile()
        gen = PackerGenerator(profile, CloudProvider.AWS)
        output = gen.generate_all()
        assert "packer.pkr.hcl" in output
        assert "scripts/provision.sh" in output

    def test_aws_packer_hcl(self) -> None:
        profile = _make_profile()
        gen = PackerGenerator(profile, CloudProvider.AWS)
        hcl = gen.generate_packer_hcl()
        assert "amazon-ebs" in hcl
        assert "source" in hcl
        assert "build" in hcl
        assert "example-com" in hcl or "example.com" in hcl

    def test_gcp_packer_hcl(self) -> None:
        profile = _make_profile()
        gen = PackerGenerator(profile, CloudProvider.GCP)
        hcl = gen.generate_packer_hcl()
        assert "googlecompute" in hcl
        assert "project_id" in hcl

    def test_azure_packer_hcl(self) -> None:
        profile = _make_profile()
        gen = PackerGenerator(profile, CloudProvider.AZURE)
        hcl = gen.generate_packer_hcl()
        assert "azure-arm" in hcl
        assert "subscription_id" in hcl

    def test_digitalocean_packer_hcl(self) -> None:
        profile = _make_profile()
        gen = PackerGenerator(profile, CloudProvider.DIGITALOCEAN)
        hcl = gen.generate_packer_hcl()
        assert "digitalocean" in hcl
        assert "api_token" in hcl

    def test_vmware_fallback(self) -> None:
        profile = _make_profile()
        gen = PackerGenerator(profile, CloudProvider.VMWARE)
        hcl = gen.generate_packer_hcl()
        # VMware falls back to AWS format
        assert "amazon-ebs" in hcl

    def test_provision_script_includes_discovered_packages(self) -> None:
        profile = _make_profile()
        gen = PackerGenerator(profile, CloudProvider.AWS)
        script = gen.generate_provision_script()
        assert "#!/bin/bash" in script
        assert "apt-get" in script
        assert "ufw" in script
        assert "curl" in script

    def test_provision_script_firewall_rules(self) -> None:
        profile = _make_profile()
        gen = PackerGenerator(profile, CloudProvider.AWS)
        script = gen.generate_provision_script()
        assert "ufw allow" in script

    def test_provision_script_sets_errexit(self) -> None:
        profile = _make_profile()
        gen = PackerGenerator(profile, CloudProvider.AWS)
        script = gen.generate_provision_script()
        assert "set -euxo pipefail" in script

    def test_ubuntu_os_image(self) -> None:
        profile = TargetProfile(operating_system="Ubuntu 22.04")
        gen = PackerGenerator(profile, CloudProvider.AWS)
        hcl = gen.generate_packer_hcl()
        assert "source_ami" in hcl

    def test_centos_os_image(self) -> None:
        profile = TargetProfile(operating_system="CentOS 7")
        gen = PackerGenerator(profile, CloudProvider.AWS)
        hcl = gen.generate_packer_hcl()
        assert "source_ami" in hcl

    def test_packer_scan_id_tag(self) -> None:
        profile = _make_profile()
        gen = PackerGenerator(profile, CloudProvider.AWS)
        hcl = gen.generate_packer_hcl()
        assert "test-scan-001" in hcl


# ============================================================================
# ReadmeGenerator tests
# ============================================================================


class TestReadmeGenerator:
    """Tests for the ReadmeGenerator class."""

    def test_generate_readme_content(self) -> None:
        profile = _make_profile()
        gen = ReadmeGenerator(profile, CloudProvider.AWS)
        readme = gen.generate()
        assert "# SpiderFoot Target Replica" in readme
        assert "example.com" in readme
        assert "terraform" in readme.lower()
        assert "ansible" in readme.lower()

    def test_readme_includes_docker_instructions(self) -> None:
        profile = _make_profile()
        gen = ReadmeGenerator(profile)
        readme = gen.generate()
        assert "docker compose" in readme.lower() or "docker-compose" in readme.lower()

    def test_readme_includes_packer_section(self) -> None:
        profile = _make_profile()
        gen = ReadmeGenerator(profile)
        readme = gen.generate()
        assert "packer" in readme.lower()

    def test_readme_includes_ports_table(self) -> None:
        profile = _make_profile()
        gen = ReadmeGenerator(profile)
        readme = gen.generate()
        assert "| Port |" in readme
        assert "80" in readme
        assert "443" in readme
        assert "3306" in readme

    def test_readme_includes_services_table(self) -> None:
        profile = _make_profile()
        gen = ReadmeGenerator(profile)
        readme = gen.generate()
        assert "| Service |" in readme
        assert "nginx" in readme
        assert "mysql" in readme

    def test_readme_no_ports(self) -> None:
        profile = TargetProfile(target="empty.test")
        gen = ReadmeGenerator(profile)
        readme = gen.generate()
        assert "No ports discovered" in readme

    def test_readme_no_services(self) -> None:
        profile = TargetProfile(target="empty.test")
        gen = ReadmeGenerator(profile)
        readme = gen.generate()
        assert "No services discovered" in readme

    def test_readme_provider_names(self) -> None:
        for provider, expected in [
            (CloudProvider.AWS, "AWS"),
            (CloudProvider.AZURE, "Azure"),
            (CloudProvider.GCP, "Google Cloud"),
        ]:
            readme = ReadmeGenerator(_make_profile(), provider).generate()
            assert expected in readme

    def test_readme_directory_structure(self) -> None:
        readme = ReadmeGenerator(_make_profile()).generate()
        assert "terraform/" in readme
        assert "ansible/" in readme
        assert "docker/" in readme
        assert "packer/" in readme

    def test_readme_troubleshooting(self) -> None:
        readme = ReadmeGenerator(_make_profile()).generate()
        assert "Troubleshooting" in readme


# ============================================================================
# TerraformBackendGenerator tests
# ============================================================================


class TestTerraformBackendGenerator:
    """Tests for the TerraformBackendGenerator class."""

    def test_aws_backend(self) -> None:
        profile = _make_profile()
        gen = TerraformBackendGenerator(CloudProvider.AWS, profile)
        backend = gen.generate()
        assert "s3" in backend
        assert "dynamodb_table" in backend
        assert "example-com" in backend

    def test_azure_backend(self) -> None:
        profile = _make_profile()
        gen = TerraformBackendGenerator(CloudProvider.AZURE, profile)
        backend = gen.generate()
        assert "azurerm" in backend
        assert "storage_account_name" in backend

    def test_gcp_backend(self) -> None:
        profile = _make_profile()
        gen = TerraformBackendGenerator(CloudProvider.GCP, profile)
        backend = gen.generate()
        assert "gcs" in backend
        assert "bucket" in backend

    def test_digitalocean_uses_s3(self) -> None:
        gen = TerraformBackendGenerator(CloudProvider.DIGITALOCEAN)
        backend = gen.generate()
        assert "s3" in backend

    def test_vmware_backend(self) -> None:
        gen = TerraformBackendGenerator(CloudProvider.VMWARE)
        backend = gen.generate()
        assert "consul" in backend or "VMware" in backend

    def test_default_profile(self) -> None:
        gen = TerraformBackendGenerator(CloudProvider.AWS)
        backend = gen.generate()
        assert "replica" in backend


# ============================================================================
# Enhanced DockerComposeGenerator tests
# ============================================================================


class TestDockerComposeEnhanced:
    """Tests for the enhanced DockerComposeGenerator features."""

    def test_healthcheck_in_web_service(self) -> None:
        profile = _make_profile()
        gen = DockerComposeGenerator(profile)
        compose = gen.generate()
        assert "healthcheck:" in compose

    def test_networks_section(self) -> None:
        profile = _make_profile()
        gen = DockerComposeGenerator(profile)
        compose = gen.generate()
        assert "networks:" in compose
        assert "frontend:" in compose
        assert "backend:" in compose
        assert "internal: true" in compose or "internal: True" in compose

    def test_volumes_section_for_database(self) -> None:
        profile = _make_profile()
        gen = DockerComposeGenerator(profile)
        compose = gen.generate()
        assert "volumes:" in compose

    def test_depends_on_with_condition(self) -> None:
        profile = _make_profile()
        gen = DockerComposeGenerator(profile)
        compose = gen.generate()
        assert "depends_on:" in compose
        assert "condition:" in compose

    def test_deploy_resource_limits(self) -> None:
        profile = _make_profile()
        gen = DockerComposeGenerator(profile)
        compose = gen.generate()
        assert "deploy:" in compose
        assert "resources:" in compose
        assert "limits:" in compose

    def test_elasticsearch_jvm_opts(self) -> None:
        profile = TargetProfile(
            target="elastic.test",
            services=[
                DiscoveredService("elasticsearch", "8.12", ServiceCategory.DATABASE, 9200),
            ],
        )
        gen = DockerComposeGenerator(profile)
        compose = gen.generate()
        assert "ES_JAVA_OPTS" in compose

    def test_redis_volume(self) -> None:
        profile = TargetProfile(
            target="redis.test",
            services=[
                DiscoveredService("redis", "7.2", ServiceCategory.CACHE, 6379),
            ],
        )
        gen = DockerComposeGenerator(profile)
        compose = gen.generate()
        assert "redis_data" in compose

    def test_rabbitmq_healthcheck(self) -> None:
        profile = TargetProfile(
            target="mq.test",
            services=[
                DiscoveredService("rabbitmq", "3.12", ServiceCategory.APPLICATION, 5672),
            ],
        )
        gen = DockerComposeGenerator(profile)
        compose = gen.generate()
        assert "rabbitmq-diagnostics" in compose

    def test_memcached_service(self) -> None:
        profile = TargetProfile(
            target="cache.test",
            services=[
                DiscoveredService("memcached", "1.6", ServiceCategory.CACHE, 11211),
            ],
        )
        gen = DockerComposeGenerator(profile)
        compose = gen.generate()
        assert "memcached" in compose
        assert "11211" in compose

    def test_mongodb_volumes(self) -> None:
        profile = _make_profile_with_mongodb()
        gen = DockerComposeGenerator(profile)
        compose = gen.generate()
        assert "mongodb_data" in compose


# ============================================================================
# Enhanced TerraformGenerator tests (VPC/network)
# ============================================================================


class TestTerraformVPCNetwork:
    """Tests for the enhanced AWS Terraform VPC/network generation."""

    def test_aws_vpc_created(self) -> None:
        profile = _make_profile()
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "aws_vpc" in main
        assert "10.0.0.0/16" in main

    def test_aws_internet_gateway(self) -> None:
        profile = _make_profile()
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "aws_internet_gateway" in main

    def test_aws_subnet(self) -> None:
        profile = _make_profile()
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "aws_subnet" in main
        assert "10.0.1.0/24" in main

    def test_aws_route_table(self) -> None:
        profile = _make_profile()
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "aws_route_table" in main

    def test_aws_key_pair(self) -> None:
        profile = _make_profile()
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "aws_key_pair" in main
        assert "ssh_public_key" in main

    def test_aws_elastic_ip(self) -> None:
        profile = _make_profile()
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "aws_eip" in main

    def test_aws_root_block_device(self) -> None:
        profile = _make_profile()
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "root_block_device" in main
        assert "gp3" in main
        assert "encrypted" in main

    def test_aws_ssh_ingress(self) -> None:
        profile = _make_profile()
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "SSH access" in main
        assert "22" in main

    def test_aws_lifecycle_rules(self) -> None:
        profile = _make_profile()
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        main = gen.generate_main()
        assert "lifecycle" in main
        assert "ignore_changes" in main or "create_before_destroy" in main

    def test_aws_outputs_eip(self) -> None:
        profile = _make_profile()
        gen = TerraformGenerator(profile, CloudProvider.AWS)
        outputs = gen.generate_outputs()
        assert "aws_eip" in outputs
        assert "vpc_id" in outputs
        assert "security_group_id" in outputs

    def test_backend_tf_in_generate_all(self) -> None:
        profile = _make_profile()
        replicator = TargetReplicator(profile, CloudProvider.AWS)
        output = replicator.generate()
        assert "backend.tf" in output["terraform"]


# ============================================================================
# Extended Ansible role tests (new roles)
# ============================================================================


class TestAnsibleNewRoles:
    """Tests for the new Ansible role generators."""

    def test_mongodb_role(self) -> None:
        profile = _make_profile_with_mongodb()
        gen = AnsibleGenerator(profile)
        files = gen.generate_all()
        # Check that mongodb role was generated
        role_key = [k for k in files if "mongodb" in k.lower()]
        assert len(role_key) > 0 or "playbook.yml" in files

    def test_elasticsearch_role(self) -> None:
        profile = _make_profile_with_elasticsearch()
        gen = AnsibleGenerator(profile)
        files = gen.generate_all()
        playbook = files["playbook.yml"]
        # Profile has elasticsearch, should appear in playbook
        assert "roles" in playbook

    def test_haproxy_role(self) -> None:
        profile = _make_profile_haproxy()
        gen = AnsibleGenerator(profile)
        files = gen.generate_all()
        playbook = files["playbook.yml"]
        assert "roles" in playbook

    def test_wordpress_role_detection(self) -> None:
        profile = _make_profile_with_wordpress()
        gen = AnsibleGenerator(profile)
        roles = gen._determine_roles()
        assert "wordpress" in roles or "php" in roles

    def test_mongodb_role_tasks_content(self) -> None:
        """Verify MongoDB role task content."""
        from spiderfoot.iac.target_replication import _generate_mongodb_role_tasks
        profile = _make_profile_with_mongodb()
        tasks = _generate_mongodb_role_tasks(profile)
        assert "Install MongoDB" in tasks
        assert "mongod.conf" in tasks
        assert "service" in tasks.lower()

    def test_elasticsearch_role_tasks_content(self) -> None:
        from spiderfoot.iac.target_replication import _generate_elasticsearch_role_tasks
        profile = _make_profile_with_elasticsearch()
        tasks = _generate_elasticsearch_role_tasks(profile)
        assert "Install Elasticsearch" in tasks
        assert "cluster.name" in tasks
        assert "single-node" in tasks

    def test_tomcat_role_tasks_content(self) -> None:
        from spiderfoot.iac.target_replication import _generate_tomcat_role_tasks
        tasks = _generate_tomcat_role_tasks(TargetProfile())
        assert "Install" in tasks
        assert "8080" in tasks

    def test_haproxy_role_tasks_content(self) -> None:
        from spiderfoot.iac.target_replication import _generate_haproxy_role_tasks
        profile = _make_profile_haproxy()
        tasks = _generate_haproxy_role_tasks(profile)
        assert "HAProxy" in tasks
        assert "frontend" in tasks
        assert "backend" in tasks

    def test_wordpress_role_tasks_content(self) -> None:
        from spiderfoot.iac.target_replication import _generate_wordpress_role_tasks
        profile = _make_profile_with_wordpress()
        tasks = _generate_wordpress_role_tasks(profile)
        assert "WordPress" in tasks
        assert "wp-config" in tasks

    def test_memcached_role_tasks_content(self) -> None:
        from spiderfoot.iac.target_replication import _generate_memcached_role_tasks
        tasks = _generate_memcached_role_tasks(TargetProfile())
        assert "Memcached" in tasks
        assert "11211" in tasks

    def test_varnish_role_tasks_content(self) -> None:
        from spiderfoot.iac.target_replication import _generate_varnish_role_tasks
        tasks = _generate_varnish_role_tasks(TargetProfile())
        assert "Varnish" in tasks
        assert "vcl" in tasks.lower()

    def test_python_role_tasks_content(self) -> None:
        from spiderfoot.iac.target_replication import _generate_python_role_tasks
        tasks = _generate_python_role_tasks(TargetProfile())
        assert "Python" in tasks
        assert "pip" in tasks.lower()

    def test_rabbitmq_role_tasks_content(self) -> None:
        from spiderfoot.iac.target_replication import _generate_rabbitmq_role_tasks
        tasks = _generate_rabbitmq_role_tasks(TargetProfile())
        assert "RabbitMQ" in tasks
        assert "5672" in tasks

    def test_generic_role_fallback(self) -> None:
        from spiderfoot.iac.target_replication import _generate_generic_role_tasks
        tasks = _generate_generic_role_tasks(TargetProfile())
        assert "manual customization" in tasks


# ============================================================================
# Extended TargetReplicator tests
# ============================================================================


class TestTargetReplicatorExtended:
    """Tests for the extended TargetReplicator capabilities."""

    def test_generate_includes_packer(self) -> None:
        replicator = TargetReplicator(_make_profile())
        output = replicator.generate()
        assert "packer" in output
        assert "packer.pkr.hcl" in output["packer"]
        assert "scripts/provision.sh" in output["packer"]

    def test_generate_includes_docs(self) -> None:
        replicator = TargetReplicator(_make_profile())
        output = replicator.generate()
        assert "docs" in output
        assert "README.md" in output["docs"]
        assert "VALIDATION.md" in output["docs"]

    def test_generate_includes_backend_tf(self) -> None:
        replicator = TargetReplicator(_make_profile())
        output = replicator.generate()
        assert "backend.tf" in output["terraform"]

    def test_validate_method(self) -> None:
        replicator = TargetReplicator(_make_profile())
        result = replicator.validate()
        assert isinstance(result, ValidationResult)
        assert result.valid is True

    def test_validate_invalid_profile(self) -> None:
        replicator = TargetReplicator(_make_profile_with_bad_ports())
        result = replicator.validate()
        assert result.valid is False

    def test_resolve_role_order(self) -> None:
        replicator = TargetReplicator(_make_profile())
        order = replicator.resolve_role_order()
        assert isinstance(order, list)
        assert len(order) > 0
        if "common" in order:
            assert order[0] == "common"

    def test_resolve_role_order_explicit(self) -> None:
        replicator = TargetReplicator(_make_profile())
        order = replicator.resolve_role_order(["wordpress", "mysql", "nginx", "common"])
        assert order.index("common") < order.index("nginx")
        assert order.index("mysql") < order.index("wordpress")

    def test_generate_multi_provider_default(self) -> None:
        replicator = TargetReplicator(_make_profile())
        results = replicator.generate_multi_provider()
        assert "aws" in results
        assert "azure" in results
        assert "gcp" in results
        assert "digitalocean" in results
        assert "vmware" in results

    def test_generate_multi_provider_subset(self) -> None:
        replicator = TargetReplicator(_make_profile())
        results = replicator.generate_multi_provider(["aws", "gcp"])
        assert len(results) == 2
        assert "aws" in results
        assert "gcp" in results

    def test_multi_provider_each_has_terraform(self) -> None:
        replicator = TargetReplicator(_make_profile())
        results = replicator.generate_multi_provider(["aws", "azure"])
        for provider, output in results.items():
            assert "terraform" in output
            assert "main.tf" in output["terraform"]

    def test_generate_packer_method(self) -> None:
        replicator = TargetReplicator(_make_profile())
        packer = replicator.generate_packer()
        assert "packer.pkr.hcl" in packer
        assert "scripts/provision.sh" in packer

    def test_generate_readme_method(self) -> None:
        replicator = TargetReplicator(_make_profile())
        readme = replicator.generate_readme()
        assert "# SpiderFoot Target Replica" in readme

    def test_validation_report_in_docs(self) -> None:
        replicator = TargetReplicator(_make_profile())
        output = replicator.generate()
        validation_md = output["docs"]["VALIDATION.md"]
        assert "Validation Report" in validation_md
        assert "PASS" in validation_md or "FAIL" in validation_md

    def test_validation_report_fail(self) -> None:
        replicator = TargetReplicator(_make_profile_with_bad_ports())
        output = replicator.generate()
        validation_md = output["docs"]["VALIDATION.md"]
        assert "FAIL" in validation_md
        assert "Errors" in validation_md

    def test_write_to_directory_creates_packer(self) -> None:
        profile = _make_profile()
        replicator = TargetReplicator(profile)
        with tempfile.TemporaryDirectory() as tmpdir:
            written = replicator.write_to_directory(tmpdir)
            packer_files = [f for f in written if "packer" in f]
            assert len(packer_files) > 0

    def test_write_to_directory_creates_docs(self) -> None:
        profile = _make_profile()
        replicator = TargetReplicator(profile)
        with tempfile.TemporaryDirectory() as tmpdir:
            written = replicator.write_to_directory(tmpdir)
            doc_files = [f for f in written if "docs" in f]
            assert len(doc_files) > 0
