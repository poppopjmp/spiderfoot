#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SpiderFoot MISP Export CLI.

This script allows you to export SpiderFoot scan results to MISP format.
It can either generate a MISP-compatible JSON file or directly publish
to a MISP instance.
"""

from spiderfoot.misp_integration import MispIntegration, MispEvent
from spiderfoot import SpiderFootDb
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.append(str(Path(__file__).parent.parent))


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Export SpiderFoot scan results to MISP format')
    parser.add_argument('-s', '--scan-id',
                        help='Scan ID to export', required=True)
    parser.add_argument('-d', '--db-path', help='Path to SpiderFoot database',
                        default=str(Path.home() / '.spiderfoot' / 'spiderfoot.db'))
    parser.add_argument(
        '-o', '--output', help='Output file (defaults to stdout)')
    parser.add_argument('-p', '--publish',
                        help='Publish directly to MISP', action='store_true')
    parser.add_argument('-u', '--misp-url',
                        help='MISP URL (required if publishing)')
    parser.add_argument('-k', '--misp-key',
                        help='MISP API key (required if publishing)')
    parser.add_argument(
        '-t', '--tlp', help='TLP tag (default: tlp:amber)', default='tlp:amber')
    parser.add_argument('-c', '--confidence-threshold', help='Minimum confidence score (0-100)',
                        type=int, default=50)
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_args()

    # Validate args
    if args.publish and (not args.misp_url or not args.misp_key):
        print("Error: --misp-url and --misp-key are required when publishing to MISP")
        sys.exit(1)

    if not Path(args.db_path).exists():
        print(f"Error: Database not found at {args.db_path}")
        sys.exit(1)

    # Initialize SpiderFoot database
    print(f"Opening database {args.db_path}")
    opts = {"__database": args.db_path}
    db = SpiderFootDb(opts)

    # Check if scan exists
    scan_info = db.scanInstanceGet(args.scan_id)
    if not scan_info:
        print(f"Error: Scan with ID {args.scan_id} not found")
        sys.exit(1)

    scan_name = scan_info[0]
    print(f"Exporting scan '{scan_name}' to MISP format...")

    # Initialize MISP integration
    misp_integration = MispIntegration(db)

    # Create MISP event from scan
    misp_event = misp_integration.create_misp_event_from_scan(args.scan_id)

    # Add TLP tag
    if args.tlp:
        misp_event.add_tag(args.tlp)

    if args.publish:
        try:
            from pymisp import PyMISP, MISPEvent

            print(f"Publishing to MISP at {args.misp_url}")

            # Convert our MISP event to PyMISP format
            misp_json = misp_integration.export_misp_event(misp_event, "json")
            pymisp_event = MISPEvent()
            event_dict = json.loads(misp_json)
            pymisp_event.from_dict(**event_dict)

            # Connect to MISP
            misp = PyMISP(args.misp_url, args.misp_key, False)

            # Add event to MISP
            response = misp.add_event(pymisp_event)

            if 'errors' in response:
                print(f"Error publishing to MISP: {response['errors']}")
                sys.exit(1)
            else:
                print(
                    f"Successfully published event to MISP with ID: {response['Event']['id']}")
        except ImportError:
            print("Error: PyMISP module not installed. Install with: pip install pymisp")
            sys.exit(1)
        except Exception as e:
            print(f"Error publishing to MISP: {e}")
            sys.exit(1)
    else:
        # Export to JSON
        misp_json = misp_integration.export_misp_event(misp_event, "json")

        if args.output:
            with open(args.output, 'w') as f:
                f.write(misp_json)
            print(f"MISP event exported to {args.output}")
        else:
            print(misp_json)

    # Print summary
    print(
        f"MISP event contains {len(misp_event.attributes)} attributes and {len(misp_event.objects)} objects")


if __name__ == "__main__":
    main()
