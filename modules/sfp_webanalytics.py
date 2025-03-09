# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_webanalytics
# Purpose:     Scans retrieved content by other modules (such as sfp_spider and
#              sfp_dnsraw) and identifies web analytics IDs.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     06/04/2014
# Copyright:   (c) Steve Micallef 2014
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import re
from urllib.parse import quote_plus

from spiderfoot import SpiderFootEvent, SpiderFootPlugin
# Module now uses the logging from the SpiderFootPlugin base class

class sfp_webanalytics(SpiderFootPlugin):

    meta = {
        'name': "Web Analytics Extractor",
        'summary': "Identify web analytics IDs in scraped webpages and DNS TXT records.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Content Analysis"]
    }

    opts = {}
    optdescs = {}

    results = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ['TARGET_WEB_CONTENT', 'DNS_TEXT']

    # What events this module produces
    def producedEvents(self):
        return ["WEB_ANALYTICS_ID"]

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        sourceData = self.sf.hashstring(eventData)

        if sourceData in self.results:
            self.self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[sourceData] = True

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if event.moduleDataSource:
            datasource = event.moduleDataSource
        else:
            datasource = "Unknown"

        if eventName == 'TARGET_WEB_CONTENT':
            # Google Analytics
            matches = re.findall(r"\bua\-\d{4,10}\-\d{1,4}\b", eventData, re.IGNORECASE)
            for m in matches:
                self.self.info(f"Google Analytics ID found: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"Google Analytics: {m}", self.__name__, event)
                self.notifyListeners(evt)

            # Google AdSense
            matches = re.findall(r"\b(pub-\d{10,20})\b", eventData, re.IGNORECASE)
            for m in matches:
                self.self.info(f"Google AdSense ID found: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"Google AdSense: {m}", self.__name__, event)
                self.notifyListeners(evt)

            # Google Tag Manager
            matches = re.findall(r"\b(GTM-[0-9a-zA-Z]{6,10})\b", eventData)
            for m in set(matches):
                self.self.info(f"Google Tag Manager ID found: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"Google Tag Manager: {m}", self.__name__, event)
                self.notifyListeners(evt)

            # Google Website Verification
            # https://developers.google.com/site-verification/v1/getting_started
            matches = re.findall(r'<meta name="google-site-verification" content="([a-z0-9\-\+_=]{43,44})"', eventData, re.IGNORECASE)
            for m in matches:
                self.self.info(f"Google Site Verification ID found: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"Google Site Verification: {m}", self.__name__, event)
                self.notifyListeners(evt)

            matches = re.findall(r'<meta name="verify-v1" content="([a-z0-9\-\+_=]{43,44})"', eventData, re.IGNORECASE)
            for m in matches:
                self.self.info(f"Google Site Verification ID found: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"Google Site Verification: {m}", self.__name__, event)
                self.notifyListeners(evt)

            # Quantcast
            if '_qevents.push' in eventData:
                self.self.info("Quantcast analytics code found")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", "Quantcast Analytics", self.__name__, event)
                self.notifyListeners(evt)

            # Ahrefs Site Verification
            matches = re.findall(r'<meta name="ahrefs-site-verification" content="([a-f0-9]{64})"', eventData, re.IGNORECASE)
            for m in matches:
                self.self.info(f"Ahrefs Site Verification ID found: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"Ahrefs Site Verification: {m}", self.__name__, event)
                self.notifyListeners(evt)

        if eventName == 'DNS_TEXT':
            # Google Website Verification
            # https://developers.google.com/site-verification/v1/getting_started
            matches = re.findall(r'google-site-verification=([a-z0-9\-\+_=]{43,44})$', eventData.strip(), re.IGNORECASE)
            for m in matches:
                self.self.info(f"Google Site Verification ID found in DNS: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"Google Site Verification (DNS): {m}", self.__name__, event)
                self.notifyListeners(evt)

            # LogMeIn Domain Verification
            # https://support.logmeininc.com/openvoice/help/adding-a-txt-record-to-a-dns-server-ov710011
            matches = re.findall(r'logmein-domain-confirmation ([A-Z0-9]{24})$', eventData.strip(), re.IGNORECASE)
            for m in matches:
                self.self.info(f"LogMeIn Domain Verification ID found in DNS: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"LogMeIn Domain Verification (DNS): {m}", self.__name__, event)
                self.notifyListeners(evt)

            matches = re.findall(r'logmein-verification-code=([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$', eventData.strip(), re.IGNORECASE)
            for m in matches:
                self.self.info(f"LogMeIn Verification ID found in DNS: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"LogMeIn Verification (DNS): {m}", self.__name__, event)
                self.notifyListeners(evt)

            # DocuSign Domain Verification
            # https://support.docusign.com/en/guides/org-admin-guide-domains
            matches = re.findall(r'docusign=([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$', eventData.strip(), re.IGNORECASE)
            for m in matches:
                self.self.info(f"DocuSign Domain Verification ID found in DNS: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"DocuSign Domain Verification (DNS): {m}", self.__name__, event)
                self.notifyListeners(evt)

            # GlobalSign Site Verification
            # https://support.globalsign.com/customer/en/portal/articles/2167245-performing-domain-verification---dns-txt-record
            matches = re.findall(r'globalsign-domain-verification=([a-z0-9\-\+_=]{42,44})$', eventData.strip(), re.IGNORECASE)
            for m in matches:
                self.self.info(f"GlobalSign Site Verification ID found in DNS: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"GlobalSign Site Verification (DNS): {m}", self.__name__, event)
                self.notifyListeners(evt)

            # Atlassian Domain Verification
            # https://confluence.atlassian.com/cloud/verify-a-domain-for-your-organization-873871234.html
            matches = re.findall(r'atlassian-domain-verification=([a-z0-9\-\+\/_=]{64})$', eventData.strip(), re.IGNORECASE)
            for m in matches:
                self.self.info(f"Atlassian Domain Verification ID found in DNS: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"Atlassian Domain Verification (DNS): {m}", self.__name__, event)
                self.notifyListeners(evt)

            # Adobe IDP Site Verification
            # https://helpx.adobe.com/au/enterprise/using/verify-domain-ownership.html
            matches = re.findall(r'adobe-idp-site-verification=([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$', eventData.strip(), re.IGNORECASE)
            for m in matches:
                self.self.info(f"Adobe IDP Site Verification ID found in DNS: {m}")
                evt = SpiderFootEvent("WEB_ANALYTICS_ID", f"Adobe IDP Site Verification (DNS): {m}", self.__name__, event)
                self.notifyListeners(evt)

# End of sfp_webanalytics class
