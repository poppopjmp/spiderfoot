from __future__ import annotations

"""SpiderFoot plug-in module: cookie."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_cookie
# Purpose:      SpiderFoot plug-in for extracting cookies from HTTP headers.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     06/04/2014
# Copyright:   (c) Steve Micallef 2014
# Licence:     MIT
# -------------------------------------------------------------------------------

import json

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_cookie(SpiderFootModernPlugin):
    """SpiderFoot plugin to extract cookies from HTTP headers."""
    meta = {
        'name': "Cookie Extractor",
        'summary': "Extract Cookies from HTTP headers.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Content Analysis"]
    }

    opts = {}
    optdescs = {}

    results = None

    def setup(self, sfc, userOpts=None):
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.__dataSource__ = "Target Website"
    # What events is this module interested in for input
    def watchedEvents(self):
        """Return the list of events this module watches."""
        return ["WEBSERVER_HTTPHEADERS"]

    # What events this module produces
    def producedEvents(self):
        """Return the list of events this module produces."""
        return ["TARGET_WEB_COOKIE"]

    # Handle events sent to this module
    def handleEvent(self, event):
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        eventSource = event.actualSource

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventSource in self.results:
            return

        self.results[eventSource] = True

        fqdn = self.sf.urlFQDN(eventSource)
        if not self.getTarget().matches(fqdn):
            self.debug(
                f"Not collecting cookies from external sites. Ignoring HTTP headers from {fqdn}")
            return

        try:
            data = json.loads(eventData)
        except Exception as e:
            self.error(
                "Received HTTP headers from another module in an unexpected format.")
            return

        cookie = data.get('cookie')
        if cookie:
            evt = SpiderFootEvent("TARGET_WEB_COOKIE",
                                  cookie, getattr(self, '__name__', self.__class__.__name__), event)
            self.notifyListeners(evt)

# End of sfp_cookie class
