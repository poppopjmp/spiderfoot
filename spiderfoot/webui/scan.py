from __future__ import annotations

"""WebUI endpoints for scan creation, management, and result viewing."""

import cherrypy
import logging
from copy import deepcopy
from mako.template import Template
from spiderfoot import SpiderFootHelpers, __version__
from spiderfoot.sflib import SpiderFoot
import time
import json

log = logging.getLogger("spiderfoot.webui.scan")
from spiderfoot.scan_service.scanner import startSpiderFootScanner
import multiprocessing as mp

from spiderfoot.scan.scan_state_map import (
    DB_STATUS_ABORTED,
    DB_STATUS_ERROR_FAILED,
    DB_STATUS_FINISHED,
)

class ScanEndpoints:
    """WebUI endpoints for scan management."""
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanopts(self, id: str) -> dict:
        """Return scan options and metadata for a given scan ID."""
        dbh = self._get_dbh()
        ret = dict()
        meta = dbh.scanInstanceGet(id)
        if not meta:
            return self.jsonify_error("404", "Scan not found")
        started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(meta[3])) if meta[3] != 0 else None
        finished = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(meta[4])) if meta[4] != 0 else None
        ret['meta'] = [meta[0], meta[1], meta[2], started, finished, meta[5]]
        ret['config'] = dbh.scanConfigGet(id)
        ret['configdesc'] = dict()
        for key in list(ret['config'].keys()):
            ret['configdesc'][key] = ret['config'][key]
        return ret

    @cherrypy.expose
    def rerunscan(self, id: str) -> str | dict:
        """Re-run a previously completed scan with the same configuration."""
        cfg = deepcopy(self.config)
        dbh = self._get_dbh(cfg)
        info = dbh.scanInstanceGet(id)
        if not info:
            return self.error("Scan not found")
        scanname = info[0]
        scantarget = info[1]
        if not scantarget:
            return self.error("Invalid scan target")
        scanconfig = dbh.scanConfigGet(id)
        if not scanconfig:
            return self.error("Scan config not found")
        modlist = scanconfig['_modulesenabled'].split(',')
        if "sfp__stor_stdout" in modlist:
            modlist.remove("sfp__stor_stdout")
        targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
        if not targetType:
            return self.error("Invalid target type")
        # Start running a new scan
        scanId = SpiderFootHelpers.genScanInstanceId()
        try:
            loggingQueue = getattr(self, 'loggingQueue', None)
            if loggingQueue is None:
                loggingQueue = mp.Queue()
            startSpiderFootScanner(loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg)
        except Exception as e:
            return self.error(str(e))
        timeout = 10  # seconds
        waited = 0
        while dbh.scanInstanceGet(scanId) is None and waited < timeout:
            time.sleep(0.1)
            waited += 0.1
        if dbh.scanInstanceGet(scanId) is None:
            return self.error("Scan did not start in time. Please try again.")
        if cherrypy.request.headers.get('Accept') and 'application/json' in cherrypy.request.headers.get('Accept'):
            return {"scanId": scanId}
        raise cherrypy.HTTPRedirect(f"{self.docroot}/scaninfo?id={scanId}")

    @cherrypy.expose
    def rerunscanmulti(self, ids: str) -> str:
        """Re-run multiple scans specified by comma-separated IDs."""
        import sfwebui
        cfg = deepcopy(self.config)
        dbh = self._get_dbh(cfg)
        scan_ids = ids.split(",")
        errors = []
        for scan_id in scan_ids:
            info = dbh.scanInstanceGet(scan_id)
            if not info:
                errors.append(f"Scan not found: {scan_id}")
                continue
            scanname = info[0]
            scantarget = info[1]
            if not scantarget:
                errors.append(f"Invalid scan target: {scan_id}")
                continue
            scanconfig = dbh.scanConfigGet(scan_id)
            if not scanconfig:
                errors.append(f"Scan config not found: {scan_id}")
                continue
            modlist = scanconfig['_modulesenabled'].split(',')
            if "sfp__stor_stdout" in modlist:
                modlist.remove("sfp__stor_stdout")
            targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
            if not targetType:
                errors.append(f"Invalid target type: {scan_id}")
                continue
            scanId = SpiderFootHelpers.genScanInstanceId()
            try:
                loggingQueue = getattr(self, 'loggingQueue', None)
                if loggingQueue is None:
                    loggingQueue = mp.Queue()
                startSpiderFootScanner(loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg)
                timeout = 10  # seconds
                waited = 0
                while dbh.scanInstanceGet(scanId) is None and waited < timeout:
                    time.sleep(0.1)
                    waited += 0.1
            except Exception as e:
                errors.append(f"{scan_id}: {str(e)}")
        templ = Template(filename='spiderfoot/templates/scanlist.tmpl', lookup=self.lookup)
        return templ.render(
            rerunscans=True, docroot=self.docroot, pageid="SCANLIST",
            version=__version__, errors=errors,
        )

    @cherrypy.expose
    def newscan(self) -> str:
        """Render the new scan creation form."""
        import sfwebui  # for patching Template in tests
        dbh = self._get_dbh()
        types = dbh.eventTypes()

        templ = Template(filename='spiderfoot/templates/newscan.tmpl', lookup=self.lookup)
        return templ.render(pageid='NEWSCAN', types=types, docroot=self.docroot,
                            modules=self.config['__modules__'], scanname="",
                            selectedmods="", scantarget="", version=__version__)

    @cherrypy.expose
    def clonescan(self, id: str) -> str:
        """Render the new scan form pre-filled with settings from an existing scan."""
        import sfwebui  # for patching Template in tests
        dbh = self._get_dbh()
        types = dbh.eventTypes()
        info = dbh.scanInstanceGet(id)
        if not info:
            return self.error("Scan not found")
        scanconfig = dbh.scanConfigGet(id)
        scanname = info[0]
        scantarget = info[1]
        if not scantarget:
            return self.error("Invalid scan target")
        if scanname == "" or scantarget == "" or len(scanconfig) == 0:
            return self.error("Invalid scan config")
        targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
        if targetType is None:
            return self.error("Invalid target type")
        modlist = scanconfig['_modulesenabled'].split(',')
        templ = Template(filename='spiderfoot/templates/newscan.tmpl', lookup=self.lookup)
        return templ.render(pageid='NEWSCAN', types=types, docroot=self.docroot,
                            modules=self.config['__modules__'], selectedmods=modlist,
                            scanname=str(scanname), scantarget=str(scantarget), version=__version__)

    @cherrypy.expose
    def scaninfo(self, id: str) -> str:
        """Display detailed information for a specific scan."""
        import sfwebui
        dbh = self._get_dbh()
        res = dbh.scanInstanceGet(id)
        if res is None:
            return self.error("Scan not found")
        templ = Template(filename='spiderfoot/templates/scaninfo.tmpl', lookup=self.lookup, input_encoding='utf-8')
        return templ.render(
            id=id, name=res[0], status=res[5], docroot=self.docroot,
            version=__version__, pageid="SCANLIST",
        )

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanlist(self) -> list:
        """Return a list of all scan instances with metadata and risk summaries."""
        dbh = self._get_dbh()
        data = dbh.scanInstanceList()
        retdata = []
        for row in data:
            # row: [guid, name, seed_target, created, started, ended, status, element_count]
            scan_id = row[0]
            # Convert timestamps to human-readable format
            row_list = list(row)
            # row[3] = created, row[4] = started, row[5] = ended
            if row_list[3] and row_list[3] != 0:
                row_list[3] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row_list[3]))
            if row_list[4] and row_list[4] != 0:
                row_list[4] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row_list[4]))
            if row_list[5] and row_list[5] != 0:
                row_list[5] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row_list[5]))

            # Get risk summary for this scan
            riskmatrix = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
            try:
                correlations = dbh.scanCorrelationSummary(scan_id, by="risk")
                if correlations:
                    for r in correlations:
                        if r[0] in riskmatrix:
                            riskmatrix[r[0]] = r[1]
            except Exception as e:
                log.debug("Failed to get correlation summary for scan %s: %s", scan_id, e)
            # Append riskmatrix as 9th element
            retdata.append(row_list + [riskmatrix])
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanstatus(self, id: str) -> list | dict:
        """Return the current status and risk summary for a scan."""
        dbh = self._get_dbh()
        data = dbh.scanInstanceGet(id)
        if not data:
            return self.jsonify_error("404", "Scan not found")
        created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data[2]))
        started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data[3]))
        ended = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data[4]))
        riskmatrix = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        correlations = dbh.scanCorrelationSummary(id, by="risk")
        if correlations:
            for row in correlations:
                riskmatrix[row[0]] = row[1]
        return [data[0], data[1], created, started, ended, data[5], riskmatrix]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scansummary(self, id: str, by: str) -> list:
        """Return a summary of scan results grouped by the specified field."""
        retdata = []
        dbh = self._get_dbh()
        try:
            scandata = dbh.scanResultSummary(id, by)
        except Exception as e:
            return retdata
        try:
            eventtypes = dbh.eventTypes()
        except Exception as e:
            eventtypes = []
        retdata.extend(scandata)
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scancorrelations(self, id: str) -> list | dict:
        """Return the list of correlations found for a scan."""
        retdata = []
        dbh = self._get_dbh()
        try:
            data = dbh.scanCorrelationList(id)
            retdata = list(data)
        except Exception as e:
            return self.jsonify_error("500", str(e))
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scaneventresults(
        self, id: str, eventType: str | None = None,
        filterfp: str | bool = False,
        correlationId: str | None = None,
    ) -> list:
        """Return scan event results, optionally filtered by type or correlation."""
        retdata = []
        dbh = self._get_dbh()
        try:
            data = dbh.scanResultEvent(id, eventType, filterfp, correlationId)
            retdata = list(data)
        except Exception as e:
            return retdata
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scaneventresultsunique(self, id: str, eventType: str, filterfp: str | bool = False) -> list:
        """Return unique scan event results for a given event type."""
        dbh = self._get_dbh()
        retdata = []
        try:
            data = dbh.scanResultEventUnique(id, eventType, filterfp)
            retdata = list(data)
        except Exception as e:
            return retdata
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search(self, id: str | None = None, eventType: str | None = None, value: str | None = None) -> list:
        """Search scan results by ID, event type, or value."""
        try:
            return self.searchBase(id, eventType, value)
        except Exception as e:
            return []

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanhistory(self, id: str) -> list:
        """Return the result history for a scan."""
        if not id:
            return []
        dbh = self._get_dbh()
        try:
            # Fixed: Use the correct method name scanResultHistory instead of scanHistory
            return dbh.scanResultHistory(id)
        except Exception as e:
            return []

    @cherrypy.expose
    def startscan(
        self, scanname: str, scantarget: str, modulelist: str,
        typelist: str, usecase: str, max_wait: str | int = 10,
    ) -> str | dict:
        """Start a new scan with the specified target, modules, and configuration."""
        scanname = self.cleanUserInput([scanname])[0]
        scantarget = self.cleanUserInput([scantarget])[0]
        if not scanname:
            return self.error("Scan name required")
        if not scantarget:
            return self.error("Scan target required")
        if not typelist and not modulelist and not usecase:
            return self.error("No modules or types selected")
        targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
        if targetType is None:
            return self.error("Invalid target type")
        dbh = self._get_dbh()
        cfg = deepcopy(self.config)
        sf = SpiderFoot(cfg)
        modlist = [m for m in modulelist.split(',') if m] if modulelist else []

        if not modlist and typelist:
            # Resolve requested event types → modules that produce them
            requested_types = [t for t in typelist.split(',') if t]
            if requested_types:
                for mod_name, mod_meta in cfg.get('__modules__', {}).items():
                    provides = mod_meta.get('provides', []) or mod_meta.get('meta', {}).get('provides', [])
                    if set(requested_types) & set(provides):
                        modlist.append(mod_name)

        if not modlist and usecase:
            # Resolve use case name → modules belonging to that use case
            for mod_name, mod_meta in cfg.get('__modules__', {}).items():
                if usecase == 'all':
                    modlist.append(mod_name)
                else:
                    use_cases = mod_meta.get('group', []) or mod_meta.get('meta', {}).get('useCases', [])
                    if usecase in use_cases:
                        modlist.append(mod_name)

        if not modlist:
            return self.error("No modules selected")
        if "sfp__stor_db" not in modlist:
            modlist.append("sfp__stor_db")
        modlist.sort()
        if "sfp__stor_stdout" in modlist:
            modlist.remove("sfp__stor_stdout")
        scanId = SpiderFootHelpers.genScanInstanceId()
        try:
            loggingQueue = getattr(self, 'loggingQueue', None)
            if loggingQueue is None:
                loggingQueue = mp.Queue()
            startSpiderFootScanner(loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg)
        except Exception as e:
            return self.error(str(e))
        try:
            if max_wait is None or max_wait == '':
                max_wait = 10
            else:
                max_wait = float(max_wait)
        except (ValueError, TypeError):
            max_wait = 10
        waited = 0
        while dbh.scanInstanceGet(scanId) is None and waited < max_wait:
            time.sleep(0.1)
            waited += 0.1
        if dbh.scanInstanceGet(scanId) is None:
            return self.error("Scan did not start in time. Please try again.")
        if cherrypy.request.headers.get('Accept') and 'application/json' in cherrypy.request.headers.get('Accept'):
            return {"scanId": scanId}
        raise cherrypy.HTTPRedirect(f"{self.docroot}/scaninfo?id={scanId}")

    @cherrypy.expose
    def stopscan(self, id: str) -> bytes:
        """Stop one or more running scans by comma-separated IDs."""
        if not id:
            return b''
        dbh = self._get_dbh()
        ids = id.split(',')
        errors = []
        for scan_id in ids:
            try:
                dbh.scanInstanceStop(scan_id)
            except Exception as e:
                errors.append({"id": scan_id, "error": str(e)})
        if errors:
            return f'["ERROR", "{errors}"]'.encode('utf-8')
        return b''

    @cherrypy.expose
    def scandelete(self, id: str) -> bytes:
        """Delete one or more scans by comma-separated IDs."""
        if not id:
            return b''
        dbh = self._get_dbh()
        ids = id.split(',')
        errors = []
        for scan_id in ids:
            try:
                dbh.scanInstanceDelete(scan_id)
            except Exception as e:
                errors.append({"id": scan_id, "error": str(e)})
        if errors:
            return f'["ERROR", "{errors}"]'.encode('utf-8')
        return b''

    @cherrypy.expose
    def savesettings(self, allopts: str, token: str, configFile: str | None = None) -> str:
        """Save updated settings from the web UI options form."""
        import json
        try:
            opts = json.loads(allopts)
        except (json.JSONDecodeError, ValueError) as e:
            return self.opts(
                updated=None,
                error_message=f"Processing one or more of your inputs failed. {str(e)}",
                config=None,
            )
        self.config.update(opts)
        raise cherrypy.HTTPRedirect("/opts?updated=1")

    @cherrypy.expose
    def resultsetfp(self, id: str, resultids: str, fp: str) -> bytes:
        """Mark or unmark scan result entries as false positives."""
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        dbh = self._get_dbh()
        if fp not in ["0", "1"]:
            return b'["ERROR", "Invalid fp value"]'
        try:
            ids = resultids.split(',')
        except (AttributeError, TypeError):
            return b'["ERROR", "Invalid resultids"]'
        status = dbh.scanInstanceGet(id)
        if not status:
            return b'["ERROR", "Scan not found"]'
        if status[5] not in [DB_STATUS_ABORTED, DB_STATUS_FINISHED, DB_STATUS_ERROR_FAILED]:
            return b'["ERROR", "Scan not completed"]'
        try:
            if fp == "0":
                pass
            childs = dbh.scanElementChildrenAll(id, ids)
            allIds = ids + childs
            ret = dbh.scanResultsUpdateFP(id, allIds, fp)
            if ret:
                return b'["SUCCESS", ""]'
            return b'["ERROR", "Exception encountered."]'
        except Exception as e:
            return f'["ERROR", "{e}"]'.encode('utf-8')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanelementtypediscovery(self, id: str, eventType: str) -> dict:
        """Return the discovery tree and data map for a given event type."""
        dbh = self._get_dbh()
        pc = dict()
        datamap = dict()
        retdata = dict()
        try:
            pc = dbh.scanElementTypeDiscovery(id, eventType)
            datamap = dbh.scanElementTypeDiscoveryData(id, eventType)
        except Exception as e:
            retdata['tree'] = {}
            retdata['data'] = {}
            return retdata
        if 'ROOT' in pc:
            del pc['ROOT']
        retdata['tree'] = SpiderFootHelpers.dataParentChildToTree(pc)
        retdata['data'] = datamap
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacescanresults(self, workspace: str, limit: str | None = None) -> dict:
        """Return scan results for a given workspace with optional limit."""
        try:
            if limit is not None:
                limit = int(limit)
        except (ValueError, TypeError):
            limit = 100
        dbh = self._get_dbh()
        try:
            results = dbh.scanResultSummary(workspace, limit)
            return {'success': True, 'results': results}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @cherrypy.expose
    def index(self) -> str:
        """Render the main scan list page."""
        import sfwebui  # for patching Template in tests
        templ = Template(filename='spiderfoot/templates/scanlist.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, pageid="INDEX", version=__version__)

    @cherrypy.expose
    def scanexportlogs(self, id: str, dialect: str = "excel") -> str | bytes:
        """Export scan logs as a CSV file download."""
        import csv
        from io import StringIO
        dbh = self._get_dbh()
        try:
            data = dbh.scanLogs(id)
        except Exception as e:
            data = []
        if not data:
            return self.error("No log data found.")
        fileobj = StringIO()
        parser = csv.writer(fileobj, dialect=dialect)
        parser.writerow(["Date", "Component", "Type", "Event", "Event ID"])
        for row in data:
            parser.writerow(row)
        cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{id}.log.csv"
        cherrypy.response.headers['Content-Type'] = "application/csv"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return fileobj.getvalue().encode('utf-8')

    @cherrypy.expose
    def scancorrelationsexport(self, id: str, filetype: str = "csv", dialect: str = "excel") -> str | bytes:
        """Export scan correlations as CSV or Excel file download."""
        import csv
        import sfwebui
        from io import StringIO
        dbh = self._get_dbh()
        try:
            data = dbh.scanCorrelations(id)
        except Exception as e:
            data = []
        try:
            scan = dbh.scanInstanceGet(id)
        except Exception as e:
            scan = None
        headings = ["Rule Name", "Correlation", "Risk", "Description"]
        if filetype.lower() in ["xlsx", "excel"]:
            return self.buildExcel(data, headings, 0)
        if filetype.lower() == 'csv':
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(headings)
            for row in data:
                parser.writerow(row)
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{id}.correlations.csv"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')
        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scaneventresultexport(self, id: str, type: str, filetype: str = "csv", dialect: str = "excel") -> str | bytes:
        """Export scan event results for a specific type as CSV or Excel."""
        import csv
        from io import StringIO
        dbh = self._get_dbh()
        data = dbh.scanResultEvent(id, type)
        headings = ["Date", "Type", "Value", "Source", "Module", "Risk", "FP", "Correlation", "EventId"]
        if filetype.lower() in ["xlsx", "excel"]:
            return self.buildExcel(data, headings, 0)
        if filetype.lower() == 'csv':
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(headings)
            for row in data:
                parser.writerow(row)
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{id}.eventresults.csv"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')
        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scaneventresultexportmulti(self, ids: str, filetype: str = "csv", dialect: str = "excel") -> str | bytes:
        """Export event results from multiple scans as CSV or Excel."""
        import csv
        from io import StringIO
        dbh = self._get_dbh()
        scaninfo = dict()
        data = list()
        scan_name = ""
        for id in ids.split(','):
            d = dbh.scanResultEvent(id)
            if d:
                data.extend(d)
        if not data:
            return self.error("No data found.")
        headings = ["Date", "Type", "Value", "Source", "Module", "Risk", "FP", "Correlation", "EventId"]
        if filetype.lower() in ["xlsx", "excel"]:
            return self.buildExcel(data, headings, 0)
        if filetype.lower() == 'csv':
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(headings)
            for row in data:
                parser.writerow(row)
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-multi.eventresults.csv"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')
        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scansearchresultexport(
        self, id: str,
        eventType: str | None = None,
        value: str | None = None,
        filetype: str = "csv",
        dialect: str = "excel",
    ) -> str | bytes:
        """Export search results for a scan as CSV or Excel."""
        import csv
        from io import StringIO
        data = self.searchBase(id, eventType, value)
        headings = ["Date", "Type", "Value", "Source", "Module", "Risk", "FP", "Correlation", "EventId"]
        if not data:
            return self.error("No data found.")
        if filetype.lower() in ["xlsx", "excel"]:
            return self.buildExcel(data, headings, 0)
        if filetype.lower() == 'csv':
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(headings)
            for row in data:
                parser.writerow(row)
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{id}.searchresults.csv"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')
        return self.error("Invalid export filetype.")

    @cherrypy.expose
    def scanexportjsonmulti(self, ids: str) -> bytes:
        """Export event results from multiple scans as a JSON file download."""
        import json
        dbh = self._get_dbh()
        scaninfo = list()
        scan_name = ""
        for id in ids.split(','):
            d = dbh.scanResultEvent(id)
            if d:
                scaninfo.extend(d)
        if len(ids.split(',')) > 1 or scan_name == "":
            fname = "SpiderFoot-multi.eventresults.json"
        else:
            fname = f"SpiderFoot-{scan_name}.eventresults.json"
        cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return json.dumps(scaninfo).encode('utf-8')

    @cherrypy.expose
    def scanviz(self, id: str, gexf: str = "0") -> str | bytes:
        """Export scan results as a GEXF graph visualization file."""
        dbh = self._get_dbh()
        if not id:
            return self.error("No scan id provided.")
        data = dbh.scanResultEvent(id, filterFp=True)
        scan = dbh.scanInstanceGet(id)
        if not scan:
            return self.error("Scan not found.")
        scan_name = scan[0]
        root = scan[1]
        if gexf == "0":
            fname = f"SpiderFoot-{scan_name}.gexf"
        else:
            fname = f"SpiderFoot-{scan_name}.gexf"
        cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/gexf"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return SpiderFootHelpers.buildGraphGexf([root], "SpiderFoot Export", data)

    @cherrypy.expose
    def scanvizmulti(self, ids: str, gexf: str = "1") -> str | bytes:
        """Export results from multiple scans as a combined GEXF graph file."""
        dbh = self._get_dbh()
        data = list()
        roots = list()
        scan_name = ""
        if not ids:
            return self.error("No scan ids provided.")
        for id in ids.split(','):
            d = dbh.scanResultEvent(id, filterFp=True)
            scan = dbh.scanInstanceGet(id)
            if d:
                data.extend(d)
            if scan:
                roots.append(scan[1])
        if not data:
            return self.error("No data found.")
        if gexf == "0":
            fname = "SpiderFoot-multi.gexf"
        else:
            fname = "SpiderFoot-multi.gexf"
        cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/gexf"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return SpiderFootHelpers.buildGraphGexf(roots, "SpiderFoot Export", data)

    @cherrypy.expose
    def opts(self, updated: str | None = None, error_message: str | None = None, config: dict | None = None) -> str:
        """Render the settings/options page."""
        import sfwebui
        templ = Template(filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
        # Use provided config or fallback to self.config
        render_config = self.config if config is None else config
        return templ.render(
            pageid='OPTIONS',
            config=render_config,
            updated=updated,
            docroot=self.docroot,
            version=__version__,
            error_message=error_message
        )

    @cherrypy.expose
    def optsexport(self, pattern: str | None = None) -> str:
        """Export current settings as a JSON file download."""
        import json
        if pattern:
            filtered = {k: v for k, v in self.config.items() if pattern in k}
        else:
            filtered = self.config
        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=SpiderFoot-options.json'
        cherrypy.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        cherrypy.response.headers['Pragma'] = 'no-cache'
        return json.dumps(filtered, indent=2)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def optsraw(self) -> list:
        """Return the raw configuration dictionary."""
        return [self.config]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping(self) -> list:
        """Return a simple health-check response."""
        return ["PONG"]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def query(self, query: str) -> list:
        """Execute a raw database query and return the results."""
        dbh = self._get_dbh()
        try:
            return dbh.query(query)
        except Exception as e:
            return [["ERROR", str(e)]]

    @cherrypy.expose
    def savesettingsraw(self, allopts: str, token: str) -> bytes:
        """Save settings from a raw JSON payload and return a status response."""
        import json

        try:
            opts = json.loads(allopts)
        except (json.JSONDecodeError, ValueError) as e:
            return f'["ERROR", "{e}"]'.encode('utf-8')
        self.config.update(opts)
        return b'["SUCCESS", ""]'

    @cherrypy.expose
    def vacuum(self) -> bytes:
        """Run a database vacuum operation to reclaim unused space."""
        dbh = self._get_dbh()
        try:
            dbh.vacuum()
            return b'["SUCCESS", ""]'
        except Exception as e:
            return f'["ERROR", "{e}"]'.encode('utf-8')
