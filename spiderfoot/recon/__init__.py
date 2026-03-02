# Recon package re-exports
# IaC generators moved to spiderfoot.iac — import from there for canonical path
from spiderfoot.iac.target_replication import (
    AnsibleGenerator,
    CloudProvider,
    DockerComposeGenerator,
    TargetProfile,
    TargetProfileExtractor,
    TargetReplicator,
    TerraformGenerator,
)

from .tls_fingerprint import (
    BrowserFingerprintProfile,
    FingerprintEvasionEngine,
    JA3Calculator,
    JA4Calculator,
    TLSExtensionProfile,
    get_browser_profiles,
    list_profile_names,
)

__all__ = [
    "AnsibleGenerator",
    "CloudProvider",
    "DockerComposeGenerator",
    "TargetProfile",
    "TargetProfileExtractor",
    "TargetReplicator",
    "TerraformGenerator",
    # TLS fingerprint evasion
    "BrowserFingerprintProfile",
    "FingerprintEvasionEngine",
    "JA3Calculator",
    "JA4Calculator",
    "TLSExtensionProfile",
    "get_browser_profiles",
    "list_profile_names",
]