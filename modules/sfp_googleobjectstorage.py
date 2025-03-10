# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_googleobjectstorage
# Purpose:      SpiderFoot plug-in for identifying potential Google Object Storage
#               buckets related to the target.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     24/01/2020
# Copyright:   (c) Steve Micallef 2020
# Licence:     MIT
# -------------------------------------------------------------------------------

import random
import threading
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_googleobjectstorage(SpiderFootPlugin):

    meta = {
        'name': "Google Object Storage Finder",
        'summary': "Search for potential Google Object Storage buckets associated with the target and attempt to list their contents.",
        'flags': [],
        'useCases': ["Footprint", "Passive"],
        'categories': ["Crawling and Scanning"],
        'dataSource': {
            'website': "https://cloud.google.com/storage",
            'model': "FREE_NOAUTH_UNLIMITED",
            'favIcon': 'https://www.gstatic.com/devrel-devsite/prod/v4c1e9ea53f4457a5de1027b4eeb4608c1000a427e20261ba1771dd3fc26d5df8/cloud/images/favicons/onecloud/favicon.ico',
            'logo': 'https://www.gstatic.com/devrel-devsite/prod/v4c1e9ea53f4457a5de1027b4eeb4608c1000a427e20261ba1771dd3fc26d5df8/cloud/images/cloud-logo.svg',
            'description': "Object storage for companies of all sizes."
            "Secure, durable, and with low latency. Store any amount of data."
            "Retrieve it as often as you'd like."
        }
    }

    # Default options
    opts = {
        "suffixes": "test,dev,web,beta,bucket,space,files,content,data,prod,staging,production,stage,app,media,development,-test,-dev,-web,-beta,-bucket,-space,-files,-content,-data,-prod,-staging,-production,-stage,-app,-media,-development",
        "_maxthreads": 20
    }

    # Option descriptions
    optdescs = {
        "suffixes": "List of suffixes to append to domains tried as bucket names",
        "_maxthreads": "Maximum threads"
    }

    results = None
    gosresults = dict()
    lock = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.gosresults = dict()
        self.results = self.tempStorage()
        self.lock = threading.Lock()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["DOMAIN_NAME", "LINKED_URL_EXTERNAL"]

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self):
        return ["CLOUD_STORAGE_BUCKET", "CLOUD_STORAGE_BUCKET_OPEN"]

    def checkSite(self, url):
        res = self.sf.fetchUrl(url, timeout=10, useragent="SpiderFoot", noLog=True)

        if not res['content']:
            return

        if "NoSuchBucket" in res['content']:
            self.debug(f"Not a valid bucket: {url}")
            return

        # Bucket found
        if res['code'] in ["301", "302", "200"]:
            # Bucket has files
            if "ListBucketResult" in res['content']:
                with self.lock:
                    self.gosresults[url] = res['content'].count("<Key>")
            else:
                # Bucket has no files
                with self.lock:
                    self.gosresults[url] = 0

    def threadSites(self, siteList):
        self.gosresults = dict()
        running = True
        i = 0
        t = []

        for site in siteList:
            if self.checkForStop():
                return None

            self.info("Spawning thread to check bucket: " + site)
            tname = str(random.SystemRandom().randint(0, 999999999))
            t.append(threading.Thread(name='thread_sfp_googleobjectstorage_' + tname,
                                      target=self.checkSite, args=(site,),daemon=True))
            t[i].start()
            i += 1

        # Block until all threads are finished
        while running:
            found = False
            for rt in threading.enumerate():
                if rt.name.startswith("thread_sfp_googleobjectstorage_"):
                    found = True

            if not found:
                running = False

            time.sleep(0.25)

        # Return once the scanning has completed
        return self.gosresults

    def batchSites(self, sites):
        i = 0
        res = list()
        siteList = list()

        for site in sites:
            if i >= self.opts['_maxthreads']:
                data = self.threadSites(siteList)
                if data is None:
                    return res

                for ret in list(data.keys()):
                    # Format: "url:filecount"
                    res.append(f"{ret}:{data[ret]}")
                i = 0
                siteList = list()

            siteList.append(site)
            i += 1

        # Don't forget to process any remaining sites
        if siteList:
            data = self.threadSites(siteList)
            if data:
                for ret in list(data.keys()):
                    res.append(f"{ret}:{data[ret]}")

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
            if ".storage.googleapis.com" in eventData.lower():
                try:
                    # Extract the Google storage domain
                    b = self.sf.urlFQDN(eventData)
                    if not b:
                        return
                    
                    evt = SpiderFootEvent("CLOUD_STORAGE_BUCKET", b, self.__name__, event)
                    self.notifyListeners(evt)
                except Exception as e:
                    self.debug(f"Error processing Google storage URL: {e}")
            return

        targets = [eventData.replace('.', '')]
        kw = self.sf.domainKeyword(eventData, self.opts['_internettlds'])
        if kw:
            targets.append(kw)

        urls = list()
        for t in targets:
            suffixes = [''] + self.opts['suffixes'].split(',')
            for s in suffixes:
                if self.checkForStop():
                    return

                b = t + s + ".storage.googleapis.com"
                url = "https://" + b
                urls.append(url)

        # Batch the scans
        ret = self.batchSites(urls)
        for b in ret:
            try:
                parts = b.split(":")
                if len(parts) != 2:
                    self.debug(f"Unexpected format in bucket data: {b}")
                    continue
                
                url = parts[0]
                file_count = parts[1]
                
                evt = SpiderFootEvent("CLOUD_STORAGE_BUCKET", url, self.__name__, event)
                self.notifyListeners(evt)
                
                if file_count != "0":
                    bucket_name = url.replace("https://", "").replace("http://", "")
                    evt = SpiderFootEvent("CLOUD_STORAGE_BUCKET_OPEN", 
                                        f"{bucket_name}: {file_count} files found.",
                                        self.__name__, evt)
                    self.notifyListeners(evt)
            except Exception as e:
                self.debug(f"Error processing bucket data: {e}")


# End of sfp_googleobjectstorage class
