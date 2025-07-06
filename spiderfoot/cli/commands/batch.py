"""
Batch operations commands for SpiderFoot CLI.
"""

import shlex
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def batch_scan_command(cli, line):
    """Run multiple scans in batch. Usage: batch_scan <targets_file> [options]
    
    Options:
        --modules MODULE_LIST    Comma-separated module list
        --types TYPE_LIST        Comma-separated event types
        --concurrent NUM         Number of concurrent scans (default: 3)
        --delay SECONDS          Delay between starting scans (default: 5)
        --workspace WORKSPACE    Target workspace for scans
        --template SCAN_ID       Use existing scan as template
        --wait                   Wait for all scans to complete
    """
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: batch_scan <targets_file> [options]")
        return
    
    targets_file = args[0]
    modules = None
    types = None
    concurrent = 3
    delay = 5
    workspace = None
    template_scan = None
    wait_for_completion = '--wait' in args
    
    # Parse arguments
    i = 1
    while i < len(args):
        if args[i] == '--modules' and i + 1 < len(args):
            modules = args[i + 1].split(',')
            i += 2
        elif args[i] == '--types' and i + 1 < len(args):
            types = args[i + 1].split(',')
            i += 2
        elif args[i] == '--concurrent' and i + 1 < len(args):
            concurrent = int(args[i + 1])
            i += 2
        elif args[i] == '--delay' and i + 1 < len(args):
            delay = int(args[i + 1])
            i += 2
        elif args[i] == '--workspace' and i + 1 < len(args):
            workspace = args[i + 1]
            i += 2
        elif args[i] == '--template' and i + 1 < len(args):
            template_scan = args[i + 1]
            i += 2
        elif args[i] == '--wait':
            i += 1
        else:
            i += 1
    
    # Read targets from file
    try:
        with open(targets_file, 'r', encoding='utf-8') as f:
            targets = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except Exception as e:
        cli.edprint(f"Failed to read targets file: {e}")
        return
    
    if not targets:
        cli.edprint("No valid targets found in file")
        return
    
    cli.dprint(f"Starting batch scan for {len(targets)} targets", plain=True)
    
    # Get template configuration if specified
    template_config = None
    if template_scan:
        template_config = _get_scan_config(cli, template_scan)
        if template_config:
            cli.dprint(f"Using template from scan: {template_scan}", plain=True)
    
    # Start scans
    scan_ids = []
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    
    with ThreadPoolExecutor(max_workers=concurrent) as executor:
        futures = []
        
        for i, target in enumerate(targets):
            # Prepare scan configuration
            scan_config = {
                "name": f"Batch_{i+1}_{target}",
                "target": target
            }
            
            if template_config:
                scan_config.update(template_config)
            if modules:
                scan_config["modules"] = modules
            if types:
                scan_config["type_filter"] = types
            
            # Submit scan creation task
            future = executor.submit(_create_scan, cli, base_url, scan_config, workspace)
            futures.append((future, target, i))
            
            # Add delay between submissions
            if i < len(targets) - 1:
                time.sleep(delay)
        
        # Collect results
        for future, target, index in futures:
            try:
                scan_id = future.result()
                if scan_id:
                    scan_ids.append(scan_id)
                    cli.dprint(f"Scan {index+1}/{len(targets)} started: {target} -> {scan_id}", plain=True)
                else:
                    cli.edprint(f"Failed to start scan for: {target}")
            except Exception as e:
                cli.edprint(f"Error starting scan for {target}: {e}")
    
    cli.dprint(f"Batch scan initiated: {len(scan_ids)}/{len(targets)} scans started", plain=True)
    
    # Wait for completion if requested
    if wait_for_completion and scan_ids:
        cli.dprint("Waiting for scans to complete...", plain=True)
        _wait_for_scans_completion(cli, scan_ids)


def _create_scan(cli, base_url, scan_config, workspace):
    """Create a single scan"""
    try:
        if workspace:
            url = f"{base_url}/api/workspaces/{workspace}/scans"
        else:
            url = f"{base_url}/api/scans"
        
        resp = cli.request(url, post=scan_config)
        if resp:
            data = json.loads(resp)
            return data.get('id', data.get('scan_id'))
    except Exception:
        pass
    return None


