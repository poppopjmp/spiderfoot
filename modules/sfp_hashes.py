from __future__ import annotations

"""SpiderFoot plug-in module: hashes."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_hashes
# Purpose:      SpiderFoot plug-in for scanning retrieved content by other
#               modules (such as sfp_spider) and identifying hashes
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     24/01/2020
# Copyright:   (c) Steve Micallef 2020
# Licence:     MIT
# -------------------------------------------------------------------------------

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_hashes(SpiderFootModernPlugin):

    """Identify MD5 and SHA hashes in web content, files and more."""

    meta = {
        'name': "Hash Extractor",
        'summary': "Identify MD5 and SHA hashes in web content, files and more.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Content Analysis"],
        "dataSource": {
            "website": None,
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": [],
            "description": "Local data processing and extraction (no external API).",
        },
    }

    # Default options
    opts = {
        # options specific to this module
    }

    # Option descriptions
    optdescs = {
    }

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["TARGET_WEB_CONTENT", "BASE64_DATA",
                "LEAKSITE_CONTENT", "RAW_DNS_RECORDS",
                "RAW_FILE_META_DATA"]

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["HASH"]

    # Handle events sent to this module
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        hashes = SpiderFootHelpers.extractHashesFromText(eventData)
        for hashtup in hashes:
            hashalgo, hashval = hashtup

            evt = SpiderFootEvent(
                "HASH", f"[{hashalgo}] {hashval}", getattr(self, '__name__', self.__class__.__name__), event)
            if event.moduleDataSource:
                evt.moduleDataSource = event.moduleDataSource
            else:
                evt.moduleDataSource = "Unknown"
            self.notifyListeners(evt)

# End of sfp_hashes class
