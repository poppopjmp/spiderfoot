"""STIX 2.1 export for SpiderFoot scan data.

Converts SpiderFoot events and findings into STIX 2.1 bundles
for integration with threat intelligence platforms.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

# STIX 2.1 specification constants
STIX_SPEC_VERSION = "2.1"
STIX_NAMESPACE = "spiderfoot"
STIX_IDENTITY_ID = "identity--" + str(uuid.uuid5(uuid.NAMESPACE_DNS, "spiderfoot.net"))


def _stix_id(sdo_type: str, *parts: str) -> str:
    """Generate a deterministic STIX ID from type and identifying parts."""
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
    return f"{sdo_type}--{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _stix_common(sdo_type: str, stix_id: str, created: str | None = None) -> dict[str, Any]:
    """Common STIX SDO properties."""
    ts = created or _now_iso()
    return {
        "type": sdo_type,
        "spec_version": STIX_SPEC_VERSION,
        "id": stix_id,
        "created": ts,
        "modified": ts,
        "created_by_ref": STIX_IDENTITY_ID,
    }


# ---------------------------------------------------------------------------
#  Event type → STIX SDO mapping
# ---------------------------------------------------------------------------

_EVENT_TYPE_MAP: dict[str, str] = {
    # Network observables
    "IP_ADDRESS": "ipv4-addr",
    "IPV6_ADDRESS": "ipv6-addr",
    "INTERNET_NAME": "domain-name",
    "DOMAIN_NAME": "domain-name",
    "LINKED_URL_INTERNAL": "url",
    "LINKED_URL_EXTERNAL": "url",
    "EMAILADDR": "email-addr",
    "NETBLOCK_OWNER": "autonomous-system",
    # Vulnerabilities
    "VULNERABILITY_CVE_CRITICAL": "vulnerability",
    "VULNERABILITY_CVE_HIGH": "vulnerability",
    "VULNERABILITY_CVE_MEDIUM": "vulnerability",
    "VULNERABILITY_CVE_LOW": "vulnerability",
    "VULNERABILITY_GENERAL": "vulnerability",
    # Malicious indicators
    "MALICIOUS_IPADDR": "indicator",
    "MALICIOUS_INTERNET_NAME": "indicator",
    "MALICIOUS_AFFILIATE_IPADDR": "indicator",
    "MALICIOUS_AFFILIATE_INTERNET_NAME": "indicator",
    "MALICIOUS_EMAILADDR": "indicator",
    # Infrastructure
    "TCP_PORT_OPEN": "infrastructure",
    "TCP_PORT_OPEN_BANNER": "infrastructure",
    "UDP_PORT_OPEN": "infrastructure",
    "WEBSERVER_BANNER": "infrastructure",
    "WEBSERVER_TECHNOLOGY": "software",
    "OPERATING_SYSTEM": "software",
    # Files
    "HASH": "file",
    "HASH_COMPROMISED": "file",
}

_SEVERITY_TLP: dict[str, str] = {
    "CRITICAL": "marking-definition--826578e1-40a3-4b46-a8d0-328e5e2e7d08",  # TLP:RED
    "HIGH": "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82",      # TLP:AMBER
    "MEDIUM": "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",    # TLP:GREEN
    "LOW": "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9",       # TLP:WHITE
}


class STIXExporter:
    """Convert SpiderFoot scan data to a STIX 2.1 Bundle."""

    def __init__(self, scan_id: str, scan_name: str, scan_target: str):
        self.scan_id = scan_id
        self.scan_name = scan_name
        self.scan_target = scan_target
        self._objects: list[dict[str, Any]] = []
        self._seen_ids: set[str] = set()
        self._identity = self._create_identity()
        self._add_object(self._identity)

    def _create_identity(self) -> dict[str, Any]:
        obj = _stix_common("identity", STIX_IDENTITY_ID)
        obj.update({
            "name": "SpiderFoot",
            "description": f"SpiderFoot OSINT scan: {self.scan_name}",
            "identity_class": "system",
            "sectors": ["technology"],
        })
        return obj

    def _add_object(self, obj: dict[str, Any]) -> None:
        if obj["id"] not in self._seen_ids:
            self._seen_ids.add(obj["id"])
            self._objects.append(obj)

    def _add_relationship(
        self, source_id: str, rel_type: str, target_id: str
    ) -> None:
        rel_id = _stix_id("relationship", source_id, rel_type, target_id)
        obj = _stix_common("relationship", rel_id)
        obj.update({
            "relationship_type": rel_type,
            "source_ref": source_id,
            "target_ref": target_id,
        })
        self._add_object(obj)

    # ----- Observable converters -----

    def _convert_ip(self, event_type: str, data: str) -> dict[str, Any] | None:
        sco_type = "ipv6-addr" if event_type == "IPV6_ADDRESS" else "ipv4-addr"
        stix_id = _stix_id(sco_type, data)
        obj = _stix_common(sco_type, stix_id)
        obj["value"] = data
        return obj

    def _convert_domain(self, data: str) -> dict[str, Any] | None:
        stix_id = _stix_id("domain-name", data)
        obj = _stix_common("domain-name", stix_id)
        obj["value"] = data
        return obj

    def _convert_url(self, data: str) -> dict[str, Any] | None:
        stix_id = _stix_id("url", data)
        obj = _stix_common("url", stix_id)
        obj["value"] = data
        return obj

    def _convert_email(self, data: str) -> dict[str, Any] | None:
        stix_id = _stix_id("email-addr", data)
        obj = _stix_common("email-addr", stix_id)
        obj["value"] = data
        return obj

    def _convert_vulnerability(self, event_type: str, data: str) -> dict[str, Any] | None:
        stix_id = _stix_id("vulnerability", data)
        obj = _stix_common("vulnerability", stix_id)
        # Extract CVE if present
        cve_match = None
        for token in data.split():
            if token.upper().startswith("CVE-"):
                cve_match = token.upper()
                break
        if cve_match:
            obj["name"] = cve_match
            obj["external_references"] = [{
                "source_name": "cve",
                "external_id": cve_match,
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_match}",
            }]
        else:
            obj["name"] = data[:120]
        obj["description"] = data
        # Map severity
        severity = event_type.split("_")[-1] if "CVE" in event_type else "MEDIUM"
        tlp = _SEVERITY_TLP.get(severity)
        if tlp:
            obj["object_marking_refs"] = [tlp]
        return obj

    def _convert_indicator(self, event_type: str, data: str) -> dict[str, Any] | None:
        stix_id = _stix_id("indicator", event_type, data)
        obj = _stix_common("indicator", stix_id)
        # Determine pattern type
        if "IPADDR" in event_type:
            obj["pattern"] = f"[ipv4-addr:value = '{data}']"
        elif "INTERNET_NAME" in event_type:
            obj["pattern"] = f"[domain-name:value = '{data}']"
        elif "EMAILADDR" in event_type:
            obj["pattern"] = f"[email-addr:value = '{data}']"
        else:
            obj["pattern"] = f"[domain-name:value = '{data}']"
        obj["pattern_type"] = "stix"
        obj["valid_from"] = _now_iso()
        obj["indicator_types"] = ["malicious-activity"]
        obj["name"] = f"Malicious: {data}"
        obj["description"] = f"Detected by SpiderFoot event {event_type}"
        return obj

    def _convert_port(self, data: str) -> dict[str, Any] | None:
        stix_id = _stix_id("infrastructure", "port", data)
        obj = _stix_common("infrastructure", stix_id)
        obj["name"] = f"Open port: {data}"
        obj["infrastructure_types"] = ["hosting"]
        return obj

    def _convert_software(self, data: str) -> dict[str, Any] | None:
        stix_id = _stix_id("software", data)
        obj = _stix_common("software", stix_id)
        obj["name"] = data
        return obj

    def _convert_hash(self, data: str) -> dict[str, Any] | None:
        stix_id = _stix_id("file", data)
        obj = _stix_common("file", stix_id)
        # Detect hash type by length
        hash_len = len(data.strip())
        if hash_len == 32:
            obj["hashes"] = {"MD5": data.strip()}
        elif hash_len == 40:
            obj["hashes"] = {"SHA-1": data.strip()}
        elif hash_len == 64:
            obj["hashes"] = {"SHA-256": data.strip()}
        else:
            obj["hashes"] = {"SHA-256": data.strip()}
        return obj

    # ----- Main convert method -----

    def add_event(self, event_type: str, data: str, module: str = "",
                  source_event: str = "") -> str | None:
        """Convert a SpiderFoot event into STIX object(s).

        Returns the STIX ID of the created object, or None if unmapped.
        """
        stix_type = _EVENT_TYPE_MAP.get(event_type)
        if not stix_type:
            return None

        obj = None
        if stix_type in ("ipv4-addr", "ipv6-addr"):
            obj = self._convert_ip(event_type, data)
        elif stix_type == "domain-name":
            obj = self._convert_domain(data)
        elif stix_type == "url":
            obj = self._convert_url(data)
        elif stix_type == "email-addr":
            obj = self._convert_email(data)
        elif stix_type == "vulnerability":
            obj = self._convert_vulnerability(event_type, data)
        elif stix_type == "indicator":
            obj = self._convert_indicator(event_type, data)
        elif stix_type == "infrastructure":
            obj = self._convert_port(data)
        elif stix_type == "software":
            obj = self._convert_software(data)
        elif stix_type == "file":
            obj = self._convert_hash(data)

        if obj is None:
            return None

        self._add_object(obj)

        # Add note with module attribution
        if module:
            note_id = _stix_id("note", obj["id"], module)
            note = _stix_common("note", note_id)
            note.update({
                "abstract": f"Discovered by {module}",
                "content": f"Event {event_type} discovered by module {module}",
                "object_refs": [obj["id"]],
            })
            self._add_object(note)

        return obj["id"]

    def export_bundle(self) -> dict[str, Any]:
        """Export all added events as a STIX 2.1 Bundle."""
        bundle_id = f"bundle--{uuid.uuid4()}"
        return {
            "type": "bundle",
            "id": bundle_id,
            "objects": list(self._objects),
        }

    def export_json(self, indent: int = 2) -> str:
        """Export as formatted JSON string."""
        return json.dumps(self.export_bundle(), indent=indent, default=str)

    @property
    def object_count(self) -> int:
        return len(self._objects)


# ---------------------------------------------------------------------------
#  TAXII 2.1-compatible collection helpers
# ---------------------------------------------------------------------------

class TAXIICollection:
    """Represents a TAXII 2.1 collection backed by scan data."""

    def __init__(self, collection_id: str, title: str, description: str = ""):
        self.id = collection_id
        self.title = title
        self.description = description or f"SpiderFoot collection: {title}"
        self.can_read = True
        self.can_write = False
        self.media_types = ["application/stix+json;version=2.1"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "can_read": self.can_read,
            "can_write": self.can_write,
            "media_types": self.media_types,
        }


class TAXIIServer:
    """Minimal TAXII 2.1 server metadata for SpiderFoot."""

    def __init__(self):
        self.title = "SpiderFoot TAXII Server"
        self.description = "STIX 2.1 threat intelligence from SpiderFoot OSINT scans"
        self.contact = "https://github.com/smicallef/spiderfoot"
        self._collections: dict[str, TAXIICollection] = {}
        self._bundles: dict[str, dict[str, Any]] = {}

    def discovery(self) -> dict[str, Any]:
        """TAXII discovery endpoint response."""
        return {
            "title": self.title,
            "description": self.description,
            "contact": self.contact,
            "default": "/taxii2/",
            "api_roots": ["/taxii2/"],
        }

    def api_root(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "versions": ["application/taxii+json;version=2.1"],
            "max_content_length": 10485760,
        }

    def add_collection(self, scan_id: str, scan_name: str, bundle: dict[str, Any]) -> str:
        """Register a scan as a TAXII collection."""
        col_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"spiderfoot.scan.{scan_id}"))
        collection = TAXIICollection(col_id, scan_name)
        self._collections[col_id] = collection
        self._bundles[col_id] = bundle
        return col_id

    def list_collections(self) -> dict[str, Any]:
        return {
            "collections": [c.to_dict() for c in self._collections.values()]
        }

    def get_collection(self, collection_id: str) -> dict[str, Any] | None:
        col = self._collections.get(collection_id)
        return col.to_dict() if col else None

    def get_objects(self, collection_id: str,
                    added_after: str | None = None,
                    match_type: str | None = None,
                    limit: int = 100) -> dict[str, Any] | None:
        """Get STIX objects from a collection with optional filtering."""
        bundle = self._bundles.get(collection_id)
        if bundle is None:
            return None

        objects = bundle.get("objects", [])

        # Filter by type
        if match_type:
            types = [t.strip() for t in match_type.split(",")]
            objects = [o for o in objects if o.get("type") in types]

        # Filter by added_after
        if added_after:
            objects = [o for o in objects if o.get("created", "") > added_after]

        # Apply limit
        objects = objects[:limit]

        return {
            "objects": objects,
            "more": len(bundle.get("objects", [])) > limit,
        }

    def get_object_by_id(self, collection_id: str, object_id: str) -> dict[str, Any] | None:
        bundle = self._bundles.get(collection_id)
        if bundle is None:
            return None
        for obj in bundle.get("objects", []):
            if obj.get("id") == object_id:
                return obj
        return None
