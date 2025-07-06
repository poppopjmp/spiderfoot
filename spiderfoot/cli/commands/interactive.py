"""
Enhanced interactive features for SpiderFoot CLI.
"""

import shlex
import json
import re
from typing import List, Dict, Any


def interactive_scan_wizard(cli, line):
    """Interactive wizard for creating complex scans. Usage: scan_wizard"""
    try:
        cli.dprint("SpiderFoot Interactive Scan Wizard", plain=True)
        cli.dprint("=" * 40, plain=True)
        
        # Collect scan parameters interactively
        scan_config = {}
        
        # Basic scan info
        scan_config['name'] = _prompt_input(cli, "Scan name", "New Scan")
        scan_config['target'] = _prompt_input(cli, "Target (domain, IP, etc.)", required=True)
        
        # Target type detection
        target_type = _detect_target_type(scan_config['target'])
        cli.dprint(f"Detected target type: {target_type}", plain=True)
        
        # Module selection
        modules = _prompt_modules(cli)
        if modules:
            scan_config['modules'] = modules
        
        # Event type filtering
        use_type_filter = _prompt_yes_no(cli, "Filter by event types?", False)
        if use_type_filter:
            event_types = _prompt_event_types(cli)
            if event_types:
                scan_config['type_filter'] = event_types
        
        # Workspace selection
        use_workspace = _prompt_yes_no(cli, "Use workspace?", False)
        if use_workspace:
            workspace = _prompt_workspace(cli)
            if workspace:
                scan_config['workspace'] = workspace
        
        # Advanced options
        use_advanced = _prompt_yes_no(cli, "Configure advanced options?", False)
        if use_advanced:
            scan_config.update(_prompt_advanced_options(cli))
        
        # Confirmation
        cli.dprint("\nScan Configuration Summary:", plain=True)
        cli.dprint("-" * 30, plain=True)
        for key, value in scan_config.items():
            cli.dprint(f"{key}: {value}", plain=True)
        
        if _prompt_yes_no(cli, "\nCreate this scan?", True):
            _create_scan_from_config(cli, scan_config)
        else:
            cli.dprint("Scan creation cancelled", plain=True)
            
    except KeyboardInterrupt:
        cli.dprint("\nWizard cancelled by user", plain=True)
    except Exception as e:
        cli.edprint(f"Wizard failed: {e}")


def _prompt_input(cli, prompt, default=None, required=False):
    """Prompt for user input with optional default"""
    while True:
        try:
            if default:
                user_input = input(f"{prompt} [{default}]: ").strip()
                return user_input if user_input else default
            else:
                user_input = input(f"{prompt}: ").strip()
                if user_input or not required:
                    return user_input
                cli.dprint("This field is required", plain=True)
        except KeyboardInterrupt:
            raise
        except Exception:
            if not required:
                return ""


