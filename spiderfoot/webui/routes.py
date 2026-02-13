from __future__ import annotations

"""Main WebUI controller combining all endpoint groups and CherryPy configuration."""

from .scan import ScanEndpoints
from .export import ExportEndpoints
from .workspace import WorkspaceEndpoints
from .info import InfoEndpoints
from .settings import SettingsEndpoints
from .templates import MiscEndpoints
from .helpers import WebUiHelpers
from .performance import PerformanceEnhancedWebUI
from .db_provider import DbProvider
import logging
import multiprocessing as mp
import cherrypy
import secure
from copy import deepcopy
from spiderfoot import SpiderFootHelpers, __version__
from spiderfoot.config.constants import DEFAULT_DATABASE_NAME
try:
    from spiderfoot.sflib import SpiderFoot
except ImportError:
    pass
from spiderfoot.observability.logger import logListenerSetup, logWorkerSetup


class WebUiRoutes(
    SettingsEndpoints,
    ScanEndpoints,
    ExportEndpoints,
    WorkspaceEndpoints,
    InfoEndpoints,
    MiscEndpoints,
    WebUiHelpers,
    PerformanceEnhancedWebUI,
    DbProvider,
):
    """Main WebUI controller combining all endpoint groups."""
    defaultConfig = dict()
    config = dict()
    token = None
    docroot = ''

    def __init__(self, web_config: dict, config: dict, loggingQueue: mp.Queue | None = None) -> None:
        """Initialize the web UI routes with configuration and logging."""
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
        # Use DbProvider._get_dbh() for microservice-safe DB access
        # (routes through ApiClient in proxy mode, SpiderFootDb locally)
        dbh = self._get_dbh(self.defaultConfig, init=True)
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
            except Exception as e:
                self.config['__modules__'] = {}

        if '__globaloptdescs__' not in self.config:
            try:
                # Load global option descriptions like the legacy version
                # Import from sf.py where it's defined
                from sf import sfOptdescs
                self.config['__globaloptdescs__'] = sfOptdescs
            except Exception as e:
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
            self.log.error("Error configuring security headers: %s", e)

    def error_page(self) -> None:
        """Handle generic server error responses."""
        cherrypy.response.status = 500
        if self.config.get('_debug'):
            from cherrypy import _cperror
            cherrypy.response.body = _cperror.get_error_page(
                status=500, traceback=_cperror.format_exc())
        else:
            cherrypy.response.body = b"<html><body>Error</body></html>"

    def error_page_401(self, status: str, message: str, traceback: str, version: str) -> str:
        """Return an empty response for 401 unauthorized errors."""
        return ""

    def error_page_404(self, status: str, message: str, traceback: str, version: str) -> str:
        """Return a rendered error page for 404 not found errors."""
        from mako.template import Template
        templ = Template(
            filename='spiderfoot/templates/error.tmpl', lookup=self.lookup)
        return templ.render(message='Not Found', docroot=self.docroot, status=status, version=__version__)

    @cherrypy.expose
    def documentation(self, doc: str | None = None, q: str | None = None) -> str:
        """Render the documentation page with optional search and navigation."""
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

        def highlight(code: str, lang: str | None = None) -> str:
            """Return code unchanged as a passthrough highlight stub."""
            # Dummy highlight function for template compatibility
            return code

        if not os.path.isdir(doc_dir):
            self.log.error("Documentation directory not found: %s", doc_dir)
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
            def list_docs(base_dir: str) -> list:
                """List all Markdown documentation files under a directory."""
                docs = []
                for root, _dirs, files in os.walk(base_dir):
                    for f in files:
                        if f.lower().endswith('.md'):
                            rel = os.path.relpath(os.path.join(root, f), base_dir)
                            docs.append(rel.replace('\\', '/'))
                return docs

            def get_title(md_path: str) -> str:
                """Extract the title from a Markdown file's first heading."""
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
                    except (OSError, KeyError):
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
                    self.log.error("Error loading documentation file %s: %s", abs_selected, e)
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
            except Exception as e:
                self.log.exception("Template rendering error in documentation endpoint")
                return '<p>An error occurred while rendering this page. Please check the server logs.</p>'
        except Exception as e:
            self.log.error("Documentation endpoint error: %s", e)
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
    def footer(self) -> str:
        """Render the page footer template."""
        from mako.template import Template
        templ = Template(
            filename='spiderfoot/templates/footer.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    def active_maintenance_status(self) -> str:
        """Render the active maintenance status template."""
        from mako.template import Template
        templ = Template(
            filename='spiderfoot/templates/active_maintenance_status.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanlog(self, scanid: str) -> list | dict:
        """Return scan logs for a given scan ID, matching legacy API.

        Args:
            scanid: The scan instance ID to retrieve logs for
        """
        try:
            dbh = self._get_dbh()
            logs = dbh.scanLogs(scanid)
            return [list(row) for row in logs] if logs else []
        except Exception as e:
            return {'error': str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanerrors(self, id: str = "", scanid: str = "") -> list | dict:
        """Return scan errors for a given scan ID, matching legacy API."""
        scan_id = id or scanid
        if not scan_id:
            return []
        try:
            dbh = self._get_dbh()
            errors = dbh.scanErrors(scan_id)
            return [list(row) for row in errors] if errors else []
        except Exception as e:
            return {'error': str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scancorrelations(self, id: str) -> list | dict:
        """Return scan correlations for a given scan ID."""
        try:
            dbh = self._get_dbh()
            data = dbh.scanCorrelationList(id)
            retdata = []
            for row in data:
                retdata.append(list(row))
            return retdata
        except Exception as e:
            return self.jsonify_error("500", str(e))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def runcorrelations(self, id: str) -> dict:
        """Trigger correlation rule execution for a scan."""
        try:
            dbh = self._get_dbh()
            if hasattr(dbh, 'runCorrelations'):
                return dbh.runCorrelations(id)
            # Direct mode fallback
            import os
            from spiderfoot.correlation.rule_executor import RuleExecutor
            rules_dir = os.environ.get("SF_CORRELATION_RULES_DIR", "correlations")
            rules = []
            if os.path.isdir(rules_dir):
                try:
                    from spiderfoot.correlation.rule_loader import RuleLoader
                    loader = RuleLoader(rules_dir)
                    rules = loader.load_rules()
                except ImportError:
                    rules = SpiderFootHelpers.loadCorrelationRulesRaw(rules_dir) or []
            if not rules:
                return {"error": "No correlation rules found"}
            executor = RuleExecutor(dbh, rules, scan_ids=[id])
            raw_results = executor.run()
            total = sum(1 for r in raw_results.values() if isinstance(r, dict) and r.get("correlation_id"))
            return {"success": True, "results": total, "rules_evaluated": len(rules)}
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def vacuum(self) -> bytes | str:
        """Run a vacuum operation on the database to reclaim space."""
        try:
            dbh = self._get_dbh()
            dbh.vacuumDB()
            return b'["SUCCESS", ""]'
        except Exception as e:
            return f'["ERROR", "{e}"]'.encode('utf-8')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scanstatus(self, id: str) -> list | dict:
        """Return the status and summary of a scan by its ID."""
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
    def scandelete(self, id: str) -> str | dict:
        """Delete a scan instance by its ID."""
        try:
            dbh = self._get_dbh()
            scan = dbh.scanInstanceGet(id)
            if not scan:
                return self.jsonify_error("404", "Scan not found")
            dbh.scanInstanceDelete(id)
            return ''
        except Exception as e:
            return self.jsonify_error("500", str(e))

    def jsonify_error(self, status: str, message: str) -> dict:
        """Helper method to create JSON error responses."""
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.status = status
        return {
            'error': {
                'http_status': status,
                'message': message,
            }
        }

    def error(self, message: str) -> str:
        """Show generic error page with error message."""
        from mako.template import Template
        templ = Template(
            filename='spiderfoot/templates/error.tmpl', lookup=self.lookup)
        return templ.render(message=message, docroot=self.docroot, version=__version__)

    def reset_settings(self) -> bool:
        """Reset settings to default."""
        try:
            dbh = self._get_dbh()
            dbh.configClear()
            return True
        except Exception as e:
            return False

    @cherrypy.expose
    def resultsetfp(self, id: str, resultids: str, fp: str) -> bytes:
        """Set false positive flag for scan results."""
        try:
            dbh = self._get_dbh()
            scan = dbh.scanInstanceGet(id)
            if not scan:
                return b'["ERROR", "Scan not found"]'

            # Parse result IDs
            import json
            try:
                ids = json.loads(resultids)
            except (json.JSONDecodeError, ValueError):
                ids = [resultids]

            # Update FP status
            for result_id in ids:
                dbh.scanResultsUpdateFP(result_id, fp == '1')

            return b'["SUCCESS", ""]'
        except Exception as e:
            return f'["ERROR", "{e}"]'.encode('utf-8')

    # savesettings: The JS form sends JSON, so we need to handle JSON parsing.
    # SettingsEndpoints.savesettings parses key=value lines which is incompatible.
    @cherrypy.expose
    def savesettings(self, allopts: str, token: str, configFile=None) -> str:
        """Save configuration settings from the web UI form (JSON or RESET)."""
        # CSRF token validation
        if str(token) != str(getattr(self, 'token', None)):
            from mako.template import Template
            templ = Template(filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
            return templ.render(
                opts=self.config, pageid='SETTINGS',
                token=self.token, version=__version__,
                updated=None, docroot=self.docroot,
                error_message="Invalid CSRF token",
            )

        try:
            from spiderfoot.sflib import SpiderFoot

            # Handle file upload
            if configFile and hasattr(configFile, 'file') and configFile.file:
                uploaded = configFile.file.read().decode('utf-8')
                new_config = {}
                for line in uploaded.splitlines():
                    if '=' in line:
                        k, v = line.split('=', 1)
                        new_config[k.strip()] = v.strip()
                dbh = self._get_dbh()
                dbh.configSet(new_config)
                sf = SpiderFoot(self.defaultConfig)
                self.config = sf.configUnserialize(new_config, self.defaultConfig)
            elif allopts == "RESET":
                try:
                    dbh = self._get_dbh()
                    dbh.configClear()
                except Exception:
                    pass
                self.config = self.defaultConfig.copy()
            else:
                # JS form sends JSON
                import json
                opts = json.loads(allopts)
                self.config.update(opts)
                # Persist to DB
                try:
                    sf = SpiderFoot(self.config)
                    serialized = sf.configSerialize(opts, self.defaultConfig)
                    dbh = self._get_dbh()
                    dbh.configSet(serialized)
                except Exception as e:
                    self.log.warning("Could not persist settings to DB: %s", e)

            raise cherrypy.HTTPRedirect(f"{self.docroot}/opts?updated=1")

        except cherrypy.HTTPRedirect:
            raise
        except Exception as e:
            from mako.template import Template
            templ = Template(filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
            return templ.render(
                opts=self.config, pageid='SETTINGS',
                token=self.token, version=__version__,
                updated=None, docroot=self.docroot,
                error_message=f"Processing one or more of your inputs failed. {str(e)}",
            )

    # startscan is inherited from ScanEndpoints (scan.py)
    # which supports both local (mp.Process) and API proxy mode.

    # rerunscan is inherited from ScanEndpoints (scan.py)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stopscan(self, id: str) -> str:
        """Stop one or more running scans by their IDs."""
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

    def _legacy_get_dbh(self):
        """Superseded by DbProvider._get_dbh() — kept as alias."""
        return self._get_dbh()

    # Add methods from helpers for backward compatibility
    def cleanUserInput(self, inputList: list) -> list:
        """Clean user input by escaping HTML."""
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

    def searchBase(self, scan_id: str | None = None, eventType: str | None = None, value: str | None = None) -> list:
        """Search scan results."""
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
        except Exception as e:
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

    def buildExcel(self, data: list, columnNames: list, sheetNameIndex: int = 0) -> bytes:
        """Convert supplied raw data into Excel format."""
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
    def scanexportlogs(self, scan_id: str, dialect: str = "excel") -> str | bytes:
        """Export scan logs."""
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
    def scancorrelationsexport(self, scan_id: str, filetype: str = "csv", dialect: str = "excel") -> str:
        """Export scan correlations."""
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
                cherrypy.response.headers['Content-Disposition'] = (
                    f"attachment; filename=SpiderFoot-{scan_id}-correlations.csv"
                )
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
    def scaneventresultexport(
        self, scan_id: str, event_type: str,
        filetype: str = "csv", dialect: str = "excel",
    ) -> str | bytes:
        """Export scan event results."""
        try:
            dbh = self._get_dbh()
            data = dbh.scanResultEvent(scan_id, event_type)

            headings = ["Date", "Type", "Value", "Source", "Module", "Risk", "FP", "Correlation", "EventId"]

            if filetype.lower() == 'csv':
                import csv
                from sfwebui import StringIO
                cherrypy.response.headers['Content-Disposition'] = (
                    f"attachment; filename=SpiderFoot-{scan_id}-{event_type}.csv"
                )
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
    def scaneventresultexportmulti(self, ids: str, filetype: str = "csv", dialect: str = "excel") -> str | bytes:
        """Export multiple scan event results."""
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
    def scansearchresultexport(
        self, scan_id: str,
        eventType: str | None = None,
        value: str | None = None,
        filetype: str = "csv",
        dialect: str = "excel",
    ) -> str | bytes:
        """Export search results."""
        try:
            search_results = self.searchBase(scan_id, eventType, value)

            headings = ["Date", "Type", "Value", "Source", "Module", "Risk", "FP", "Correlation", "EventId"]

            if filetype.lower() == 'csv':
                import csv
                from sfwebui import StringIO
                cherrypy.response.headers['Content-Disposition'] = (
                    f"attachment; filename=SpiderFoot-{scan_id}-search.csv"
                )
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
    def scanexportjsonmulti(self, ids: str) -> bytes:
        """Export multiple scans as JSON."""
        import json
        import time

        dbh = self._get_dbh()
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
    def scanviz(self, id: str = "", gexf: str = "0") -> str:
        """Generate scan visualization as JSON for sigma.js or GEXF for download."""
        if not id:
            cherrypy.response.headers['Content-Type'] = 'application/json'
            return b'{}'
        try:
            dbh = self._get_dbh()
            events = dbh.scanResultEvent(id, filterFp=True)
            scan = dbh.scanInstanceGet(id)

            if not scan:
                cherrypy.response.headers['Content-Type'] = 'application/json'
                return b'{}'

            root = scan[1]

            if not events:
                cherrypy.response.headers['Content-Type'] = 'application/json'
                return json.dumps({'nodes': [], 'edges': []}).encode('utf-8')

            # Build event type category lookup for graph building
            # DB format: (event_descr, event, event_raw, event_type)
            # API/JSON format: [event_descr, event, event_raw, event_type] or dict
            event_type_categories = {}
            try:
                et_list = dbh.eventTypes()
                if et_list:
                    for et in et_list:
                        if isinstance(et, (list, tuple)):
                            if len(et) >= 4:
                                # DB tuple: (descr, event_name, raw, category)
                                event_type_categories[et[1]] = et[3]
                            elif len(et) >= 2:
                                event_type_categories[et[0]] = et[1] if len(et) > 1 else 'DATA'
                        elif isinstance(et, dict):
                            event_type_categories[et.get('event', '')] = et.get('event_type', 'DATA')
            except Exception:
                pass

            # Build hash → data value mapping for parent resolution
            hash_to_data = {}
            for row in events:
                row = list(row) if isinstance(row, tuple) else row
                event_hash = row[3] if len(row) > 3 else ''
                event_data = row[1] if len(row) > 1 else ''
                if event_hash:
                    hash_to_data[event_hash] = event_data

            # Transform 9-element tuples to 15-element format for buildGraphData
            # 15-col format: generated, data, source_data, module, type,
            #   source_event_hash, confidence, visibility, hash, false_positive,
            #   risk, event_type_category, event_descr, parent_type_category, parent_descr
            extended_data = []
            for row in events:
                row = list(row) if isinstance(row, tuple) else row
                generated = row[0] if len(row) > 0 else 0
                data_val = row[1] if len(row) > 1 else ''
                module = row[2] if len(row) > 2 else ''
                event_hash = row[3] if len(row) > 3 else ''
                event_type = row[4] if len(row) > 4 else ''
                source_hash = row[5] if len(row) > 5 else 'ROOT'
                confidence = row[6] if len(row) > 6 else 100
                visibility = row[7] if len(row) > 7 else 100
                risk = row[8] if len(row) > 8 else 0

                # Resolve parent data value from hash
                source_data = hash_to_data.get(source_hash, 'ROOT') if source_hash != 'ROOT' else root
                # Look up event type category
                category = event_type_categories.get(event_type, 'DATA')

                extended_row = (
                    generated,       # 0
                    data_val,        # 1 - entity value
                    source_data,     # 2 - parent entity value
                    module,          # 3
                    event_type,      # 4 - event type
                    source_hash,     # 5
                    confidence,      # 6
                    visibility,      # 7
                    event_hash,      # 8 - event ID
                    0,               # 9 - false_positive
                    risk,            # 10
                    category,        # 11 - ENTITY/INTERNAL/DESCRIPTOR/DATA
                    '',              # 12 - event_descr
                    '',              # 13 - parent_type_category
                    '',              # 14 - parent_descr
                )
                extended_data.append(extended_row)

            from spiderfoot.helpers import SpiderFootHelpers

            if gexf != "0":
                scan_name = scan[0] if scan[0] else 'SpiderFoot'
                cherrypy.response.headers['Content-Disposition'] = f"attachment; filename={scan_name}-SpiderFoot.gexf"
                cherrypy.response.headers['Content-Type'] = 'application/gexf'
                cherrypy.response.headers['Pragma'] = 'no-cache'
                return SpiderFootHelpers.buildGraphGexf([root], 'SpiderFoot Export', extended_data)

            cherrypy.response.headers['Content-Type'] = 'application/json'
            result = SpiderFootHelpers.buildGraphJson([root], extended_data)
            if isinstance(result, str):
                return result.encode('utf-8')
            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            cherrypy.response.headers['Content-Type'] = 'application/json'
            return b'{}'

    @cherrypy.expose
    def scanvizmulti(self, ids: str, gexf: str = "1") -> str:
        """Generate multi-scan visualization."""
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
            self.config['__database'] = DEFAULT_DATABASE_NAME

        # Validate other critical configuration keys
        if '__version__' not in self.config:
            self.config['__version__'] = __version__

        if '_logging' not in self.config:
            self.config['_logging'] = 'INFO'

        if '_modulesenabled' not in self.config:
            self.config['_modulesenabled'] = []
