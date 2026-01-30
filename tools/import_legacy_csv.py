#!/usr/bin/env python3
"""
Import Legacy SpiderFoot CSV Exports

This script imports CSV files exported from older SpiderFoot versions
into the current database. It creates a new scan instance and imports
all events from the CSV.

Usage:
    python3 tools/import_legacy_csv.py --csv /path/to/export.csv --name "Imported Scan"

CSV Format Expected (standard SpiderFoot export):
    Updated, Type, Module, Source, F/P, Data
    or
    Scan Name, Updated, Type, Module, Source, F/P, Data
"""

import argparse
import csv
import hashlib
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from spiderfoot import SpiderFootDb
from spiderfoot import SpiderFootHelpers


def generate_event_hash(scan_id: str, event_type: str, data: str, source: str) -> str:
    """Generate a unique hash for an event."""
    hash_input = f"{scan_id}|{event_type}|{data}|{source}|{time.time()}"
    return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:32]


def parse_timestamp(timestamp_str: str) -> int:
    """Parse timestamp string to milliseconds since epoch."""
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(timestamp_str.strip(), fmt)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue

    # Default to current time if parsing fails
    return int(time.time() * 1000)


def detect_csv_format(headers: list) -> dict:
    """Detect the CSV format based on headers."""
    headers_lower = [h.lower().strip() for h in headers]

    # Check for multi-scan format (has Scan Name column)
    if 'scan name' in headers_lower:
        return {
            'format': 'multi',
            'scan_name': headers_lower.index('scan name'),
            'updated': headers_lower.index('updated'),
            'type': headers_lower.index('type'),
            'module': headers_lower.index('module'),
            'source': headers_lower.index('source'),
            'fp': headers_lower.index('f/p') if 'f/p' in headers_lower else None,
            'data': headers_lower.index('data'),
        }
    else:
        return {
            'format': 'single',
            'updated': headers_lower.index('updated'),
            'type': headers_lower.index('type'),
            'module': headers_lower.index('module'),
            'source': headers_lower.index('source'),
            'fp': headers_lower.index('f/p') if 'f/p' in headers_lower else None,
            'data': headers_lower.index('data'),
        }


