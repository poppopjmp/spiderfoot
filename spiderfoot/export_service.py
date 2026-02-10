#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         export_service
# Purpose:      Multi-format scan result export service for SpiderFoot.
#               Provides streaming exports in JSON, CSV, STIX 2.1, and
#               SARIF formats via DataService.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Export Service

Exports scan results in multiple formats:

    - **JSON**: Full scan data with metadata
    - **CSV**: Tabular event data
    - **STIX 2.1**: Cyber threat intelligence format
    - **SARIF**: Static Analysis Results Interchange Format

Usage::

    from spiderfoot.export_service import ExportService, ExportFormat
    exporter = ExportService()
    data = exporter.export_scan("scan-id", ExportFormat.JSON)
    exporter.export_to_file("scan-id", ExportFormat.CSV, "/tmp/results.csv")
"""

import csv
import io
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generator, IO, List, Optional

log = logging.getLogger("spiderfoot.export_service")


class ExportFormat(Enum):
    """Supported export formats."""
    JSON = "json"
    CSV = "csv"
    STIX = "stix"
    SARIF = "sarif"


@dataclass
class ExportConfig:
    """Export configuration."""
    include_raw_data: bool = True
    include_correlations: bool = True
    max_events: int = 0       # 0 = unlimited
    event_types: List[str] = field(default_factory=list)  # empty = all
    pretty_print: bool = True

    @classmethod
    def from_config(cls, opts: dict) -> "ExportConfig":
        return cls(
            include_raw_data=opts.get("_export_raw_data", True),
            include_correlations=opts.get("_export_correlations", True),
            max_events=int(opts.get("_export_max_events", 0)),
            pretty_print=opts.get("_export_pretty", True),
        )


class ExportService:
    """Multi-format scan result exporter."""

    def __init__(self, config: Optional[ExportConfig] = None):
        self.config = config or ExportConfig()

    def export_scan(self, scan_id: str,
                    fmt: ExportFormat,
                    dbh=None) -> str:
        """Export scan results as a string.

        Args:
            scan_id: Scan ID to export.
            fmt: Output format.
            dbh: Database handle (auto-resolved if not provided).

        Returns:
            Formatted string of scan results.
        """
        events = self._get_events(scan_id, dbh)
        scan_info = self._get_scan_info(scan_id, dbh)

        formatters = {
            ExportFormat.JSON: self._to_json,
            ExportFormat.CSV: self._to_csv,
            ExportFormat.STIX: self._to_stix,
            ExportFormat.SARIF: self._to_sarif,
        }

        formatter = formatters.get(fmt)
        if formatter is None:
            raise ValueError(f"Unsupported format: {fmt}")

        return formatter(scan_info, events)

    def export_to_file(self, scan_id: str,
                       fmt: ExportFormat,
                       filepath: str,
                       dbh=None) -> str:
        """Export scan results to a file.

        Returns the filepath written.
        """
        content = self.export_scan(scan_id, fmt, dbh)

        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        log.info("Exported scan %s to %s (%s)", scan_id, filepath, fmt.value)
        return filepath

    def export_to_stream(self, scan_id: str,
                         fmt: ExportFormat,
                         stream: IO,
                         dbh=None) -> None:
        """Export scan results to a stream/file-like object."""
        content = self.export_scan(scan_id, fmt, dbh)
        stream.write(content)

    # ------------------------------------------------------------------
    # Format implementations
    # ------------------------------------------------------------------

    def _to_json(self, scan_info: dict,
                 events: List[dict]) -> str:
        """Export as JSON."""
        output = {
            "meta": {
                "format": "spiderfoot-json",
                "version": "1.0",
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                             time.gmtime()),
            },
            "scan": scan_info,
            "events": events,
            "event_count": len(events),
        }

        indent = 2 if self.config.pretty_print else None
        return json.dumps(output, indent=indent, default=str)

    def _to_csv(self, scan_info: dict,
                events: List[dict]) -> str:
        """Export as CSV."""
        output = io.StringIO()
        columns = [
            "type", "data", "module", "source_event",
            "confidence", "visibility", "risk", "hash",
        ]

        writer = csv.DictWriter(
            output, fieldnames=columns,
            extrasaction="ignore",
        )
        writer.writeheader()

        for event in events:
            row = {col: event.get(col, "") for col in columns}
            # Truncate long data for CSV
            if isinstance(row.get("data"), str) and len(row["data"]) > 1000:
                row["data"] = row["data"][:997] + "..."
            writer.writerow(row)

        return output.getvalue()

    def _to_stix(self, scan_info: dict,
                 events: List[dict]) -> str:
        """Export as STIX 2.1 bundle.

        Maps SpiderFoot event types to STIX Cyber Observable objects.
        """
        stix_objects = []

        # Identity for the tool
        identity = {
            "type": "identity",
            "spec_version": "2.1",
            "id": f"identity--{uuid.uuid5(uuid.NAMESPACE_URL, 'spiderfoot')}",
            "name": "SpiderFoot",
            "identity_class": "system",
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "modified": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        stix_objects.append(identity)

        # Map events to STIX objects
        type_mapping = {
            "IP_ADDRESS": "ipv4-addr",
            "IPV6_ADDRESS": "ipv6-addr",
            "DOMAIN_NAME": "domain-name",
            "DOMAIN_NAME_PARENT": "domain-name",
            "INTERNET_NAME": "domain-name",
            "EMAILADDR": "email-addr",
            "URL_STATIC": "url",
            "URL_DYNAMIC": "url",
            "VULNERABILITY_CVE_CRITICAL": "vulnerability",
            "VULNERABILITY_CVE_HIGH": "vulnerability",
            "VULNERABILITY_CVE_MEDIUM": "vulnerability",
            "VULNERABILITY_CVE_LOW": "vulnerability",
        }

        for event in events:
            event_type = event.get("type", "")
            data = event.get("data", "")
            stix_type = type_mapping.get(event_type)

            if stix_type is None:
                # Generic observed-data for unmapped types
                obj = {
                    "type": "observed-data",
                    "spec_version": "2.1",
                    "id": f"observed-data--{uuid.uuid4()}",
                    "created": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "modified": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "first_observed": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "last_observed": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "number_observed": 1,
                    "created_by_ref": identity["id"],
                    "object_refs": [],
                }
                stix_objects.append(obj)
                continue

            if stix_type in ("ipv4-addr", "ipv6-addr"):
                obj = {
                    "type": stix_type,
                    "spec_version": "2.1",
                    "id": f"{stix_type}--{uuid.uuid4()}",
                    "value": data,
                }
            elif stix_type == "domain-name":
                obj = {
                    "type": "domain-name",
                    "spec_version": "2.1",
                    "id": f"domain-name--{uuid.uuid4()}",
                    "value": data,
                }
            elif stix_type == "email-addr":
                obj = {
                    "type": "email-addr",
                    "spec_version": "2.1",
                    "id": f"email-addr--{uuid.uuid4()}",
                    "value": data,
                }
            elif stix_type == "url":
                obj = {
                    "type": "url",
                    "spec_version": "2.1",
                    "id": f"url--{uuid.uuid4()}",
                    "value": data,
                }
            elif stix_type == "vulnerability":
                obj = {
                    "type": "vulnerability",
                    "spec_version": "2.1",
                    "id": f"vulnerability--{uuid.uuid4()}",
                    "name": data,
                    "created": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "modified": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            else:
                continue

            stix_objects.append(obj)

        bundle = {
            "type": "bundle",
            "id": f"bundle--{uuid.uuid4()}",
            "objects": stix_objects,
        }

        indent = 2 if self.config.pretty_print else None
        return json.dumps(bundle, indent=indent, default=str)

    def _to_sarif(self, scan_info: dict,
                  events: List[dict]) -> str:
        """Export as SARIF 2.1.0.

        Maps vulnerability and security findings to SARIF results.
        """
        results = []

        vuln_types = {
            "VULNERABILITY_CVE_CRITICAL": "error",
            "VULNERABILITY_CVE_HIGH": "error",
            "VULNERABILITY_CVE_MEDIUM": "warning",
            "VULNERABILITY_CVE_LOW": "note",
            "BLACKLISTED_IPADDR": "warning",
            "BLACKLISTED_AFFILIATE_IPADDR": "warning",
            "MALICIOUS_IPADDR": "error",
        }

        for event in events:
            event_type = event.get("type", "")
            level = vuln_types.get(event_type)
            if level is None:
                continue

            results.append({
                "ruleId": event_type,
                "level": level,
                "message": {
                    "text": event.get("data", ""),
                },
                "properties": {
                    "module": event.get("module", ""),
                    "source": event.get("source_event", ""),
                },
            })

        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/"
                       "sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "SpiderFoot",
                        "version": scan_info.get("version", "5.10+"),
                        "informationUri": "https://github.com/poppopjmp/spiderfoot",
                    }
                },
                "results": results,
            }],
        }

        indent = 2 if self.config.pretty_print else None
        return json.dumps(sarif, indent=indent, default=str)

    # ------------------------------------------------------------------
    # Data retrieval
    # ------------------------------------------------------------------

    def _get_events(self, scan_id: str,
                    dbh=None) -> List[dict]:
        """Get events for a scan via DataService or dbh."""
        events = []

        # Try DataService first
        try:
            from spiderfoot.service_registry import ServiceRegistry
            registry = ServiceRegistry.get_instance()
            data_svc = registry.get_optional("data")
            if data_svc and hasattr(data_svc, "event_get_all"):
                raw = data_svc.event_get_all(scan_id)
                if raw:
                    return self._normalize_events(raw)
        except Exception as e:
            log.debug("optional data service lookup failed: %s", e)

        # Fallback to dbh
        if dbh:
            try:
                raw = dbh.scanResultEvent(scan_id)
                if raw:
                    return self._normalize_events(raw)
            except Exception as e:
                log.error("Failed to get events via dbh: %s", e)

        return events

    def _get_scan_info(self, scan_id: str,
                       dbh=None) -> dict:
        """Get scan metadata."""
        try:
            from spiderfoot.service_registry import ServiceRegistry
            registry = ServiceRegistry.get_instance()
            data_svc = registry.get_optional("data")
            if data_svc and hasattr(data_svc, "scan_get"):
                info = data_svc.scan_get(scan_id)
                if info:
                    return info
        except Exception as e:
            log.debug("optional data service lookup failed: %s", e)

        return {"scan_id": scan_id}

    def _normalize_events(self, raw_events) -> List[dict]:
        """Normalize raw event data to dicts."""
        events = []

        for event in raw_events:
            if isinstance(event, dict):
                events.append(event)
            elif isinstance(event, (list, tuple)):
                # DB row format
                events.append({
                    "hash": event[0] if len(event) > 0 else "",
                    "type": event[1] if len(event) > 1 else "",
                    "data": event[2] if len(event) > 2 else "",
                    "module": event[3] if len(event) > 3 else "",
                    "source_event": event[4] if len(event) > 4 else "",
                    "confidence": event[5] if len(event) > 5 else 100,
                    "visibility": event[6] if len(event) > 6 else 100,
                    "risk": event[7] if len(event) > 7 else 0,
                })
            else:
                events.append({"data": str(event)})

        # Apply filters
        if self.config.event_types:
            events = [
                e for e in events
                if e.get("type") in self.config.event_types
            ]

        if self.config.max_events > 0:
            events = events[:self.config.max_events]

        return events
