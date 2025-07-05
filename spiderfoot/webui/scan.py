import cherrypy
from copy import deepcopy
from spiderfoot import SpiderFootDb, SpiderFootHelpers, __version__
from spiderfoot.sflib import SpiderFoot
import time
import json
from spiderfoot.scan_service.scanner import startSpiderFootScanner
import multiprocessing as mp
import html

class ScanEndpoints:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanopts(self, id):
        dbh = SpiderFootDb(self.config)
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
    def rerunscan(self, id):
        cfg = deepcopy(self.config)
        dbh = SpiderFootDb(cfg)
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
    def rerunscanmulti(self, ids):
        import sfwebui
        cfg = deepcopy(self.config)
        dbh = SpiderFootDb(cfg)
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
        templ = sfwebui.Template(filename='spiderfoot/templates/scanlist.tmpl', lookup=self.lookup)
        return templ.render(rerunscans=True, docroot=self.docroot, pageid="SCANLIST", version=__version__, errors=errors)

    @cherrypy.expose
    def newscan(self):
        import sfwebui  # for patching Template in tests
        dbh = SpiderFootDb(self.config)
        types = dbh.eventTypes()
        templ = sfwebui.Template(filename='spiderfoot/templates/newscan.tmpl', lookup=self.lookup)
        return templ.render(pageid='NEWSCAN', types=types, docroot=self.docroot,
                            modules=self.config['__modules__'], scanname="",
                            selectedmods="", scantarget="", version=__version__)

    @cherrypy.expose
    def clonescan(self, id):
        import sfwebui  # for patching Template in tests
        dbh = SpiderFootDb(self.config)
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
        templ = sfwebui.Template(filename='spiderfoot/templates/newscan.tmpl', lookup=self.lookup)
        return templ.render(pageid='NEWSCAN', types=types, docroot=self.docroot,
                            modules=self.config['__modules__'], selectedmods=modlist,
                            scanname=str(scanname), scantarget=str(scantarget), version=__version__)

    @cherrypy.expose
    def scaninfo(self, id):
        import sfwebui
        dbh = SpiderFootDb(self.config)
        res = dbh.scanInstanceGet(id)
        if res is None:
            return self.error("Scan not found")
        templ = sfwebui.Template(filename='spiderfoot/templates/scaninfo.tmpl', lookup=self.lookup, input_encoding='utf-8')
        return templ.render(id=id, name=res[0], status=res[5], docroot=self.docroot, version=__version__, pageid="SCANLIST")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanlist(self):
        dbh = SpiderFootDb(self.config)
        data = dbh.scanInstanceList()
        retdata = []
        for row in data:
            # row: [guid, name, seed_target, created, started, ended, status, element_count]
            scan_id = row[0]
            # Get risk summary for this scan
            riskmatrix = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
            try:
                correlations = dbh.scanCorrelationSummary(scan_id, by="risk")
                if correlations:
                    for r in correlations:
                        if r[0] in riskmatrix:
                            riskmatrix[r[0]] = r[1]
            except Exception:
                pass
            # Append riskmatrix as 9th element
            retdata.append(list(row) + [riskmatrix])
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanstatus(self, id):
        dbh = SpiderFootDb(self.config)
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
    def scansummary(self, id, by):
        retdata = []
        dbh = SpiderFootDb(self.config)
        try:
            scandata = dbh.scanSummary(id, by)
        except Exception:
            return retdata
        try:
            eventtypes = dbh.eventTypes()
        except Exception:
            eventtypes = []
        for row in scandata:
            retdata.append(row)
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scancorrelations(self, id):
        retdata = []
        dbh = SpiderFootDb(self.config)
        try:
            data = dbh.scanCorrelations(id)
            for row in data:
                retdata.append(row)
        except Exception as e:
            return self.jsonify_error("500", str(e))
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scaneventresults(self, id, eventType=None, filterfp=False, correlationId=None):
        retdata = []
        dbh = SpiderFootDb(self.config)
        try:
            data = dbh.scanResultEvent(id, eventType, filterfp, correlationId)
            for row in data:
                retdata.append(row)
        except Exception:
            return retdata
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scaneventresultsunique(self, id, eventType, filterfp=False):
        dbh = SpiderFootDb(self.config)
        retdata = []
        try:
            data = dbh.scanResultEventUnique(id, eventType, filterfp)
            for row in data:
                retdata.append(row)
        except Exception:
            return retdata
        return retdata

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search(self, id=None, eventType=None, value=None):
        try:
            return self.searchBase(id, eventType, value)
        except Exception:
            return []

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanhistory(self, id):
        if not id:
            return []
        dbh = SpiderFootDb(self.config)
        try:
            return dbh.scanHistory(id)
        except Exception:
            return []

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanelementtypediscovery(self, id, eventType):
        dbh = SpiderFootDb(self.config)
        pc = dict()
        datamap = dict()
        retdata = dict()
        try:
            pc = dbh.scanElementTypeDiscovery(id, eventType)
            datamap = dbh.scanElementTypeDiscoveryData(id, eventType)
        except Exception:
            retdata['tree'] = {}
            retdata['data'] = {}
            return retdata
        if 'ROOT' in pc:
            del pc['ROOT']
        retdata['tree'] = SpiderFootHelpers.dataParentChildToTree(pc)
        retdata['data'] = datamap
        return retdata

    @cherrypy.expose
    def startscan(self, scanname, scantarget, modulelist, typelist, usecase, max_wait=10):
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
        dbh = SpiderFootDb(self.config)
        cfg = deepcopy(self.config)
        sf = SpiderFoot(cfg)
        modlist = []
        if modulelist:
            modlist = modulelist.split(',')
        if len(modlist) == 0 and typelist:
            modlist = typelist.split(',')
        if len(modlist) == 0 and usecase:
            modlist = usecase.split(',')
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
        except Exception:
            max_wait = 10
        print(f"DEBUG: max_wait={max_wait} (type={type(max_wait)})")
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
    @cherrypy.tools.json_out()
    def stopscan(self, id):
        if not id:
            return b'["ERROR", "No scan id provided"]'
        dbh = SpiderFootDb(self.config)
        ids = id.split(',')
        errors = []
        for scan_id in ids:
            try:
                dbh.scanInstanceStop(scan_id)
            except Exception as e:
                errors.append({"id": scan_id, "error": str(e)})
        if errors:
            return b'["ERROR", "%s"]' % str(errors).encode('utf-8')
        return b''

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scandelete(self, id):
        if not id:
            return b'["ERROR", "No scan id provided"]'
        dbh = SpiderFootDb(self.config)
        ids = id.split(',')
        errors = []
        for scan_id in ids:
            try:
                dbh.scanInstanceDelete(scan_id)
            except Exception as e:
                errors.append({"id": scan_id, "error": str(e)})
        if errors:
            return b'["ERROR", "%s"]' % str(errors).encode('utf-8')
        return b''

    @cherrypy.expose
    def savesettings(self, allopts, token, configFile=None):
        import json
        try:
            opts = json.loads(allopts)
            self.config.update(opts)
            raise cherrypy.HTTPRedirect("/opts?updated=1")
        except Exception as e:
            return self.opts(updated=None, error_message=f"Processing one or more of your inputs failed. {str(e)}", config=None)

    @cherrypy.expose
    def resultsetfp(self, id, resultids, fp):
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        dbh = SpiderFootDb(self.config)
        if fp not in ["0", "1"]:
            return b'["ERROR", "Invalid fp value"]'
        try:
            ids = resultids.split(',')
        except Exception:
            return b'["ERROR", "Invalid resultids"]'
        status = dbh.scanInstanceGet(id)
        if not status:
            return b'["ERROR", "Scan not found"]'
        if status[5] not in ["ABORTED", "FINISHED", "ERROR-FAILED"]:
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
            return ('["ERROR", "%s"]' % str(e)).encode('utf-8')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanelementtypediscovery(self, id, eventType):
        dbh = SpiderFootDb(self.config)
        pc = dict()
        datamap = dict()
        retdata = dict()
        try:
            pc = dbh.scanElementTypeDiscovery(id, eventType)
            datamap = dbh.scanElementTypeDiscoveryData(id, eventType)
        except Exception:
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
    def workspacescanresults(self, workspace, limit=None):
        try:
            if limit is not None:
                limit = int(limit)
        except Exception:
            limit = 100
        dbh = SpiderFootDb(self.config)
        try:
            results = dbh.scanResultSummary(workspace, limit)
            return {'success': True, 'results': results}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @cherrypy.expose
    def index(self):
        import sfwebui  # for patching Template in tests
        templ = sfwebui.Template(filename='spiderfoot/templates/scanlist.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, pageid="INDEX", version=__version__)

    @cherrypy.expose
    def scanexportlogs(self, id, dialect="excel"):
        import csv
        from io import StringIO
        dbh = SpiderFootDb(self.config)
        try:
            data = dbh.scanLog(id)
        except Exception:
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
    def scancorrelationsexport(self, id, filetype="csv", dialect="excel"):
        import csv
        import sfwebui
        from io import StringIO
        dbh = SpiderFootDb(self.config)
        try:
            data = dbh.scanCorrelations(id)
        except Exception:
            data = []
        try:
            scan = dbh.scanInstanceGet(id)
        except Exception:
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
    def scaneventresultexport(self, id, type, filetype="csv", dialect="excel"):
        import csv
        from io import StringIO
        dbh = SpiderFootDb(self.config)
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
    def scaneventresultexportmulti(self, ids, filetype="csv", dialect="excel"):
        import csv
        from io import StringIO
        dbh = SpiderFootDb(self.config)
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
    def scansearchresultexport(self, id, eventType=None, value=None, filetype="csv", dialect="excel"):
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
    def scanexportjsonmulti(self, ids):
        import json
        dbh = SpiderFootDb(self.config)
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
    def scanviz(self, id, gexf="0"):
        dbh = SpiderFootDb(self.config)
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
    def scanvizmulti(self, ids, gexf="1"):
        dbh = SpiderFootDb(self.config)
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
    def opts(self, updated=None, error_message=None, config=None):
        import sfwebui
        templ = sfwebui.Template(filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
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
    def optsexport(self, pattern=None):
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
    def optsraw(self):
        return [self.config]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping(self):
        return ["PONG"]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def query(self, query):
        dbh = SpiderFootDb(self.config)
        try:
            return dbh.query(query)
        except Exception as e:
            return [["ERROR", str(e)]]

    @cherrypy.expose
    def savesettingsraw(self, allopts, token):
        import json
        try:
            opts = json.loads(allopts)
        except Exception as e:
            return b'["ERROR", "%s"]' % str(e).encode('utf-8')
        self.config.update(opts)
        return b'["SUCCESS", ""]'

    @cherrypy.expose
    def vacuum(self):
        dbh = SpiderFootDb(self.config)
        try:
            dbh.vacuum()
            return b'["SUCCESS", ""]'
        except Exception as e:
            return b'["ERROR", "%s"]' % str(e).encode('utf-8')

    @cherrypy.expose
    def stopscan(self, id):
        if not id:
            return b''
        dbh = SpiderFootDb(self.config)
        ids = id.split(',')
        errors = []
        for scan_id in ids:
            try:
                dbh.scanInstanceStop(scan_id)
            except Exception as e:
                errors.append({"id": scan_id, "error": str(e)})
        if errors:
            return ('["ERROR", "%s"]' % str(errors)).encode('utf-8')
        return b''

    @cherrypy.expose
    def scandelete(self, id):
        if not id:
            return b''
        dbh = SpiderFootDb(self.config)
        ids = id.split(',')
        errors = []
        for scan_id in ids:
            try:
                dbh.scanInstanceDelete(scan_id)
            except Exception as e:
                errors.append({"id": scan_id, "error": str(e)})
        if errors:
            return ('["ERROR", "%s"]' % str(errors)).encode('utf-8')
        return b''

    @cherrypy.expose
    def savesettings(self, allopts, token, configFile=None):
        import json
        try:
            opts = json.loads(allopts)
            self.config.update(opts)
            raise cherrypy.HTTPRedirect("/opts?updated=1")
        except Exception as e:
            return self.opts(updated=None, error_message=f"Processing one or more of your inputs failed. {str(e)}", config=None)

    @cherrypy.expose
    def resultsetfp(self, id, resultids, fp):
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        dbh = SpiderFootDb(self.config)
        if fp not in ["0", "1"]:
            return b'["ERROR", "Invalid fp value"]'
        try:
            ids = resultids.split(',')
        except Exception:
            return b'["ERROR", "Invalid resultids"]'
        status = dbh.scanInstanceGet(id)
        if not status:
            return b'["ERROR", "Scan not found"]'
        if status[5] not in ["ABORTED", "FINISHED", "ERROR-FAILED"]:
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
            return ('["ERROR", "%s"]' % str(e)).encode('utf-8')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanelementtypediscovery(self, id, eventType):
        dbh = SpiderFootDb(self.config)
        pc = dict()
        datamap = dict()
        retdata = dict()
        try:
            pc = dbh.scanElementTypeDiscovery(id, eventType)
            datamap = dbh.scanElementTypeDiscoveryData(id, eventType)
        except Exception:
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
    def workspacescanresults(self, workspace, limit=None):
        try:
            if limit is not None:
                limit = int(limit)
        except Exception:
            limit = 100
        dbh = SpiderFootDb(self.config)
        try:
            results = dbh.scanResultSummary(workspace, limit)
            return {'success': True, 'results': results}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @cherrypy.expose
    def index(self):
        import sfwebui  # for patching Template in tests
        templ = sfwebui.Template(filename='spiderfoot/templates/scanlist.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, pageid="INDEX", version=__version__)

    @cherrypy.expose
    def scanexportlogs(self, id, dialect="excel"):
        import csv
        from io import StringIO
        dbh = SpiderFootDb(self.config)
        try:
            data = dbh.scanLog(id)
        except Exception:
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
    def scancorrelationsexport(self, id, filetype="csv", dialect="excel"):
        import csv
        import sfwebui
        from io import StringIO
        dbh = SpiderFootDb(self.config)
        try:
            data = dbh.scanCorrelations(id)
        except Exception:
            data = []
        try:
            scan = dbh.scanInstanceGet(id)
        except Exception:
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
    def scaneventresultexport(self, id, type, filetype="csv", dialect="excel"):
        import csv
        from io import StringIO
        dbh = SpiderFootDb(self.config)
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
    def scaneventresultexportmulti(self, ids, filetype="csv", dialect="excel"):
        import csv
        from io import StringIO
        dbh = SpiderFootDb(self.config)
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
    def scansearchresultexport(self, id, eventType=None, value=None, filetype="csv", dialect="excel"):
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
    def scanexportjsonmulti(self, ids):
        import json
        dbh = SpiderFootDb(self.config)
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
    def scanviz(self, id, gexf="0"):
        dbh = SpiderFootDb(self.config)
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
    def scanvizmulti(self, ids, gexf="1"):
        dbh = SpiderFootDb(self.config)
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
    def opts(self, updated=None, error_message=None, config=None):
        import sfwebui
        templ = sfwebui.Template(filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
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
    def optsexport(self, pattern=None):
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
    def optsraw(self):
        return [self.config]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping(self):
        return ["PONG"]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def query(self, query):
        dbh = SpiderFootDb(self.config)
        try:
            return dbh.query(query)
        except Exception as e:
            return [["ERROR", str(e)]]

    @cherrypy.expose
    def savesettingsraw(self, allopts, token):
        import json
        try:
            opts = json.loads(allopts)
        except Exception as e:
            return b'["ERROR", "%s"]' % str(e).encode('utf-8')
        self.config.update(opts)
        return b'["SUCCESS", ""]'

    @cherrypy.expose
    def vacuum(self):
        dbh = SpiderFootDb(self.config)
        try:
            dbh.vacuum()
            return b'["SUCCESS", ""]'
        except Exception as e:
            return b'["ERROR", "%s"]' % str(e).encode('utf-8')

    @cherrypy.expose
    def stopscan(self, id):
        if not id:
            return b''
        dbh = SpiderFootDb(self.config)
        ids = id.split(',')
        errors = []
        for scan_id in ids:
            try:
                dbh.scanInstanceStop(scan_id)
            except Exception as e:
                errors.append({"id": scan_id, "error": str(e)})
        if errors:
            return ('["ERROR", "%s"]' % str(errors)).encode('utf-8')
        return b''

    @cherrypy.expose
    def scandelete(self, id):
        if not id:
            return b''
        dbh = SpiderFootDb(self.config)
        ids = id.split(',')
        errors = []
        for scan_id in ids:
            try:
                dbh.scanInstanceDelete(scan_id)
            except Exception as e:
                errors.append({"id": scan_id, "error": str(e)})
        if errors:
            return ('["ERROR", "%s"]' % str(errors)).encode('utf-8')
        return b''

    @cherrypy.expose
    def savesettings(self, allopts, token, configFile=None):
        import json
        try:
            opts = json.loads(allopts)
            self.config.update(opts)
            raise cherrypy.HTTPRedirect("/opts?updated=1")
        except Exception as e:
            return self.opts(updated=None, error_message=f"Processing one or more of your inputs failed. {str(e)}", config=None)

    @cherrypy.expose
    def resultsetfp(self, id, resultids, fp):
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        dbh = SpiderFootDb(self.config)
        if fp not in ["0", "1"]:
            return b'["ERROR", "Invalid fp value"]'
        try:
            ids = resultids.split(',')
        except Exception:
            return b'["ERROR", "Invalid resultids"]'
        status = dbh.scanInstanceGet(id)
        if not status:
            return b'["ERROR", "Scan not found"]'
        if status[5] not in ["ABORTED", "FINISHED", "ERROR-FAILED"]:
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
            return ('["ERROR", "%s"]' % str(e)).encode('utf-8')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanelementtypediscovery(self, id, eventType):
        dbh = SpiderFootDb(self.config)
        pc = dict()
        datamap = dict()
        retdata = dict()
        try:
            pc = dbh.scanElementTypeDiscovery(id, eventType)
            datamap = dbh.scanElementTypeDiscoveryData(id, eventType)
        except Exception:
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
    def workspacescanresults(self, workspace, limit=None):
        try:
            if limit is not None:
                limit = int(limit)
        except Exception:
            limit = 100
        dbh = SpiderFootDb(self.config)
        try:
            results = dbh.scanResultSummary(workspace, limit)
            return {'success': True, 'results': results}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @cherrypy.expose
    def index(self):
        import sfwebui  # for patching Template in tests
        templ = sfwebui.Template(filename='spiderfoot/templates/scanlist.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, pageid="INDEX", version=__version__)

    @cherrypy.expose
    def scanexportlogs(self, id, dialect="excel"):
        import csv
        from io import StringIO
        dbh = SpiderFootDb(self.config)
        try:
            data = dbh.scanLog(id)
        except Exception:
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
    def scancorrelationsexport(self, id, filetype="csv", dialect="excel"):
        import csv
        import sfwebui
        from io import StringIO
        dbh = SpiderFootDb(self.config)
        try:
            data = dbh.scanCorrelations(id)
        except Exception:
            data = []
        try:
            scan = dbh.scanInstanceGet(id)
        except Exception:
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
    def scaneventresultexport(self, id, type, filetype="csv", dialect="excel"):
        import csv
        from io import StringIO
        dbh = SpiderFootDb(self.config)
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
    def scaneventresultexportmulti(self, ids, filetype="csv", dialect="excel"):
        import csv
        from io import StringIO
        dbh = SpiderFootDb(self.config)
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
    def scansearchresultexport(self, id, eventType=None, value=None, filetype="csv", dialect="excel"):
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
    def scanexportjsonmulti(self, ids):
        import json
        dbh = SpiderFootDb(self.config)
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
    def scanviz(self, id, gexf="0"):
        dbh = SpiderFootDb(self.config)
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
    def scanvizmulti(self, ids, gexf="1"):
        dbh = SpiderFootDb(self.config)
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
    def opts(self, updated=None, error_message=None, config=None):
        import sfwebui
        templ = sfwebui.Template(filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
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
    def optsexport(self, pattern=None):
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
    def optsraw(self):
        return [self.config]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping(self):
        return ["PONG"]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def query(self, query):
        dbh = SpiderFootDb(self.config)
        try:
            return dbh.query(query)
        except Exception as e:
            return [["ERROR", str(e)]]

    @cherrypy.expose
    def savesettingsraw(self, allopts, token):
        import json
        try:
            opts = json.loads(allopts)
        except Exception as e:
            return b'["ERROR", "%s"]' % str(e).encode('utf-8')
        self.config.update(opts)
        return b'["SUCCESS", ""]'

    @cherrypy.expose
    def vacuum(self):
        dbh = SpiderFootDb(self.config)
        try:
            dbh.vacuum()
            return b'["SUCCESS", ""]'
        except Exception as e:
            return b'["ERROR", "%s"]' % str(e).encode('utf-8')

    @cherrypy.expose
    def stopscan(self, id):
        if not id:
            return b''
        dbh = SpiderFootDb(self.config)
        ids = id.split(',')
        errors = []
        for scan_id in ids:
            try:
                dbh.scanInstanceStop(scan_id)
            except Exception as e:
                errors.append({"id": scan_id, "error": str(e)})
        if errors:
            return ('["ERROR", "%s"]' % str(errors)).encode('utf-8')
        return b''

    @cherrypy.expose
    def scandelete(self, id):
        if not id:
            return b''
        dbh = SpiderFootDb(self.config)
        ids = id.split(',')
        errors = []
        for scan_id in ids:
            try:
                dbh.scanInstanceDelete(scan_id)
            except Exception as e:
                errors.append({"id": scan_id, "error": str(e)})
        if errors:
            return ('["ERROR", "%s"]' % str(errors)).encode('utf-8')
        return b''

    @cherrypy.expose
    def savesettings(self, allopts, token, configFile=None):
        import json
        try:
            opts = json.loads(allopts)
            self.config.update(opts)
            raise cherrypy.HTTPRedirect("/opts?updated=1")
        except Exception as e:
            return self.opts(updated=None, error_message=f"Processing one or more of your inputs failed. {str(e)}", config=None)

    @cherrypy.expose
    def resultsetfp(self, id, resultids, fp):
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        dbh = SpiderFootDb(self.config)
        if fp not in ["0", "1"]:
            return b'["ERROR", "Invalid fp value"]'
        try:
            ids = resultids.split(',')
        except Exception:
            return b'["ERROR", "Invalid resultids"]'
        status = dbh.scanInstanceGet(id)
        if not status:
            return b'["ERROR", "Scan not found"]'
        if status[5] not in ["ABORTED", "FINISHED", "ERROR-FAILED"]:
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
            return ('["ERROR", "%s"]' % str(e)).encode('utf-8')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanelementtypediscovery(self, id, eventType):
        dbh = SpiderFootDb(self.config)
        pc = dict()
        datamap = dict()
        retdata = dict()
        try:
            pc = dbh.scanElementTypeDiscovery(id, eventType)
            datamap = dbh.scanElementTypeDiscoveryData(id, eventType)
        except Exception:
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
    def workspacescanresults(self, workspace, limit=None):
        try:
            if limit is not None:
                limit = int(limit)
        except Exception:
            limit = 100
        dbh = SpiderFootDb(self.config)
        try:
            results = dbh.scanResultSummary(workspace, limit)
            return {'success': True, 'results': results}
        except Exception as e:
            return {'success': False, 'error': str(e)}
