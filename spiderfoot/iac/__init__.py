# -*- coding: utf-8 -*-
"""IaC (Infrastructure as Code) generation package.

Generates Terraform, Ansible, Docker Compose, and Packer configurations
from SpiderFoot scan results. Includes schema-based validation.
"""
from __future__ import annotations

from .target_replication import (
    AnsibleGenerator,
    CloudProvider,
    DockerComposeGenerator,
    IaCValidator,
    PackerGenerator,
    ReadmeGenerator,
    ServiceDependencyResolver,
    TargetProfile,
    TargetProfileExtractor,
    TargetReplicator,
    TerraformBackendGenerator,
    TerraformGenerator,
    ValidationResult,
)
from .schema_validation import (
    SchemaValidationResult,
    validate_ansible_inventory,
    validate_ansible_playbook,
    validate_docker_compose,
    validate_iac_bundle,
    validate_terraform_json,
)
from .hcl_validator import (
    HCLValidationResult,
    audit_terraform_bundle,
    validate_hcl,
    validate_hcl_bundle,
)
from .iac_agent import (
    AgentResult,
    IaCAgent,
)

__all__ = [
    # target_replication
    "AnsibleGenerator",
    "CloudProvider",
    "DockerComposeGenerator",
    "IaCValidator",
    "PackerGenerator",
    "ReadmeGenerator",
    "ServiceDependencyResolver",
    "TargetProfile",
    "TargetProfileExtractor",
    "TargetReplicator",
    "TerraformBackendGenerator",
    "TerraformGenerator",
    "ValidationResult",
    # schema_validation
    "SchemaValidationResult",
    "validate_ansible_inventory",
    "validate_ansible_playbook",
    "validate_docker_compose",
    "validate_iac_bundle",
    "validate_terraform_json",
    # hcl_validator
    "HCLValidationResult",
    "audit_terraform_bundle",
    "validate_hcl",
    "validate_hcl_bundle",
    # iac_agent
    "AgentResult",
    "IaCAgent",
]
