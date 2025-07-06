from .scan import ScanEndpoints
from .export import ExportEndpoints
from .workspace import WorkspaceEndpoints
from .info import InfoEndpoints
from .settings import SettingsEndpoints
from .helpers import WebUiHelpers
import logging
import multiprocessing as mp
import cherrypy
import secure
from copy import deepcopy
from spiderfoot import SpiderFootDb, SpiderFootHelpers, __version__
try:
    from spiderfoot.sflib import SpiderFoot
except ImportError:
    pass
from spiderfoot.logger import logListenerSetup, logWorkerSetup

class WebUiRoutes(SettingsEndpoints, ScanEndpoints, ExportEndpoints, WorkspaceEndpoints, InfoEndpoints, WebUiHelpers):
    defaultConfig = dict()
    config = dict()
    token = None
    docroot = ''

    def __init__(self, web_config, config, loggingQueue=None):
        from mako.lookup import TemplateLookup

        if not isinstance(config, dict):
            raise TypeError(f"config is {type(config)}; expected dict()")
        if not config:
            raise ValueError("config is empty")

        if not isinstance(web_config, dict):
            raise TypeError(f"web_config is {type(web_config)}; expected dict()")
        if not web_config:
            raise ValueError("web_config is empty")

        self.docroot = web_config.get('root', '/').rstrip('/')
        self.defaultConfig = deepcopy(config)
        dbh = SpiderFootDb(self.defaultConfig, init=True)
        sf = SpiderFoot(self.defaultConfig)
        self.config = sf.configUnserialize(dbh.configGet(), self.defaultConfig)
        
        # Ensure required keys for opts template are populated
        if '__modules__' not in self.config:
            try:
                import os
                # Load modules like the legacy version
                script_dir = os.path.dirname(os.path.abspath(__file__))
                mod_dir = os.path.join(script_dir, '../../modules')
                if os.path.exists(mod_dir):
                    modules = SpiderFootHelpers.loadModulesAsDict(mod_dir, ['sfp_template.py'])
                    self.config['__modules__'] = modules
                else:
                    self.config['__modules__'] = {}
            except Exception:
                self.config['__modules__'] = {}
        
        if '__globaloptdescs__' not in self.config:
            try:
                # Load global option descriptions like the legacy version
                # Import from sf.py where it's defined
                from sf import sfOptdescs
                self.config['__globaloptdescs__'] = sfOptdescs
            except Exception:
                # Fallback to basic descriptions
                self.config['__globaloptdescs__'] = {
                    '_debug': "Enable debugging?",
                    '_maxthreads': "Max number of modules to run concurrently",
                    '_useragent': "User-Agent string to use for HTTP requests",
                    '_dnsserver': "Override the default resolver with another DNS server",
                    '_fetchtimeout': "Number of seconds before giving up on a HTTP request",
                    '_modulesenabled': "Modules enabled for the scan"
                }

        if loggingQueue is None:
            self.loggingQueue = mp.Queue()
            logListenerSetup(self.loggingQueue, self.config)
        else:
            self.loggingQueue = loggingQueue
        logWorkerSetup(self.loggingQueue)
        self.log = logging.getLogger(f"spiderfoot.{__name__}")

        cherrypy.config.update({
            'error_page.401': self.error_page_401,
            'error_page.404': self.error_page_404,
            'request.error_response': self.error_page
        })

        self.lookup = TemplateLookup(directories=['.'], filesystem_checks=True, collection_size=500)

        # Setup security headers
        self._setup_security_headers()

    def _setup_security_headers(self):
        """Set up security headers for the web interface."""
        try:
            if secure is None:
                self.log.info("secure module not available, skipping security headers")
                return
                
            csp = (
                secure.ContentSecurityPolicy()
                    .default_src("'self'")
                    .script_src("'self'", "'unsafe-inline'", "blob:")
                    .style_src("'self'", "'unsafe-inline'")
                    .base_uri("'self'")
                    .connect_src("'self'", "data:")
                    .frame_src("'self'", 'data:')
                    .img_src("'self'", "data:")
            )

            secure_headers = secure.Secure(
                server=secure.Server().set("server"),
                cache=secure.CacheControl().must_revalidate(),
                csp=csp,
                referrer=secure.ReferrerPolicy().no_referrer(),
            )

            cherrypy.config.update({
                "tools.response_headers.on": True,
                "tools.response_headers.headers": secure_headers.framework.cherrypy()
            })
            
            self.log.info("Additional security headers configured successfully")
            
        except Exception as e:
            self.log.error(f"Error configuring security headers: {e}")

    def error_page(self):
        cherrypy.response.status = 500
        if self.config.get('_debug'):
            from cherrypy import _cperror
            cherrypy.response.body = _cperror.get_error_page(
                status=500, traceback=_cperror.format_exc())
        else:
            cherrypy.response.body = b"<html><body>Error</body></html>"

    def error_page_401(self, status, message, traceback, version):
        return ""

    def error_page_404(self, status, message, traceback, version):
        from mako.template import Template
        templ = Template(
            filename='spiderfoot/templates/error.tmpl', lookup=self.lookup)
        return templ.render(message='Not Found', docroot=self.docroot, status=status, version=__version__)

    @cherrypy.expose
    def documentation(self, doc=None, q=None):
        import os
        import markdown
        from datetime import datetime
        doc_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../documentation'))
        doc_index = []
        selected_file = doc or 'Home.md'
        content = ''
        search_results = []
        search_query = q or ''
        toc_html = ''
        breadcrumbs = []
        last_updated = ''
        author = ''
        version_dirs = []
        current_version = 'latest'
        related = []
        title = ''

        def highlight(code, lang=None):
            # Dummy highlight function for template compatibility
            return code

        if not os.path.isdir(doc_dir):
            self.log.error(f"Documentation directory not found: {doc_dir}")
            content = '<div class="alert alert-danger">Documentation directory not found.</div>'
            from mako.template import Template
            templ = Template(filename='spiderfoot/templates/documentation.tmpl', lookup=self.lookup)
            try:
                return templ.render(
                    docroot=self.docroot,
                    version=__version__,
                    doc_index=doc_index,
                    selected_file=selected_file,
                    content=content,
                    search_results=search_results,
                    search_query=search_query,
                    toc_html=toc_html,
                    breadcrumbs=breadcrumbs,
                    last_updated=last_updated,
                    author=author,
                    version_dirs=version_dirs,
                    current_version=current_version,
                    related=related,
                    title=title,
                    highlight=highlight,
                    v='',
                    entry={},
                    crumb={}
                )
            except Exception as te:
                return f'<pre>Template error: {te}</pre>'
        try:
            def list_docs(base_dir):
                docs = []
                for root, _dirs, files in os.walk(base_dir):
                    for f in files:
                        if f.lower().endswith('.md'):
                            rel = os.path.relpath(os.path.join(root, f), base_dir)
                            docs.append(rel.replace('\\', '/'))
                return docs

            def get_title(md_path):
                import contextlib
                with contextlib.suppress(Exception):
                    with open(md_path, encoding='utf-8') as f:
                        for line in f:
                            if line.strip().startswith('#'):
                                return line.strip('#').strip()
                return os.path.splitext(os.path.basename(md_path))[0]

            all_docs = list_docs(doc_dir)
            for f in all_docs:
                abs_path = os.path.join(doc_dir, f)
                doc_index.append({
                    'file': f,
                    'title': get_title(abs_path),
                    'icon': 'fa fa-file-text-o',
                })
            if search_query:
                for entry in doc_index:
                    abs_path = os.path.join(doc_dir, entry['file'])
                    try:
                        with open(abs_path, encoding='utf-8') as f:
                            text = f.read()
                            if search_query.lower() in text.lower() or search_query.lower() in entry['title'].lower():
                                search_results.append(entry)
                    except Exception:
                        continue
            selected_entry = next((e for e in doc_index if e['file'] == selected_file), None)
            abs_selected = os.path.join(doc_dir, selected_file) if selected_file else None
            if selected_entry:
                title = selected_entry['title']
            else:
                title = selected_file
            if selected_file:
                parts = selected_file.split('/')
                path = ''
                for i, part in enumerate(parts):
                    path = '/'.join(parts[:i + 1])
                    breadcrumbs.append({'url': f'/documentation/{path}', 'title': part})
            if abs_selected and os.path.isfile(abs_selected):
                try:
                    with open(abs_selected, encoding='utf-8') as f:
                        md = f.read()
                    last_updated = datetime.utcfromtimestamp(os.path.getmtime(abs_selected)).strftime('%Y-%m-%d')
                    content = markdown.markdown(md, extensions=['toc', 'fenced_code', 'tables'])
                    if hasattr(markdown, 'toc'):
                        toc_html = getattr(markdown, 'toc', '')
                except Exception as e:
                    self.log.error(f"Error loading documentation file {abs_selected}: {e}")
                    content = f'<div class="alert alert-danger">Error loading documentation: {e}</div>'
            else:
                content = '<div class="alert alert-warning">Documentation file not found.</div>'
            from mako.template import Template
            templ = Template(filename='spiderfoot/templates/documentation.tmpl', lookup=self.lookup)
            try:
                return templ.render(
                    docroot=self.docroot,
                    version=__version__,
                    doc_index=doc_index,
                    selected_file=selected_file,
                    content=content,
                    search_results=search_results,
                    search_query=search_query,
                    toc_html=toc_html,
                    breadcrumbs=breadcrumbs,
                    last_updated=last_updated,
                    author=author,
                    version_dirs=version_dirs,
                    current_version=current_version,
                    related=related,
                    title=title,
                    highlight=highlight,
                    v='',
                    entry={},
                    crumb={}
                )
            except Exception as te:
                import traceback
                return f'<pre>Template error: {te}\n\nTraceback:\n{traceback.format_exc()}</pre>'
        except Exception as e:
            self.log.error(f"Documentation endpoint error: {e}")
            from mako.template import Template
            templ = Template(filename='spiderfoot/templates/documentation.tmpl', lookup=self.lookup)
            try:
                return templ.render(
                    docroot=self.docroot,
                    version=__version__,
                    doc_index=doc_index,
                    selected_file=selected_file,
                    content=f'<div class="alert alert-danger">Documentation error: {e}</div>',
                    search_results=search_results,
                    search_query=search_query,
                    toc_html=toc_html,
                    breadcrumbs=breadcrumbs,
                    last_updated=last_updated,
                    author=author,
                    version_dirs=version_dirs,
                    current_version=current_version,
                    related=related,
                    title=title,
                    highlight=highlight,
                    v='',
                    entry={},
                    crumb={}
                )
            except Exception as te:
                return f'<pre>Template error: {te}</pre>'

    @cherrypy.expose
    def footer(self):
        from mako.template import Template
        templ = Template(
            filename='spiderfoot/templates/footer.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    def active_maintenance_status(self):
        from mako.template import Template
        templ = Template(
            filename='spiderfoot/templates/active_maintenance_status.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanlog(self, scanid):
        """Return scan logs for a given scan ID, matching legacy API.
        
        Args:
            scanid: The scan instance ID to retrieve logs for
        """
        try:
            dbh = self._get_dbh()
            logs = dbh.scanLogs(scanid)
            return logs if logs is not None else []
        except Exception as e:
            return {'error': str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanerrors(self, scanid):
        """Return scan errors for a given scan ID, matching legacy API."""
        try:
            dbh = self._get_dbh()
            errors = dbh.scanErrors(scanid)
            return errors if errors is not None else []
        except Exception as e:
            return {'error': str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scancorrelations(self, id):
        """Return scan correlations for a given scan ID"""
        try:
            dbh = self._get_dbh()
            data = dbh.scanCorrelationList(id)
            retdata = []
            for row in data:
                retdata.append(row)
            return retdata
        except Exception as e:
            return self.jsonify_error("500", str(e))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def vacuum(self):
        """Vacuum the database"""
        try:
            dbh = self._get_dbh()
            dbh.vacuumDB()
            return b'["SUCCESS", ""]'
        except Exception as e:
            return b'["ERROR", "%s"]' % str(e).encode('utf-8')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanstatus(self, id):
        """Return scan status for a given scan ID"""
        try:
            dbh = self._get_dbh()
            data = dbh.scanInstanceGet(id)
            if not data:
                return []
            
            import time
            created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data[2]))
            started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data[3]))
            ended = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data[4]))
            
            riskmatrix = {
                "HIGH": 0,
                "MEDIUM": 0,
                "LOW": 0,
                "INFO": 0
            }
            
            correlations = dbh.scanCorrelationSummary(id, by="risk")
            if correlations:
                for c in correlations:
                    riskmatrix[c[0]] = c[1]
            
            return [data[0], data[1], created, started, ended, data[5], riskmatrix]
        except Exception as e:
            return self.jsonify_error("500", str(e))

    @cherrypy.expose  
    @cherrypy.tools.json_out()
    def scandelete(self, id):
        """Delete a scan"""
        try:
            dbh = self._get_dbh()
            scan = dbh.scanInstanceGet(id)
            if not scan:
                return self.jsonify_error("404", "Scan not found")
            dbh.scanInstanceDelete(id)
            return ''
        except Exception as e:
            return self.jsonify_error("500", str(e))

    def jsonify_error(self, status, message):
        """Helper method to create JSON error responses"""
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.status = status
        return {
            'error': {
                'http_status': status,
                'message': message,
            }
        }

    def error(self, message):
        """Show generic error page with error message"""
        from mako.template import Template
        templ = Template(
            filename='spiderfoot/templates/error.tmpl', lookup=self.lookup)
        return templ.render(message=message, docroot=self.docroot, version=__version__)

    def reset_settings(self):
        """Reset settings to default"""
        try:
            dbh = self._get_dbh()
            dbh.configClear()
            return True
        except Exception:
            return False

    @cherrypy.expose
    def resultsetfp(self, id, resultids, fp):
        """Set false positive flag for scan results"""
        try:
            dbh = self._get_dbh()
            scan = dbh.scanInstanceGet(id)
            if not scan:
                return b'["ERROR", "Scan not found"]'
            
            # Parse result IDs
            import json
            try:
                ids = json.loads(resultids)
            except:
                ids = [resultids]
            
            # Update FP status
            for result_id in ids:
                dbh.scanResultsUpdateFP(result_id, fp == '1')
            
            return b'["SUCCESS", ""]'
        except Exception as e:
            return b'["ERROR", "%s"]' % str(e).encode('utf-8')

    @cherrypy.expose
    def savesettings(self, allopts, token, configFile=None):
        """Save settings"""
        if not hasattr(self, 'token') or self.token != token:
            return self.error("Invalid token")
        
        try:
            import json
            dbh = self._get_dbh()
            opts = json.loads(allopts)
            
            # Save configuration
            from spiderfoot.sflib import SpiderFoot
            sf = SpiderFoot(self.config)
            serialized = sf.configSerialize(opts, self.defaultConfig)
            dbh.configSet(serialized)
            
            # Redirect to settings page
            raise cherrypy.HTTPRedirect(f"{self.docroot}/opts?updated=1")
            
        except cherrypy.HTTPRedirect:
            raise
        except Exception as e:
            return self.error(f"Processing one or more of your inputs failed. {str(e)}")

    @cherrypy.expose
    def startscan(self, scanname, scantarget, modulelist, typelist, usecase):
        """Start a new scan"""
        try:
            from sfwebui import SpiderFootHelpers
            
            # Generate scan ID
            scanId = SpiderFootHelpers.genScanInstanceId()
            
            # Determine target type
            targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
            if not targetType:
                return self.error("Invalid target type")
            
            # Start the scan process
            from sfwebui import mp
            from spiderfoot.scan_service.scanner import startSpiderFootScanner
            
            process = mp.Process(
                target=startSpiderFootScanner,
                args=(self.loggingQueue, scanname, scanId, scantarget, targetType, 
                      modulelist.split(','), self.config)
            )
            process.daemon = True
            process.start()
            
            # Wait for scan to initialize (with timeout)
            dbh = self._get_dbh()
            from sfwebui import time
            timeout_iterations = 10  # 10 iterations for tests (not seconds)
            iterations = 0
            while dbh.scanInstanceGet(scanId) is None and iterations < timeout_iterations:
                time.sleep(1)
                iterations += 1
                
            raise cherrypy.HTTPRedirect(f"{self.docroot}/scaninfo?id={scanId}")
            
        except cherrypy.HTTPRedirect:
            raise
        except Exception as e:
            return self.error(f"Failed to start scan: {str(e)}")

    @cherrypy.expose
    def rerunscan(self, id):
        """Re-run an existing scan"""
        try:
            from copy import deepcopy
            from sfwebui import SpiderFootDb
            cfg = deepcopy(self.config)
            dbh = SpiderFootDb(cfg)
            info = dbh.scanInstanceGet(id)
            if not info:
                return self.error("Invalid scan ID.")
                
            scanname = info[0]
            scantarget = info[1]
            
            if not scantarget:
                return self.error(f"Scan {id} has no target defined.")
                
            # Get scan configuration
            scanconfig = dbh.scanConfigGet(id)
            if not scanconfig:
                return self.error(f"Error loading config from scan: {id}")
                
            modlist = scanconfig['_modulesenabled'].split(',')
            if "sfp__stor_stdout" in modlist:
                modlist.remove("sfp__stor_stdout")
                
            from sfwebui import SpiderFootHelpers
            targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
            if not targetType:
                # Try with quotes
                targetType = SpiderFootHelpers.targetTypeFromString(f'"{scantarget}"')
                
            if not targetType:
                return self.error(f"Cannot determine target type for scan rerun. Target '{scantarget}' is not recognized.")
                
            if targetType not in ["HUMAN_NAME", "BITCOIN_ADDRESS"]:
                scantarget = scantarget.lower()
                
            # Start new scan
            scanId = SpiderFootHelpers.genScanInstanceId()
            
            from sfwebui import mp
            from spiderfoot.scan_service.scanner import startSpiderFootScanner
            
            process = mp.Process(
                target=startSpiderFootScanner,
                args=(self.loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg)
            )
            process.daemon = True
            process.start()
            
            # Wait for scan to initialize (with timeout)
            from sfwebui import time
            timeout_iterations = 10  # 10 iterations for tests (not seconds)
            iterations = 0
            while dbh.scanInstanceGet(scanId) is None and iterations < timeout_iterations:
                time.sleep(1)
                iterations += 1
                
            raise cherrypy.HTTPRedirect(f"{self.docroot}/scaninfo?id={scanId}")
            
        except cherrypy.HTTPRedirect:
            raise
        except Exception as e:
            return self.error(f"Failed to rerun scan: {str(e)}")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stopscan(self, id):
        """Stop a running scan"""
        try:
            if not id:
                return ''
                
            dbh = self._get_dbh()
            ids = id.split(',')
            errors = []
            
            for scan_id in ids:
                try:
                    scan = dbh.scanInstanceGet(scan_id)
                    if not scan:
                        errors.append({'id': scan_id, 'error': 'Scan not found'})
                        continue
                    
                    # Set scan status to stopped
                    dbh.scanInstanceSet(scan_id, None, None, 'STOPPED')
                    
                except Exception as e:
                    errors.append({'id': scan_id, 'error': str(e)})
            
            if errors:
                return f'["ERROR", "{errors}"]'
            else:
                return ''
                
        except Exception as e:
            return f'["ERROR", "{str(e)}"]'

    def _get_dbh(self):
        """Helper to get a new DB handle (matches legacy pattern)"""
        from sfwebui import SpiderFootDb
        return SpiderFootDb(self.config, init=False)

    # Add methods from helpers for backward compatibility
    def cleanUserInput(self, inputList):
        """Clean user input by escaping HTML"""
        if not isinstance(inputList, list):
            raise TypeError(f"inputList is {type(inputList)}; expected list()")
        ret = list()
        for item in inputList:
            if not item:
                ret.append("")
                continue
            import html
            c = html.escape(item, True)
            c = c.replace("&amp;", "&").replace("&quot;", "\"")
            ret.append(c)
        return ret

    def searchBase(self, scan_id=None, eventType=None, value=None):
        """Search scan results"""
        retdata = []
        
        if not scan_id and not eventType and not value:
            return retdata
            
        if not value:
            value = ''
            
        regex = ""
        if value.startswith("/") and value.endswith("/"):
            regex = value[1:len(value) - 1] 
            value = ""
            
        value = value.replace('*', '%')
        if value in [None, ""] and regex in [None, ""]:
            value = "%"
            regex = ""
            
        dbh = self._get_dbh()
        criteria = {
            'scan_id': scan_id or '',
            'type': eventType or '',
            'value': value or '',
            'regex': regex or '',
        }
        
        try:
            data = dbh.search(criteria)
        except Exception:
            return retdata
            
        for row in data:
            import time
            import html
            lastseen = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
            escapeddata = html.escape(row[1])
            escapedsrc = html.escape(row[2])
            retdata.append([lastseen, escapeddata, escapedsrc,
                            row[3], row[5], row[6], row[7], row[8], row[10],
                            row[11], row[4], row[13], row[14]])
        
        return retdata

    def buildExcel(self, data, columnNames, sheetNameIndex=0):
        """Convert supplied raw data into Excel format"""
        from spiderfoot import SpiderFootDb
        from sfwebui import openpyxl, BytesIO
        import string
        
        rowNums = dict()
        workbook = openpyxl.Workbook()
        defaultSheet = workbook.active
        columnNames.pop(sheetNameIndex)
        allowed_sheet_chars = string.ascii_uppercase + string.digits + '_'
        
        for row in data:
            sheetName = "".join(
                [c for c in str(row.pop(sheetNameIndex)) if c.upper() in allowed_sheet_chars])
            try:
                worksheet = workbook[sheetName]
            except KeyError:
                worksheet = workbook.create_sheet(sheetName)
                rowNums[sheetName] = 1
                # Write headers
                for col_num, header in enumerate(columnNames, 1):
                    worksheet.cell(row=1, column=col_num, value=header)
                rowNums[sheetName] = 2

            # Write row
            for col_num, cell_value in enumerate(row, 1):
                worksheet.cell(row=rowNums[sheetName], column=col_num, value=str(cell_value))

            rowNums[sheetName] += 1

        if rowNums:
            workbook.remove(defaultSheet)

        # Sort sheets alphabetically
        workbook._sheets.sort(key=lambda ws: ws.title)

        # Save workbook
        with BytesIO() as f:
            workbook.save(f)
            f.seek(0)
            return f.read()

    # Export methods
    @cherrypy.expose
    def scanexportlogs(self, scan_id, dialect="excel"):
        """Export scan logs"""
        try:
            dbh = self._get_dbh()
            data = dbh.scanLogs(scan_id)
            if not data:
                return self.error("No scan logs found")
                
            import csv
            from sfwebui import StringIO
            fileobj = StringIO()
            parser = csv.writer(fileobj, dialect=dialect)
            parser.writerow(["Date", "Component", "Type", "Event", "Event ID"])
            for row in data:
                parser.writerow([str(x) for x in row])
                
            cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{scan_id}.log.csv"
            cherrypy.response.headers['Content-Type'] = "application/csv"
            cherrypy.response.headers['Pragma'] = "no-cache"
            return fileobj.getvalue().encode('utf-8')
            
        except Exception as e:
            return self.error(f"Export failed: {str(e)}")

    @cherrypy.expose
    def scancorrelationsexport(self, scan_id, filetype="csv", dialect="excel"):
        """Export scan correlations"""
        try:
            dbh = self._get_dbh()
            data = dbh.scanCorrelations(scan_id)
            scan = dbh.scanInstanceGet(scan_id)
            if not scan:
                return self.error("Scan not found")
                
            headings = ["Rule Name", "Correlation", "Risk", "Description"]
            
            if filetype.lower() == 'csv':
                import csv
                from sfwebui import StringIO
                cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{scan_id}-correlations.csv"
                cherrypy.response.headers['Content-Type'] = "application/csv"
                cherrypy.response.headers['Pragma'] = "no-cache"
                fileobj = StringIO()
                parser = csv.writer(fileobj, dialect=dialect)
                parser.writerow(headings)
                for row in data:
                    parser.writerow([str(x) for x in row])
                return fileobj.getvalue()
            else:
                return self.error("Unsupported file type")
                
        except Exception as e:
            return self.error(f"Export failed: {str(e)}")

    @cherrypy.expose
    def scaneventresultexport(self, scan_id, event_type, filetype="csv", dialect="excel"):
        """Export scan event results"""
        try:
            dbh = self._get_dbh()
            data = dbh.scanResultEvent(scan_id, event_type)
            
            headings = ["Date", "Type", "Value", "Source", "Module", "Risk", "FP", "Correlation", "EventId"]
            
            if filetype.lower() == 'csv':
                import csv
                from sfwebui import StringIO
                cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{scan_id}-{event_type}.csv"
                cherrypy.response.headers['Content-Type'] = "application/csv"
                cherrypy.response.headers['Pragma'] = "no-cache"
                fileobj = StringIO()
                parser = csv.writer(fileobj, dialect=dialect)
                parser.writerow(headings)
                
                for row in data:
                    import time
                    formatted_row = [
                        time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0])),
                        row[3], row[1], row[2], row[4],  
                        '', '', '', row[12] if len(row) > 12 else ''
                    ]
                    parser.writerow(formatted_row)
                    
                return fileobj.getvalue().encode('utf-8')
            else:
                return self.error("Unsupported file type")
                
        except Exception as e:
            return self.error(f"Export failed: {str(e)}")

    @cherrypy.expose
    def scaneventresultexportmulti(self, ids, filetype="csv", dialect="excel"):
        """Export multiple scan event results"""
        try:
            scan_ids = ids.split(',')
            dbh = self._get_dbh()
            
            # Validate scans exist
            for scan_id in scan_ids:
                scan = dbh.scanInstanceGet(scan_id)
                if not scan:
                    return self.error(f"Scan not found: {scan_id}")
            
            # Get all data
            all_data = []
            for scan_id in scan_ids:
                data = dbh.scanResultEvent(scan_id)
                for row in data:
                    import time
                    formatted_row = [
                        time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0])),
                        row[3], row[1], row[2], row[4],
                        '', '', '', scan_id
                    ]
                    all_data.append(formatted_row)
            
            if filetype.lower() == 'csv':
                import csv
                from sfwebui import StringIO
                cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-multi-export.csv"
                cherrypy.response.headers['Content-Type'] = "application/csv"
                cherrypy.response.headers['Pragma'] = "no-cache"
                fileobj = StringIO()
                parser = csv.writer(fileobj, dialect=dialect)
                parser.writerow(["Date", "Type", "Value", "Source", "Module", "Risk", "FP", "Correlation", "ScanId"])
                
                for row in all_data:
                    parser.writerow(row)
                    
                return fileobj.getvalue().encode('utf-8')
            else:
                return self.error("Unsupported file type")
                
        except Exception as e:
            return self.error(f"Export failed: {str(e)}")

    @cherrypy.expose
    def scansearchresultexport(self, scan_id, eventType=None, value=None, filetype="csv", dialect="excel"):
        """Export search results"""
        try:
            search_results = self.searchBase(scan_id, eventType, value)
            
            headings = ["Date", "Type", "Value", "Source", "Module", "Risk", "FP", "Correlation", "EventId"]
            
            if filetype.lower() == 'csv':
                import csv
                from sfwebui import StringIO
                cherrypy.response.headers['Content-Disposition'] = f"attachment; filename=SpiderFoot-{scan_id}-search.csv"
                cherrypy.response.headers['Content-Type'] = "application/csv"
                cherrypy.response.headers['Pragma'] = "no-cache"
                fileobj = StringIO()
                parser = csv.writer(fileobj, dialect=dialect)
                parser.writerow(headings)
                
                for row in search_results:
                    parser.writerow(row)
                    
                return fileobj.getvalue().encode('utf-8')
            else:
                return self.error("Unsupported file type")
                
        except Exception as e:
            return self.error(f"Export failed: {str(e)}")

    @cherrypy.expose
    def scanexportjsonmulti(self, ids):
        """Export multiple scans as JSON"""
        from spiderfoot import SpiderFootDb
        import json
        import time
        
        dbh = SpiderFootDb(self.config)
        scaninfo = list()
        scan_name = ""

        for scan_id in ids.split(','):
            scan = dbh.scanInstanceGet(scan_id)

            if scan is None:
                continue

            scan_name = scan[0]

            for row in dbh.scanResultEvent(scan_id):
                lastseen = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(row[0]))
                event_data = str(row[1]).replace(
                    "<SFURL>", "").replace("</SFURL>", "")
                source_data = str(row[2])
                source_module = str(row[3])
                event_type = row[4]
                false_positive = row[13] if len(row) > 13 else ""

                if event_type == "ROOT":
                    continue

                scaninfo.append({
                    "data": event_data,
                    "event_type": event_type,
                    "module": source_module,
                    "source_data": source_data,
                    "false_positive": false_positive,
                    "last_seen": lastseen,
                    "scan_name": scan_name,
                    "scan_target": scan[1] if len(scan) > 1 else ""
                })

        if len(ids.split(',')) > 1 or scan_name == "":
            fname = "SpiderFoot.json"
        else:
            fname = scan_name + "-SpiderFoot.json"

        cherrypy.response.headers[
            'Content-Disposition'] = f"attachment; filename={fname}"
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        cherrypy.response.headers['Pragma'] = "no-cache"
        return json.dumps(scaninfo).encode('utf-8')

    @cherrypy.expose
    def scanviz(self, scan_id, gexf="0"):
        """Generate scan visualization"""
        try:
            dbh = self._get_dbh()
            data = dbh.scanResultEvent(scan_id)
            scan = dbh.scanInstanceGet(scan_id)
            
            if not scan:
                return self.error("Scan not found")
            
            from spiderfoot.helpers import SpiderFootHelpers
            graph_data = SpiderFootHelpers.buildGraphJson(data, scan[1])
            return graph_data
            
        except Exception as e:
            return self.error(f"Visualization failed: {str(e)}")

    @cherrypy.expose
    def scanvizmulti(self, ids, gexf="1"):
        """Generate multi-scan visualization"""
        try:
            scan_ids = ids.split(',')
            dbh = self._get_dbh()
            
            all_data = []
            root_target = None
            
            for scan_id in scan_ids:
                scan = dbh.scanInstanceGet(scan_id)
                if scan:
                    if not root_target:
                        root_target = scan[1]
                    data = dbh.scanResultEvent(scan_id)
                    all_data.extend(data)
            
            if not all_data:
                return self.error("No scan data found")
            
            from spiderfoot.helpers import SpiderFootHelpers
            graph_data = SpiderFootHelpers.buildGraphGexf(all_data, root_target or "multi-scan")
            return graph_data
            
        except Exception as e:
            return self.error(f"Visualization failed: {str(e)}")

    # Workspace methods  
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def workspacescanresults(self, workspace_id, scan_id=None, event_type=None, limit=100):
        """Get workspace scan results"""
        try:
            # Convert string limit to int if needed
            if isinstance(limit, str):
                try:
                    limit = int(limit)
                    if limit < 0:
                        limit = 100
                except ValueError:
                    limit = 100
                    
            from sfwebui import SpiderFootWorkspace
            workspace = SpiderFootWorkspace(self.config)
            workspace_instance = workspace.getWorkspace(workspace_id)
            
            if not workspace_instance:
                return {'success': False, 'error': 'Workspace not found'}
            
            from sfwebui import SpiderFootDb
            dbh = SpiderFootDb(self.config)
            results = []
            
            # Get scans from workspace
            scans = getattr(workspace_instance, 'scans', [])
            if scans:
                for scan in scans[:limit]:  # Apply limit properly
                    scan_data = dbh.scanResultSummary(scan.get('scan_id'))
                    if scan_data:
                        results.append(scan_data)
            
            return {
                'success': True, 
                'workspace_id': workspace_id,
                'results': results
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _validate_configuration(self):
        """Validate and fix configuration values."""
        # Validate modules structure - ensure it's a dict
        if '__modules__' in self.config:
            modules = self.config['__modules__']
            if not isinstance(modules, dict):
                if isinstance(modules, list):
                    # Convert list to dict format
                    modules_dict = {}
                    for m in modules:
                        if isinstance(m, dict) and 'name' in m:
                            modules_dict[m['name']] = m
                        elif isinstance(m, str):
                            modules_dict[m] = {'name': m}
                    self.config['__modules__'] = modules_dict
                else:
                    self.config['__modules__'] = {}
        else:
            self.config['__modules__'] = {}
        
        # Validate database configuration
        if '__database' not in self.config:
            self.config['__database'] = 'spiderfoot.db'
        
        # Validate other critical configuration keys
        if '__version__' not in self.config:
            self.config['__version__'] = __version__
        
        if '_logging' not in self.config:
            self.config['_logging'] = 'INFO'
        
        if '_modulesenabled' not in self.config:
            self.config['_modulesenabled'] = []
