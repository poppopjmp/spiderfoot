"""
Real-time monitoring commands for SpiderFoot CLI.
"""

import shlex
import json
import time
import threading
from datetime import datetime


def monitor_command(cli, line):
    """Monitor scan progress in real-time. Usage: monitor <scan_id> [options]
    
    Options:
        --interval SECONDS    Update interval in seconds (default: 5)
        --logs               Also show log messages
        --events             Show event counts
        --duration SECONDS   Stop monitoring after duration
        --format FORMAT      Output format: simple, detailed, json
    """
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: monitor <scan_id> [options]")
        return
    
    scan_id = args[0]
    interval = 5
    show_logs = False
    show_events = False
    duration = None
    output_format = 'simple'
    
    # Parse arguments
    i = 1
    while i < len(args):
        if args[i] == '--interval' and i + 1 < len(args):
            interval = int(args[i + 1])
            i += 2
        elif args[i] == '--logs':
            show_logs = True
            i += 1
        elif args[i] == '--events':
            show_events = True
            i += 1
        elif args[i] == '--duration' and i + 1 < len(args):
            duration = int(args[i + 1])
            i += 2
        elif args[i] == '--format' and i + 1 < len(args):
            output_format = args[i + 1]
            i += 2
        else:
            i += 1
    
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    
    # Monitor loop
    start_time = time.time()
    last_log_count = 0
    last_event_count = 0
    
    cli.dprint(f"Monitoring scan {scan_id} (Press Ctrl+C to stop)", plain=True)
    cli.dprint("=" * 60, plain=True)
    
    try:
        while True:
            # Get scan status
            status_url = f"{base_url}/api/scans/{scan_id}/status"
            status_resp = cli.request(status_url)
            
            if not status_resp:
                cli.edprint("Failed to get scan status")
                break
            
            try:
                status_data = json.loads(status_resp)
                
                # Display status based on format
                if output_format == 'json':
                    cli.dprint(json.dumps(status_data, indent=2), plain=True)
                elif output_format == 'detailed':
                    _display_detailed_status(cli, status_data)
                else:  # simple
                    _display_simple_status(cli, status_data)
                
                # Check if scan is finished
                scan_status = status_data.get('status', 'UNKNOWN')
                if scan_status in ['FINISHED', 'ABORTED', 'ERROR-FAILED']:
                    cli.dprint(f"Scan {scan_status.lower()}", plain=True)
                    break
                
                # Show logs if requested
                if show_logs:
                    logs_url = f"{base_url}/api/scans/{scan_id}/logs"
                    logs_resp = cli.request(logs_url)
                    if logs_resp:
                        try:
                            logs_data = json.loads(logs_resp)
                            logs = logs_data.get('logs', [])
                            if len(logs) > last_log_count:
                                cli.dprint("Recent log entries:", plain=True)
                                for log in logs[last_log_count:]:
                                    timestamp = log.get('timestamp', 'Unknown')
                                    message = log.get('message', '')
                                    cli.dprint(f"  {timestamp}: {message}", plain=True)
                                last_log_count = len(logs)
                        except Exception:
                            pass
                
                # Show events if requested
                if show_events:
                    events_url = f"{base_url}/api/scans/{scan_id}/events"
                    events_resp = cli.request(events_url)
                    if events_resp:
                        try:
                            events_data = json.loads(events_resp)
                            events = events_data.get('events', [])
                            if len(events) > last_event_count:
                                new_events = len(events) - last_event_count
                                cli.dprint(f"New events: {new_events}", plain=True)
                                last_event_count = len(events)
                        except Exception:
                            pass
                
            except Exception as e:
                cli.edprint(f"Failed to parse status: {e}")
                break
            
            # Check duration limit
            if duration and (time.time() - start_time) > duration:
                cli.dprint("Duration limit reached", plain=True)
                break
            
            # Wait for next update
            time.sleep(interval)
            
    except KeyboardInterrupt:
        cli.dprint("Monitoring stopped by user", plain=True)
    except Exception as e:
        cli.edprint(f"Monitoring failed: {e}")


def _display_simple_status(cli, status_data):
    """Display simple status format"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    status = status_data.get('status', 'UNKNOWN')
    progress = status_data.get('progress', 0)
    
    cli.dprint(f"[{timestamp}] Status: {status} | Progress: {progress}%", plain=True)


def _display_detailed_status(cli, status_data):
    """Display detailed status format"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    status = status_data.get('status', 'UNKNOWN')
    progress = status_data.get('progress', 0)
    
    cli.dprint(f"[{timestamp}] Scan Status Report", plain=True)
    cli.dprint(f"  Status: {status}", plain=True)
    cli.dprint(f"  Progress: {progress}%", plain=True)
    
    if 'events' in status_data:
        events = status_data['events']
        cli.dprint(f"  Total Events: {events.get('total', 0)}", plain=True)
        cli.dprint(f"  Event Types: {len(events.get('types', []))}", plain=True)
    
    if 'correlations' in status_data:
        correlations = status_data['correlations']
        total_corr = sum(correlations.values()) if isinstance(correlations, dict) else 0
        cli.dprint(f"  Correlations: {total_corr}", plain=True)
    
    cli.dprint("-" * 40, plain=True)


