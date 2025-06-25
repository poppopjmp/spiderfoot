let's #!/usr/bin/env python3
"""SpiderFoot Workflow CLI.

Command-line interface for SpiderFoot workflow functionality,
workspace management, and CTI report generation.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

from spiderfoot import SpiderFootDb, SpiderFootHelpers
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot.workflow import SpiderFootWorkflow
from spiderfoot.mcp_integration import SpiderFootMCPClient, CTIReportExporter


class SpiderFootWorkflowCLI:
    """Command-line interface for SpiderFoot workflows."""
    
    def __init__(self, config: dict):
        """Initialize CLI.
        
        Args:
            config: SpiderFoot configuration
        """
        self.config = config
        self.db = SpiderFootDb(config)
        self.log = logging.getLogger("spiderfoot.workflow_cli")
    
    def run(self, args: List[str] = None):
        """Run CLI with arguments.
        
        Args:
            args: Command line arguments (default: sys.argv[1:])
        """
        parser = self._create_parser()
        parsed_args = parser.parse_args(args)
        
        # Set up logging
        log_level = logging.DEBUG if parsed_args.verbose else logging.INFO
        logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Execute command
        try:
            if hasattr(parsed_args, 'func'):
                if asyncio.iscoroutinefunction(parsed_args.func):
                    asyncio.run(parsed_args.func(parsed_args))
                else:
                    parsed_args.func(parsed_args)
            else:
                parser.print_help()
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            sys.exit(1)
        except Exception as e:
            self.log.error(f"Command failed: {e}")
            if parsed_args.verbose:
                raise
            sys.exit(1)
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser."""
        parser = argparse.ArgumentParser(
            description="SpiderFoot Workflow Management CLI",
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
        
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # Workspace commands
        self._add_workspace_commands(subparsers)
        
        # Target commands
        self._add_target_commands(subparsers)
        
        # Scan commands
        self._add_scan_commands(subparsers)
        
        # Workflow commands
        self._add_workflow_commands(subparsers)
        
        # CTI commands
        self._add_cti_commands(subparsers)
        
        # Utility commands
        self._add_utility_commands(subparsers)
        
        return parser
    
    def _add_workspace_commands(self, subparsers):
        """Add workspace management commands."""
        # List workspaces
        list_parser = subparsers.add_parser('list-workspaces', help='List all workspaces')
        list_parser.set_defaults(func=self.list_workspaces)
        
        # Create workspace
        create_parser = subparsers.add_parser('create-workspace', help='Create new workspace')
        create_parser.add_argument('name', help='Workspace name')
        create_parser.add_argument('--description', help='Workspace description')
        create_parser.set_defaults(func=self.create_workspace)
        
        # Show workspace
        show_parser = subparsers.add_parser('show-workspace', help='Show workspace details')
        show_parser.add_argument('workspace_id', help='Workspace ID')
        show_parser.set_defaults(func=self.show_workspace)
        
        # Delete workspace
        delete_parser = subparsers.add_parser('delete-workspace', help='Delete workspace')
        delete_parser.add_argument('workspace_id', help='Workspace ID')
        delete_parser.add_argument('--force', action='store_true', help='Force deletion without confirmation')
        delete_parser.set_defaults(func=self.delete_workspace)
        
        # Clone workspace
        clone_parser = subparsers.add_parser('clone-workspace', help='Clone workspace')
        clone_parser.add_argument('workspace_id', help='Source workspace ID')
        clone_parser.add_argument('--name', help='New workspace name')
        clone_parser.set_defaults(func=self.clone_workspace)
        
        # Merge workspaces
        merge_parser = subparsers.add_parser('merge-workspaces', help='Merge workspaces')
        merge_parser.add_argument('target_workspace_id', help='Target workspace ID')
        merge_parser.add_argument('source_workspace_id', help='Source workspace ID')
        merge_parser.set_defaults(func=self.merge_workspaces)
    
    def _add_target_commands(self, subparsers):
        """Add target management commands."""
        # Add target
        add_target_parser = subparsers.add_parser('add-target', help='Add target to workspace')
        add_target_parser.add_argument('workspace_id', help='Workspace ID')
        add_target_parser.add_argument('target', help='Target value (domain, IP, etc.)')
        add_target_parser.add_argument('--type', help='Target type')
        add_target_parser.add_argument('--metadata', help='Target metadata (JSON)')
        add_target_parser.set_defaults(func=self.add_target)
        
        # List targets
        list_targets_parser = subparsers.add_parser('list-targets', help='List workspace targets')
        list_targets_parser.add_argument('workspace_id', help='Workspace ID')
        list_targets_parser.set_defaults(func=self.list_targets)
        
        # Remove target
        remove_target_parser = subparsers.add_parser('remove-target', help='Remove target from workspace')
        remove_target_parser.add_argument('workspace_id', help='Workspace ID')
        remove_target_parser.add_argument('target_id', help='Target ID')
        remove_target_parser.set_defaults(func=self.remove_target)
    
    def _add_scan_commands(self, subparsers):
        """Add scan management commands."""
        # Import scan
        import_parser = subparsers.add_parser('import-scan', help='Import scan into workspace')
        import_parser.add_argument('workspace_id', help='Workspace ID')
        import_parser.add_argument('scan_id', help='Scan ID to import')
        import_parser.add_argument('--metadata', help='Import metadata (JSON)')
        import_parser.set_defaults(func=self.import_scan)
        
        # Import multiple scans
        import_bulk_parser = subparsers.add_parser('import-scans', help='Import multiple scans')
        import_bulk_parser.add_argument('workspace_id', help='Workspace ID')
        import_bulk_parser.add_argument('scan_ids', nargs='+', help='Scan IDs to import')
        import_bulk_parser.add_argument('--metadata', help='Import metadata (JSON)')
        import_bulk_parser.set_defaults(func=self.import_scans)
        
        # List scans
        list_scans_parser = subparsers.add_parser('list-scans', help='List workspace scans')
        list_scans_parser.add_argument('workspace_id', help='Workspace ID')
        list_scans_parser.set_defaults(func=self.list_scans)
    
    def _add_workflow_commands(self, subparsers):
        """Add workflow commands."""
        # Start multi-target scan
        multi_scan_parser = subparsers.add_parser('multi-scan', help='Start multi-target scan')
        multi_scan_parser.add_argument('workspace_id', help='Workspace ID')
        multi_scan_parser.add_argument('--targets-file', help='JSON file with targets')
        multi_scan_parser.add_argument('--targets', nargs='+', help='Target values')
        multi_scan_parser.add_argument('--modules', nargs='+', required=True, help='Modules to use')
        multi_scan_parser.add_argument('--options', help='Scan options (JSON)')
        multi_scan_parser.add_argument('--wait', action='store_true', help='Wait for completion')
        multi_scan_parser.set_defaults(func=self.multi_target_scan)
        
        # Run correlation
        correlate_parser = subparsers.add_parser('correlate', help='Run cross-correlation analysis')
        correlate_parser.add_argument('workspace_id', help='Workspace ID')
        correlate_parser.add_argument('--scan-ids', nargs='+', help='Specific scan IDs')
        correlate_parser.add_argument('--rules', nargs='+', help='Specific correlation rules')
        correlate_parser.set_defaults(func=self.run_correlation)
        
        # Show correlations
        show_corr_parser = subparsers.add_parser('show-correlations', help='Show correlation results')
        show_corr_parser.add_argument('workspace_id', help='Workspace ID')
        show_corr_parser.set_defaults(func=self.show_correlations)
    
    def _add_cti_commands(self, subparsers):
        """Add CTI report commands."""
        # Generate CTI report
        cti_parser = subparsers.add_parser('generate-cti', help='Generate CTI report')
        cti_parser.add_argument('workspace_id', help='Workspace ID')
        cti_parser.add_argument('--type', default='threat_assessment', 
                               choices=['threat_assessment', 'infrastructure_analysis', 'attack_surface'],
                               help='Report type')
        cti_parser.add_argument('--prompt', help='Custom prompt for report generation')
        cti_parser.add_argument('--output', help='Output file path')
        cti_parser.set_defaults(func=self.generate_cti_report)
        
        # List CTI reports
        list_cti_parser = subparsers.add_parser('list-cti', help='List CTI reports')
        list_cti_parser.add_argument('workspace_id', help='Workspace ID')
        list_cti_parser.set_defaults(func=self.list_cti_reports)
        
        # Export CTI report
        export_cti_parser = subparsers.add_parser('export-cti', help='Export CTI report')
        export_cti_parser.add_argument('workspace_id', help='Workspace ID')
        export_cti_parser.add_argument('report_id', help='Report ID')
        export_cti_parser.add_argument('--format', default='json', 
                                      choices=['json', 'html', 'pdf', 'docx'],
                                      help='Export format')
        export_cti_parser.add_argument('--output', help='Output file path')
        export_cti_parser.set_defaults(func=self.export_cti_report)
    
    def _add_utility_commands(self, subparsers):
        """Add utility commands."""
        # Search events
        search_parser = subparsers.add_parser('search', help='Search events across workspace')
        search_parser.add_argument('workspace_id', help='Workspace ID')
        search_parser.add_argument('query', help='Search query')
        search_parser.add_argument('--types', nargs='+', help='Event types to search')
        search_parser.add_argument('--scans', nargs='+', help='Specific scan IDs')
        search_parser.add_argument('--limit', type=int, default=100, help='Maximum results')
        search_parser.set_defaults(func=self.search_events)
        
        # Export workspace
        export_parser = subparsers.add_parser('export', help='Export workspace data')
        export_parser.add_argument('workspace_id', help='Workspace ID')
        export_parser.add_argument('--format', default='json', choices=['json'], help='Export format')
        export_parser.add_argument('--output', help='Output file path')
        export_parser.set_defaults(func=self.export_workspace)
        
        # Test MCP connection
        test_mcp_parser = subparsers.add_parser('test-mcp', help='Test MCP server connection')
        test_mcp_parser.set_defaults(func=self.test_mcp_connection)
    
    def _get_workspace(self, workspace_id: str) -> SpiderFootWorkspace:
        """Get workspace by ID."""
        try:
            return SpiderFootWorkspace(self.config, workspace_id)
        except ValueError:
            raise ValueError(f"Workspace {workspace_id} not found")
    
    def _parse_json_arg(self, json_str: str) -> dict:
        """Parse JSON argument."""
        if not json_str:
            return {}
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    
    # Workspace command implementations
    
    def list_workspaces(self, args):
        """List all workspaces."""
        workspaces = SpiderFootWorkspace.list_workspaces(self.config)
        
        if not workspaces:
            print("No workspaces found")
            return
        
        print(f"{'Workspace ID':<15} {'Name':<25} {'Targets':<8} {'Scans':<6} {'Modified'}")
        print("-" * 70)
        
        for workspace in workspaces:
            modified = time.strftime('%Y-%m-%d %H:%M', time.localtime(workspace['modified_time']))
            print(f"{workspace['workspace_id']:<15} {workspace['name']:<25} "
                  f"{workspace['target_count']:<8} {workspace['scan_count']:<6} {modified}")
    
    def create_workspace(self, args):
        """Create new workspace."""
        workspace = SpiderFootWorkspace(self.config, name=args.name)
        if args.description:
            workspace.description = args.description
            workspace.save_workspace()
        
        print(f"Created workspace: {workspace.workspace_id}")
        print(f"Name: {workspace.name}")
        if workspace.description:
            print(f"Description: {workspace.description}")
    
    def show_workspace(self, args):
        """Show workspace details."""
        workspace = self._get_workspace(args.workspace_id)
        summary = workspace.get_workspace_summary()
        
        print(f"Workspace: {workspace.name} ({workspace.workspace_id})")
        print(f"Description: {workspace.description}")
        print(f"Created: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(workspace.created_time))}")
        print(f"Modified: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(workspace.modified_time))}")
        print()
        
        stats = summary['statistics']
        print("Statistics:")
        print(f"  Targets: {stats['target_count']}")
        print(f"  Scans: {stats['scan_count']} (Completed: {stats['completed_scans']}, "
              f"Running: {stats['running_scans']}, Failed: {stats['failed_scans']})")
        print(f"  Events: {stats['total_events']:,}")
        print(f"  Correlations: {stats['correlation_count']}")
        print(f"  CTI Reports: {stats['cti_report_count']}")
        
        if summary['targets_by_type']:
            print("\nTargets by type:")
            for target_type, count in summary['targets_by_type'].items():
                print(f"  {target_type}: {count}")
    
    def delete_workspace(self, args):
        """Delete workspace."""
        workspace = self._get_workspace(args.workspace_id)
        
        if not args.force:
            response = input(f"Delete workspace '{workspace.name}' ({workspace.workspace_id})? [y/N]: ")
            if response.lower() != 'y':
                print("Cancelled")
                return
        
        workspace.delete_workspace()
        print(f"Deleted workspace: {workspace.workspace_id}")
    
    def clone_workspace(self, args):
        """Clone workspace."""
        workspace = self._get_workspace(args.workspace_id)
        cloned = workspace.clone_workspace(args.name)
        
        print(f"Cloned workspace: {args.workspace_id} -> {cloned.workspace_id}")
        print(f"New workspace name: {cloned.name}")
    
    def merge_workspaces(self, args):
        """Merge workspaces."""
        target_workspace = self._get_workspace(args.target_workspace_id)
        source_workspace = self._get_workspace(args.source_workspace_id)
        
        success = target_workspace.merge_workspace(source_workspace)
        if success:
            print(f"Successfully merged {args.source_workspace_id} into {args.target_workspace_id}")
        else:
            print("Failed to merge workspaces")
            sys.exit(1)
    
    # Target command implementations
    
    def add_target(self, args):
        """Add target to workspace."""
        workspace = self._get_workspace(args.workspace_id)
        metadata = self._parse_json_arg(args.metadata)
        
        target_id = workspace.add_target(args.target, args.type, metadata)
        print(f"Added target: {args.target} (ID: {target_id})")
    
    def list_targets(self, args):
        """List workspace targets."""
        workspace = self._get_workspace(args.workspace_id)
        targets = workspace.get_targets()
        
        if not targets:
            print("No targets found")
            return
        
        print(f"{'Target ID':<12} {'Type':<15} {'Value':<30} {'Added'}")
        print("-" * 70)
        
        for target in targets:
            added = time.strftime('%Y-%m-%d %H:%M', time.localtime(target['added_time']))
            print(f"{target['target_id']:<12} {target['type']:<15} {target['value']:<30} {added}")
    
    def remove_target(self, args):
        """Remove target from workspace."""
        workspace = self._get_workspace(args.workspace_id)
        success = workspace.remove_target(args.target_id)
        
        if success:
            print(f"Removed target: {args.target_id}")
        else:
            print(f"Target not found: {args.target_id}")
            sys.exit(1)
    
    # Scan command implementations
    
    def import_scan(self, args):
        """Import scan into workspace."""
        workspace = self._get_workspace(args.workspace_id)
        metadata = self._parse_json_arg(args.metadata)
        
        success = workspace.import_single_scan(args.scan_id, metadata)
        if success:
            print(f"Imported scan: {args.scan_id}")
        else:
            print(f"Failed to import scan: {args.scan_id}")
            sys.exit(1)
    
    def import_scans(self, args):
        """Import multiple scans."""
        workspace = self._get_workspace(args.workspace_id)
        metadata = self._parse_json_arg(args.metadata)
        
        results = workspace.bulk_import_scans(args.scan_ids, metadata)
        
        successful = sum(results.values())
        total = len(results)
        
        print(f"Import completed: {successful}/{total} scans imported")
        
        for scan_id, success in results.items():
            status = "✓" if success else "✗"
            print(f"  {status} {scan_id}")
    
    def list_scans(self, args):
        """List workspace scans."""
        workspace = self._get_workspace(args.workspace_id)
        scans = workspace.get_scans()
        
        if not scans:
            print("No scans found")
            return
        
        print(f"{'Scan ID':<15} {'Target':<25} {'Status':<12} {'Added'}")
        print("-" * 70)
        
        for scan in scans:
            scan_info = self.db.scanInstanceGet(scan['scan_id'])
            status = scan_info[5] if scan_info else 'UNKNOWN'
            target = scan_info[2] if scan_info else 'UNKNOWN'
            added = time.strftime('%Y-%m-%d %H:%M', time.localtime(scan['added_time']))
            
            print(f"{scan['scan_id']:<15} {target:<25} {status:<12} {added}")
    
    # Workflow command implementations
    
    def multi_target_scan(self, args):
        """Start multi-target scan."""
        workspace = self._get_workspace(args.workspace_id)
        
        # Get targets
        targets = []
        if args.targets_file:
            with open(args.targets_file, 'r') as f:
                targets_data = json.load(f)
            targets = targets_data if isinstance(targets_data, list) else [targets_data]
        elif args.targets:
            for target_value in args.targets:
                target_type = SpiderFootHelpers.targetTypeFromString(target_value)
                targets.append({'value': target_value, 'type': target_type})
        else:
            raise ValueError("Either --targets-file or --targets must be specified")
        
        scan_options = self._parse_json_arg(args.options)
        
        workflow = workspace.create_workflow()
        
        print(f"Starting multi-target scan for {len(targets)} targets...")
        scan_ids = workflow.start_multi_target_scan(targets, args.modules, scan_options)
        
        print(f"Started {len(scan_ids)} scans:")
        for scan_id in scan_ids:
            print(f"  {scan_id}")
        
        if args.wait:
            print("\nWaiting for scans to complete...")
            statuses = workflow.wait_for_scans_completion(scan_ids)
            
            print("\nScan results:")
            for scan_id, status in statuses.items():
                print(f"  {scan_id}: {status}")
    
    def run_correlation(self, args):
        """Run cross-correlation analysis."""
        workspace = self._get_workspace(args.workspace_id)
        workflow = workspace.create_workflow()
        
        print("Running cross-correlation analysis...")
        results = workflow.run_cross_correlation(args.scan_ids, args.rules)
        
        if not results:
            print("No correlation results found")
            return
        
        print(f"Found {len(results)} correlation results:")
        for result in results:
            print(f"  {result.get('rule_name', 'Unknown')}: {result.get('type', 'Unknown')}")
    
    def show_correlations(self, args):
        """Show correlation results."""
        workspace = self._get_workspace(args.workspace_id)
        correlations = workspace.metadata.get('correlations', [])
        
        if not correlations:
            print("No correlations found")
            return
        
        print(f"Found {len(correlations)} correlation runs:")
        for i, correlation in enumerate(correlations, 1):
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(correlation['timestamp']))
            print(f"{i}. {timestamp}: {correlation['results_count']} results across {len(correlation['scan_ids'])} scans")
    
    # CTI command implementations
    
    async def generate_cti_report(self, args):
        """Generate CTI report."""
        workspace = self._get_workspace(args.workspace_id)
        
        print(f"Generating {args.type} CTI report...")
        report = await workspace.generate_cti_report(args.type, args.prompt)
        
        print(f"Generated CTI report: {report['report_id']}")
        print(f"Risk rating: {report['risk_rating']}")
        
        if args.output:
            exporter = CTIReportExporter()
            output_format = Path(args.output).suffix[1:] or 'json'
            file_path = exporter.export_report(report, output_format, args.output)
            print(f"Exported to: {file_path}")
    
    def list_cti_reports(self, args):
        """List CTI reports."""
        workspace = self._get_workspace(args.workspace_id)
        reports = workspace.metadata.get('cti_reports', [])
        
        if not reports:
            print("No CTI reports found")
            return
        
        print(f"{'Report ID':<25} {'Type':<20} {'Risk':<8} {'Generated'}")
        print("-" * 70)
        
        for report in reports:
            generated = report['generated_time'][:19]  # Remove microseconds
            print(f"{report['report_id']:<25} {report['report_type']:<20} "
                  f"{report['risk_rating']:<8} {generated}")
    
    def export_cti_report(self, args):
        """Export CTI report."""
        workspace = self._get_workspace(args.workspace_id)
        report_key = f'cti_report_{args.report_id}'
        
        if report_key not in workspace.metadata:
            print(f"Report not found: {args.report_id}")
            sys.exit(1)
        
        report = workspace.metadata[report_key]
        exporter = CTIReportExporter()
        
        file_path = exporter.export_report(report, args.format, args.output)
        print(f"Exported report to: {file_path}")
    
    # Utility command implementations
    
    def search_events(self, args):
        """Search events across workspace."""
        workspace = self._get_workspace(args.workspace_id)
        
        results = workspace.search_events(args.query, args.types, args.scans)
        
        if not results:
            print("No events found")
            return
        
        # Limit results
        limited_results = results[:args.limit]
        
        print(f"Found {len(results)} events (showing {len(limited_results)}):")
        print(f"{'Scan ID':<15} {'Type':<20} {'Data':<40} {'Risk'}")
        print("-" * 85)
        
        for event in limited_results:
            data = event['data'][:37] + "..." if len(event['data']) > 40 else event['data']
            print(f"{event['scan_id']:<15} {event['type']:<20} {data:<40} {event.get('risk', 0)}")
    
    def export_workspace(self, args):
        """Export workspace data."""
        workspace = self._get_workspace(args.workspace_id)
        
        data = workspace.export_data(args.format)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Exported workspace to: {args.output}")
        else:
            print(json.dumps(data, indent=2))
    
    async def test_mcp_connection(self, args):
        """Test MCP server connection."""
        try:
            mcp_client = SpiderFootMCPClient(self.config)
            success = await mcp_client.test_mcp_connection()
            
            if success:
                print("✓ MCP server connection successful")
                print(f"Server URL: {mcp_client.server_url}")
            else:
                print("✗ MCP server connection failed")
                sys.exit(1)
                
        except Exception as e:
            print(f"✗ MCP server connection error: {e}")
            sys.exit(1)


def main():
    """Main entry point for CLI."""
    # Use a basic configuration
    config = {
        '__database': f"{SpiderFootHelpers.dataPath()}/spiderfoot.db",
        '_internettlds': ['com', 'org', 'net'],
        '_maxthreads': 3,
        '__correlationrules__': []
    }
    
    cli = SpiderFootWorkflowCLI(config)
    cli.run()


if __name__ == '__main__':
    main()
