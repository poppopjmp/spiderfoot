import cherrypy
import sfwebui
from spiderfoot import __version__

# Optional: helpers for template rendering
# Add template-related helpers here if needed

class MiscEndpoints:
    @cherrypy.expose
    def documentation(self, doc=None, q=None):
        # Render documentation page or search results
        templ = sfwebui.Template(filename='spiderfoot/templates/documentation.tmpl', lookup=self.lookup)
        return templ.render(doc=doc, q=q, docroot=self.docroot, version=__version__)

    @cherrypy.expose
    def active_maintenance_status(self):
        # Return a simple status string or JSON
        return "OK"

    @cherrypy.expose
    def footer(self):
        # Render a footer template or return a static string
        templ = sfwebui.Template(filename='spiderfoot/templates/footer.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)

    @cherrypy.expose
    def workspaces(self):
        # Render the workspace list UI page
        templ = sfwebui.Template(filename='spiderfoot/templates/workspaces.tmpl', lookup=self.lookup)
        return templ.render(docroot=self.docroot, version=__version__)
