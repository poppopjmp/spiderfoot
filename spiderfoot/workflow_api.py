"""SpiderFoot Workflow API.

This module provides RESTful API endpoints for workflow functionality,
workspace management, and MCP integration.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from flask import Flask, request, jsonify, abort
from functools import wraps

from spiderfoot import SpiderFootDb, SpiderFootHelpers
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot.workflow import SpiderFootWorkflow
from spiderfoot.mcp_integration import SpiderFootMCPClient, CTIReportExporter


class SpiderFootWorkflowAPI:
    """RESTful API for SpiderFoot workflow functionality."""
    
    def __init__(self, config: dict, app: Flask = None):
        """Initialize workflow API.
        
        Args:
            config: SpiderFoot configuration
            app: Flask application instance
        """
        self.config = config
        self.db = SpiderFootDb(config)
        self.log = logging.getLogger("spiderfoot.workflow_api")
        
        if app is None:
            app = Flask(__name__)
        self.app = app
        
        # Register API routes
        self._register_routes()
    
    def _register_routes(self):
        """Register all API routes."""
        
        # Workspace management routes
        self.app.route('/api/workspaces', methods=['GET'])(self.list_workspaces)
        self.app.route('/api/workspaces', methods=['POST'])(self.create_workspace)
        self.app.route('/api/workspaces/<workspace_id>', methods=['GET'])(self.get_workspace)
        self.app.route('/api/workspaces/<workspace_id>', methods=['PUT'])(self.update_workspace)
        self.app.route('/api/workspaces/<workspace_id>', methods=['DELETE'])(self.delete_workspace)
        self.app.route('/api/workspaces/<workspace_id>/summary', methods=['GET'])(self.get_workspace_summary)
        self.app.route('/api/workspaces/<workspace_id>/clone', methods=['POST'])(self.clone_workspace)
        self.app.route('/api/workspaces/<workspace_id>/merge', methods=['POST'])(self.merge_workspace)
        
        # Target management routes
        self.app.route('/api/workspaces/<workspace_id>/targets', methods=['GET'])(self.get_targets)
        self.app.route('/api/workspaces/<workspace_id>/targets', methods=['POST'])(self.add_target)
        self.app.route('/api/workspaces/<workspace_id>/targets/<target_id>', methods=['DELETE'])(self.remove_target)
        
        # Scan management routes
        self.app.route('/api/workspaces/<workspace_id>/scans', methods=['GET'])(self.get_scans)
        self.app.route('/api/workspaces/<workspace_id>/scans/import', methods=['POST'])(self.import_scans)
        self.app.route('/api/workspaces/<workspace_id>/scans/<scan_id>', methods=['DELETE'])(self.remove_scan)
        
        # Workflow routes
        self.app.route('/api/workspaces/<workspace_id>/workflows', methods=['POST'])(self.start_workflow)
        self.app.route('/api/workspaces/<workspace_id>/workflows/<workflow_id>/status', methods=['GET'])(self.get_workflow_status)
        self.app.route('/api/workspaces/<workspace_id>/workflows/<workflow_id>/stop', methods=['POST'])(self.stop_workflow)
        
        # Multi-target scanning routes
        self.app.route('/api/workspaces/<workspace_id>/multi-scan', methods=['POST'])(self.start_multi_target_scan)
        self.app.route('/api/workspaces/<workspace_id>/correlations', methods=['POST'])(self.run_correlation)
        self.app.route('/api/workspaces/<workspace_id>/correlations', methods=['GET'])(self.get_correlations)
        
        # MCP and CTI routes
        self.app.route('/api/workspaces/<workspace_id>/cti-reports', methods=['POST'])(self.generate_cti_report)
        self.app.route('/api/workspaces/<workspace_id>/cti-reports', methods=['GET'])(self.list_cti_reports)
        self.app.route('/api/workspaces/<workspace_id>/cti-reports/<report_id>', methods=['GET'])(self.get_cti_report)
        self.app.route('/api/workspaces/<workspace_id>/cti-reports/<report_id>/export', methods=['POST'])(self.export_cti_report)
        
        # Search and query routes
        self.app.route('/api/workspaces/<workspace_id>/search', methods=['POST'])(self.search_events)
        self.app.route('/api/workspaces/<workspace_id>/export', methods=['POST'])(self.export_workspace)
        
        # MCP server management
        self.app.route('/api/mcp/test-connection', methods=['GET'])(self.test_mcp_connection)
        self.app.route('/api/mcp/templates', methods=['GET'])(self.list_mcp_templates)
    
    def _get_workspace(self, workspace_id: str) -> SpiderFootWorkspace:
        """Get workspace by ID or abort with 404."""
        try:
            workspace = SpiderFootWorkspace(self.config, workspace_id)
            return workspace
        except ValueError:
            abort(404, description=f"Workspace {workspace_id} not found")
    
    def _handle_api_error(self, func):
        """Decorator to handle API errors."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
            except Exception as e:
                self.log.error(f"API error in {func.__name__}: {e}")
                return jsonify({'error': 'Internal server error'}), 500
        return wrapper
    
    # Workspace management endpoints
    
    def list_workspaces(self):
        """List all workspaces."""
        try:
            workspaces = SpiderFootWorkspace.list_workspaces(self.config)
            return jsonify({'workspaces': workspaces})
        except Exception as e:
            self.log.error(f"Failed to list workspaces: {e}")
            return jsonify({'error': 'Failed to list workspaces'}), 500
    
    def create_workspace(self):
        """Create a new workspace."""
        try:
            data = request.get_json()
            name = data.get('name')
            description = data.get('description', '')
            
            workspace = SpiderFootWorkspace(self.config, name=name)
            workspace.description = description
            workspace.save_workspace()
            
            return jsonify({
                'workspace_id': workspace.workspace_id,
                'name': workspace.name,
                'description': workspace.description,
                'created_time': workspace.created_time
            }), 201
        except Exception as e:
            self.log.error(f"Failed to create workspace: {e}")
            return jsonify({'error': 'Failed to create workspace'}), 500
    
    def get_workspace(self, workspace_id: str):
        """Get workspace details."""
        workspace = self._get_workspace(workspace_id)
        
        return jsonify({
            'workspace_id': workspace.workspace_id,
            'name': workspace.name,
            'description': workspace.description,
            'created_time': workspace.created_time,
            'modified_time': workspace.modified_time,
            'targets': workspace.targets,
            'scans': workspace.scans,
            'metadata': workspace.metadata
        })
    
    def update_workspace(self, workspace_id: str):
        """Update workspace details."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        
        if 'name' in data:
            workspace.name = data['name']
        if 'description' in data:
            workspace.description = data['description']
        
        workspace.save_workspace()
        
        return jsonify({'message': 'Workspace updated successfully'})
    
    def delete_workspace(self, workspace_id: str):
        """Delete a workspace."""
        workspace = self._get_workspace(workspace_id)
        workspace.delete_workspace()
        
        return jsonify({'message': 'Workspace deleted successfully'})
    
    def get_workspace_summary(self, workspace_id: str):
        """Get workspace summary with statistics."""
        workspace = self._get_workspace(workspace_id)
        summary = workspace.get_workspace_summary()
        
        return jsonify(summary)
    
    def clone_workspace(self, workspace_id: str):
        """Clone a workspace."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        new_name = data.get('name')
        
        cloned_workspace = workspace.clone_workspace(new_name)
        
        return jsonify({
            'workspace_id': cloned_workspace.workspace_id,
            'name': cloned_workspace.name,
            'message': 'Workspace cloned successfully'
        }), 201
    
    def merge_workspace(self, workspace_id: str):
        """Merge another workspace into this one."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        source_workspace_id = data.get('source_workspace_id')
        
        if not source_workspace_id:
            return jsonify({'error': 'source_workspace_id is required'}), 400
        
        source_workspace = self._get_workspace(source_workspace_id)
        success = workspace.merge_workspace(source_workspace)
        
        if success:
            return jsonify({'message': 'Workspaces merged successfully'})
        else:
            return jsonify({'error': 'Failed to merge workspaces'}), 500
    
    # Target management endpoints
    
    def get_targets(self, workspace_id: str):
        """Get workspace targets."""
        workspace = self._get_workspace(workspace_id)
        return jsonify({'targets': workspace.get_targets()})
    
    def add_target(self, workspace_id: str):
        """Add target to workspace."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        
        target = data.get('target')
        target_type = data.get('target_type')
        metadata = data.get('metadata', {})
        
        if not target:
            return jsonify({'error': 'target is required'}), 400
        
        try:
            target_id = workspace.add_target(target, target_type, metadata)
            return jsonify({
                'target_id': target_id,
                'message': 'Target added successfully'
            }), 201
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
    
    def remove_target(self, workspace_id: str, target_id: str):
        """Remove target from workspace."""
        workspace = self._get_workspace(workspace_id)
        success = workspace.remove_target(target_id)
        
        if success:
            return jsonify({'message': 'Target removed successfully'})
        else:
            return jsonify({'error': 'Target not found'}), 404
    
    # Scan management endpoints
    
    def get_scans(self, workspace_id: str):
        """Get workspace scans."""
        workspace = self._get_workspace(workspace_id)
        return jsonify({'scans': workspace.get_scans()})
    
    def import_scans(self, workspace_id: str):
        """Import scans into workspace."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        
        scan_ids = data.get('scan_ids', [])
        metadata = data.get('metadata', {})
        
        if not scan_ids:
            return jsonify({'error': 'scan_ids is required'}), 400
        
        if isinstance(scan_ids, str):
            # Single scan import
            success = workspace.import_single_scan(scan_ids, metadata)
            if success:
                return jsonify({'message': 'Scan imported successfully'})
            else:
                return jsonify({'error': 'Failed to import scan'}), 500
        else:
            # Bulk import
            results = workspace.bulk_import_scans(scan_ids, metadata)
            return jsonify({
                'results': results,
                'message': f'Import completed: {sum(results.values())} of {len(results)} scans imported'
            })
    
    def remove_scan(self, workspace_id: str, scan_id: str):
        """Remove scan from workspace."""
        workspace = self._get_workspace(workspace_id)
        success = workspace.remove_scan(scan_id)
        
        if success:
            return jsonify({'message': 'Scan removed successfully'})
        else:
            return jsonify({'error': 'Scan not found'}), 404
    
    # Workflow endpoints
    
    def start_workflow(self, workspace_id: str):
        """Start a new workflow."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        
        workflow_type = data.get('type', 'multi_target_scan')
        
        workflow = workspace.create_workflow()
        
        # Store workflow reference (in production, use proper storage)
        if not hasattr(self, '_active_workflows'):
            self._active_workflows = {}
        self._active_workflows[workflow.workflow_id] = workflow
        
        return jsonify({
            'workflow_id': workflow.workflow_id,
            'type': workflow_type,
            'status': 'CREATED',
            'message': 'Workflow created successfully'
        }), 201
    
    def get_workflow_status(self, workspace_id: str, workflow_id: str):
        """Get workflow status."""
        if not hasattr(self, '_active_workflows') or workflow_id not in self._active_workflows:
            return jsonify({'error': 'Workflow not found'}), 404
        
        workflow = self._active_workflows[workflow_id]
        status = workflow.get_scan_status()
        
        return jsonify({
            'workflow_id': workflow_id,
            'status': status,
            'active_scans': workflow.active_scans
        })
    
    def stop_workflow(self, workspace_id: str, workflow_id: str):
        """Stop a workflow."""
        if not hasattr(self, '_active_workflows') or workflow_id not in self._active_workflows:
            return jsonify({'error': 'Workflow not found'}), 404
        
        workflow = self._active_workflows[workflow_id]
        workflow.cleanup_workflow()
        
        del self._active_workflows[workflow_id]
        
        return jsonify({'message': 'Workflow stopped successfully'})
    
    # Multi-target scanning endpoints
    
    def start_multi_target_scan(self, workspace_id: str):
        """Start multi-target scan."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        
        targets = data.get('targets', [])
        modules = data.get('modules', [])
        scan_options = data.get('scan_options', {})
        
        if not targets:
            return jsonify({'error': 'targets is required'}), 400
        if not modules:
            return jsonify({'error': 'modules is required'}), 400
        
        workflow = workspace.create_workflow()
        
        try:
            scan_ids = workflow.start_multi_target_scan(targets, modules, scan_options)
            
            # Store workflow reference
            if not hasattr(self, '_active_workflows'):
                self._active_workflows = {}
            self._active_workflows[workflow.workflow_id] = workflow
            
            return jsonify({
                'workflow_id': workflow.workflow_id,
                'scan_ids': scan_ids,
                'message': f'Started {len(scan_ids)} scans'
            }), 201
            
        except Exception as e:
            self.log.error(f"Failed to start multi-target scan: {e}")
            return jsonify({'error': str(e)}), 500
    
    def run_correlation(self, workspace_id: str):
        """Run cross-correlation analysis."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        
        scan_ids = data.get('scan_ids')
        correlation_rules = data.get('correlation_rules')
        
        workflow = workspace.create_workflow()
        
        try:
            results = workflow.run_cross_correlation(scan_ids, correlation_rules)
            
            return jsonify({
                'correlation_results': results,
                'message': f'Found {len(results)} correlation results'
            })
            
        except Exception as e:
            self.log.error(f"Correlation analysis failed: {e}")
            return jsonify({'error': str(e)}), 500
    
    def get_correlations(self, workspace_id: str):
        """Get workspace correlations."""
        workspace = self._get_workspace(workspace_id)
        correlations = workspace.metadata.get('correlations', [])
        
        return jsonify({'correlations': correlations})
    
    # MCP and CTI endpoints
    
    async def generate_cti_report(self, workspace_id: str):
        """Generate CTI report using MCP."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        
        report_type = data.get('report_type', 'threat_assessment')
        custom_prompt = data.get('custom_prompt')
        
        try:
            report = await workspace.generate_cti_report(report_type, custom_prompt)
            
            return jsonify({
                'report_id': report['report_id'],
                'report_type': report['report_type'],
                'generated_time': report['generated_time'],
                'message': 'CTI report generated successfully'
            }), 201
            
        except Exception as e:
            self.log.error(f"CTI report generation failed: {e}")
            return jsonify({'error': str(e)}), 500
    
    def list_cti_reports(self, workspace_id: str):
        """List CTI reports for workspace."""
        workspace = self._get_workspace(workspace_id)
        reports = workspace.metadata.get('cti_reports', [])
        
        return jsonify({'cti_reports': reports})
    
    def get_cti_report(self, workspace_id: str, report_id: str):
        """Get specific CTI report."""
        workspace = self._get_workspace(workspace_id)
        report_key = f'cti_report_{report_id}'
        
        if report_key not in workspace.metadata:
            return jsonify({'error': 'Report not found'}), 404
        
        report = workspace.metadata[report_key]
        return jsonify(report)
    
    def export_cti_report(self, workspace_id: str, report_id: str):
        """Export CTI report in specified format."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        
        export_format = data.get('format', 'json')
        output_path = data.get('output_path')
        
        report_key = f'cti_report_{report_id}'
        if report_key not in workspace.metadata:
            return jsonify({'error': 'Report not found'}), 404
        
        report = workspace.metadata[report_key]
        
        try:
            exporter = CTIReportExporter()
            file_path = exporter.export_report(report, export_format, output_path)
            
            return jsonify({
                'file_path': file_path,
                'format': export_format,
                'message': 'Report exported successfully'
            })
            
        except Exception as e:
            self.log.error(f"Report export failed: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Search and query endpoints
    
    def search_events(self, workspace_id: str):
        """Search events across workspace scans."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        
        query = data.get('query', '')
        event_types = data.get('event_types')
        scan_ids = data.get('scan_ids')
        
        if not query:
            return jsonify({'error': 'query is required'}), 400
        
        try:
            results = workspace.search_events(query, event_types, scan_ids)
            
            return jsonify({
                'results': results,
                'count': len(results),
                'query': query
            })
            
        except Exception as e:
            self.log.error(f"Event search failed: {e}")
            return jsonify({'error': str(e)}), 500
    
    def export_workspace(self, workspace_id: str):
        """Export workspace data."""
        workspace = self._get_workspace(workspace_id)
        data = request.get_json()
        
        export_format = data.get('format', 'json')
        
        try:
            exported_data = workspace.export_data(export_format)
            
            return jsonify({
                'data': exported_data,
                'format': export_format,
                'exported_time': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            self.log.error(f"Workspace export failed: {e}")
            return jsonify({'error': str(e)}), 500
    
    # MCP server management endpoints
    
    async def test_mcp_connection(self):
        """Test MCP server connection."""
        try:
            mcp_client = SpiderFootMCPClient(self.config)
            success = await mcp_client.test_mcp_connection()
            
            return jsonify({
                'connected': success,
                'server_url': mcp_client.server_url,
                'message': 'Connection successful' if success else 'Connection failed'
            })
            
        except Exception as e:
            self.log.error(f"MCP connection test failed: {e}")
            return jsonify({'error': str(e)}), 500
    
    async def list_mcp_templates(self):
        """List available MCP report templates."""
        try:
            mcp_client = SpiderFootMCPClient(self.config)
            templates = await mcp_client.list_available_templates()
            
            return jsonify({'templates': templates})
            
        except Exception as e:
            self.log.error(f"Failed to list MCP templates: {e}")
            return jsonify({'error': str(e)}), 500


def create_workflow_api(config: dict) -> Flask:
    """Create Flask application with workflow API.
    
    Args:
        config: SpiderFoot configuration
        
    Returns:
        Flask application
    """
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False
    
    # Enable CORS if needed
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
    
    # Initialize API
    workflow_api = SpiderFootWorkflowAPI(config, app)
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'version': '1.0.0',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    return app
