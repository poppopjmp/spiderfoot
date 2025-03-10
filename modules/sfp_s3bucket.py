# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_s3bucket
# Purpose:      SpiderFoot plug-in for identifying potential S3 buckets related to
#               the target.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     24/07/2016
# Copyright:   (c) Steve Micallef 2016
# Licence:     MIT
# -------------------------------------------------------------------------------

import random
import threading
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_s3bucket(SpiderFootPlugin):

    meta = {
        'name': "Amazon S3 Bucket Finder",
        'summary': "Search for potential Amazon S3 buckets associated with the target and attempt to list their contents.",
        'flags': [],
        'useCases': ["Footprint", "Passive"],
        'categories': ["Crawling and Scanning"],
        'dataSource': {
            'website': "https://aws.amazon.com/s3/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'favIcon': 'https://a0.awsstatic.com/libra-css/images/site/fav/favicon.ico',
            'logo': 'https://a0.awsstatic.com/libra-css/images/site/touch-icon-ipad-144-smile.png',
            'description': "Amazon S3 is cloud object storage with industry-leading scalability, data availability, security, and performance. "
            "S3 is ideal for data lakes, mobile applications, backup and restore, archival, IoT devices, ML, AI, and analytics."
        }
    }

    # Default options
    opts = {
        "endpoints": "s3.amazonaws.com,s3-external-1.amazonaws.com,s3-us-west-1.amazonaws.com,s3-us-west-2.amazonaws.com,s3.ap-south-1.amazonaws.com,s3-ap-south-1.amazonaws.com,s3.ap-northeast-2.amazonaws.com,s3-ap-northeast-2.amazonaws.com,s3-ap-southeast-1.amazonaws.com,s3-ap-southeast-2.amazonaws.com,s3-ap-northeast-1.amazonaws.com,s3.eu-central-1.amazonaws.com,s3-eu-central-1.amazonaws.com,s3-eu-west-1.amazonaws.com,s3-sa-east-1.amazonaws.com",
        "suffixes": "test,dev,web,beta,bucket,space,files,content,data,prod,staging,production,stage,app,media,development,-test,-dev,-web,-beta,-bucket,-space,-files,-content,-data,-prod,-staging,-production,-stage,-app,-media,-development",
        "_maxthreads": 20
    }

    # Option descriptions
    optdescs = {
        "endpoints": "Different S3 endpoints to check where buckets may exist, as per http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region",
        "suffixes": "List of suffixes to append to domains tried as bucket names",
        "_maxthreads": "Maximum threads"
    }

    results = None
    s3results = dict()
    lock = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.s3results = dict()
        self.results = self.tempStorage()
        self.lock = threading.Lock()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["DOMAIN_NAME", "LINKED_URL_EXTERNAL"]

    # What events this module produces
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
                    self.s3results[url] = res['content'].count("<Key>")
            else:
                # Bucket has no files
                with self.lock:
                    self.s3results[url] = 0

    def threadSites(self, siteList):
        self.s3results = dict()
        running = True
        t = []

        for i, site in enumerate(siteList):
            if self.checkForStop():
                return False

            self.info("Spawning thread to check bucket: " + site)
            tname = str(random.SystemRandom().randint(0, 999999999))
            t.append(threading.Thread(name='thread_sfp_s3buckets_' + tname,
                                      target=self.checkSite, args=(site,),daemon=True))
            t[i].start()

        # Block until all threads are finished
        while running:
            found = False
            for rt in threading.enumerate():
                if rt.name.startswith("thread_sfp_s3buckets_"):
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
            if ".amazonaws.com" in eventData.lower():
                try:
                    # Extract the AWS domain
                    b = self.sf.urlFQDN(eventData)
                    if not b:
                        return
                        
                    if b in self.opts['endpoints'].split(','):
                        try:
                            # Extract the bucket name from path
                            path_parts = eventData.split(b + "/")
                            if len(path_parts) > 1 and path_parts[1]:
                                bucket_path = path_parts[1].split("/")[0]
                                if bucket_path:
                                    b += "/" + bucket_path
                        except Exception as e:
                            self.debug(f"Error extracting bucket path: {e}")
                            # Not a proper bucket path
                            return
                    
                    evt = SpiderFootEvent("CLOUD_STORAGE_BUCKET", b, self.__name__, event)
                    self.notifyListeners(evt)
                except Exception as e:
                    self.debug(f"Error processing AWS S3 URL: {e}")
            return

        targets = [eventData.replace('.', '')]
        kw = self.sf.domainKeyword(eventData, self.opts['_internettlds'])
        if kw:
            targets.append(kw)

        urls = list()
        for t in targets:
            for e in self.opts['endpoints'].split(','):
                suffixes = [''] + self.opts['suffixes'].split(',')
                for s in suffixes:
                    if self.checkForStop():
                        return

                    b = t + s + "." + e
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


# End of sfp_s3bucket class
