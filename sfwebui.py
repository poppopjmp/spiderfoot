# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         sfwebui wrapper
# Purpose:      Web User interface class for use with a web browser
#
# Author:       Agostino Panico poppopjmp 
#
# Created:      03/07/2025
# Copyright:    (c) Agostino Panico poppopjmp 
# License:      MIT
# -----------------------------------------------------------------

from spiderfoot.webui.main import create_app, main
from spiderfoot.webui.routes import WebUiRoutes
from spiderfoot import SpiderFootDb, SpiderFoot
from spiderfoot.logger import logListenerSetup, logWorkerSetup
from mako.template import Template
from mako.lookup import TemplateLookup
import openpyxl
from io import BytesIO, StringIO
import multiprocessing as mp
import time
from spiderfoot.helpers import SpiderFootHelpers
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot.webui.scan import ScanEndpoints
from spiderfoot.webui.workspace import WorkspaceEndpoints
from spiderfoot.webui.templates import MiscEndpoints
import cherrypy
try:
    import secure
except ImportError:
    secure = None

# For backward compatibility
SpiderFootWebUi = WebUiRoutes
SpiderFootDb = SpiderFootDb
SpiderFoot = SpiderFoot
logListenerSetup = logListenerSetup
logWorkerSetup = logWorkerSetup

Template = Template
openpyxl = openpyxl
BytesIO = BytesIO
StringIO = StringIO
mp = mp
time = time
SpiderFootHelpers = SpiderFootHelpers
SpiderFootWorkspace = SpiderFootWorkspace

class SpiderFootWebUiApp:
    def __init__(self, config, docroot=None, loggingQueue=None):
        # --- Config merging (DB + defaults) ---
        from copy import deepcopy
        self.defaultConfig = deepcopy(config)
        dbh = SpiderFootDb(self.defaultConfig, init=True)
        sf = SpiderFoot(self.defaultConfig)
        self.config = sf.configUnserialize(dbh.configGet(), self.defaultConfig)
        self.docroot = docroot or '/'
        # --- Logging queue/listener/worker setup ---
        import logging
        if loggingQueue is None:
            self.loggingQueue = mp.Queue()
            logListenerSetup(self.loggingQueue, self.config)
        else:
            self.loggingQueue = loggingQueue
        logWorkerSetup(self.loggingQueue)
        self.log = logging.getLogger(f"spiderfoot.{__name__}")
        # --- TemplateLookup setup ---
        self.lookup = TemplateLookup(directories=['spiderfoot/templates'])
        # Instantiate endpoint classes
        self.scan = ScanEndpoints()
        self.scan.config = self.config
        self.scan.docroot = self.docroot
        self.scan.lookup = self.lookup
        self.workspace = WorkspaceEndpoints()
        self.workspace.config = self.config
        self.workspace.docroot = self.docroot
        self.workspace.lookup = self.lookup
        self.misc = MiscEndpoints()
        self.misc.config = self.config
        self.misc.docroot = self.docroot
        self.misc.lookup = self.lookup
        # --- CSP and Secure Headers Setup ---
        if secure:
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

    def mount(self):
        cherrypy.tree.mount(self.scan, '/scan')
        cherrypy.tree.mount(self.workspace, '/workspace')
        cherrypy.tree.mount(self.misc, '/')
        # Register error handlers
        cherrypy.config.update({
            'error_page.401': self.scan.error_page_401,
            'error_page.404': self.scan.error_page_404,
            'request.error_response': self.scan.error_page
        })

if __name__ == "__main__":
    main()