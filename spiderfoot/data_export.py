"""Data Export Formats for SpiderFoot.

Multi-format export system for scan results supporting JSON, CSV,
STIX-like bundles, and human-readable summaries. Extensible with
custom exporters via registry pattern.
"""

import csv
import io
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("spiderfoot.data_export")


@dataclass
class ExportEvent:
    """Normalized event for export."""
    event_type: str
    data: str
    module: str = ""
    source_event: Optional[str] = None
    risk: int = 0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "module": self.module,
            "source_event": self.source_event,
            "risk": self.risk,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ExportOptions:
    """Options controlling export behavior."""
    include_metadata: bool = True
    include_raw: bool = False
    min_risk: int = 0
    max_results: Optional[int] = None
    event_types: Optional[set[str]] = None
    modules: Optional[set[str]] = None
    pretty: bool = True
    timestamp_format: str = "iso"


class Exporter(ABC):
    """Base class for data exporters."""

    def __init__(self, name: str = "") -> None:
        self.name = name or self.__class__.__name__

    @abstractmethod
    def export(self, events: list[ExportEvent], options: ExportOptions) -> str:
        """Export events to string format."""
        ...

    @property
    @abstractmethod
    def format_name(self) -> str:
        ...

    @property
    @abstractmethod
    def file_extension(self) -> str:
        ...

    @property
    @abstractmethod
    def content_type(self) -> str:
        ...

    def _filter_events(self, events: list[ExportEvent], options: ExportOptions) -> list[ExportEvent]:
        """Apply common filters to events."""
        filtered = events

        if options.min_risk > 0:
            filtered = [e for e in filtered if e.risk >= options.min_risk]

        if options.event_types:
            filtered = [e for e in filtered if e.event_type in options.event_types]

        if options.modules:
            filtered = [e for e in filtered if e.module in options.modules]

        if not options.include_raw:
            filtered = [e for e in filtered if not e.event_type.startswith("RAW_")]

        if options.max_results:
            filtered = filtered[:options.max_results]

        return filtered


class JsonExporter(Exporter):
    """Export events as JSON."""

    def __init__(self) -> None:
        super().__init__("json")

    @property
    def format_name(self) -> str:
        return "JSON"

    @property
    def file_extension(self) -> str:
        return ".json"

    @property
    def content_type(self) -> str:
        return "application/json"

    def export(self, events: list[ExportEvent], options: ExportOptions) -> str:
        filtered = self._filter_events(events, options)
        data = {
            "export_timestamp": time.time(),
            "event_count": len(filtered),
            "events": [e.to_dict() for e in filtered],
        }

        if not options.include_metadata:
            for ev in data["events"]:
                ev.pop("metadata", None)

        indent = 2 if options.pretty else None
        return json.dumps(data, indent=indent, default=str)


class CsvExporter(Exporter):
    """Export events as CSV."""

    def __init__(self) -> None:
        super().__init__("csv")

    @property
    def format_name(self) -> str:
        return "CSV"

    @property
    def file_extension(self) -> str:
        return ".csv"

    @property
    def content_type(self) -> str:
        return "text/csv"

    def export(self, events: list[ExportEvent], options: ExportOptions) -> str:
        filtered = self._filter_events(events, options)
        output = io.StringIO()
        writer = csv.writer(output)

        headers = ["event_type", "data", "module", "risk", "timestamp"]
        if options.include_metadata:
            headers.append("metadata")
        writer.writerow(headers)

        for e in filtered:
            row = [e.event_type, e.data, e.module, e.risk, e.timestamp]
            if options.include_metadata:
                row.append(json.dumps(e.metadata))
            writer.writerow(row)

        return output.getvalue()


