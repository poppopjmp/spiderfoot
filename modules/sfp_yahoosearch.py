# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_yahoosearch
# Purpose:      Searches Yahoo for information related to the target.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     07/09/2018
# Copyright:   (c) Steve Micallef
# Licence:     GPL
# -------------------------------------------------------------------------------

from spiderfoot import SpiderFootEvent, SpiderFootPlugin

class sfp_yahoosearch(SpiderFootPlugin):

    meta = {
        'name': "Yahoo Search",
        'summary': "Search Yahoo for information related to the target.",
        'flags': ["slow"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Search Engines"]
    }

    # Default options
    opts = {
        'fetchlinks': True,
        'maxresults': 100
    }

    # Option descriptions
    optdescs = {
        'fetchlinks': "Fetch the URLs mentioned in Yahoo search results.",
        'maxresults': "Maximum number of results to obtain."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.__dataSource__ = "Yahoo"

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ["DOMAIN_NAME", "HUMAN_NAME", "COMPANY_NAME"]

    def producedEvents(self):
        return ["LINKED_URL", "SEARCH_ENGINE_WEB_CONTENT"]

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if eventData in self.results:
            self.debug(f"Already did a search for {eventData}, skipping.")
            return None

        self.results[eventData] = True
        
        self.debug(f"Searching Yahoo for: {eventData}")
        
        # Mock implementation - in a real plugin this would perform an actual search
        return None
