import cherrypy
from mako.template import Template
from spiderfoot import __version__

# Optional: helpers for template rendering
# Add template-related helpers here if needed


class MiscEndpoints:
    @cherrypy.expose
    def documentation(self, doc=None, q=None):
        # Render documentation page or search results
        import re
        
        def highlight(text, query):
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
    def active_maintenance_status(self):
        # Return a simple status string or JSON
        return "OK"

    @cherrypy.expose
    def footer(self):
        # Render a footer template or return a static string
        templ = Template(filename='spiderfoot/templates/FOOTER.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    def workspaces(self):
        # Render the workspace list UI page
        templ = Template(filename='spiderfoot/templates/workspaces.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)