class StixExporter(Exporter):
    """Export events in a STIX-like bundle format."""

    def __init__(self) -> None:
        super().__init__("stix")

    @property
    def format_name(self) -> str:
        return "STIX"

    @property
    def file_extension(self) -> str:
        return ".json"

    @property
    def content_type(self) -> str:
        return "application/json"

    _TYPE_MAP = {
        "IP_ADDRESS": "ipv4-addr",
        "IPV6_ADDRESS": "ipv6-addr",
        "DOMAIN_NAME": "domain-name",
        "EMAILADDR": "email-addr",
        "URL_FORM": "url",
        "HASH": "file",
    }

    def _event_to_sco(self, event: ExportEvent) -> dict:
        """Convert an event to a STIX Cyber Observable."""
        sco_type = self._TYPE_MAP.get(event.event_type, "x-spiderfoot-event")
        sco = {
            "type": sco_type,
            "id": f"{sco_type}--{hash(event.data) & 0xFFFFFFFF:08x}",
            "value": event.data,
        }
        if sco_type == "x-spiderfoot-event":
            sco["x_event_type"] = event.event_type
        if event.module:
            sco["x_source_module"] = event.module
        return sco

    def export(self, events: list[ExportEvent], options: ExportOptions) -> str:
        filtered = self._filter_events(events, options)
        bundle = {
            "type": "bundle",
            "id": f"bundle--spiderfoot-{int(time.time())}",
            "objects": [self._event_to_sco(e) for e in filtered],
        }
        indent = 2 if options.pretty else None
        return json.dumps(bundle, indent=indent, default=str)


class SummaryExporter(Exporter):
    """Export a human-readable summary."""

    def __init__(self) -> None:
        super().__init__("summary")

    @property
    def format_name(self) -> str:
        return "Summary"

    @property
    def file_extension(self) -> str:
        return ".txt"

    @property
    def content_type(self) -> str:
        return "text/plain"

    def export(self, events: list[ExportEvent], options: ExportOptions) -> str:
        filtered = self._filter_events(events, options)

        # Aggregate stats
        type_counts: dict[str, int] = {}
        module_counts: dict[str, int] = {}
        max_risk = 0
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

        for e in filtered:
            type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1
            if e.module:
                module_counts[e.module] = module_counts.get(e.module, 0) + 1
            max_risk = max(max_risk, e.risk)

            if e.risk >= 90:
                risk_counts["critical"] += 1
            elif e.risk >= 70:
                risk_counts["high"] += 1
            elif e.risk >= 40:
                risk_counts["medium"] += 1
            elif e.risk >= 10:
                risk_counts["low"] += 1
            else:
                risk_counts["info"] += 1

        lines = [
            "=" * 60,
            "SpiderFoot Scan Summary",
            "=" * 60,
            f"Total Events: {len(filtered)}",
            f"Event Types: {len(type_counts)}",
            f"Modules Used: {len(module_counts)}",
            f"Max Risk Score: {max_risk}",
            "",
            "Risk Distribution:",
        ]
        for level, count in risk_counts.items():
            if count > 0:
                lines.append(f"  {level.upper()}: {count}")

        lines.extend(["", "Top Event Types:"])
        for et, count in sorted(type_counts.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"  {et}: {count}")

        if module_counts:
            lines.extend(["", "Top Modules:"])
            for mod, count in sorted(module_counts.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"  {mod}: {count}")

        lines.append("=" * 60)
        return "\n".join(lines)


class ExportRegistry:
    """Registry of available exporters.

    Usage:
        registry = ExportRegistry()
        registry.register(JsonExporter())
        result = registry.export("json", events, options)
    """

    def __init__(self) -> None:
        self._exporters: dict[str, Exporter] = {}
        # Register built-in exporters
        for exporter in [JsonExporter(), CsvExporter(), StixExporter(), SummaryExporter()]:
            self._exporters[exporter.name] = exporter

    def register(self, exporter: Exporter) -> None:
        self._exporters[exporter.name] = exporter

    def unregister(self, name: str) -> bool:
        return self._exporters.pop(name, None) is not None

    def get(self, name: str) -> Optional[Exporter]:
        return self._exporters.get(name)

    def export(self, format_name: str, events: list[ExportEvent], options: Optional[ExportOptions] = None) -> str:
        exporter = self._exporters.get(format_name)
        if exporter is None:
            raise ValueError(f"Unknown export format: {format_name}")
        return exporter.export(events, options or ExportOptions())

    @property
    def available_formats(self) -> list[str]:
        return sorted(self._exporters.keys())

    def to_dict(self) -> dict:
        return {
            "formats": {
                name: {
                    "format_name": e.format_name,
                    "extension": e.file_extension,
                    "content_type": e.content_type,
                }
                for name, e in self._exporters.items()
            }
        }
