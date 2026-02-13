"""SARIF (Static Analysis Results Interchange Format) v2.1.0 export.

Converts SpiderFoot scan findings into SARIF format compatible with
GitHub Code Scanning, Azure DevOps, and other SARIF consumers.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"

# SpiderFoot event severity → SARIF level mapping
_SEVERITY_MAP: dict[str, str] = {
    "CRITICAL": "error",
    "HIGH": "error",
    "MEDIUM": "warning",
    "LOW": "note",
    "INFO": "note",
}

# Event types that produce SARIF results
_SARIF_RULE_MAP: dict[str, dict[str, Any]] = {
    "VULNERABILITY_CVE_CRITICAL": {
        "id": "SF-VULN-CRITICAL",
        "name": "CriticalVulnerability",
        "shortDescription": "Critical severity vulnerability detected",
        "level": "error",
        "tags": ["security", "vulnerability", "critical"],
    },
    "VULNERABILITY_CVE_HIGH": {
        "id": "SF-VULN-HIGH",
        "name": "HighVulnerability",
        "shortDescription": "High severity vulnerability detected",
        "level": "error",
        "tags": ["security", "vulnerability", "high"],
    },
    "VULNERABILITY_CVE_MEDIUM": {
        "id": "SF-VULN-MEDIUM",
        "name": "MediumVulnerability",
        "shortDescription": "Medium severity vulnerability detected",
        "level": "warning",
        "tags": ["security", "vulnerability", "medium"],
    },
    "VULNERABILITY_CVE_LOW": {
        "id": "SF-VULN-LOW",
        "name": "LowVulnerability",
        "shortDescription": "Low severity vulnerability detected",
        "level": "note",
        "tags": ["security", "vulnerability", "low"],
    },
    "VULNERABILITY_GENERAL": {
        "id": "SF-VULN-GENERAL",
        "name": "GeneralVulnerability",
        "shortDescription": "General vulnerability or misconfiguration",
        "level": "warning",
        "tags": ["security", "vulnerability"],
    },
    "MALICIOUS_IPADDR": {
        "id": "SF-MAL-IP",
        "name": "MaliciousIPAddress",
        "shortDescription": "IP address flagged as malicious",
        "level": "error",
        "tags": ["security", "malicious", "network"],
    },
    "MALICIOUS_INTERNET_NAME": {
        "id": "SF-MAL-HOST",
        "name": "MaliciousHostname",
        "shortDescription": "Hostname flagged as malicious",
        "level": "error",
        "tags": ["security", "malicious", "network"],
    },
    "MALICIOUS_AFFILIATE_IPADDR": {
        "id": "SF-MAL-AFF-IP",
        "name": "MaliciousAffiliateIP",
        "shortDescription": "Affiliated IP address flagged as malicious",
        "level": "warning",
        "tags": ["security", "malicious", "affiliate"],
    },
    "MALICIOUS_AFFILIATE_INTERNET_NAME": {
        "id": "SF-MAL-AFF-HOST",
        "name": "MaliciousAffiliateHostname",
        "shortDescription": "Affiliated hostname flagged as malicious",
        "level": "warning",
        "tags": ["security", "malicious", "affiliate"],
    },
    "MALICIOUS_EMAILADDR": {
        "id": "SF-MAL-EMAIL",
        "name": "MaliciousEmailAddress",
        "shortDescription": "Email address flagged as malicious",
        "level": "warning",
        "tags": ["security", "malicious", "email"],
    },
    "HASH_COMPROMISED": {
        "id": "SF-HASH-COMPROMISED",
        "name": "CompromisedHash",
        "shortDescription": "File hash found in breach/malware databases",
        "level": "error",
        "tags": ["security", "compromised", "hash"],
    },
    "TCP_PORT_OPEN": {
        "id": "SF-PORT-OPEN",
        "name": "OpenPort",
        "shortDescription": "Open TCP port detected",
        "level": "note",
        "tags": ["security", "network", "port"],
    },
    "EMAILADDR_COMPROMISED": {
        "id": "SF-EMAIL-BREACH",
        "name": "EmailInBreach",
        "shortDescription": "Email address found in data breach",
        "level": "warning",
        "tags": ["security", "breach", "email"],
    },
    "PASSWORD_COMPROMISED": {
        "id": "SF-PASS-BREACH",
        "name": "PasswordCompromised",
        "shortDescription": "Compromised password or credential detected",
        "level": "error",
        "tags": ["security", "breach", "credential"],
    },
}


def _fingerprint(*parts: str) -> str:
    """Generate a deterministic result fingerprint."""
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


class SARIFExporter:
    """Convert SpiderFoot scan data to SARIF v2.1.0 format."""

    def __init__(self, scan_id: str, scan_name: str, scan_target: str,
                 version: str = "5.5.6"):
        self.scan_id = scan_id
        self.scan_name = scan_name
        self.scan_target = scan_target
        self.version = version
        self._results: list[dict[str, Any]] = []
        self._rules_used: dict[str, dict[str, Any]] = {}
        self._artifacts: dict[str, int] = {}  # uri → artifact index

    def _get_artifact_index(self, uri: str) -> int:
        """Get or register an artifact and return its index."""
        if uri not in self._artifacts:
            self._artifacts[uri] = len(self._artifacts)
        return self._artifacts[uri]

    def add_event(self, event_type: str, data: str, module: str = "",
                  source_event: str = "", timestamp: str = "") -> bool:
        """Add a SpiderFoot event as a SARIF result.

        Returns True if the event was converted, False if unmapped.
        """
        rule_info = _SARIF_RULE_MAP.get(event_type)
        if rule_info is None:
            return False

        rule_id = rule_info["id"]
        self._rules_used[rule_id] = rule_info

        # Build the result
        result: dict[str, Any] = {
            "ruleId": rule_id,
            "level": rule_info["level"],
            "message": {
                "text": data,
            },
            "fingerprints": {
                "primaryLocationHash": _fingerprint(
                    self.scan_id, event_type, data
                ),
            },
            "properties": {
                "eventType": event_type,
                "scanId": self.scan_id,
                "scanTarget": self.scan_target,
            },
        }

        # Add module info
        if module:
            result["properties"]["module"] = module

        # Add source event
        if source_event:
            result["properties"]["sourceEvent"] = source_event

        # Add timestamp
        if timestamp:
            result["properties"]["timestamp"] = timestamp

        # Add location based on data type
        location = self._build_location(event_type, data)
        if location:
            result["locations"] = [location]

        # Extract CVE references
        cve_refs = self._extract_cve_refs(data)
        if cve_refs:
            result["relatedLocations"] = []
            for cve in cve_refs:
                result.setdefault("properties", {})["cveId"] = cve
                # SARIF external properties
                result.setdefault("partialFingerprints", {})["cveId"] = cve

        self._results.append(result)
        return True

    def _build_location(self, event_type: str, data: str) -> dict[str, Any] | None:
        """Build a SARIF location from event data."""
        # Use scan target as the logical "artifact"
        uri = self.scan_target or "unknown"

        # For network-related events, use the data as the URI
        if event_type in (
            "MALICIOUS_IPADDR", "MALICIOUS_INTERNET_NAME",
            "TCP_PORT_OPEN", "UDP_PORT_OPEN",
        ):
            uri = data.split(":")[0] if ":" in data else data

        artifact_idx = self._get_artifact_index(uri)
        return {
            "physicalLocation": {
                "artifactLocation": {
                    "uri": uri,
                    "index": artifact_idx,
                },
            },
            "logicalLocations": [
                {
                    "name": data[:200],
                    "kind": "target",
                }
            ],
        }

    @staticmethod
    def _extract_cve_refs(data: str) -> list[str]:
        """Extract CVE identifiers from event data."""
        import re
        return re.findall(r"CVE-\d{4}-\d{4,}", data, re.IGNORECASE)

    def _build_rules(self) -> list[dict[str, Any]]:
        """Build the SARIF rules array from used rules."""
        rules = []
        for rule_id, info in sorted(self._rules_used.items()):
            rule: dict[str, Any] = {
                "id": rule_id,
                "name": info["name"],
                "shortDescription": {
                    "text": info["shortDescription"],
                },
                "fullDescription": {
                    "text": info["shortDescription"],
                },
                "defaultConfiguration": {
                    "level": info["level"],
                },
                "properties": {
                    "tags": info.get("tags", []),
                    "precision": "high",
                },
            }
            # Add help URI for vulnerability rules
            if "vulnerability" in info.get("tags", []):
                rule["helpUri"] = "https://www.first.org/cvss/"
            rules.append(rule)
        return rules

    def _build_artifacts(self) -> list[dict[str, Any]]:
        """Build the SARIF artifacts array."""
        artifacts = []
        for uri in sorted(self._artifacts, key=self._artifacts.get):  # type: ignore
            artifacts.append({
                "location": {"uri": uri},
                "roles": ["analysisTarget"],
            })
        return artifacts

    def export(self) -> dict[str, Any]:
        """Export as a SARIF v2.1.0 document."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "$schema": SARIF_SCHEMA,
            "version": SARIF_VERSION,
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "SpiderFoot",
                            "version": self.version,
                            "semanticVersion": self.version,
                            "informationUri": "https://github.com/smicallef/spiderfoot",
                            "rules": self._build_rules(),
                            "properties": {
                                "scanId": self.scan_id,
                                "scanName": self.scan_name,
                                "scanTarget": self.scan_target,
                            },
                        },
                    },
                    "results": self._results,
                    "artifacts": self._build_artifacts(),
                    "invocations": [
                        {
                            "executionSuccessful": True,
                            "startTimeUtc": now,
                            "endTimeUtc": now,
                            "properties": {
                                "scanId": self.scan_id,
                            },
                        }
                    ],
                    "automationDetails": {
                        "id": f"spiderfoot-scan/{self.scan_id}",
                        "guid": str(uuid.uuid5(
                            uuid.NAMESPACE_DNS,
                            f"spiderfoot.scan.{self.scan_id}"
                        )),
                    },
                    "columnKind": "utf16CodeUnits",
                }
            ],
        }

    def export_json(self, indent: int = 2) -> str:
        """Export as formatted JSON string."""
        return json.dumps(self.export(), indent=indent, default=str)

    @property
    def result_count(self) -> int:
        return len(self._results)

    @property
    def rule_count(self) -> int:
        return len(self._rules_used)

    def summary(self) -> dict[str, int]:
        """Return count of results by severity level."""
        counts: dict[str, int] = {"error": 0, "warning": 0, "note": 0}
        for r in self._results:
            level = r.get("level", "note")
            counts[level] = counts.get(level, 0) + 1
        return counts
