# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_googletagmanager
# Purpose:      Spiderfoot plugin to extract Google Tag Manager IDs (GTM-XXXXXX)
#               from a target website.
#
# Author:      Agostino Panico
#
# Created:     22/04/2025
# Copyright:   (c) 2025 Agostino Panico @poppopjmp
# Licence:     MIT
# -------------------------------------------------------------------------------

import re
from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_googletagmanager(SpiderFootPlugin):

    meta = {
        'name': "Google Tag Manager Identifier",
        'summary': "Identify Google Tag Manager (GTM-XXXXXX) IDs on web pages.",
        'flags': ["slow"],
        'useCases': ["Footprint", "Passive"],
        'categories': ["Content Analysis"],
        'dataSource': {
            'website': "https://marketingplatform.google.com/about/tag-manager/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://developers.google.com/tag-manager/quickstart",
                "https://support.google.com/tagmanager/answer/6102821"
            ],
            'favIcon': "https://www.google.com/s2/favicons?domain=google.com",
            'logo': "https://marketingplatform.google.com/about/static/images/gmp/product-icon-tag-manager.svg",
            'description': "Google Tag Manager is a tag management system that allows you to quickly and "
            "easily update measurement codes and related code fragments collectively known as tags on your website or mobile app."
        }
    }

    # Default options
    opts = {
        'checklinks': True,
        'checkcontent': True,
        'checkrobots': True,
    }

    # Option descriptions
    optdescs = {
        'checklinks': "Check links for Google Tag Manager IDs",
        'checkcontent': "Check page content for Google Tag Manager IDs",
        'checkrobots': "Check robots.txt for Google Tag Manager IDs",
    }

    results = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["LINKED_URL_INTERNAL", "TARGET_WEB_CONTENT"]

    # What events this module produces
    def producedEvents(self):
        return ["GTM_ID"]

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if eventData in self.results:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")
        self.results[eventData] = True

        if eventName == "TARGET_WEB_CONTENT":
            # Extract Google Tag Manager IDs from content
            if self.opts['checkcontent']:
                gtm_ids = self.extractGtmIds(eventData)
                for gtm_id in gtm_ids:
                    evt = SpiderFootEvent("GTM_ID", gtm_id, self.__name__, event)
                    self.notifyListeners(evt)

        if eventName == "LINKED_URL_INTERNAL" and self.opts['checklinks']:
            # Fetch the web content
            res = self.sf.fetchUrl(eventData, timeout=self.opts['_fetchtimeout'],
                                    useragent=self.opts['_useragent'])
            
            if res['content'] is None:
                self.debug(f"No content returned from {eventData}")
                return
            
            # Look for Google Tag Manager IDs in the content
            gtm_ids = self.extractGtmIds(str(res['content']))
            for gtm_id in gtm_ids:
                evt = SpiderFootEvent("GTM_ID", gtm_id, self.__name__, event)
                self.notifyListeners(evt)

    def extractGtmIds(self, content):
        """Extract Google Tag Manager IDs from content

        Args:
            content (str): Content to extract from

        Returns:
            list: List of Google Tag Manager IDs
        """
        # Google Tag Manager IDs follow the format GTM-XXXXXX where X is alphanumeric
        # They are found in script tags or in the URL to googletagmanager.com
        pattern = r'GTM-[A-Z0-9]{1,7}'
        matches = re.findall(pattern, content, re.IGNORECASE)
        
        return list(set([m.upper() for m in matches]))  # Return unique IDs