def _prompt_yes_no(cli, prompt, default=True):
    """Prompt for yes/no input"""
    default_text = "Y/n" if default else "y/N"
    while True:
        try:
            response = input(f"{prompt} [{default_text}]: ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            elif response == '':
                return default
            else:
                cli.dprint("Please enter 'y' or 'n'", plain=True)
        except KeyboardInterrupt:
            raise


def _detect_target_type(target):
    """Detect target type based on input"""
    import ipaddress
    
    try:
        ipaddress.ip_address(target)
        return "IP_ADDRESS"
    except ValueError:
        pass
    
    if target.startswith('http://') or target.startswith('https://'):
        return "URL"
    elif '.' in target and not target.startswith('www.'):
        return "INTERNET_NAME"
    else:
        return "HUMAN_NAME"


def _prompt_modules(cli):
    """Interactive module selection"""
    cli.dprint("\nAvailable module categories:", plain=True)
    categories = {
        '1': 'DNS/Network Discovery',
        '2': 'Web Technologies',
        '3': 'Social Media',
        '4': 'Security/Vulnerabilities',
        '5': 'Threat Intelligence',
        '6': 'All modules',
        '7': 'Custom selection'
    }
    
    for key, desc in categories.items():
        cli.dprint(f"  {key}. {desc}", plain=True)
    
    choice = _prompt_input(cli, "\nSelect category", "6")
    
    if choice == '6':
        return None  # Use all modules
    elif choice == '7':
        return _prompt_custom_modules(cli)
    else:
        # Return predefined module sets (simplified)
        module_sets = {
            '1': ['sfp_dnsdb', 'sfp_dnsresolve', 'sfp_portscan'],
            '2': ['sfp_webanalytics', 'sfp_webframework', 'sfp_webheaders'],
            '3': ['sfp_twitter', 'sfp_facebook', 'sfp_linkedin'],
            '4': ['sfp_shodan', 'sfp_vulndb', 'sfp_cve'],
            '5': ['sfp_threatcrowd', 'sfp_virustotal', 'sfp_alienvault']
        }
        return module_sets.get(choice, [])


def _prompt_custom_modules(cli):
    """Custom module selection"""
    cli.dprint("Enter module names (comma-separated) or 'list' to see all:", plain=True)
    modules_input = _prompt_input(cli, "Modules")
    
    if modules_input.lower() == 'list':
        # This would show available modules
        cli.dprint("Available modules: [list would be fetched from API]", plain=True)
        modules_input = _prompt_input(cli, "Modules")
    
    if modules_input:
        return [m.strip() for m in modules_input.split(',') if m.strip()]
    return []


def _prompt_event_types(cli):
    """Interactive event type selection"""
    cli.dprint("Common event types:", plain=True)
    common_types = [
        'IP_ADDRESS', 'INTERNET_NAME', 'DOMAIN_NAME',
        'EMAILADDR', 'URL', 'PHONE_NUMBER'
    ]
    
    for i, event_type in enumerate(common_types, 1):
        cli.dprint(f"  {i}. {event_type}", plain=True)
    
    types_input = _prompt_input(cli, "Select types (numbers, comma-separated)")
    
    if types_input:
        try:
            selected_indices = [int(x.strip()) - 1 for x in types_input.split(',')]
            return [common_types[i] for i in selected_indices if 0 <= i < len(common_types)]
        except ValueError:
            return []
    return []


def _prompt_workspace(cli):
    """Interactive workspace selection"""
    # This would fetch available workspaces from API
    cli.dprint("Available workspaces: [would be fetched from API]", plain=True)
    return _prompt_input(cli, "Workspace ID")


def _prompt_advanced_options(cli):
    """Advanced configuration options"""
    advanced = {}
    
    if _prompt_yes_no(cli, "Set scan timeout?", False):
        timeout = _prompt_input(cli, "Timeout (minutes)", "60")
        try:
            advanced['timeout'] = int(timeout) * 60  # Convert to seconds
        except ValueError:
            pass
    
    if _prompt_yes_no(cli, "Set custom user agent?", False):
        user_agent = _prompt_input(cli, "User agent")
        if user_agent:
            advanced['user_agent'] = user_agent
    
    return advanced


def _create_scan_from_config(cli, scan_config):
    """Create scan from wizard configuration"""
    try:
        base_url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001')
        
        if 'workspace' in scan_config:
            workspace = scan_config.pop('workspace')
            url = f"{base_url}/api/workspaces/{workspace}/scans"
        else:
            url = f"{base_url}/api/scans"
        
        resp = cli.request(url, post=scan_config)
        if resp:
            try:
                data = json.loads(resp)
                scan_id = data.get('id', data.get('scan_id'))
                cli.dprint(f"Scan created successfully! ID: {scan_id}", plain=True)
            except:
                cli.dprint("Scan created successfully!", plain=True)
        else:
            cli.edprint("Failed to create scan")
            
    except Exception as e:
        cli.edprint(f"Failed to create scan: {e}")


def enhanced_help_command(cli, line):
    """Enhanced help with search and categories. Usage: help [search_term] [--category]"""
    args = shlex.split(line)
    search_term = args[0] if args else None
    show_categories = '--category' in args
    
    if show_categories:
        _show_command_categories(cli)
        return
    
    if search_term:
        _search_commands(cli, search_term)
    else:
        _show_enhanced_help(cli)


def _show_command_categories(cli):
    """Show commands organized by categories"""
    categories = {
        "Scan Management": [
            "start", "stop", "scans", "scaninfo", "delete"
        ],
        "Workspace Operations": [
            "workspaces", "workspace_create", "workspace_delete", "workspace_info"
        ],
        "Data Export": [
            "export", "batch_export", "export_logs"
        ],
        "Monitoring": [
            "monitor", "watch_scans", "logs_stream"
        ],
        "Correlation Analysis": [
            "correlations", "correlation_rules", "correlation_summary"
        ],
        "Configuration": [
            "set", "config", "modules", "types"
        ],
        "Interactive Tools": [
            "scan_wizard", "help", "find"
        ]
    }
    
    cli.dprint("SpiderFoot CLI Commands by Category", plain=True)
    cli.dprint("=" * 40, plain=True)
    
    for category, commands in categories.items():
        cli.dprint(f"\n{category}:", plain=True)
        for cmd in commands:
            help_text = cli.registry.help(cmd) if hasattr(cli, 'registry') else "No description"
            cli.dprint(f"  {cmd:<20} - {help_text[:50]}...", plain=True)


def _search_commands(cli, search_term):
    """Search commands by term"""
    cli.dprint(f"Commands matching '{search_term}':", plain=True)
    cli.dprint("-" * 30, plain=True)
    
    # This would search through registered commands
    # For now, just show a placeholder
    cli.dprint("Search functionality would be implemented here", plain=True)


def _show_enhanced_help(cli):
    """Show enhanced help overview"""
    cli.dprint("SpiderFoot CLI - Enhanced Help", plain=True)
    cli.dprint("=" * 35, plain=True)
    cli.dprint("Available help options:", plain=True)
    cli.dprint("  help [command]     - Get help for specific command", plain=True)
    cli.dprint("  help --category    - Show commands by category", plain=True)
    cli.dprint("  help [search]      - Search commands", plain=True)
    cli.dprint("  scan_wizard        - Interactive scan creation", plain=True)
    cli.dprint("\nTip: Use TAB completion for commands and arguments!", plain=True)


def smart_completion_command(cli, line):
    """Provide intelligent command completion and suggestions"""
    # This would integrate with the CLI's completion system
    # For now, just demonstrate the concept
    args = shlex.split(line)
    if not args:
        cli.dprint("Smart completion would suggest commands here", plain=True)
        return
    
    partial_command = args[0]
    suggestions = _get_command_suggestions(cli, partial_command)
    
    if suggestions:
        cli.dprint(f"Suggestions for '{partial_command}':", plain=True)
        for suggestion in suggestions:
            cli.dprint(f"  {suggestion}", plain=True)
    else:
        cli.dprint(f"No suggestions found for '{partial_command}'", plain=True)


def _get_command_suggestions(cli, partial):
    """Get command suggestions based on partial input"""
    # This would use fuzzy matching against available commands
    all_commands = [
        "start", "stop", "scans", "scaninfo", "delete",
        "workspaces", "workspace_create", "workspace_delete",
        "export", "monitor", "correlations", "help"
    ]
    
    # Simple prefix matching for demonstration
    suggestions = [cmd for cmd in all_commands if cmd.startswith(partial)]
    
    # Add fuzzy matching suggestions
    import difflib
    fuzzy_matches = difflib.get_close_matches(partial, all_commands, n=3, cutoff=0.6)
    
    # Combine and deduplicate
    all_suggestions = list(dict.fromkeys(suggestions + fuzzy_matches))
    return all_suggestions[:5]  # Limit to 5 suggestions


def register(registry):
    """Register all interactive enhancement commands"""
    registry.register("scan_wizard", interactive_scan_wizard, 
                     help_text="Interactive wizard for creating complex scans")
    registry.register("help", enhanced_help_command, 
                     help_text="Enhanced help with search and categories")
    registry.register("complete", smart_completion_command, 
                     help_text="Smart command completion and suggestions")
