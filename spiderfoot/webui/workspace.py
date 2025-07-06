import cherrypy
import json
from mako.template import Template
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot import __version__

class WorkspaceEndpoints:
    @cherrypy.expose
    def workspaces(self):
        """Show workspace management page.

        Returns:
            str: Workspace management page HTML
        """
        templ = Template(filename='spiderfoot/templates/workspaces.tmpl', lookup=self.lookup)
        return templ.render(pageid='WORKSPACES', docroot=self.docroot, version=__version__)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacelist(self):
        try:
            workspaces = SpiderFootWorkspace.list_workspaces(self.config)
            return workspaces
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacecreate(self, name, description=''):
        try:
            ws = SpiderFootWorkspace(self.config, name=name)
            ws.description = description
            ws.save_workspace()
            return {"success": True, "workspace_id": ws.workspace_id}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspaceget(self, workspace_id):
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
    def workspaceupdate(self, workspace_id, name=None, description=None):
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
    def workspacedelete(self, workspace_id):
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            ws.delete_workspace()
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacesummary(self, workspace_id):
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            return ws.get_workspace_summary()
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspaceaddtarget(self, workspace_id, target, target_type=None):
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            target_id = ws.add_target(target, target_type)
            return {"success": True, "target_id": target_id}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspaceremovetarget(self, workspace_id, target_id):
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            ok = ws.remove_target(target_id)
            return {"success": ok}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspaceimportscans(self, workspace_id, scan_ids):
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            scan_id_list = [s.strip() for s in scan_ids.split(',') if s.strip()]
            results = ws.bulk_import_scans(scan_id_list)
            return {"success": True, "results": results}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacemultiscan(self, workspace_id, targets, modules, scan_name_prefix, enable_correlation='false'):
        self.log.info(f"[MULTISCAN] Starting multi-target scan for workspace: {workspace_id}")
        self.log.debug(f"[MULTISCAN] Input parameters - targets: {targets}, modules: {modules}, prefix: {scan_name_prefix}")
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
    def workspacemcpreport(self, workspace_id, report_type, format='json', include_correlations='true', include_threat_intel='true', include_recommendations='true', tlp_level='amber'):
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            report = ws.generate_mcp_report(report_type, format, include_correlations, include_threat_intel, include_recommendations, tlp_level)
            return {"success": True, "download_url": report.get('download_url', ''), "error": report.get('error', '')}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacetiming(self, workspace_id, timezone=None, default_start_time=None, retention_period=None, auto_scheduling=None, business_hours_only=None, enable_throttling=None, business_start=None, business_end=None):
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            timing = ws.update_timing_config(timezone, default_start_time, retention_period, auto_scheduling, business_hours_only, enable_throttling, business_start, business_end)
            return {"success": True, "timing": timing}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacescanresults(self, workspace_id, scan_id=None, event_type=None, limit=100):
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            results = ws.get_scan_results(scan_id=scan_id, event_type=event_type, limit=limit)
            return {"results": results}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacescancorrelations(self, workspace_id):
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            correlations = ws.get_cross_scan_correlations()
            return {"correlations": correlations}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    def workspacedetails(self, workspace_id):
        try:
            ws = SpiderFootWorkspace(self.config, workspace_id=workspace_id)
            
            # Ensure workspace has required attributes
            if not hasattr(ws, 'name') or not ws.name:
                return f"Error: Workspace {workspace_id} not found or has no name"
            
            # For now, return a simple HTML page with the workspace details
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>SpiderFoot - Workspace Details</title>
                <link href="{self.docroot}/static/node_modules/bootstrap/dist/css/bootstrap.min.css" rel="stylesheet">
                <link href="{self.docroot}/static/css/spiderfoot.css" rel="stylesheet">
            </head>
            <body>
                <div class="container-fluid">
                    <nav class="navbar navbar-default">
                        <div class="container-fluid">
                            <div class="navbar-header">
                                <a class="navbar-brand" href="{self.docroot}/">SpiderFoot</a>
                            </div>
                        </div>
                    </nav>
                    
                    <div class="row">
                        <div class="col-md-12">
                            <ol class="breadcrumb">
                                <li><a href="{self.docroot}/">Home</a></li>
                                <li><a href="{self.docroot}/workspaces">Workspaces</a></li>
                                <li class="active">{ws.name}</li>
                            </ol>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-12">
                            <h1>{ws.name} <small>{ws.description}</small></h1>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-3">
                            <div class="panel panel-primary">
                                <div class="panel-heading">
                                    <h3 class="panel-title">Targets</h3>
                                </div>
                                <div class="panel-body text-center">
                                    <h2>{len(ws.targets) if hasattr(ws, 'targets') and ws.targets else 0}</h2>
                                    <p>Total Targets</p>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-3">
                            <div class="panel panel-success">
                                <div class="panel-heading">
                                    <h3 class="panel-title">Scans</h3>
                                </div>
                                <div class="panel-body text-center">
                                    <h2>{len(ws.scans) if hasattr(ws, 'scans') and ws.scans else 0}</h2>
                                    <p>Total Scans</p>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-3">
                            <div class="panel panel-info">
                                <div class="panel-heading">
                                    <h3 class="panel-title">Created</h3>
                                </div>
                                <div class="panel-body text-center">
                                    <h4>{ws.created_time if hasattr(ws, 'created_time') else 'Unknown'}</h4>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-3">
                            <div class="panel panel-warning">
                                <div class="panel-heading">
                                    <h3 class="panel-title">Last Modified</h3>
                                </div>
                                <div class="panel-body text-center">
                                    <h4>{ws.modified_time if hasattr(ws, 'modified_time') else 'Unknown'}</h4>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-12">
                            <h3>Workspace ID: {workspace_id}</h3>
                            <p>This workspace contains {len(ws.targets) if hasattr(ws, 'targets') and ws.targets else 0} targets and {len(ws.scans) if hasattr(ws, 'scans') and ws.scans else 0} scans.</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return html
            
        except Exception as e:
            import traceback
            return f"Error loading workspace details: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"

    @cherrypy.expose
    def workspacereportdownload(self, report_id, workspace_id, format='json'):
        try:
            # Placeholder: implement report download logic
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=workspace-{workspace_id}-report.{format}"
            cherrypy.response.headers['Content-Type'] = f"application/{format}"
            cherrypy.response.headers['Pragma'] = 'no-cache'
            return "{}"
        except Exception as e:
            return str(e)
