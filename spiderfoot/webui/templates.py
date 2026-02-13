"""WebUI endpoints for documentation pages and miscellaneous template rendering."""

from __future__ import annotations

import cherrypy
from mako.template import Template
from spiderfoot import __version__

# Optional: helpers for template rendering
# Add template-related helpers here if needed


class MiscEndpoints:
    """WebUI endpoints for documentation and miscellaneous pages."""
    @cherrypy.expose
    def documentation(self, doc: str | None = None, q: str | None = None) -> str:
        """Render the documentation page with optional search query highlighting."""
        # Render documentation page or search results
        import re

        def highlight(text: str, query: str) -> str:
            """Highlight occurrences of a query string in text with HTML marks."""
            if not text or not query:
                return text
            pattern = re.compile(re.escape(query), re.IGNORECASE)
            return pattern.sub(lambda m: f'<mark>{m.group(0)}</mark>', text)

        templ = Template(filename='spiderfoot/templates/documentation.tmpl', lookup=self.lookup)
        return templ.render(
            doc=doc,
            q=q,
            docroot=self.docroot,
            version=__version__,
            current_version='latest',
            selected_file=doc,
            search_query=q or '',
            version_dirs=[],
            doc_index=[],  # Changed from sidebar_entries to doc_index
            content='',
            search_results=[],
            toc_html='',
            breadcrumbs=[],
            last_updated='',
            author='@poppopjmp',
            related=[],
            title='Documentation',
            highlight=highlight
        )

    @cherrypy.expose
    def active_maintenance_status(self) -> str:
        """Return the current active maintenance status."""
        # Return a simple status string or JSON
        return "OK"

    @cherrypy.expose
    def footer(self) -> str:
        """Render the page footer template."""
        # Render a footer template or return a static string
        templ = Template(filename='spiderfoot/templates/FOOTER.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    def workspaces(self) -> str:
        """Render the workspace list page."""
        # Render the workspace list UI page
        templ = Template(filename='spiderfoot/templates/workspaces.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    def enrichment(self) -> str:
        """Render the document upload & enrichment page."""
        templ = Template(filename='spiderfoot/templates/enrichment.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__, pageid='ENRICHMENT')

    @cherrypy.expose
    def userinput(self) -> str:
        """Render the user input / IOC submission page."""
        templ = Template(filename='spiderfoot/templates/userinput.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__, pageid='USERINPUT')

    @cherrypy.expose
    def agents(self) -> str:
        """Render the AI agents dashboard page."""
        templ = Template(filename='spiderfoot/templates/agents.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__, pageid='AGENTS')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload_document(self, **kwargs) -> dict:
        """Handle document upload and forward to enrichment service.

        Accepts multipart file upload, forwards to the enrichment pipeline,
        and returns extracted entities.
        """
        import requests
        import json

        enrichment_url = self.config.get('_enrichment_url', 'http://enrichment:8200')

        cl = cherrypy.request.headers.get('Content-Length', 0)
        if int(cl) > 100 * 1024 * 1024:  # 100MB
            raise cherrypy.HTTPError(413, 'File too large')

        upload_file = kwargs.get('file')
        scan_id = kwargs.get('scan_id', '')

        if not upload_file:
            raise cherrypy.HTTPError(400, 'No file provided')

        try:
            filename = upload_file.filename
            file_data = upload_file.file.read()

            resp = requests.post(
                f"{enrichment_url}/process",
                files={'file': (filename, file_data)},
                data={'scan_id': scan_id} if scan_id else {},
                timeout=120
            )

            if resp.status_code == 200:
                return resp.json()
            else:
                return {'status': 'error', 'message': resp.text, 'entities': {}}

        except requests.exceptions.ConnectionError:
            # Enrichment service offline — do local regex extraction
            return self._local_extract(file_data.decode('utf-8', errors='ignore') if file_data else '')
        except Exception as e:
            return {'status': 'error', 'message': str(e), 'entities': {}}

    def _local_extract(self, text: str) -> dict:
        """Fallback local entity extraction when enrichment service is unavailable."""
        import re
        entities = {}

        patterns = {
            'ip': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'domain': r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'md5': r'\b[a-fA-F0-9]{32}\b',
            'sha256': r'\b[a-fA-F0-9]{64}\b',
            'cve': r'CVE-\d{4}-\d{4,}',
            'url': r'https?://[^\s<>"{}|\\^`\[\]]+',
        }

        for entity_type, pattern in patterns.items():
            matches = list(set(re.findall(pattern, text)))
            if matches:
                entities[entity_type] = matches[:100]  # cap at 100 per type

        return {'status': 'ok', 'message': 'Local extraction (enrichment offline)', 'entities': entities}
