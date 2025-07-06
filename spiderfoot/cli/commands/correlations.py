"""
Enhanced correlations commands for SpiderFoot CLI.
"""

import shlex
import json


def correlations_command(cli, line):
    """Show correlation results from a scan. Usage: correlations <scan_id> [options]
    
    Options:
        --risk LEVEL       Filter by risk level (HIGH, MEDIUM, LOW, INFO)
        --rule RULE_ID     Filter by specific rule ID
        --details          Show detailed information
        --count            Show only count summary
    """
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: correlations <scan_id> [options]")
        return
    
    scan_id = args[0]
    risk_filter = None
    rule_filter = None
    show_details = '--details' in args
    show_count = '--count' in args
    
    # Parse arguments
    i = 1
    while i < len(args):
        if args[i] == '--risk' and i + 1 < len(args):
            risk_filter = args[i + 1]
            i += 2
        elif args[i] == '--rule' and i + 1 < len(args):
            rule_filter = args[i + 1]
            i += 2
        elif args[i] in ['--details', '--count']:
            i += 1
        else:
            i += 1
    
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    url = f"{base_url}/api/scans/{scan_id}/correlations"
    
    # Add filters if specified
    params = []
    if risk_filter:
        params.append(f"risk={risk_filter}")
    if rule_filter:
        params.append(f"rule={rule_filter}")
    
    if params:
        url += '?' + '&'.join(params)
    
    resp = cli.request(url)
    if not resp:
        cli.dprint("No correlation results found.")
        return
    
    try:
        data = json.loads(resp)
        correlations = data.get('correlations', []) if isinstance(data, dict) else data
        
        if show_count:
            # Show summary count
            risk_counts = {}
            for corr in correlations:
                risk = corr.get('risk', 'UNKNOWN')
                risk_counts[risk] = risk_counts.get(risk, 0) + 1
            
            cli.dprint("Correlation Summary:", plain=True)
            for risk, count in sorted(risk_counts.items()):
                cli.dprint(f"  {risk}: {count}", plain=True)
            cli.dprint(f"Total: {len(correlations)}", plain=True)
            
        elif show_details:
            # Show detailed information
            cli.dprint("Detailed Correlations:", plain=True)
            for i, corr in enumerate(correlations, 1):
                cli.dprint(f"\n[{i}] {corr.get('title', 'Unknown')}", plain=True)
                cli.dprint(f"    Risk: {corr.get('risk', 'UNKNOWN')}", plain=True)
                cli.dprint(f"    Rule: {corr.get('rule_name', 'Unknown')}", plain=True)
                cli.dprint(f"    Description: {corr.get('description', 'No description')}", plain=True)
                cli.dprint(f"    Count: {corr.get('count', 0)}", plain=True)
        else:
            # Show basic list
            cli.dprint("Scan Correlations:", plain=True)
            for corr in correlations:
                title = corr.get('title', 'Unknown')
                risk = corr.get('risk', 'UNKNOWN')
                count = corr.get('count', 0)
                cli.dprint(f"  • {title} [{risk}] ({count} instances)", plain=True)
    
    except Exception as e:
        cli.edprint(f"Failed to parse correlations: {e}")


def correlation_rules_command(cli, line):
    """List available correlation rules. Usage: correlation_rules [options]
    
    Options:
        --risk LEVEL       Filter by risk level (HIGH, MEDIUM, LOW, INFO)
        --enabled          Show only enabled rules
        --disabled         Show only disabled rules
        --details          Show detailed information
    """
    args = shlex.split(line)
    risk_filter = None
    enabled_filter = None
    show_details = '--details' in args
    
    # Parse arguments
    i = 0
    while i < len(args):
        if args[i] == '--risk' and i + 1 < len(args):
            risk_filter = args[i + 1]
            i += 2
        elif args[i] == '--enabled':
            enabled_filter = True
            i += 1
        elif args[i] == '--disabled':
            enabled_filter = False
            i += 1
        elif args[i] == '--details':
            i += 1
        else:
            i += 1
    
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    url = f"{base_url}/api/correlationrules"
    
    # Add filters if specified
    params = []
    if risk_filter:
        params.append(f"risk={risk_filter}")
    if enabled_filter is not None:
        params.append(f"enabled={str(enabled_filter).lower()}")
    
    if params:
        url += '?' + '&'.join(params)
    
    resp = cli.request(url)
    if not resp:
        cli.dprint("No correlation rules found.")
        return
    
    try:
        data = json.loads(resp)
        rules = data.get('rules', []) if isinstance(data, dict) else data
        
        if show_details:
            cli.dprint("Correlation Rules (Detailed):", plain=True)
            for i, rule in enumerate(rules, 1):
                cli.dprint(f"\n[{i}] {rule.get('name', 'Unknown')}", plain=True)
                cli.dprint(f"    ID: {rule.get('id', 'Unknown')}", plain=True)
                cli.dprint(f"    Risk: {rule.get('risk', 'UNKNOWN')}", plain=True)
                cli.dprint(f"    Enabled: {rule.get('enabled', 'Unknown')}", plain=True)
                cli.dprint(f"    Description: {rule.get('description', 'No description')}", plain=True)
                cli.dprint(f"    Logic: {rule.get('logic', 'No logic defined')}", plain=True)
        else:
            cli.dprint("Correlation Rules:", plain=True)
            for rule in rules:
                name = rule.get('name', 'Unknown')
                risk = rule.get('risk', 'UNKNOWN')
                enabled = '✓' if rule.get('enabled', False) else '✗'
                cli.dprint(f"  {enabled} {name} [{risk}]", plain=True)
    
    except Exception as e:
        cli.edprint(f"Failed to parse correlation rules: {e}")


def correlation_summary_command(cli, line):
    """Show correlation summary for a scan. Usage: correlation_summary <scan_id>"""
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: correlation_summary <scan_id>")
        return
    
    scan_id = args[0]
    base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
    url = f"{base_url}/api/scans/{scan_id}/status"
    
    resp = cli.request(url)
    if not resp:
        cli.edprint("Failed to get scan status.")
        return
    
    try:
        data = json.loads(resp)
        correlations = data.get('correlations', {})
        
        cli.dprint(f"Correlation Summary for Scan: {scan_id}", plain=True)
        cli.dprint("=" * 50, plain=True)
        
        total = 0
        for risk_level, count in correlations.items():
            cli.dprint(f"{risk_level}: {count}", plain=True)
            total += count
        
        cli.dprint("-" * 20, plain=True)
        cli.dprint(f"Total: {total}", plain=True)
        
    except Exception as e:
        cli.edprint(f"Failed to parse scan status: {e}")


def register(registry):
    """Register all correlation commands"""
    registry.register("correlations", correlations_command, 
                     help_text="Show correlation results from a scan")
    registry.register("correlation_rules", correlation_rules_command, 
                     help_text="List available correlation rules")
    registry.register("correlation_summary", correlation_summary_command, 
                     help_text="Show correlation summary for a scan")
