#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         cli_service
# Purpose:      Modern CLI service commands that integrate with the
#               microservices architecture. Provides direct CLI access
#               to service health, metrics, scans, and configuration
#               without requiring the web server to be running.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot CLI Service Commands

Provides standalone CLI commands that interact directly with services:

    sf-service status          Show all service health
    sf-service scan submit     Submit a new scan
    sf-service scan list       List scans
    sf-service scan abort      Abort a running scan
    sf-service metrics         Show Prometheus metrics
    sf-service config get      Get configuration value
    sf-service config set      Set configuration value
    sf-service correlate       Run correlations for a scan
    sf-service modules         List available modules
    sf-service version         Show version info

Usage::

    python -m spiderfoot.cli_service status
    python -m spiderfoot.cli_service scan submit --target example.com
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional


def _print_json(data: Any, indent: int = 2) -> None:
    """Pretty-print JSON data."""
    print(json.dumps(data, indent=indent, default=str))


def _print_table(rows: List[Dict[str, Any]], columns: List[str]) -> None:
    """Print data as a simple ASCII table."""
    if not rows:
        print("(no data)")
        return

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, ""))
            widths[col] = max(widths[col], len(val))

    # Header
    header = " | ".join(col.ljust(widths[col]) for col in columns)
    print(header)
    print("-+-".join("-" * widths[col] for col in columns))

    # Rows
    for row in rows:
        line = " | ".join(
            str(row.get(col, "")).ljust(widths[col])
            for col in columns
        )
        print(line)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_version(args: argparse.Namespace) -> None:
    """Show version information."""
    try:
        from spiderfoot import __version__
        version = __version__
    except ImportError:
        version_file = os.path.join(
            os.path.dirname(__file__), "..", "VERSION")
        try:
            with open(version_file) as f:
                version = f.read().strip()
        except FileNotFoundError:
            version = "unknown"

    print(f"SpiderFoot v{version}")
    print(f"Python {sys.version}")


