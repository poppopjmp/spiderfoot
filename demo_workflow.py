#!/usr/bin/env python3
"""Simple demonstration of SpiderFoot Workflow functionality."""

import json
from spiderfoot import SpiderFootDb
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot.workflow_config import WorkflowConfig

def demo_workflow():
    """Demonstrate workflow functionality."""
    
    print("🕷️  SpiderFoot Workflow Demo")
    print("=" * 50)
      # Load configuration
    config = {
        '__database': ':memory:',
        '_internettlds': ['com', 'org', 'net'],
        '_maxthreads': 3,
        '__correlationrules__': []
    }
    
    print(f"✅ Configuration loaded")
    
    # Create workspace
    workspace = SpiderFootWorkspace(config, name="Demo Workspace")
    workspace.description = "Demonstration of workflow functionality"
    
    print(f"✅ Created workspace: {workspace.workspace_id}")
    
    # Add targets
    target1_id = workspace.add_target("example.com", "DOMAIN_NAME")
    target2_id = workspace.add_target("test.example.com", "INTERNET_NAME")
    
    print(f"✅ Added targets:")
    print(f"   - example.com ({target1_id})")
    print(f"   - test.example.com ({target2_id})")
    
    # Test single scan import (mock scan)
    # In a real scenario, these would be actual scan IDs
    print(f"✅ Workspace has {len(workspace.get_targets())} targets")
    print(f"✅ Workspace has {len(workspace.get_scans())} scans")
    
    # Get workspace summary
    summary = workspace.get_workspace_summary()
    print(f"✅ Workspace summary:")
    print(f"   - Target count: {summary['statistics']['target_count']}")
    print(f"   - Scan count: {summary['statistics']['scan_count']}")
    print(f"   - Targets by type: {summary['targets_by_type']}")
    
    # Test workspace cloning
    cloned_workspace = workspace.clone_workspace("Demo Workspace Clone")
    print(f"✅ Cloned workspace: {cloned_workspace.workspace_id}")
    print(f"   - Clone has {len(cloned_workspace.get_targets())} targets")
    
    # Test export
    exported_data = workspace.export_data()
    print(f"✅ Exported workspace data")
    print(f"   - Workspace info: {exported_data['workspace_info']['name']}")
    print(f"   - Targets exported: {len(exported_data['targets'])}")
    
    # List all workspaces
    workspaces = SpiderFootWorkspace.list_workspaces(config)
    print(f"✅ Total workspaces: {len(workspaces)}")
    
    print("\n🎉 Demo completed successfully!")
    return True

if __name__ == "__main__":
    try:
        demo_workflow()
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
