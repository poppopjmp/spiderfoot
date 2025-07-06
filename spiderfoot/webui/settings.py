import cherrypy
import random
import json
from mako.template import Template
from spiderfoot.sflib import SpiderFoot
from spiderfoot import __version__

class SettingsEndpoints:
    @cherrypy.expose
    def opts(self, updated=None):
        templ = Template(filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
        self.token = random.SystemRandom().randint(0, 99999999)
        return templ.render(opts=self.config, pageid='SETTINGS', token=self.token, version=__version__, updated=updated, docroot=self.docroot)

    @cherrypy.expose
    def optsexport(self, pattern=None):
        sf = SpiderFoot(self.config)
        conf = sf.configSerialize(self.config)
        content = ""
        for opt in sorted(conf):
            content += f"{opt}={conf[opt]}\n"
        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename="SpiderFoot.cfg"'
        cherrypy.response.headers['Content-Type'] = "text/plain"
        return content

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def optsraw(self):
        ret = dict()
        self.token = random.SystemRandom().randint(0, 99999999)
        for opt in self.config:
            ret[opt] = self.config[opt]
        return ['SUCCESS', {'token': self.token, 'data': ret}]

    @cherrypy.expose
    def savesettings(self, allopts, token, configFile=None):
        if str(token) != str(self.token):
            # Render opts.tmpl with error message for CSRF error
            templ = Template(filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
            return templ.render(
                opts=self.config,
                pageid='SETTINGS',
                token=self.token,
                version=__version__,
                updated=None,
                docroot=self.docroot,
                error_message="Invalid CSRF token"
            )
        from spiderfoot import SpiderFootDb, SpiderFoot
        # Handle file upload
        if configFile and hasattr(configFile, 'file') and configFile.file:
            try:
                uploaded = configFile.file.read().decode('utf-8')
                # Parse config: key=value per line
                new_config = {}
                for line in uploaded.splitlines():
                    if '=' in line:
                        k, v = line.split('=', 1)
                        new_config[k.strip()] = v.strip()
                dbh = SpiderFootDb(self.config)
                dbh.configSet(new_config)
                sf = SpiderFoot(self.defaultConfig)
                self.config = sf.configUnserialize(new_config, self.defaultConfig)
            except Exception as e:
                from sfwebui import Template
                templ = Template(filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
                return templ.render(
                    opts=self.config,
                    pageid='SETTINGS',
                    token=self.token,
                    version=__version__,
                    updated=None,
                    docroot=self.docroot,
                    error_message=f"Processing one or more of your inputs failed. {str(e)}"
                )
        # Reset config to default
        elif allopts == "RESET":
            self.reset_settings()
        # Save settings from form
        else:
            try:
                # allopts is key=value per line
                new_config = {}
                for line in allopts.splitlines():
                    if '=' in line:
                        k, v = line.split('=', 1)
                        new_config[k.strip()] = v.strip()
                dbh = SpiderFootDb(self.config)
                dbh.configSet(new_config)
                sf = SpiderFoot(self.defaultConfig)
                self.config = sf.configUnserialize(new_config, self.defaultConfig)
            except Exception as e:
                from sfwebui import Template
                templ = Template(filename='spiderfoot/templates/opts.tmpl', lookup=self.lookup)
                return templ.render(
                    opts=self.config,
                    pageid='SETTINGS',
                    token=self.token,
                    version=__version__,
                    updated=None,
                    docroot=self.docroot,
                    error_message=f"Processing one or more of your inputs failed. {str(e)}"
                )
        raise cherrypy.HTTPRedirect(f"{self.docroot}/opts?updated=1")

    @cherrypy.expose
    def savesettingsraw(self, allopts, token):
        cherrypy.response.headers['Content-Type'] = "application/json; charset=utf-8"
        from spiderfoot import SpiderFootDb, SpiderFoot
        if str(token) != str(self.token):
            return json.dumps(["ERROR", "Invalid CSRF token"]).encode('utf-8')
        # Reset config to default
        if allopts == "RESET":
            self.reset_settings()
        # Save settings from raw
        else:
            try:
                new_config = {}
                for line in allopts.splitlines():
                    if '=' in line:
                        k, v = line.split('=', 1)
                        new_config[k.strip()] = v.strip()
                dbh = SpiderFootDb(self.config)
                dbh.configSet(new_config)
                sf = SpiderFoot(self.defaultConfig)
                self.config = sf.configUnserialize(new_config, self.defaultConfig)
            except Exception as e:
                return json.dumps(["ERROR", str(e)]).encode('utf-8')
        return json.dumps(["SUCCESS", ""]).encode('utf-8')

    def reset_settings(self):
        try:
            from spiderfoot import SpiderFootDb
            dbh = SpiderFootDb(self.config)
            dbh.configClear()  # Clear it in the DB
            self.config = self.defaultConfig.copy()  # Clear in memory
        except Exception:
            return False
        return True
