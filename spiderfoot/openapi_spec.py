#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         openapi_spec
# Purpose:      Auto-generate OpenAPI 3.1 specification for the
#               SpiderFoot REST API from endpoint metadata.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot OpenAPI Specification Generator

Generates a complete OpenAPI 3.1 spec from registered API endpoints::

    from spiderfoot.openapi_spec import OpenAPIGenerator

    generator = OpenAPIGenerator()
    spec = generator.generate()

    # Write to file
    generator.write_yaml("openapi.yaml")
    generator.write_json("openapi.json")
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger("spiderfoot.openapi_spec")


def _read_version() -> str:
    """Read SpiderFoot version."""
    try:
        version_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "VERSION")
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return "5.17.1"


class OpenAPIGenerator:
    """Generates OpenAPI 3.1 specification for the SpiderFoot API."""

    def __init__(self, *, title: str = "SpiderFoot API",
                 version: Optional[str] = None,
                 description: str = ""):
        self.title = title
        self.version = version or _read_version()
        self.description = description or (
            "SpiderFoot OSINT automation API. "
            "Provides endpoints for scan management, data retrieval, "
            "module configuration, correlation analysis, and system "
            "administration."
        )

    def generate(self) -> dict:
        """Generate the complete OpenAPI 3.1 specification."""
        spec = {
            "openapi": "3.1.0",
            "info": self._info(),
            "servers": self._servers(),
            "tags": self._tags(),
            "paths": self._paths(),
            "components": self._components(),
        }
        return spec

    def write_json(self, filepath: str) -> bool:
        """Write spec to a JSON file."""
        try:
            spec = self.generate()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(spec, f, indent=2)
            log.info("Wrote OpenAPI spec to %s", filepath)
            return True
        except Exception as e:
            log.error("Failed to write spec: %s", e)
            return False

    def write_yaml(self, filepath: str) -> bool:
        """Write spec to a YAML file."""
        try:
            import yaml
        except ImportError:
            log.error("PyYAML not installed; use write_json instead")
            return False

        try:
            spec = self.generate()
            with open(filepath, "w", encoding="utf-8") as f:
                yaml.dump(spec, f, default_flow_style=False,
                         sort_keys=False, allow_unicode=True)
            log.info("Wrote OpenAPI spec to %s", filepath)
            return True
        except Exception as e:
            log.error("Failed to write spec: %s", e)
            return False

    # ------------------------------------------------------------------
    # Spec sections
    # ------------------------------------------------------------------

    def _info(self) -> dict:
        return {
            "title": self.title,
            "version": self.version,
            "description": self.description,
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
            },
            "contact": {
                "name": "SpiderFoot Team",
                "url": "https://github.com/smicallef/spiderfoot",
            },
        }

    def _servers(self) -> list:
        return [
            {
                "url": "http://localhost:8001",
                "description": "Local development API",
            },
            {
                "url": "http://localhost:5001",
                "description": "Local development WebUI",
            },
        ]

    def _tags(self) -> list:
        return [
            {"name": "Scans", "description": "Scan lifecycle management"},
            {"name": "Workspaces", "description": "Workspace management"},
            {"name": "Data", "description": "Entity types, modules, and data sources"},
            {"name": "Configuration", "description": "System and module configuration"},
            {"name": "Correlations", "description": "Correlation rule management"},
            {"name": "Visualization", "description": "Scan visualization endpoints"},
            {"name": "Gateway", "description": "API gateway for microservices"},
            {"name": "System", "description": "Health, metrics, and system status"},
        ]

    def _paths(self) -> dict:
        paths = {}
        paths.update(self._scan_paths())
        paths.update(self._workspace_paths())
        paths.update(self._data_paths())
        paths.update(self._config_paths())
        paths.update(self._correlation_paths())
        paths.update(self._visualization_paths())
        paths.update(self._gateway_paths())
        paths.update(self._system_paths())
        return paths

    # ------------------------------------------------------------------
    # Scan endpoints
    # ------------------------------------------------------------------

    def _scan_paths(self) -> dict:
        return {
            "/api/scans": {
                "get": {
                    "tags": ["Scans"],
                    "summary": "List all scans",
                    "operationId": "listScans",
                    "responses": {
                        "200": {
                            "description": "List of scans",
                            "content": {"application/json": {
                                "schema": {"type": "array", "items": {"$ref": "#/components/schemas/ScanSummary"}},
                            }},
                        },
                    },
                },
                "post": {
                    "tags": ["Scans"],
                    "summary": "Create and start a new scan",
                    "operationId": "createScan",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/ScanRequest"},
                        }},
                    },
                    "responses": {
                        "201": {"description": "Scan created", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ScanSummary"}}}},
                        "400": {"description": "Invalid request"},
                    },
                },
            },
            "/api/scans/{scan_id}": {
                "get": {
                    "tags": ["Scans"],
                    "summary": "Get scan details",
                    "operationId": "getScan",
                    "parameters": [{"$ref": "#/components/parameters/ScanId"}],
                    "responses": {
                        "200": {"description": "Scan details", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ScanDetail"}}}},
                        "404": {"description": "Scan not found"},
                    },
                },
                "delete": {
                    "tags": ["Scans"],
                    "summary": "Delete scan results",
                    "operationId": "deleteScan",
                    "parameters": [{"$ref": "#/components/parameters/ScanId"}],
                    "responses": {
                        "204": {"description": "Scan deleted"},
                        "404": {"description": "Scan not found"},
                    },
                },
            },
            "/api/scans/{scan_id}/stop": {
                "post": {
                    "tags": ["Scans"],
                    "summary": "Stop a running scan",
                    "operationId": "stopScan",
                    "parameters": [{"$ref": "#/components/parameters/ScanId"}],
                    "responses": {
                        "200": {"description": "Scan stopped"},
                        "404": {"description": "Scan not found"},
                    },
                },
            },
            "/api/scans/{scan_id}/rerun": {
                "post": {
                    "tags": ["Scans"],
                    "summary": "Re-run a scan",
                    "operationId": "rerunScan",
                    "parameters": [{"$ref": "#/components/parameters/ScanId"}],
                    "responses": {
                        "201": {"description": "Scan re-started"},
                    },
                },
            },
            "/api/scans/{scan_id}/clone": {
                "post": {
                    "tags": ["Scans"],
                    "summary": "Clone a scan",
                    "operationId": "cloneScan",
                    "parameters": [{"$ref": "#/components/parameters/ScanId"}],
                    "responses": {
                        "201": {"description": "Scan cloned"},
                    },
                },
            },
            "/api/scans/{scan_id}/events/export": {
                "get": {
                    "tags": ["Scans"],
                    "summary": "Export scan event results",
                    "operationId": "exportScanEvents",
                    "parameters": [
                        {"$ref": "#/components/parameters/ScanId"},
                        {"name": "type", "in": "query", "schema": {"type": "string"}, "description": "Event type filter"},
                    ],
                    "responses": {
                        "200": {"description": "Exported events", "content": {"text/csv": {}, "application/json": {}}},
                    },
                },
            },
            "/api/scans/{scan_id}/logs/export": {
                "get": {
                    "tags": ["Scans"],
                    "summary": "Export scan logs",
                    "operationId": "exportScanLogs",
                    "parameters": [{"$ref": "#/components/parameters/ScanId"}],
                    "responses": {"200": {"description": "Scan logs"}},
                },
            },
            "/api/scans/{scan_id}/metadata": {
                "get": {
                    "tags": ["Scans"],
                    "summary": "Get scan metadata",
                    "operationId": "getScanMetadata",
                    "parameters": [{"$ref": "#/components/parameters/ScanId"}],
                    "responses": {"200": {"description": "Scan metadata"}},
                },
                "patch": {
                    "tags": ["Scans"],
                    "summary": "Update scan metadata",
                    "operationId": "updateScanMetadata",
                    "parameters": [{"$ref": "#/components/parameters/ScanId"}],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "Metadata updated"}},
                },
            },
        }

    # ------------------------------------------------------------------
    # Workspace endpoints
    # ------------------------------------------------------------------

    def _workspace_paths(self) -> dict:
        return {
            "/api/workspaces": {
                "get": {
                    "tags": ["Workspaces"],
                    "summary": "List all workspaces",
                    "operationId": "listWorkspaces",
                    "responses": {"200": {"description": "List of workspaces", "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/Workspace"}}}}}},
                },
                "post": {
                    "tags": ["Workspaces"],
                    "summary": "Create a workspace",
                    "operationId": "createWorkspace",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WorkspaceRequest"}}}},
                    "responses": {"201": {"description": "Workspace created"}},
                },
            },
            "/api/workspaces/{workspace_id}": {
                "get": {
                    "tags": ["Workspaces"],
                    "summary": "Get workspace details",
                    "operationId": "getWorkspace",
                    "parameters": [{"$ref": "#/components/parameters/WorkspaceId"}],
                    "responses": {"200": {"description": "Workspace details"}},
                },
                "put": {
                    "tags": ["Workspaces"],
                    "summary": "Update workspace",
                    "operationId": "updateWorkspace",
                    "parameters": [{"$ref": "#/components/parameters/WorkspaceId"}],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WorkspaceRequest"}}}},
                    "responses": {"200": {"description": "Workspace updated"}},
                },
                "delete": {
                    "tags": ["Workspaces"],
                    "summary": "Delete workspace",
                    "operationId": "deleteWorkspace",
                    "parameters": [{"$ref": "#/components/parameters/WorkspaceId"}],
                    "responses": {"204": {"description": "Workspace deleted"}},
                },
            },
        }

    # ------------------------------------------------------------------
    # Data endpoints
    # ------------------------------------------------------------------

    def _data_paths(self) -> dict:
        return {
            "/api/data/entity-types": {
                "get": {
                    "tags": ["Data"],
                    "summary": "List all entity/event types",
                    "operationId": "listEntityTypes",
                    "responses": {"200": {"description": "Event type list"}},
                },
            },
            "/api/data/modules": {
                "get": {
                    "tags": ["Data"],
                    "summary": "List all modules",
                    "operationId": "listModules",
                    "responses": {"200": {"description": "Module list", "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/ModuleInfo"}}}}}},
                },
            },
            "/api/data/modules/{module_name}": {
                "get": {
                    "tags": ["Data"],
                    "summary": "Get module details",
                    "operationId": "getModule",
                    "parameters": [{"name": "module_name", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Module details"}},
                },
            },
        }

    # ------------------------------------------------------------------
    # Configuration endpoints
    # ------------------------------------------------------------------

    def _config_paths(self) -> dict:
        return {
            "/api/config": {
                "get": {
                    "tags": ["Configuration"],
                    "summary": "Get current configuration",
                    "operationId": "getConfig",
                    "responses": {"200": {"description": "Configuration object"}},
                },
                "patch": {
                    "tags": ["Configuration"],
                    "summary": "Partially update configuration",
                    "operationId": "patchConfig",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "Configuration updated"}},
                },
            },
            "/api/config/reload": {
                "post": {
                    "tags": ["Configuration"],
                    "summary": "Reload configuration from disk",
                    "operationId": "reloadConfig",
                    "responses": {"200": {"description": "Configuration reloaded"}},
                },
            },
            "/api/config/validate": {
                "post": {
                    "tags": ["Configuration"],
                    "summary": "Validate configuration",
                    "operationId": "validateConfig",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "Validation result"}},
                },
            },
        }

    # ------------------------------------------------------------------
    # Correlation endpoints
    # ------------------------------------------------------------------

    def _correlation_paths(self) -> dict:
        return {
            "/api/correlation-rules": {
                "get": {
                    "tags": ["Correlations"],
                    "summary": "List correlation rules",
                    "operationId": "listCorrelationRules",
                    "responses": {"200": {"description": "Correlation rules"}},
                },
                "post": {
                    "tags": ["Correlations"],
                    "summary": "Create a correlation rule",
                    "operationId": "createCorrelationRule",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"201": {"description": "Rule created"}},
                },
            },
            "/api/correlation-rules/{rule_id}": {
                "get": {
                    "tags": ["Correlations"],
                    "summary": "Get correlation rule",
                    "operationId": "getCorrelationRule",
                    "parameters": [{"name": "rule_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Rule details"}},
                },
                "put": {
                    "tags": ["Correlations"],
                    "summary": "Update correlation rule",
                    "operationId": "updateCorrelationRule",
                    "parameters": [{"name": "rule_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "Rule updated"}},
                },
                "delete": {
                    "tags": ["Correlations"],
                    "summary": "Delete correlation rule",
                    "operationId": "deleteCorrelationRule",
                    "parameters": [{"name": "rule_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"204": {"description": "Rule deleted"}},
                },
            },
            "/api/correlations/analyze": {
                "post": {
                    "tags": ["Correlations"],
                    "summary": "Run correlation analysis",
                    "operationId": "runCorrelationAnalysis",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {"scan_id": {"type": "string"}}}}}},
                    "responses": {"200": {"description": "Analysis results"}},
                },
            },
        }

    # ------------------------------------------------------------------
    # Visualization endpoints
    # ------------------------------------------------------------------

    def _visualization_paths(self) -> dict:
        return {
            "/api/visualization/graph/{scan_id}": {
                "get": {
                    "tags": ["Visualization"],
                    "summary": "Get scan relationship graph",
                    "operationId": "getScanGraph",
                    "parameters": [{"$ref": "#/components/parameters/ScanId"}],
                    "responses": {"200": {"description": "Graph data"}},
                },
            },
            "/api/visualization/timeline/{scan_id}": {
                "get": {
                    "tags": ["Visualization"],
                    "summary": "Get scan event timeline",
                    "operationId": "getScanTimeline",
                    "parameters": [{"$ref": "#/components/parameters/ScanId"}],
                    "responses": {"200": {"description": "Timeline data"}},
                },
            },
        }

    # ------------------------------------------------------------------
    # Gateway endpoints
    # ------------------------------------------------------------------

    def _gateway_paths(self) -> dict:
        return {
            "/gateway/route/{service}/{method}": {
                "post": {
                    "tags": ["Gateway"],
                    "summary": "Route request to backend service",
                    "operationId": "gatewayRoute",
                    "parameters": [
                        {"name": "service", "in": "path", "required": True, "schema": {"type": "string", "enum": ["scanner", "data", "config"]}},
                        {"name": "method", "in": "path", "required": True, "schema": {"type": "string"}},
                    ],
                    "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "Service response"}, "502": {"description": "Service unavailable"}},
                },
            },
            "/gateway/status": {
                "get": {
                    "tags": ["Gateway"],
                    "summary": "Get system status",
                    "operationId": "gatewayStatus",
                    "responses": {"200": {"description": "System status"}},
                },
            },
        }

    # ------------------------------------------------------------------
    # System endpoints
    # ------------------------------------------------------------------

    def _system_paths(self) -> dict:
        return {
            "/health": {
                "get": {
                    "tags": ["System"],
                    "summary": "Liveness health check",
                    "operationId": "healthCheck",
                    "responses": {"200": {"description": "Healthy", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HealthStatus"}}}}},
                },
            },
            "/health/ready": {
                "get": {
                    "tags": ["System"],
                    "summary": "Readiness health check",
                    "operationId": "readinessCheck",
                    "responses": {"200": {"description": "Ready"}, "503": {"description": "Not ready"}},
                },
            },
            "/metrics": {
                "get": {
                    "tags": ["System"],
                    "summary": "Prometheus metrics",
                    "operationId": "getMetrics",
                    "responses": {"200": {"description": "Prometheus metrics", "content": {"text/plain": {}}}},
                },
            },
        }

    # ------------------------------------------------------------------
    # Components (schemas, parameters, security)
    # ------------------------------------------------------------------

    def _components(self) -> dict:
        return {
            "schemas": self._schemas(),
            "parameters": self._parameters(),
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                },
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                },
                "BasicAuth": {
                    "type": "http",
                    "scheme": "basic",
                },
            },
        }

    def _parameters(self) -> dict:
        return {
            "ScanId": {
                "name": "scan_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": "Unique scan identifier",
            },
            "WorkspaceId": {
                "name": "workspace_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": "Unique workspace identifier",
            },
        }

    def _schemas(self) -> dict:
        return {
            "ScanRequest": {
                "type": "object",
                "required": ["scanname", "scantarget"],
                "properties": {
                    "scanname": {"type": "string", "description": "Name for the scan"},
                    "scantarget": {"type": "string", "description": "Target to scan (domain, IP, etc.)"},
                    "modulelist": {"type": "array", "items": {"type": "string"}, "description": "Specific modules to use"},
                    "typelist": {"type": "array", "items": {"type": "string"}, "description": "Event types to collect"},
                    "usecase": {"type": "string", "enum": ["Footprint", "Investigate", "Passive"], "description": "Scan use case"},
                },
            },
            "ScanSummary": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "target": {"type": "string"},
                    "status": {"type": "string", "enum": ["CREATED", "RUNNING", "FINISHED", "ABORTED", "ERROR"]},
                    "started": {"type": "string", "format": "date-time"},
                    "ended": {"type": "string", "format": "date-time"},
                    "total_events": {"type": "integer"},
                },
            },
            "ScanDetail": {
                "allOf": [
                    {"$ref": "#/components/schemas/ScanSummary"},
                    {
                        "type": "object",
                        "properties": {
                            "modules": {"type": "array", "items": {"type": "string"}},
                            "config": {"type": "object"},
                            "events": {"type": "array", "items": {"$ref": "#/components/schemas/ScanEvent"}},
                        },
                    },
                ],
            },
            "ScanEvent": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Event type (e.g., IP_ADDRESS, DOMAIN_NAME)"},
                    "data": {"type": "string"},
                    "module": {"type": "string"},
                    "source_event": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "generated": {"type": "string", "format": "date-time"},
                },
            },
            "Workspace": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "created": {"type": "string", "format": "date-time"},
                    "scan_count": {"type": "integer"},
                },
            },
            "WorkspaceRequest": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
            "ModuleInfo": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "display_name": {"type": "string"},
                    "description": {"type": "string"},
                    "categories": {"type": "array", "items": {"type": "string"}},
                    "flags": {"type": "array", "items": {"type": "string"}},
                    "watched_events": {"type": "array", "items": {"type": "string"}},
                    "produced_events": {"type": "array", "items": {"type": "string"}},
                },
            },
            "HealthStatus": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["UP", "DOWN", "DEGRADED"]},
                    "components": {"type": "object", "additionalProperties": {"type": "object", "properties": {"status": {"type": "string"}, "detail": {"type": "string"}}}},
                    "timestamp": {"type": "string", "format": "date-time"},
                },
            },
            "Error": {
                "type": "object",
                "properties": {
                    "code": {"type": "integer"},
                    "message": {"type": "string"},
                    "detail": {"type": "string"},
                },
            },
        }