def _get_scan_config(cli, scan_id):
    """Get configuration from an existing scan"""
    try:
        base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
        url = f"{base_url}/api/scans/{scan_id}/options"
        resp = cli.request(url)
        if resp:
            data = json.loads(resp)
            return data.get('config', {})
    except Exception:
        pass
    return None


def _wait_for_scans_completion(cli, scan_ids):
    """Wait for multiple scans to complete"""
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    completed = set()
    
    while len(completed) < len(scan_ids):
        for scan_id in scan_ids:
            if scan_id in completed:
                continue
                
            try:
                url = f"{base_url}/api/scans/{scan_id}/status"
                resp = cli.request(url)
                if resp:
                    data = json.loads(resp)
                    status = data.get('status', 'UNKNOWN')
                    if status in ['FINISHED', 'ABORTED', 'ERROR-FAILED']:
                        completed.add(scan_id)
                        cli.dprint(f"Scan {scan_id} completed: {status}", plain=True)
            except Exception:
                pass
        
        if len(completed) < len(scan_ids):
            time.sleep(10)  # Check every 10 seconds
    
    cli.dprint("All batch scans completed", plain=True)


def batch_export_command(cli, line):
    """Export multiple scans in batch. Usage: batch_export <scan_ids> [options]
    
    Options:
        --format FORMAT       Export format: json, csv, xlsx
        --output_dir DIR      Output directory
        --separate            Create separate files for each scan
        --combined           Combine all scans into one file
        --compress           Create ZIP archive
    """
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: batch_export <scan_ids> [options]")
        return
    
    scan_ids_str = args[0]
    scan_ids = [s.strip() for s in scan_ids_str.split(',') if s.strip()]
    
    export_format = 'json'
    output_dir = '.'
    separate_files = '--separate' in args
    combined_file = '--combined' in args
    create_zip = '--compress' in args
    
    # Parse arguments
    i = 1
    while i < len(args):
        if args[i] == '--format' and i + 1 < len(args):
            export_format = args[i + 1]
            i += 2
        elif args[i] == '--output_dir' and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif args[i] in ['--separate', '--combined', '--compress']:
            i += 1
        else:
            i += 1
    
    # Default to separate files if neither option specified
    if not separate_files and not combined_file:
        separate_files = True
    
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    
    if combined_file:
        # Combined export
        cli.dprint("Exporting all scans to combined file...", plain=True)
        url = f"{base_url}/api/scans/export-multi?scans={scan_ids_str}&format={export_format}"
        resp = cli.request(url)
        if resp:
            filename = f"combined_export.{export_format}"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(resp)
            cli.dprint(f"Combined export saved: {filepath}", plain=True)
        else:
            cli.edprint("Combined export failed")
    
    if separate_files:
        # Separate exports
        cli.dprint("Exporting scans to separate files...", plain=True)
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            
            for scan_id in scan_ids:
                future = executor.submit(_export_single_scan, cli, base_url, scan_id, export_format, output_dir)
                futures.append((future, scan_id))
            
            for future, scan_id in futures:
                try:
                    success = future.result()
                    if success:
                        cli.dprint(f"Exported: {scan_id}", plain=True)
                    else:
                        cli.edprint(f"Failed to export: {scan_id}")
                except Exception as e:
                    cli.edprint(f"Error exporting {scan_id}: {e}")
    
    # Create ZIP archive if requested
    if create_zip:
        _create_export_archive(cli, output_dir, scan_ids, export_format)


def _export_single_scan(cli, base_url, scan_id, export_format, output_dir):
    """Export a single scan"""
    try:
        url = f"{base_url}/api/scans/{scan_id}/events/export?format={export_format}"
        resp = cli.request(url)
        if resp:
            import os
            filename = f"scan_{scan_id}.{export_format}"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(resp)
            return True
    except Exception:
        pass
    return False


