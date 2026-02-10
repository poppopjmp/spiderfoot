from __future__ import annotations

"""SpiderFoot plug-in module: intfiles."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_intfiles
# Purpose:      From Spidered pages found, identifies files of potential interest.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     06/04/2014
# Copyright:   (c) Steve Micallef 2014
# Licence:     MIT
# -------------------------------------------------------------------------------

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_intfiles(SpiderFootModernPlugin):
    """Identifies potential files of interest, e.g. office documents, zip files."""

    __name__ = "sfp_intfiles"

    meta = {
        'name': "Interesting File Finder",
        'summary': "Identifies potential files of interest, e.g. office documents, zip files.",
        'flags': [],
        'useCases': ["Footprint", "Passive"],
        'categories': ["Crawling and Scanning"]
    }

    # Default options
    opts = {
        'fileexts': ["doc", "docx", "ppt", "pptx", "pdf", 'xls', 'xlsx', 'zip']
    }

    # Option descriptions
    optdescs = {
        'fileexts': "File extensions of files you consider interesting."
    }

    results = None

    def setup(self, sfc, userOpts=None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.__dataSource__ = "Target Website"
    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["LINKED_URL_INTERNAL"]

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["INTERESTING_FILE"]

    # Handle events sent to this module
    def handleEvent(self, event) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            return

        self.results[eventData] = True

        for fileExt in self.opts['fileexts']:
            if "." + fileExt.lower() in eventData.lower():
                evt = SpiderFootEvent("INTERESTING_FILE", eventData,
                                      self.__name__, event)
                self.notifyListeners(evt)

# End of sfp_intfiles class
