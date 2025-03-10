# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:   sfp_bambanek
# Purpose:  Check if a host/domain or IP appears in Bambenek Consulting feeds.
#
# Author:   Agostino Panico <van1sh@van1shland.io>
#
# Created:  01/02/2025
# Copyright:  (c) poppopjmp
# Licence:  MIT
# -------------------------------------------------------------------------------

import json
import time
from netaddr import IPNetwork
from datetime import datetime

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_bambenek(SpiderFootPlugin):

    meta = {
        'name': "Bambenek Consulting",
        'summary': "Check if a host/domain or IP appears in Bambenek Consulting feeds.",
        'flags': ["slow"],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://www.bambenekconsulting.com/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://osint.bambenekconsulting.com/feeds/",
                "https://osint.bambenekconsulting.com/feeds/dga-feed.txt"
            ],
            'favIcon': "https://www.bambenekconsulting.com/wp-content/uploads/2019/12/cropped-bamblogo-32x32.png",
            'logo': "https://www.bambenekconsulting.com/wp-content/uploads/2019/07/bamblogo.png",
            'description': "Bambenek Consulting provides cybersecurity intelligence "
                           "including IP and domain blacklists based on threat intelligence."
        }
    }

    # Default options
    opts = {
        'checkaffiliates': True,
        'checkcohosts': True,
        'cacheperiod': 18,
        'dga_feed': True,
        'c2_feed': True
    }

    # Option descriptions
    optdescs = {
        'checkaffiliates': "Apply checks to affiliates?",
        'checkcohosts': "Apply checks to sites found to be co-hosted on the target's IP?",
        'cacheperiod': "Hours to cache list data before re-fetching.",
        'dga_feed': "Enable Bambenek DGA feed checks?",
        'c2_feed': "Enable Bambenek C2 feed checks?"
    }

    # Be sure to completely clear any class variables in setup()
    # or you risk data persisting between scan runs.
    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.opts.update(userOpts)
        
        # Initialize data cache
        self.feedCache = {
            'dga_domains': self.retrieveDataFromFeed("https://osint.bambenekconsulting.com/feeds/dga-feed.txt"),
            'c2_ips': self.retrieveDataFromFeed("https://osint.bambenekconsulting.com/feeds/c2-ipmasterlist.txt"),
            'c2_domains': self.retrieveDataFromFeed("https://osint.bambenekconsulting.com/feeds/c2-dommasterlist.txt")
        }

    def retrieveDataFromFeed(self, url):
        data = self.sf.cacheGet('bambenek_' + url, self.opts['cacheperiod'])
        if data:
            self.debug(f"Using cached data from Bambenek feed: {url}")
            return self.parseData(data)
            
        self.debug(f"Fetching data from Bambenek feed: {url}")
        res = self.sf.fetchUrl(url, timeout=self.opts['_fetchtimeout'], useragent=self.opts['_useragent'])
        if res['code'] != "200":
            self.error(f"Unable to fetch {url}")
            return []
            
        if res['content'] is None:
            self.error(f"Empty response from {url}")
            return []

        try:
            self.sf.cachePut('bambenek_' + url, res['content'], self.opts['cacheperiod'])
            return self.parseData(res['content'])
        except Exception as e:
            self.error(f"Error processing Bambenek data: {str(e)}")
            return []
            
    def parseData(self, data):
        items = []
        for line in data.splitlines():
            if not line or line.startswith('#'):
                continue
                
            item = line.strip().split(',')[0]  # First column is typically the domain/IP
            if item:
                items.append(item.lower())
                
        return items

    # What events is this module interested in for input
    def watchedEvents(self):
        return [
            "INTERNET_NAME",
            "AFFILIATE_INTERNET_NAME",
            "IP_ADDRESS",
            "AFFILIATE_IPADDR",
            "CO_HOSTED_SITE"
        ]

    # What events this module produces
    def producedEvents(self):
        return [
            "BLACKLISTED_INTERNET_NAME",
            "BLACKLISTED_AFFILIATE_INTERNET_NAME",
            "BLACKLISTED_IPADDR",
            "BLACKLISTED_AFFILIATE_IPADDR",
            "BLACKLISTED_COHOST",
            "MALICIOUS_INTERNET_NAME",
            "MALICIOUS_AFFILIATE_INTERNET_NAME",
            "MALICIOUS_IPADDR",
            "MALICIOUS_AFFILIATE_IPADDR",
            "MALICIOUS_COHOST"
        ]

    # Check if an IP or domain is malicious
    def queryFeed(self, qry, feed_type):
        if feed_type == "dga_domains":
            return qry.lower() in self.feedCache.get('dga_domains', [])
        elif feed_type == "c2_ips":
            return qry.lower() in self.feedCache.get('c2_ips', [])
        elif feed_type == "c2_domains":
            return qry.lower() in self.feedCache.get('c2_domains', [])
        return False

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        
        self.debug(f"Received event, {eventName}, from {srcModuleName}")
        
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return
        
        self.results[eventData] = True
        
        # Check based on event type
        if eventName == "IP_ADDRESS":
            malicious_type = "BLACKLISTED_IPADDR"
            malicious_desc = "Bambenek Consulting [C2 IP]"
            is_malicious = self.queryFeed(eventData, "c2_ips") if self.opts.get('c2_feed', True) else False
            
        elif eventName == "AFFILIATE_IPADDR":
            if not self.opts.get('checkaffiliates', False):
                return
            malicious_type = "BLACKLISTED_AFFILIATE_IPADDR"
            malicious_desc = "Bambenek Consulting [C2 IP]"
            is_malicious = self.queryFeed(eventData, "c2_ips") if self.opts.get('c2_feed', True) else False
            
        elif eventName == "INTERNET_NAME":
            malicious_types = []
            if self.opts.get('dga_feed', True) and self.queryFeed(eventData, "dga_domains"):
                malicious_types.append(("BLACKLISTED_INTERNET_NAME", "Bambenek Consulting [DGA Domain]"))
            if self.opts.get('c2_feed', True) and self.queryFeed(eventData, "c2_domains"):
                malicious_types.append(("BLACKLISTED_INTERNET_NAME", "Bambenek Consulting [C2 Domain]"))
            
            for malicious_type, malicious_desc in malicious_types:
                evt = SpiderFootEvent(malicious_type, malicious_desc, self.__name__, event)
                self.notifyListeners(evt)
                evt = SpiderFootEvent("MALICIOUS_" + malicious_type.split("_", 1)[1], 
                                    malicious_desc, self.__name__, event)
                self.notifyListeners(evt)
            return
            
        elif eventName == "AFFILIATE_INTERNET_NAME":
            if not self.opts.get('checkaffiliates', False):
                return
            malicious_types = []
            if self.opts.get('dga_feed', True) and self.queryFeed(eventData, "dga_domains"):
                malicious_types.append(("BLACKLISTED_AFFILIATE_INTERNET_NAME", "Bambenek Consulting [DGA Domain]"))
            if self.opts.get('c2_feed', True) and self.queryFeed(eventData, "c2_domains"):
                malicious_types.append(("BLACKLISTED_AFFILIATE_INTERNET_NAME", "Bambenek Consulting [C2 Domain]"))
            
            for malicious_type, malicious_desc in malicious_types:
                evt = SpiderFootEvent(malicious_type, malicious_desc, self.__name__, event)
                self.notifyListeners(evt)
                evt = SpiderFootEvent("MALICIOUS_" + malicious_type.split("_", 1)[1], 
                                    malicious_desc, self.__name__, event)
                self.notifyListeners(evt)
            return
            
        elif eventName == "CO_HOSTED_SITE":
            if not self.opts.get('checkcohosts', False):
                return
            malicious_types = []
            if self.opts.get('dga_feed', True) and self.queryFeed(eventData, "dga_domains"):
                malicious_types.append(("BLACKLISTED_COHOST", "Bambenek Consulting [DGA Domain]"))
            if self.opts.get('c2_feed', True) and self.queryFeed(eventData, "c2_domains"):
                malicious_types.append(("BLACKLISTED_COHOST", "Bambenek Consulting [C2 Domain]"))
            
            for malicious_type, malicious_desc in malicious_types:
                evt = SpiderFootEvent(malicious_type, malicious_desc, self.__name__, event)
                self.notifyListeners(evt)
                evt = SpiderFootEvent("MALICIOUS_COHOST", malicious_desc, self.__name__, event)
                self.notifyListeners(evt)
            return
        else:
            return
        
        # For IP addresses, handle in a simpler way
        if is_malicious:
            self.debug(f"{eventData} found in Bambenek Consulting feeds")
            
            evt = SpiderFootEvent(malicious_type, malicious_desc, self.__name__, event)
            self.notifyListeners(evt)
            
            evt = SpiderFootEvent("MALICIOUS_" + malicious_type.split("_", 1)[1], 
                                malicious_desc, self.__name__, event)
            self.notifyListeners(evt)
