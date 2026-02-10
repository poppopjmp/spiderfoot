"""WebUI endpoints for workspace creation, listing, and management."""

from __future__ import annotations

import cherrypy
import json
from mako.template import Template
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot import __version__

class WorkspaceEndpoints:
    """WebUI endpoints for workspace management."""
    @cherrypy.expose
    def workspaces(self) -> str:
        """Show workspace management page.

        Returns:
            str: Workspace management page HTML
        """
        # Generate CSRF token for the session
        csrf_token = None
        try:
            # Try to get CSRF token from security middleware
            if hasattr(cherrypy, 'session') and hasattr(cherrypy.tools, 'csrf'):
                from spiderfoot.csrf_protection import csrf_token as get_csrf_token
                csrf_token = get_csrf_token()
        except Exception as e:
            self.log.warning("Could not generate CSRF token: %s", e)
            csrf_token = "disabled"

        templ = Template(filename='spiderfoot/templates/workspaces.tmpl', lookup=self.lookup)
        return templ.render(
            pageid='WORKSPACES',
            docroot=self.docroot,
            version=__version__,
            csrf_token=csrf_token
        )

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacelist(self) -> list | dict:
        """List all available workspaces as JSON."""
        try:
            workspaces = SpiderFootWorkspace.list_workspaces(self.config)
            return workspaces
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacecreate(self, name: str, description: str = '') -> dict:
        """Create a new workspace with the given name and description."""
        try:
            ws = SpiderFootWorkspace(self.config, name=name)
            ws.description = description
            ws.save_workspace()
            return {"success": True, "workspace_id": ws.workspace_id}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspaceget(self, workspace_id: str) -> dict:
        """Retrieve workspace details including targets, scans, and metadata."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            return {
                "workspace_id": ws.workspace_id,
                "name": ws.name,
                "description": ws.description,
                "created_time": ws.created_time,
                "modified_time": ws.modified_time,
                "targets": ws.get_targets(),
                "scans": ws.get_scans(),
                "metadata": ws.metadata
            }
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspaceupdate(self, workspace_id: str, name: str | None = None, description: str | None = None) -> dict:
        """Update workspace name and description."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            if name:
                ws.name = name
            if description:
                ws.description = description
            ws.save_workspace()
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacedelete(self, workspace_id: str) -> dict:
        """Delete a workspace by its ID."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            ws.delete_workspace()
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacesummary(self, workspace_id: str) -> dict:
        """Return a summary of the workspace including scan statistics."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            return ws.get_workspace_summary()
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspaceaddtarget(self, workspace_id: str, target: str, target_type: str | None = None) -> dict:
        """Add a scan target to the specified workspace."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            target_id = ws.add_target(target, target_type)
            return {"success": True, "target_id": target_id}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspaceremovetarget(self, workspace_id: str, target_id: str) -> dict:
        """Remove a scan target from the specified workspace."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            ok = ws.remove_target(target_id)
            return {"success": ok}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspaceimportscans(self, workspace_id: str, scan_ids: str) -> dict:
        """Import existing scans into a workspace by scan IDs."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            scan_id_list = [s.strip() for s in scan_ids.split(',') if s.strip()]
            results = ws.bulk_import_scans(scan_id_list)
            return {"success": True, "results": results}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacemultiscan(self, workspace_id: str, targets: str, modules: str, scan_name_prefix: str, enable_correlation: str = 'false') -> dict:
        """Launch scans against multiple targets in a workspace."""
        self.log.info("[MULTISCAN] Starting multi-target scan for workspace: %s", workspace_id)
        self.log.debug("[MULTISCAN] Input parameters - targets: %s, modules: %s, prefix: %s", targets, modules, scan_name_prefix)
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            target_list = [t.strip() for t in targets.split(',') if t.strip()]
            module_list = [m.strip() for m in modules.split(',') if m.strip()]
            results = ws.start_multiscan(target_list, module_list, scan_name_prefix, enable_correlation)
            return {"success": True, "results": results}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacemcpreport(self, workspace_id: str, report_type: str, format: str = 'json', include_correlations: str = 'true', include_threat_intel: str = 'true', include_recommendations: str = 'true', tlp_level: str = 'amber') -> dict:
        """Generate an MCP-format report for the specified workspace."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            report = ws.generate_mcp_report(report_type, format, include_correlations, include_threat_intel, include_recommendations, tlp_level)
            return {"success": True, "download_url": report.get('download_url', ''), "error": report.get('error', '')}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacetiming(self, workspace_id: str, timezone: str | None = None, default_start_time: str | None = None, retention_period: str | None = None, auto_scheduling: str | None = None, business_hours_only: str | None = None, enable_throttling: str | None = None, business_start: str | None = None, business_end: str | None = None) -> dict:
        """Update scan timing and scheduling configuration for a workspace."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            timing = ws.update_timing_config(timezone, default_start_time, retention_period, auto_scheduling, business_hours_only, enable_throttling, business_start, business_end)
            return {"success": True, "timing": timing}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacescanresults(self, workspace_id: str, scan_id: str | None = None, event_type: str | None = None, limit: str | int = 100) -> dict:
        """Retrieve scan results for a workspace, optionally filtered by scan or event type."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            results = ws.get_scan_results(scan_id=scan_id, event_type=event_type, limit=limit)
            return {"results": results}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacescancorrelations(self, workspace_id: str) -> dict:
        """Retrieve cross-scan correlations for a workspace."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            correlations = ws.get_cross_scan_correlations()
            return {"correlations": correlations}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    def workspacedetails(self, workspace_id: str) -> str:
        """Render the workspace details page with scans and metadata."""
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)

            # Ensure workspace has required attributes
            if not hasattr(ws, 'name') or not ws.name:
                return f"Error: Workspace {workspace_id} not found or has no name"

            # Generate CSRF token for the session
            csrf_token = None
            try:
                # Try to get CSRF token from security middleware
                if hasattr(cherrypy, 'session') and hasattr(cherrypy.tools, 'csrf'):
                    from spiderfoot.csrf_protection import csrf_token as get_csrf_token
                    csrf_token = get_csrf_token()
            except Exception as e:
                self.log.warning("Could not generate CSRF token: %s", e)
                csrf_token = "disabled"

            # Load scans for the workspace
            scan_details = []
            try:
                scan_details = ws.get_scans()
            except Exception as e:
                self.log.warning("Could not load scans for workspace %s: %s", workspace_id, e)

            # Use the template
            templ = Template(filename='spiderfoot/templates/workspace_details.tmpl', lookup=self.lookup)
            return templ.render(
                workspace=ws,
                scan_details=scan_details,
                docroot=self.docroot,
                version=__version__,
                csrf_token=csrf_token
            )
        except Exception as e:
            return f"Error loading workspace details: {str(e)}"

    @cherrypy.expose
    def workspacereportdownload(self, report_id: str, workspace_id: str, format: str = 'json') -> str:
        """Download a generated workspace report by report ID."""
        try:
            cherrypy.response.headers['Content-Type'] = 'application/json'
            raise cherrypy.HTTPError(501, "Report download not yet implemented")
        except cherrypy.HTTPError:
            raise
        except Exception as e:
            return str(e)