def watch_scans_command(cli, line):
    """Watch all active scans. Usage: watch_scans [options]
    
    Options:
        --interval SECONDS    Update interval in seconds (default: 10)
        --duration SECONDS   Stop watching after duration
        --format FORMAT      Output format: simple, table
    """
    args = shlex.split(line)
    interval = 10
    duration = None
    output_format = 'simple'
    
    # Parse arguments
    i = 0
    while i < len(args):
        if args[i] == '--interval' and i + 1 < len(args):
            interval = int(args[i + 1])
            i += 2
        elif args[i] == '--duration' and i + 1 < len(args):
            duration = int(args[i + 1])
            i += 2
        elif args[i] == '--format' and i + 1 < len(args):
            output_format = args[i + 1]
            i += 2
        else:
            i += 1
    
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    start_time = time.time()
    
    cli.dprint("Watching active scans (Press Ctrl+C to stop)", plain=True)
    cli.dprint("=" * 80, plain=True)
    
    try:
        while True:
            # Get all scans
            scans_url = f"{base_url}/api/scans"
            scans_resp = cli.request(scans_url)
            
            if not scans_resp:
                cli.edprint("Failed to get scans list")
                break
            
            try:
                scans_data = json.loads(scans_resp)
                scans = scans_data.get('scans', [])
                
                # Filter active scans
                active_scans = [s for s in scans if s.get('status', '').upper() in ['RUNNING', 'STARTING']]
                
                if output_format == 'table':
                    _display_scans_table(cli, active_scans)
                else:  # simple
                    _display_scans_simple(cli, active_scans)
                
                if not active_scans:
                    cli.dprint("No active scans", plain=True)
                    break
                
            except Exception as e:
                cli.edprint(f"Failed to parse scans: {e}")
                break
            
            # Check duration limit
            if duration and (time.time() - start_time) > duration:
                cli.dprint("Duration limit reached", plain=True)
                break
            
            # Wait for next update
            time.sleep(interval)
            
    except KeyboardInterrupt:
        cli.dprint("Watching stopped by user", plain=True)
    except Exception as e:
        cli.edprint(f"Watching failed: {e}")


def _display_scans_table(cli, scans):
    """Display scans in table format"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    cli.dprint(f"[{timestamp}] Active Scans:", plain=True)
    
    if not scans:
        cli.dprint("  No active scans", plain=True)
        return
    
    # Table header
    cli.dprint("  ID       | Name           | Target         | Status  | Progress", plain=True)
    cli.dprint("  " + "-" * 70, plain=True)
    
    for scan in scans:
        scan_id = scan.get('id', 'Unknown')[:8]
        name = scan.get('name', 'Unknown')[:15]
        target = scan.get('target', 'Unknown')[:15]
        status = scan.get('status', 'Unknown')[:8]
        progress = scan.get('progress', 0)
        
        cli.dprint(f"  {scan_id:<8} | {name:<15} | {target:<15} | {status:<8} | {progress:>3}%", plain=True)


def _display_scans_simple(cli, scans):
    """Display scans in simple format"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    cli.dprint(f"[{timestamp}] Active Scans: {len(scans)}", plain=True)
    
    for scan in scans:
        name = scan.get('name', 'Unknown')
        status = scan.get('status', 'Unknown')
        progress = scan.get('progress', 0)
        cli.dprint(f"  • {name} ({status}) - {progress}%", plain=True)


def logs_stream_command(cli, line):
    """Stream logs from a scan in real-time. Usage: logs_stream <scan_id> [options]
    
    Options:
        --follow             Follow log output (like tail -f)
        --level LEVEL        Filter by log level (DEBUG, INFO, WARNING, ERROR)
        --lines NUM          Number of recent lines to show first
    """
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: logs_stream <scan_id> [options]")
        return
    
    scan_id = args[0]
    follow = '--follow' in args
    level_filter = None
    initial_lines = 50
    
    # Parse arguments
    i = 1
    while i < len(args):
        if args[i] == '--level' and i + 1 < len(args):
            level_filter = args[i + 1]
            i += 2
        elif args[i] == '--lines' and i + 1 < len(args):
            initial_lines = int(args[i + 1])
            i += 2
        elif args[i] == '--follow':
            i += 1
        else:
            i += 1
    
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    logs_url = f"{base_url}/api/scans/{scan_id}/logs"
    
    # Add filters
    params = []
    if level_filter:
        params.append(f"level={level_filter}")
    if initial_lines:
        params.append(f"limit={initial_lines}")
    
    if params:
        logs_url += '?' + '&'.join(params)
    
    last_count = 0
    
    try:
        while True:
            resp = cli.request(logs_url)
            if not resp:
                cli.edprint("Failed to get logs")
                break
            
            try:
                logs_data = json.loads(resp)
                logs = logs_data.get('logs', [])
                
                # Show new logs
                if len(logs) > last_count:
                    for log in logs[last_count:]:
                        timestamp = log.get('timestamp', 'Unknown')
                        level = log.get('level', 'INFO')
                        message = log.get('message', '')
                        cli.dprint(f"[{timestamp}] {level}: {message}", plain=True)
                    last_count = len(logs)
                
                if not follow:
                    break
                
            except Exception as e:
                cli.edprint(f"Failed to parse logs: {e}")
                break
            
            if follow:
                time.sleep(2)  # Poll every 2 seconds
            
    except KeyboardInterrupt:
        cli.dprint("Log streaming stopped by user", plain=True)
    except Exception as e:
        cli.edprint(f"Log streaming failed: {e}")


def register(registry):
    """Register all monitoring commands"""
    registry.register("monitor", monitor_command, 
                     help_text="Monitor scan progress in real-time")
    registry.register("watch_scans", watch_scans_command, 
                     help_text="Watch all active scans")
    registry.register("logs_stream", logs_stream_command, 
                     help_text="Stream logs from a scan in real-time")
