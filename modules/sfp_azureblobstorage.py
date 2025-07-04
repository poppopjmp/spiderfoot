# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_azureblobstorage
# Purpose:      SpiderFoot plug-in for identifying potential Azure blobs related
#               to the target.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     14/07/2019
# Copyright:   (c) Steve Micallef 2019
# Licence:     MIT
# -------------------------------------------------------------------------------

import random
import threading
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_azureblobstorage(SpiderFootPlugin):
    meta = {
        "name": "Azure Blob Finder",
        "summary": "Search for potential Azure blobs associated with the target and attempt to list their contents.",
        "flags": [],
        "useCases": ["Footprint", "Passive"],
        "categories": ["Crawling and Scanning"],
        "dataSource": {
            "website": "https://azure.microsoft.com/en-in/services/storage/blobs/",
            "model": "FREE_NOAUTH_UNLIMITED",
            "favIcon": "https://azurecomcdn.azureedge.net/cvt-4fd6fa9ffb60246fd6387e4b34f89dc454cdf3df85d2b5d3215846066fceb0b6/images/icon/favicon.ico",
            "logo": "https://azurecomcdn.azureedge.net/cvt-4fd6fa9ffb60246fd6387e4b34f89dc454cdf3df85d2b5d3215846066fceb0b6/images/icon/favicon.ico",
            "description": "Massively scalable and secure object storage for cloud-native workloads,"
            "archives, data lakes, high-performance computing and machine learning.",
        },
    }

    # Default options
    opts = {
        "suffixes": "test,dev,web,beta,bucket,space,files,content,data,prod,staging,production,stage,app,media,development,-test,-dev,-web,-beta,-bucket,-space,-files,-content,-data,-prod,-staging,-production,-stage,-app,-media,-development",
        "_maxthreads": 20,
    }

    # Option descriptions
    optdescs = {
        "suffixes": "List of suffixes to append to domains tried as blob storage names",
        "_maxthreads": "Maximum threads",
    }

    results = None
    s3results = None

    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        # Debug: print options to ensure suffixes is set
        print("DEBUG sfp_azureblobstorage opts:", self.opts)
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]
        print("DEBUG sfp_azureblobstorage opts after userOpts:", self.opts)

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["DOMAIN_NAME", "LINKED_URL_EXTERNAL"]

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self):
        return ["CLOUD_STORAGE_BUCKET"]

    def checkSite(self, url):
        res = self.sf.fetchUrl(
            url, timeout=10, useragent="SpiderFoot", noLog=True)

        if res["code"]:
            print(f"DEBUG: Emitting CLOUD_STORAGE_BUCKET for {url}")
            with self.lock:
                self.s3results[url] = True

    def threadSites(self, siteList):
        self.s3results = dict()
        running = True
        i = 0
        t = []

        for site in siteList:
            if self.checkForStop():
                return None

            self.info("Spawning thread to check bucket: " + site)
            tname = str(random.SystemRandom().randint(0, 999999999))
            t.append(
                threading.Thread(
                    name="thread_sfp_azureblobstorages_" + tname,
                    target=self.checkSite,
                    args=(site,),
                )
            )
            t[i].start()
            i += 1

        # Block until all threads are finished
        while running:
            found = False
            for rt in threading.enumerate():
                if rt.name.startswith("thread_sfp_azureblobstorages_"):
                    found = True

            if not found:
                running = False

            time.sleep(0.25)

        # Return once the scanning has completed
        return self.s3results

    def batchSites(self, sites):
        i = 0
        res = list()
        siteList = list()

        for site in sites:
            if i >= self.opts["_maxthreads"]:
                data = self.threadSites(siteList)
                if data is None:
                    return res

                for ret in list(data.keys()):
                    if data[ret]:
                        res.append(ret)
                i = 0
                siteList = list()

            siteList.append(site)
            i += 1

        return res

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if eventData in self.results:
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventName == "LINKED_URL_EXTERNAL":
            from urllib.parse import urlparse
            parsed_url = urlparse(eventData)
            if parsed_url.hostname and parsed_url.hostname.endswith(".blob.core.windows.net"):
                b = self.sf.urlFQDN(eventData)
                evt = SpiderFootEvent(
                    "CLOUD_STORAGE_BUCKET", b, self.__class__.__name__, event)
                self.notifyListeners(evt)
            return

        targets = [eventData.replace(".", "")]
        kw = self.sf.domainKeyword(eventData, self.opts["_internettlds"])
        if kw:
            targets.append(kw)

        urls = list()
        for t in targets:
            suffixes = [""] + self.opts["suffixes"].split(",")
            for s in suffixes:
                if self.checkForStop():
                    return

                b = t + s + ".blob.core.windows.net"
                url = "https://" + b
                urls.append(url)

        # Batch the scans
        ret = self.batchSites(urls)
        for b in ret:
            # Extract bucket name from URL
            if b.startswith("https://"):
                bucket = b[len("https://"):]
            else:
                bucket = b
            evt = SpiderFootEvent("CLOUD_STORAGE_BUCKET",
                                  bucket, self.__class__.__name__, event)
            self.notifyListeners(evt)


# End of sfp_azureblobstorage class