def cmd_status(args: argparse.Namespace) -> None:
    """Show service health status."""
    try:
        from spiderfoot.health import (
            HealthAggregator, register_default_checks,
        )

        health = HealthAggregator.get_instance()
        register_default_checks(health)
        result = health.check_all()

        if args.json:
            _print_json(result)
            return

        print(f"Overall: {result['status'].upper()}")
        print(f"Uptime:  {result['uptime_seconds']}s")
        print()

        if result["components"]:
            rows = []
            for name, info in result["components"].items():
                rows.append({
                    "component": name,
                    "status": info["status"],
                    "latency": f"{info.get('latency_ms', 0):.1f}ms",
                    "message": info.get("message", ""),
                })
            _print_table(rows, ["component", "status", "latency", "message"])
        else:
            print("No components registered.")

    except ImportError as e:
        print(f"Health module not available: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_metrics(args: argparse.Namespace) -> None:
    """Show Prometheus metrics."""
    try:
        from spiderfoot.metrics import get_registry

        registry = get_registry()

        if args.format == "prometheus":
            print(registry.render())
        else:
            metrics = {}
            for name, metric in registry._metrics.items():
                metrics[name] = {
                    "type": type(metric).__name__,
                    "help": metric.help_text,
                }
            _print_json(metrics)

    except ImportError as e:
        print(f"Metrics module not available: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config_get(args: argparse.Namespace) -> None:
    """Get a configuration value."""
    try:
        from spiderfoot.config_service import get_config_service

        config = get_config_service()
        value = config.get(args.key)

        if value is None:
            print(f"Key not found: {args.key}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            _print_json({args.key: value})
        else:
            print(value)

    except ImportError as e:
        print(f"Config service not available: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config_set(args: argparse.Namespace) -> None:
    """Set a configuration value."""
    try:
        from spiderfoot.config_service import get_config_service

        config = get_config_service()
        config.set(args.key, args.value)
        print(f"Set {args.key} = {args.value}")

    except ImportError as e:
        print(f"Config service not available: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config_list(args: argparse.Namespace) -> None:
    """List all configuration keys."""
    try:
        from spiderfoot.config_service import get_config_service

        config = get_config_service()
        all_config = config._config

        if args.json:
            _print_json(all_config)
            return

        if args.filter:
            filtered = {
                k: v for k, v in all_config.items()
                if args.filter.lower() in k.lower()
            }
        else:
            filtered = all_config

        for key in sorted(filtered.keys()):
            val = filtered[key]
            if isinstance(val, str) and len(val) > 60:
                val = val[:57] + "..."
            print(f"  {key} = {val}")

        print(f"\n({len(filtered)} keys)")

    except ImportError as e:
        print(f"Config service not available: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_scan_submit(args: argparse.Namespace) -> None:
    """Submit a new scan."""
    try:
        from spiderfoot.scan_scheduler import (
            ScanScheduler, ScanRequest, ScanPriority,
        )

        priority_map = {
            "low": ScanPriority.LOW,
            "normal": ScanPriority.NORMAL,
            "high": ScanPriority.HIGH,
            "critical": ScanPriority.CRITICAL,
        }

        scheduler = ScanScheduler.from_config({})

        priority = priority_map.get(args.priority, ScanPriority.NORMAL)
        request = ScanRequest(
            target=args.target,
            scan_name=args.name or f"CLI scan: {args.target}",
            modules=args.modules.split(",") if args.modules else [],
            priority=priority,
        )

        scan_id = scheduler.submit_scan(request)
        print(f"Scan submitted: {scan_id}")
        print(f"  Target:   {args.target}")
        print(f"  Priority: {args.priority}")

        if args.json:
            _print_json({
                "scan_id": scan_id,
                "target": args.target,
                "priority": args.priority,
            })

    except ImportError as e:
        print(f"Scan scheduler not available: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_scan_list(args: argparse.Namespace) -> None:
    """List scans."""
    try:
        from spiderfoot.scan_scheduler import ScanScheduler

        scheduler = ScanScheduler.from_config({})
        statuses = scheduler.all_status()

        if args.json:
            _print_json([s.__dict__ for s in statuses.values()]
                        if statuses else [])
            return

        if not statuses:
            print("No scans found.")
            return

        rows = []
        for sid, status in statuses.items():
            rows.append({
                "scan_id": sid[:12] + "...",
                "state": status.state.value if hasattr(status.state, 'value') else str(status.state),
                "progress": f"{status.progress:.0%}" if hasattr(status, 'progress') else "N/A",
            })

        _print_table(rows, ["scan_id", "state", "progress"])

    except ImportError as e:
        print(f"Scan scheduler not available: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_correlate(args: argparse.Namespace) -> None:
    """Run correlations for a scan."""
    try:
        from spiderfoot.correlation_service import get_correlation_service

        svc = get_correlation_service({})
        svc.start()

        print(f"Running correlations for scan {args.scan_id}...")
        results = svc.run_for_scan(args.scan_id)

        svc.stop()

        if args.json:
            _print_json([{
                "rule_id": r.rule_id,
                "headline": r.headline,
                "risk": r.risk,
                "event_count": r.event_count,
            } for r in results])
            return

        if not results:
            print("No correlations found.")
            return

        for r in results:
            print(f"  [{r.risk}] {r.headline} ({r.event_count} events)")

        print(f"\n{len(results)} correlation(s) found.")

    except ImportError as e:
        print(f"Correlation service not available: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_modules(args: argparse.Namespace) -> None:
    """List available modules."""
    import glob
    import importlib

    modules_dir = os.path.join(os.path.dirname(__file__), "..", "modules")
    pattern = os.path.join(modules_dir, "sfp_*.py")
    files = sorted(glob.glob(pattern))

    rows = []
    for fpath in files:
        name = os.path.basename(fpath).replace(".py", "")
        rows.append({"module": name})

    if args.json:
        _print_json([r["module"] for r in rows])
        return

    print(f"Available modules ({len(rows)}):\n")
    for r in rows:
        print(f"  {r['module']}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="sf-service",
        description="SpiderFoot Service CLI",
    )
    parser.add_argument("--json", action="store_true",
                        help="Output in JSON format")

    sub = parser.add_subparsers(dest="command", help="Command")

    # version
    sub.add_parser("version", help="Show version info")

    # status
    status_p = sub.add_parser("status", help="Show service health")
    status_p.add_argument("--json", action="store_true",
                          dest="json")

    # metrics
    metrics_p = sub.add_parser("metrics", help="Show metrics")
    metrics_p.add_argument("--format",
                           choices=["prometheus", "json"],
                           default="prometheus")

    # config
    config_p = sub.add_parser("config", help="Configuration management")
    config_sub = config_p.add_subparsers(dest="config_cmd")

    get_p = config_sub.add_parser("get", help="Get config value")
    get_p.add_argument("key", help="Configuration key")
    get_p.add_argument("--json", action="store_true", dest="json")

    set_p = config_sub.add_parser("set", help="Set config value")
    set_p.add_argument("key", help="Configuration key")
    set_p.add_argument("value", help="Configuration value")

    list_p = config_sub.add_parser("list", help="List config keys")
    list_p.add_argument("--filter", help="Filter keys by substring")
    list_p.add_argument("--json", action="store_true", dest="json")

    # scan
    scan_p = sub.add_parser("scan", help="Scan management")
    scan_sub = scan_p.add_subparsers(dest="scan_cmd")

    submit_p = scan_sub.add_parser("submit", help="Submit a new scan")
    submit_p.add_argument("--target", required=True, help="Scan target")
    submit_p.add_argument("--name", help="Scan name")
    submit_p.add_argument("--modules", help="Comma-separated module list")
    submit_p.add_argument("--priority", default="normal",
                          choices=["low", "normal", "high", "critical"])
    submit_p.add_argument("--json", action="store_true", dest="json")

    list_scan_p = scan_sub.add_parser("list", help="List scans")
    list_scan_p.add_argument("--json", action="store_true", dest="json")

    # correlate
    corr_p = sub.add_parser("correlate", help="Run correlations")
    corr_p.add_argument("scan_id", help="Scan ID to correlate")
    corr_p.add_argument("--json", action="store_true", dest="json")

    # modules
    mod_p = sub.add_parser("modules", help="List available modules")
    mod_p.add_argument("--json", action="store_true", dest="json")

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "version": cmd_version,
        "status": cmd_status,
        "metrics": cmd_metrics,
        "correlate": cmd_correlate,
        "modules": cmd_modules,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    elif args.command == "config":
        config_dispatch = {
            "get": cmd_config_get,
            "set": cmd_config_set,
            "list": cmd_config_list,
        }
        if args.config_cmd in config_dispatch:
            config_dispatch[args.config_cmd](args)
        else:
            parser.parse_args(["config", "--help"])
    elif args.command == "scan":
        scan_dispatch = {
            "submit": cmd_scan_submit,
            "list": cmd_scan_list,
        }
        if args.scan_cmd in scan_dispatch:
            scan_dispatch[args.scan_cmd](args)
        else:
            parser.parse_args(["scan", "--help"])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
