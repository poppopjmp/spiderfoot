import cherrypy
from operator import itemgetter
from spiderfoot import __version__
try:
    from spiderfoot.sflib import SpiderFoot
except ImportError:
    pass

class InfoEndpoints:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def eventtypes(self):
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        dbh = self.get_dbh()
        types = dbh.eventTypes()
        ret = list()
        for r in types:
            ret.append(r)
        return sorted(ret, key=itemgetter(0))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def modules(self):
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        modlist = list()
        modules_data = self.config['__modules__']
        
        # Handle both dict and list formats for backward compatibility
        if isinstance(modules_data, dict):
            # Convert dict to list format expected by frontend
            for mod_name, mod_obj in modules_data.items():
                if hasattr(mod_obj, '__doc__') and hasattr(mod_obj, 'opts'):
                    mod_dict = {
                        'name': mod_name,
                        'descr': mod_obj.__doc__ or 'No description available',
                        'provides': getattr(mod_obj, 'produces', []),
                        'consumes': getattr(mod_obj, 'watchedEvents', []),
                        'opts': getattr(mod_obj, 'opts', {})
                    }
                    modlist.append(mod_dict)
                else:
                    # Fallback for simple string entries
                    modlist.append({
                        'name': mod_name,
                        'descr': 'Module description not available',
                        'provides': [],
                        'consumes': [],
                        'opts': {}
                    })
        else:
            # Handle list format (original)
            for mod in modules_data:
                modlist.append(mod)
        
        return sorted(modlist, key=lambda x: x['name'])

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def correlationrules(self):
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        rules = list()
        for rule in self.config.get('__correlationrules__', []):
            rules.append(rule)
        return sorted(rules, key=lambda x: x['name'])

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ping(self):
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        return ["SUCCESS", __version__]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def query(self, query):
        dbh = self.get_dbh()
        if not query:
            return ["ERROR", "No query provided"]
        if not query.lower().startswith("select"):
            return ["ERROR", "Only SELECT queries are allowed"]
        try:
            result = dbh.query(query)
            return ["SUCCESS", result]
        except Exception as e:
            return ["ERROR", str(e)]

    def get_dbh(self):
        from spiderfoot import SpiderFootDb
        return SpiderFootDb(self.config)
