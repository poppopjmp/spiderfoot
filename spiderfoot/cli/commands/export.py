"""
Enhanced export commands for SpiderFoot CLI.
"""

import shlex
import json
import os


def export_command(cli, line):
    """Export data from a scan. Usage: export <scan_id> [options]
    
    Options:
        -f, --format FORMAT    Export format: json, csv, xlsx, gexf (default: json)
        -o, --output FILE      Output file path (default: stdout)
        -t, --type EVENTTYPE   Filter by event type
        --search VALUE         Search/filter by value
        --multi SCAN_IDS       Export multiple scans (comma-separated)
    """
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: export <scan_id> [options]")
        cli.edprint("Use 'help export' for detailed options")
        return
    
    scan_id = args[0]
    export_format = 'json'
    output_file = None
    event_type = None
    search_value = None
    multi_scans = None
    
    # Parse arguments
    i = 1
    while i < len(args):
        if args[i] in ['-f', '--format'] and i + 1 < len(args):
            export_format = args[i + 1]
            i += 2
        elif args[i] in ['-o', '--output'] and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] in ['-t', '--type'] and i + 1 < len(args):
            event_type = args[i + 1]
            i += 2
        elif args[i] == '--search' and i + 1 < len(args):
            search_value = args[i + 1]
            i += 2
        elif args[i] == '--multi' and i + 1 < len(args):
            multi_scans = args[i + 1]
            i += 2
        else:
            i += 1
    
    # Build URL based on export type
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    
    if multi_scans:
        # Multi-scan export
        url = f"{base_url}/api/scans/export-multi"
        params = [f"scans={multi_scans}", f"format={export_format}"]
    elif search_value:
        # Search export
        url = f"{base_url}/api/scans/{scan_id}/search/export"
        params = [f"format={export_format}", f"value={search_value}"]
        if event_type:
            params.append(f"eventType={event_type}")
    else:
        # Regular scan export
        url = f"{base_url}/api/scans/{scan_id}/events/export"
        params = [f"format={export_format}"]
        if event_type:
            params.append(f"eventType={event_type}")
    
    if params:
        url += '?' + '&'.join(params)
    
    resp = cli.request(url)
    if not resp:
        cli.edprint("Export failed - no data received")
        return
    
    # Handle output
    if output_file:
        try:
            # Determine file mode based on format
            mode = 'wb' if export_format in ['xlsx'] else 'w'
            encoding = None if export_format in ['xlsx'] else 'utf-8'
            
            with open(output_file, mode, encoding=encoding) as f:
                if export_format in ['xlsx']:
                    f.write(resp if isinstance(resp, bytes) else resp.encode())
                else:
                    f.write(resp)
            cli.dprint(f"Export saved to: {output_file}")
            
            # Show file info
            size = os.path.getsize(output_file)
            cli.dprint(f"File size: {size:,} bytes")
            
        except Exception as e:
            cli.edprint(f"Failed to save export: {e}")
    else:
        # Output to stdout
        if export_format == 'json':
            try:
                # Pretty print JSON
                data = json.loads(resp)
                formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
                cli.dprint(formatted_json, plain=True)
            except:
                cli.dprint(resp, plain=True)
        else:
            cli.dprint(resp, plain=True)


def export_logs_command(cli, line):
    """Export scan logs. Usage: export_logs <scan_id> [options]
    
    Options:
        -o, --output FILE      Output file path (default: stdout)
        -f, --format FORMAT    Export format: csv, json (default: csv)
    """
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: export_logs <scan_id> [options]")
        return
    
    scan_id = args[0]
    output_file = None
    export_format = 'csv'
    
    # Parse arguments
    i = 1
    while i < len(args):
        if args[i] in ['-o', '--output'] and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] in ['-f', '--format'] and i + 1 < len(args):
            export_format = args[i + 1]
            i += 2
        else:
            i += 1
    
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    url = f"{base_url}/api/scans/{scan_id}/logs/export?format={export_format}"
    
    resp = cli.request(url)
    if not resp:
        cli.edprint("Log export failed")
        return
    
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(resp)
            cli.dprint(f"Logs exported to: {output_file}")
        except Exception as e:
            cli.edprint(f"Failed to save logs: {e}")
    else:
        cli.dprint(resp, plain=True)


def export_correlations_command(cli, line):
    """Export scan correlations. Usage: export_correlations <scan_id> [options]
    
    Options:
        -o, --output FILE      Output file path (default: stdout)
        -f, --format FORMAT    Export format: csv, json (default: csv)
    """
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: export_correlations <scan_id> [options]")
        return
    
    scan_id = args[0]
    output_file = None
    export_format = 'csv'
    
    # Parse arguments
    i = 1
    while i < len(args):
        if args[i] in ['-o', '--output'] and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] in ['-f', '--format'] and i + 1 < len(args):
            export_format = args[i + 1]
            i += 2
        else:
            i += 1
    
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    url = f"{base_url}/api/scans/{scan_id}/correlations/export?format={export_format}"
    
    resp = cli.request(url)
    if not resp:
        cli.edprint("Correlations export failed")
        return
    
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(resp)
            cli.dprint(f"Correlations exported to: {output_file}")
        except Exception as e:
            cli.edprint(f"Failed to save correlations: {e}")
    else:
        cli.dprint(resp, plain=True)


def export_viz_command(cli, line):
    """Export visualization data. Usage: export_viz <scan_id> [options]
    
    Options:
        -o, --output FILE      Output file path (default: stdout)
        -f, --format FORMAT    Export format: gexf, json (default: gexf)
        --multi SCAN_IDS       Export multiple scans (comma-separated)
    """
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: export_viz <scan_id> [options]")
        return
    
    scan_id = args[0]
    output_file = None
    export_format = 'gexf'
    multi_scans = None
    
    # Parse arguments
    i = 1
    while i < len(args):
        if args[i] in ['-o', '--output'] and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] in ['-f', '--format'] and i + 1 < len(args):
            export_format = args[i + 1]
            i += 2
        elif args[i] == '--multi' and i + 1 < len(args):
            multi_scans = args[i + 1]
            i += 2
        else:
            i += 1
    
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    
    if multi_scans:
        url = f"{base_url}/api/scans/viz-multi?scans={multi_scans}&format={export_format}"
    else:
        url = f"{base_url}/api/scans/{scan_id}/viz?format={export_format}"
    
    resp = cli.request(url)
    if not resp:
        cli.edprint("Visualization export failed")
        return
    
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(resp)
            cli.dprint(f"Visualization data exported to: {output_file}")
        except Exception as e:
            cli.edprint(f"Failed to save visualization data: {e}")
    else:
        cli.dprint(resp, plain=True)


def register(registry):
    """Register all export commands"""
    registry.register("export", export_command, 
                     help_text="Export scan data in various formats")
    registry.register("export_logs", export_logs_command, 
                     help_text="Export scan logs")
    registry.register("export_correlations", export_correlations_command, 
                     help_text="Export scan correlations")
    registry.register("export_viz", export_viz_command, 
                     help_text="Export visualization data")
