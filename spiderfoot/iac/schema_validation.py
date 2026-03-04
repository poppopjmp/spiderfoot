# -*- coding: utf-8 -*-
"""Schema-based validation for generated IaC artifacts.

Validates generated Terraform, Ansible, and Docker Compose files using
JSON Schema and structural checks — no external binaries required.

Consumed by:
  - spiderfoot.iac.target_replication.IaCValidator (extended validation)
  - spiderfoot.api.routers.iac (API endpoint validation)
  - spiderfoot.services.cli_service (CLI validation command)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger("spiderfoot.iac.schema_validation")

# ---------------------------------------------------------------------------
# Shared result type
# ---------------------------------------------------------------------------


@dataclass
class SchemaValidationResult:
    """Result of schema validation for one artifact."""

    artifact_type: str = ""
    file_name: str = ""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: "SchemaValidationResult") -> "SchemaValidationResult":
        return SchemaValidationResult(
            artifact_type=self.artifact_type or other.artifact_type,
            file_name=self.file_name or other.file_name,
            valid=self.valid and other.valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "file_name": self.file_name,
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Terraform JSON validator (Steps 56-60)
# ---------------------------------------------------------------------------

# Required top-level keys in Terraform JSON format
_TF_VALID_TOP_KEYS = {
    "terraform", "provider", "resource", "data", "variable",
    "output", "locals", "module",
}

# Common resource types per provider
_TF_KNOWN_RESOURCE_TYPES = {
    "aws_instance", "aws_security_group", "aws_security_group_rule",
    "aws_vpc", "aws_subnet", "aws_internet_gateway", "aws_route_table",
    "aws_route_table_association", "aws_key_pair", "aws_eip",
    "azurerm_resource_group", "azurerm_virtual_network", "azurerm_subnet",
    "azurerm_network_security_group", "azurerm_network_interface",
    "azurerm_linux_virtual_machine", "azurerm_public_ip",
    "google_compute_instance", "google_compute_network",
    "google_compute_subnetwork", "google_compute_firewall",
    "google_compute_address",
    "digitalocean_droplet", "digitalocean_firewall",
}


def validate_terraform_json(content: str | dict, filename: str = "main.tf.json") -> SchemaValidationResult:
    """Validate a Terraform JSON configuration.

    Checks:
      1. Valid JSON syntax
      2. Expected top-level structure (terraform, provider, resource, etc.)
      3. Provider blocks have required fields
      4. Resources have valid type + name structure
      5. Security group rules have valid port ranges
      6. Variables have type/description
    """
    result = SchemaValidationResult(artifact_type="terraform", file_name=filename)

    # 1. Parse JSON
    if isinstance(content, str):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            result.valid = False
            result.errors.append(f"Invalid JSON: {e}")
            return result
    else:
        data = content

    if not isinstance(data, dict):
        result.valid = False
        result.errors.append("Terraform JSON must be a JSON object at top level")
        return result

    # 2. Top-level structure
    unknown_keys = set(data.keys()) - _TF_VALID_TOP_KEYS
    for key in unknown_keys:
        result.warnings.append(f"Unknown top-level key: '{key}'")

    if not data:
        result.valid = False
        result.errors.append("Empty Terraform configuration")
        return result

    # 3. Provider validation
    providers = data.get("provider", {})
    if isinstance(providers, dict):
        for provider_name, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                result.errors.append(f"Provider '{provider_name}' config must be an object")
                result.valid = False
                continue
            # AWS needs region
            if provider_name == "aws" and "region" not in provider_config:
                result.warnings.append("AWS provider missing 'region'")
            # Azure needs features block
            if provider_name == "azurerm" and "features" not in provider_config:
                result.warnings.append("Azure provider missing 'features' block")
    elif isinstance(providers, list):
        # List of provider blocks is also valid
        for p in providers:
            if not isinstance(p, dict):
                result.errors.append("Provider entry must be an object")
                result.valid = False

    # 4. Resource validation
    resources = data.get("resource", {})
    if isinstance(resources, dict):
        for resource_type, resource_instances in resources.items():
            # Validate type format: must have exactly one underscore-separated prefix
            if "_" not in resource_type:
                result.errors.append(
                    f"Resource type '{resource_type}' must follow 'provider_type' format"
                )
                result.valid = False
                continue

            if not isinstance(resource_instances, dict):
                result.errors.append(
                    f"Resource '{resource_type}' instances must be an object"
                )
                result.valid = False
                continue

            for instance_name, instance_config in resource_instances.items():
                if not isinstance(instance_config, dict):
                    result.errors.append(
                        f"Resource '{resource_type}.{instance_name}' config must be an object"
                    )
                    result.valid = False
                    continue

                # Check security group rules for valid ports
                if "security_group" in resource_type or "firewall" in resource_type:
                    _validate_security_rules(
                        resource_type, instance_name, instance_config, result
                    )

    # 5. Variable validation
    variables = data.get("variable", {})
    if isinstance(variables, dict):
        for var_name, var_config in variables.items():
            if not isinstance(var_config, dict):
                result.warnings.append(f"Variable '{var_name}' should be an object")
                continue
            if "type" not in var_config and "default" not in var_config:
                result.warnings.append(
                    f"Variable '{var_name}' has no type or default"
                )

    # 6. Output validation
    outputs = data.get("output", {})
    if isinstance(outputs, dict):
        for out_name, out_config in outputs.items():
            if isinstance(out_config, dict) and "value" not in out_config:
                result.errors.append(f"Output '{out_name}' missing 'value'")
                result.valid = False

    return result


def _validate_security_rules(
    resource_type: str, name: str, config: dict, result: SchemaValidationResult
) -> None:
    """Validate security group / firewall rule port ranges."""
    # Check ingress/egress rules
    for rule_key in ("ingress", "egress", "inbound_rule", "outbound_rule"):
        rules = config.get(rule_key, [])
        if not isinstance(rules, list):
            rules = [rules]
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            from_port = rule.get("from_port", rule.get("port_range", {}).get("min"))
            to_port = rule.get("to_port", rule.get("port_range", {}).get("max"))
            if from_port is not None and to_port is not None:
                try:
                    fp, tp = int(from_port), int(to_port)
                    if fp < 0 or tp > 65535:
                        result.errors.append(
                            f"{resource_type}.{name} {rule_key}[{i}]: "
                            f"port range {fp}-{tp} out of bounds"
                        )
                        result.valid = False
                    if fp > tp:
                        result.errors.append(
                            f"{resource_type}.{name} {rule_key}[{i}]: "
                            f"from_port ({fp}) > to_port ({tp})"
                        )
                        result.valid = False
                except (ValueError, TypeError):
                    pass  # Skip non-integer port references


# ---------------------------------------------------------------------------
# Ansible YAML validator (Steps 61-65)
# ---------------------------------------------------------------------------

def validate_ansible_playbook(content: str | dict | list, filename: str = "playbook.yml") -> SchemaValidationResult:
    """Validate an Ansible playbook structure.

    Checks:
      1. Valid YAML syntax
      2. Playbook is a list of plays
      3. Each play has required keys (hosts)
      4. Tasks have 'name' and at least one module
      5. Role references are strings or dicts with 'role' key
      6. Handler names are unique
    """
    result = SchemaValidationResult(artifact_type="ansible_playbook", file_name=filename)

    # 1. Parse YAML
    if isinstance(content, str):
        try:
            import yaml
            data = yaml.safe_load(content)
        except Exception as e:
            result.valid = False
            result.errors.append(f"Invalid YAML: {e}")
            return result
    else:
        data = content

    if data is None:
        result.valid = False
        result.errors.append("Empty playbook")
        return result

    # 2. Must be a list
    if not isinstance(data, list):
        result.valid = False
        result.errors.append("Playbook must be a YAML list of plays")
        return result

    if not data:
        result.warnings.append("Playbook is empty (no plays)")
        return result

    # 3. Validate each play
    for i, play in enumerate(data):
        if not isinstance(play, dict):
            result.errors.append(f"Play {i}: must be a YAML mapping")
            result.valid = False
            continue

        # hosts is required (except for import_playbook)
        if "hosts" not in play and "import_playbook" not in play:
            result.errors.append(f"Play {i}: missing 'hosts' key")
            result.valid = False

        # Validate tasks
        for task_key in ("tasks", "pre_tasks", "post_tasks"):
            tasks = play.get(task_key, [])
            if not isinstance(tasks, list):
                result.errors.append(f"Play {i}: '{task_key}' must be a list")
                result.valid = False
                continue
            _validate_ansible_tasks(i, task_key, tasks, result)

        # Validate roles
        roles = play.get("roles", [])
        if isinstance(roles, list):
            for j, role in enumerate(roles):
                if isinstance(role, str):
                    continue  # Simple role reference
                elif isinstance(role, dict):
                    if "role" not in role:
                        result.errors.append(
                            f"Play {i} role {j}: dict role must have 'role' key"
                        )
                        result.valid = False
                else:
                    result.errors.append(f"Play {i} role {j}: must be string or dict")
                    result.valid = False

        # Validate handlers
        handlers = play.get("handlers", [])
        if isinstance(handlers, list):
            handler_names = []
            for j, handler in enumerate(handlers):
                if not isinstance(handler, dict):
                    continue
                name = handler.get("name")
                if not name:
                    result.warnings.append(f"Play {i} handler {j}: missing 'name'")
                elif name in handler_names:
                    result.warnings.append(
                        f"Play {i}: duplicate handler name '{name}'"
                    )
                else:
                    handler_names.append(name)

    return result


def _validate_ansible_tasks(
    play_idx: int, key: str, tasks: list, result: SchemaValidationResult
) -> None:
    """Validate a list of Ansible tasks."""
    # Known Ansible module names (subset — enough for validation)
    _KNOWN_MODULES = {
        "apt", "yum", "dnf", "package", "pip", "copy", "template",
        "file", "lineinfile", "service", "systemd", "command", "shell",
        "raw", "script", "debug", "set_fact", "include_tasks",
        "import_tasks", "include_role", "import_role", "include_vars",
        "uri", "get_url", "unarchive", "stat", "wait_for", "pause",
        "user", "group", "cron", "mount", "sysctl", "ufw", "firewalld",
        "docker_container", "docker_image", "docker_compose",
        "k8s", "helm", "git", "mysql_db", "mysql_user",
        "postgresql_db", "postgresql_user", "redis", "block",
    }

    # Keys that are task modifiers, not modules
    _TASK_MODIFIERS = {
        "name", "when", "register", "become", "become_user", "become_method",
        "environment", "vars", "loop", "with_items", "with_dict",
        "with_fileglob", "notify", "tags", "ignore_errors", "changed_when",
        "failed_when", "no_log", "delegate_to", "run_once", "listen",
        "retries", "delay", "until", "check_mode", "diff", "block",
        "rescue", "always", "timeout", "throttle", "any_errors_fatal",
    }

    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            result.errors.append(f"Play {play_idx} {key}[{i}]: must be a mapping")
            result.valid = False
            continue

        # Check for name (warning only — name is optional but recommended)
        if "name" not in task and "block" not in task:
            result.warnings.append(f"Play {play_idx} {key}[{i}]: missing 'name'")

        # Check that at least one module key exists
        module_keys = set(task.keys()) - _TASK_MODIFIERS
        if not module_keys and "block" not in task:
            result.errors.append(
                f"Play {play_idx} {key}[{i}]: no module specified"
            )
            result.valid = False


def validate_ansible_inventory(content: str | dict, filename: str = "inventory.ini") -> SchemaValidationResult:
    """Validate an Ansible inventory file (INI or YAML format)."""
    result = SchemaValidationResult(artifact_type="ansible_inventory", file_name=filename)

    if isinstance(content, dict):
        # YAML inventory
        if not content:
            result.warnings.append("Empty inventory")
        return result

    if not isinstance(content, str):
        result.valid = False
        result.errors.append("Inventory must be a string or dict")
        return result

    if not content.strip():
        result.warnings.append("Empty inventory file")
        return result

    # Basic INI format validation
    lines = content.strip().split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        if stripped.startswith("[") and not stripped.endswith("]"):
            result.errors.append(f"Line {i}: malformed group header: {stripped}")
            result.valid = False

    return result


# ---------------------------------------------------------------------------
# Docker Compose validator (Steps 66-70)
# ---------------------------------------------------------------------------

# Docker Compose v3 valid top-level keys
_COMPOSE_VALID_TOP_KEYS = {
    "version", "services", "networks", "volumes", "configs",
    "secrets", "x-", "name",
}

# Valid service-level keys
_COMPOSE_VALID_SERVICE_KEYS = {
    "image", "build", "container_name", "command", "entrypoint",
    "environment", "env_file", "ports", "expose", "volumes",
    "networks", "depends_on", "restart", "deploy", "healthcheck",
    "logging", "labels", "working_dir", "user", "stdin_open", "tty",
    "cap_add", "cap_drop", "security_opt", "sysctls", "ulimits",
    "privileged", "read_only", "tmpfs", "shm_size", "mem_limit",
    "memswap_limit", "cpus", "cpu_shares", "hostname", "domainname",
    "dns", "dns_search", "extra_hosts", "links", "external_links",
    "pid", "ipc", "stop_signal", "stop_grace_period", "init",
    "platform", "profiles", "pull_policy", "devices", "configs",
    "secrets",
}


def validate_docker_compose(content: str | dict, filename: str = "docker-compose.yml") -> SchemaValidationResult:
    """Validate a Docker Compose configuration.

    Checks:
      1. Valid YAML syntax
      2. Top-level structure (services required)
      3. Service definitions have image or build
      4. Port mappings are valid
      5. Volume references are consistent
      6. depends_on references exist
      7. Network references are consistent
    """
    result = SchemaValidationResult(artifact_type="docker_compose", file_name=filename)

    # 1. Parse YAML
    if isinstance(content, str):
        try:
            import yaml
            data = yaml.safe_load(content)
        except Exception as e:
            result.valid = False
            result.errors.append(f"Invalid YAML: {e}")
            return result
    else:
        data = content

    if not isinstance(data, dict):
        result.valid = False
        result.errors.append("Docker Compose must be a YAML mapping")
        return result

    # 2. Top-level structure
    if "services" not in data:
        result.valid = False
        result.errors.append("Missing required 'services' key")
        return result

    unknown_top = {
        k for k in data.keys()
        if k not in _COMPOSE_VALID_TOP_KEYS and not k.startswith("x-")
    }
    for key in unknown_top:
        result.warnings.append(f"Unknown top-level key: '{key}'")

    services = data["services"]
    if not isinstance(services, dict):
        result.valid = False
        result.errors.append("'services' must be a mapping")
        return result

    # Collect defined names for cross-referencing
    service_names = set(services.keys())
    defined_volumes = set((data.get("volumes") or {}).keys()) if isinstance(data.get("volumes"), dict) else set()
    defined_networks = set((data.get("networks") or {}).keys()) if isinstance(data.get("networks"), dict) else set()

    # 3-7. Validate each service
    for svc_name, svc_config in services.items():
        if not isinstance(svc_config, dict):
            result.errors.append(f"Service '{svc_name}': must be a mapping")
            result.valid = False
            continue

        # Must have image or build
        if "image" not in svc_config and "build" not in svc_config:
            result.errors.append(f"Service '{svc_name}': missing 'image' or 'build'")
            result.valid = False

        # Validate ports
        ports = svc_config.get("ports", [])
        if isinstance(ports, list):
            for i, port in enumerate(ports):
                _validate_compose_port(svc_name, i, port, result)

        # Validate depends_on references
        depends = svc_config.get("depends_on", [])
        if isinstance(depends, list):
            for dep in depends:
                if isinstance(dep, str) and dep not in service_names:
                    result.errors.append(
                        f"Service '{svc_name}': depends_on '{dep}' not defined"
                    )
                    result.valid = False
        elif isinstance(depends, dict):
            for dep_name in depends.keys():
                if dep_name not in service_names:
                    result.errors.append(
                        f"Service '{svc_name}': depends_on '{dep_name}' not defined"
                    )
                    result.valid = False

        # Validate volume references
        volumes = svc_config.get("volumes", [])
        if isinstance(volumes, list):
            for vol in volumes:
                if isinstance(vol, str) and ":" in vol:
                    vol_name = vol.split(":")[0]
                    # Named volumes (not paths) should be defined
                    if (
                        not vol_name.startswith(".")
                        and not vol_name.startswith("/")
                        and not vol_name.startswith("~")
                        and defined_volumes
                        and vol_name not in defined_volumes
                    ):
                        result.warnings.append(
                            f"Service '{svc_name}': volume '{vol_name}' "
                            f"not in top-level volumes"
                        )

        # Validate network references
        networks = svc_config.get("networks", [])
        if isinstance(networks, list):
            for net in networks:
                if isinstance(net, str) and defined_networks and net not in defined_networks:
                    result.warnings.append(
                        f"Service '{svc_name}': network '{net}' not in top-level networks"
                    )
        elif isinstance(networks, dict):
            for net_name in networks.keys():
                if defined_networks and net_name not in defined_networks:
                    result.warnings.append(
                        f"Service '{svc_name}': network '{net_name}' not in top-level networks"
                    )

        # Validate healthcheck
        healthcheck = svc_config.get("healthcheck")
        if isinstance(healthcheck, dict):
            if "test" not in healthcheck and "disable" not in healthcheck:
                result.warnings.append(
                    f"Service '{svc_name}': healthcheck missing 'test'"
                )

    return result


def _validate_compose_port(
    svc_name: str, idx: int, port: Any, result: SchemaValidationResult
) -> None:
    """Validate a single port mapping."""
    if isinstance(port, int):
        if port < 1 or port > 65535:
            result.errors.append(
                f"Service '{svc_name}' port {idx}: {port} out of range"
            )
            result.valid = False
    elif isinstance(port, str):
        # Parse "host:container" or "host:container/proto"
        parts = port.replace("/tcp", "").replace("/udp", "").split(":")
        for p in parts:
            if p and p != "":
                try:
                    port_num = int(p.split("-")[0])  # Handle ranges like "8080-8090"
                    if port_num < 0 or port_num > 65535:
                        result.errors.append(
                            f"Service '{svc_name}' port {idx}: "
                            f"port number {port_num} out of range in '{port}'"
                        )
                        result.valid = False
                except ValueError:
                    pass  # Variable reference or IP:port format


# ---------------------------------------------------------------------------
# Unified validation
# ---------------------------------------------------------------------------

def validate_iac_bundle(bundle: dict[str, Any]) -> list[SchemaValidationResult]:
    """Validate a complete IaC bundle as returned by TargetReplicator.generate().

    Args:
        bundle: Dict with keys like 'terraform', 'ansible', 'docker', etc.
                Each value is a dict of {filename: content}.

    Returns:
        List of SchemaValidationResult for each validated artifact.
    """
    results: list[SchemaValidationResult] = []

    # Terraform
    tf_files = bundle.get("terraform", {})
    if isinstance(tf_files, dict):
        for fname, content in tf_files.items():
            if fname.endswith(".tf.json") or fname == "main.tf.json":
                results.append(validate_terraform_json(content, fname))
            elif fname.endswith(".tf") and isinstance(content, str):
                # HCL text — delegate to the full HCL validator
                from spiderfoot.iac.hcl_validator import validate_hcl as _validate_hcl
                hcl_res = _validate_hcl(fname, content)
                # Wrap into SchemaValidationResult so callers see a uniform type
                r = SchemaValidationResult(
                    artifact_type="terraform_hcl", file_name=fname
                )
                r.valid = hcl_res.valid
                r.errors = list(hcl_res.errors)
                r.warnings = list(hcl_res.warnings)
                results.append(r)

    # Ansible
    ansible_files = bundle.get("ansible", {})
    if isinstance(ansible_files, dict):
        for fname, content in ansible_files.items():
            if "playbook" in fname or fname.endswith(".yml") and "inventory" not in fname:
                results.append(validate_ansible_playbook(content, fname))
            elif "inventory" in fname:
                results.append(validate_ansible_inventory(content, fname))

    # Docker Compose
    docker_files = bundle.get("docker", {})
    if isinstance(docker_files, dict):
        for fname, content in docker_files.items():
            if "docker-compose" in fname or "compose" in fname:
                results.append(validate_docker_compose(content, fname))

    return results
