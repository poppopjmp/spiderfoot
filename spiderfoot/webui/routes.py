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

class WebUiRoutes(ScanEndpoints, ExportEndpoints, WorkspaceEndpoints, InfoEndpoints, SettingsEndpoints, WebUiHelpers):
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

        self.lookup = TemplateLookup(directories=[''])

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
        from sfwebui import Template
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
            from sfwebui import Template
            templ = Template(filename='spiderfoot/templates/documentation.tmpl', lookup=self.lookup)
            try:
                return templ.render(
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
            from sfwebui import Template
            templ = Template(filename='spiderfoot/templates/documentation.tmpl', lookup=self.lookup)
            try:
                return templ.render(
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
        except Exception as e:
            self.log.error(f"Documentation endpoint error: {e}")
            from sfwebui import Template
            templ = Template(filename='spiderfoot/templates/documentation.tmpl', lookup=self.lookup)
            try:
                return templ.render(
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
        from sfwebui import Template
        templ = Template(
            filename='spiderfoot/templates/footer.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    def active_maintenance_status(self):
        from sfwebui import Template
        templ = Template(
            filename='spiderfoot/templates/active_maintenance_status.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)
