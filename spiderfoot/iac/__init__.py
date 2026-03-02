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

__all__ = [
    "AnsibleGenerator",
    "CloudProvider",
    "DockerComposeGenerator",
    "IaCValidator",
    "PackerGenerator",
    "ReadmeGenerator",
    "SchemaValidationResult",
    "ServiceDependencyResolver",
    "TargetProfile",
    "TargetProfileExtractor",
    "TargetReplicator",
    "TerraformBackendGenerator",
    "TerraformGenerator",
    "ValidationResult",
    "validate_ansible_inventory",
    "validate_ansible_playbook",
    "validate_docker_compose",
    "validate_iac_bundle",
    "validate_terraform_json",
]