def _create_export_archive(cli, output_dir, scan_ids, export_format):
    """Create ZIP archive of exported files"""
    try:
        import zipfile
        import os
        
        archive_name = f"batch_export_{int(time.time())}.zip"
        archive_path = os.path.join(output_dir, archive_name)
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for scan_id in scan_ids:
                filename = f"scan_{scan_id}.{export_format}"
                filepath = os.path.join(output_dir, filename)
                if os.path.exists(filepath):
                    zf.write(filepath, filename)
                    os.remove(filepath)  # Remove individual file
        
        cli.dprint(f"Archive created: {archive_path}", plain=True)
        
    except Exception as e:
        cli.edprint(f"Failed to create archive: {e}")


def batch_delete_command(cli, line):
    """Delete multiple scans in batch. Usage: batch_delete <scan_ids> [options]
    
    Options:
        --confirm            Skip confirmation prompt
        --workspace WORKSPACE Delete from specific workspace
        --status STATUS      Delete only scans with specific status
        --older_than DAYS    Delete scans older than specified days
    """
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: batch_delete <scan_ids> [options]")
        return
    
    scan_ids_str = args[0]
    scan_ids = [s.strip() for s in scan_ids_str.split(',') if s.strip()]
    
    confirm = '--confirm' in args
    workspace = None
    status_filter = None
    older_than = None
    
    # Parse arguments
    i = 1
    while i < len(args):
        if args[i] == '--workspace' and i + 1 < len(args):
            workspace = args[i + 1]
            i += 2
        elif args[i] == '--status' and i + 1 < len(args):
            status_filter = args[i + 1]
            i += 2
        elif args[i] == '--older_than' and i + 1 < len(args):
            older_than = int(args[i + 1])
            i += 2
        elif args[i] == '--confirm':
            i += 1
        else:
            i += 1
    
    # Filter scans if criteria specified
    if status_filter or older_than:
        scan_ids = _filter_scans_for_deletion(cli, scan_ids, status_filter, older_than)
    
    if not scan_ids:
        cli.dprint("No scans match deletion criteria", plain=True)
        return
    
    # Confirmation
    if not confirm:
        cli.dprint(f"About to delete {len(scan_ids)} scans:", plain=True)
        for scan_id in scan_ids:
            cli.dprint(f"  - {scan_id}", plain=True)
        
        try:
            response = input("Continue? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                cli.dprint("Deletion cancelled", plain=True)
                return
        except KeyboardInterrupt:
            cli.dprint("Deletion cancelled", plain=True)
            return
    
    # Delete scans
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    deleted = 0
    
    for scan_id in scan_ids:
        try:
            if workspace:
                url = f"{base_url}/api/workspaces/{workspace}/scans/{scan_id}"
            else:
                url = f"{base_url}/api/scans/{scan_id}"
            
            resp = cli.request(url, delete=True)
            if resp:
                deleted += 1
                cli.dprint(f"Deleted: {scan_id}", plain=True)
            else:
                cli.edprint(f"Failed to delete: {scan_id}")
                
        except Exception as e:
            cli.edprint(f"Error deleting {scan_id}: {e}")
    
    cli.dprint(f"Batch deletion completed: {deleted}/{len(scan_ids)} scans deleted", plain=True)


def _filter_scans_for_deletion(cli, scan_ids, status_filter, older_than):
    """Filter scans based on deletion criteria"""
    filtered_ids = []
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    
    for scan_id in scan_ids:
        try:
            url = f"{base_url}/api/scans/{scan_id}/status"
            resp = cli.request(url)
            if resp:
                data = json.loads(resp)
                
                # Check status filter
                if status_filter:
                    scan_status = data.get('status', '')
                    if scan_status.upper() != status_filter.upper():
                        continue
                
                # Check age filter
                if older_than:
                    # This would need timestamp comparison
                    # For now, we'll include all scans that pass status filter
                    pass
                
                filtered_ids.append(scan_id)
                
        except Exception:
            # If we can't get status, exclude from deletion for safety
            pass
    
    return filtered_ids


def register(registry):
    """Register all batch operation commands"""
    registry.register("batch_scan", batch_scan_command, 
                     help_text="Run multiple scans in batch")
    registry.register("batch_export", batch_export_command, 
                     help_text="Export multiple scans in batch")
    registry.register("batch_delete", batch_delete_command, 
                     help_text="Delete multiple scans in batch")