def import_csv(csv_path: str, scan_name: str = None, target: str = None, dry_run: bool = False) -> dict:
    """
    Import a CSV file into SpiderFoot database.

    Args:
        csv_path: Path to the CSV file
        scan_name: Name for the imported scan (optional, derived from filename if not provided)
        target: Target for the scan (optional, derived from first source if not provided)
        dry_run: If True, don't actually insert, just validate

    Returns:
        dict with import statistics
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Default scan name from filename
    if not scan_name:
        scan_name = f"Imported: {Path(csv_path).stem}"

    stats = {
        'rows_read': 0,
        'rows_imported': 0,
        'rows_skipped': 0,
        'fps_imported': 0,
        'errors': [],
        'scan_id': None,
        'event_types': set(),
    }

    # Read CSV
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        headers = next(reader)

        # Detect format
        try:
            col_map = detect_csv_format(headers)
        except ValueError as e:
            raise ValueError(f"Could not detect CSV format. Headers: {headers}") from e

        print(f"Detected CSV format: {col_map['format']}")
        print(f"Columns: {headers}")

        rows = list(reader)
        stats['rows_read'] = len(rows)

    if not rows:
        print("No data rows found in CSV")
        return stats

    # Determine target from first row if not provided
    if not target:
        first_row = rows[0]
        target = first_row[col_map['source']] if first_row[col_map['source']] else "imported_target"

    print(f"\nImport Details:")
    print(f"  Scan Name: {scan_name}")
    print(f"  Target: {target}")
    print(f"  Rows to import: {len(rows)}")

    if dry_run:
        print("\n[DRY RUN] No changes will be made to the database")
        # Just collect stats
        for row in rows:
            event_type = row[col_map['type']]
            stats['event_types'].add(event_type)
        stats['rows_imported'] = len(rows)
        return stats

    # Initialize database
    config = {
        '__database': f"{SpiderFootHelpers.dataPath()}/spiderfoot.db",
    }

    try:
        db = SpiderFootDb(config)
    except Exception as e:
        raise RuntimeError(f"Failed to connect to database: {e}") from e

    # Create scan instance
    scan_id = str(uuid.uuid4())
    stats['scan_id'] = scan_id

    try:
        db.scanInstanceNew(scan_id, scan_name, target)
        print(f"\nCreated scan instance: {scan_id}")
    except Exception as e:
        raise RuntimeError(f"Failed to create scan instance: {e}") from e

    # Import events
    print("\nImporting events...")

    # We need to insert events directly since we don't have SpiderFootEvent objects
    for i, row in enumerate(rows):
        try:
            event_type = row[col_map['type']]
            module = row[col_map['module']]
            source = row[col_map['source']]
            data = row[col_map['data']]
            timestamp = parse_timestamp(row[col_map['updated']])

            # Handle false positive flag
            fp = 0
            if col_map['fp'] is not None and len(row) > col_map['fp']:
                fp_val = row[col_map['fp']]
                fp = 1 if fp_val and fp_val.lower() in ('1', 'true', 'yes') else 0

            # Skip ROOT events
            if event_type == 'ROOT':
                stats['rows_skipped'] += 1
                continue

            # Generate hash
            event_hash = generate_event_hash(scan_id, event_type, data, source)

            # Insert into database
            qry = """INSERT INTO tbl_scan_results
                (scan_instance_id, hash, type, generated, confidence,
                visibility, risk, module, data, false_positive, source_event_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

            qvals = [scan_id, event_hash, event_type, timestamp,
                     100, 100, 0, module, data, fp, 'ROOT']

            db.dbh.execute(qry, qvals)

            # If marked as FP, also save to target-level false positives table
            # so it persists for future scans of this target
            if fp == 1:
                try:
                    fp_qry = """INSERT OR IGNORE INTO tbl_target_false_positives
                        (target, event_type, event_data, date_added, notes)
                        VALUES (?, ?, ?, ?, ?)"""
                    fp_qvals = [target, event_type, data, int(time.time() * 1000),
                               f"Imported from legacy CSV: {Path(csv_path).name}"]
                    db.dbh.execute(fp_qry, fp_qvals)
                    stats['fps_imported'] += 1
                except Exception:
                    pass  # Ignore duplicate FP entries

            stats['event_types'].add(event_type)
            stats['rows_imported'] += 1

            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{len(rows)} rows...")

        except Exception as e:
            stats['errors'].append(f"Row {i + 1}: {str(e)}")
            stats['rows_skipped'] += 1

    # Commit and finalize
    db.conn.commit()

    # Mark scan as finished
    db.scanInstanceSet(scan_id, status='FINISHED', ended=time.time() * 1000)

    print(f"\nImport complete!")
    print(f"  Scan ID: {scan_id}")
    print(f"  Rows imported: {stats['rows_imported']}")
    print(f"  Rows skipped: {stats['rows_skipped']}")
    print(f"  False positives saved: {stats['fps_imported']}")
    print(f"  Unique event types: {len(stats['event_types'])}")

    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats['errors'][:10]:
            print(f"  - {err}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Import legacy SpiderFoot CSV exports into the current database'
    )
    parser.add_argument('--csv', required=True, help='Path to CSV file to import')
    parser.add_argument('--name', help='Name for the imported scan')
    parser.add_argument('--target', help='Target for the scan')
    parser.add_argument('--dry-run', action='store_true', help='Validate without importing')

    args = parser.parse_args()

    try:
        stats = import_csv(
            csv_path=args.csv,
            scan_name=args.name,
            target=args.target,
            dry_run=args.dry_run
        )

        print(f"\nEvent types found: {sorted(stats['event_types'])}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
