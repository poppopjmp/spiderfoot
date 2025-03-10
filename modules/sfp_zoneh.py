# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_zoneh
# Purpose:      Checks if a domain or IP appears on the zone-h.org defacement
#               archive.
#
# Author:       steve@binarypool.com
#
# Created:     09/01/2014
# Copyright:   (c) Steve Micallef, 2014
# Licence:     MIT
# -------------------------------------------------------------------------------

import re
import time
import requests

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_zoneh(SpiderFootPlugin):

    meta = {
        'name': "Zone-H Defacement Check",
        'summary': "Check if a hostname/domain appears on the zone-h.org defacement archives.",
        'flags': [],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Leaks, Dumps and Breaches"],
        'dataSource': {
            'website': "https://zone-h.org/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://www.zone-h.org/archive",
                "https://www.zone-h.org/archive/special=1",
                "https://www.zone-h.org/archive/published=0"
            ],
            'favIcon': "https://zone-h.org/images/logo.gif",
            'logo': "https://zone-h.org/images/logo.gif",
            'description': "Once a defaced website is submitted to Zone-H, it is mirrored on the Zone-H servers. "
            "The website is then moderated by the Zone-H staff to check if the defacement was fake. "
            "Sometimes, the hackers themselves submit their hacked pages to the site.\n"
            "It is an Internet security portal containing original IT security news, digital warfare news, "
            "geopolitics, proprietary and general advisories, analyses, forums, researches. "
            "Zone-H is the largest web intrusions archive. It is published in several languages.",
        }
    }

    # Default options
    opts = {
        'checkcohosts': True,
        'checkaffiliates': True,
        'feeds': ["specialdefacements", "published=0"],
        'cachetime': 48,
        'fetchtimeout': 30,
        'delay': 1,  # Added delay option like in zoomeye
    }

    # Option descriptions
    optdescs = {
        'checkcohosts': "Check co-hosted sites?",
        'checkaffiliates': "Check affiliates?",
        'feeds': "Zone-H RSS feeds to check: specialdefacements and/or published=0",
        'cachetime': "Hours to cache the feeds for (0 = no caching)",
        'fetchtimeout': "Timeout for fetch operations in seconds",
        'delay': "Delay between API requests (in seconds)",  # Added description
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.errorState = False
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ["INTERNET_NAME", "IP_ADDRESS", "IPV6_ADDRESS",
                "AFFILIATE_INTERNET_NAME", "AFFILIATE_IPADDR", "AFFILIATE_IPV6_ADDRESS",
                "CO_HOSTED_SITE"]

    def producedEvents(self):
        return ["DEFACED_INTERNET_NAME", "DEFACED_IPADDR",
                "DEFACED_AFFILIATE_INTERNET_NAME",
                "DEFACED_COHOST", "DEFACED_AFFILIATE_IPADDR"]

    def lookupItem(self, target, content):
        # Enhanced regex pattern to better handle different formats
        pattern = r"<title><!\[CDATA\[(.*?)\]\]></title>\s+<link><!\[CDATA\[(.*?)\]\]></link>"
        matches = re.findall(pattern, content, re.DOTALL)
        
        for title, link in matches:
            if target.lower() in title.lower():
                self.debug(f"Found Zone-H entry for {target}: {title}")
                return f"{title.strip()}\n<SFURL>{link.strip()}</SFURL>"
                
        return False

    def fetchFeed(self, feed_name):
        if self.errorState:
            return None
            
        feed_url = f"https://www.zone-h.org/rss/{feed_name}"
        cache_key = f"sfzoneh_{feed_name}"
        
        content = self.sf.cacheGet(cache_key, self.opts['cachetime'])
        if content:
            return content
            
        self.debug(f"Fetching Zone-H feed: {feed_url}")
        
        try:
            headers = {
                'User-Agent': self.opts['_useragent'],
                'Accept': 'application/rss+xml'
            }
            
            response = requests.get(
                feed_url, 
                headers=headers,
                timeout=self.opts['fetchtimeout']
            )
            time.sleep(self.opts['delay'])
            
            if response.status_code != 200:
                self.error(f"Zone-H API returned HTTP status {response.status_code}: {response.text}")
                self.errorState = True
                return None
                
            content = response.text
            
            if not content:
                self.debug(f"Empty content from {feed_url}")
                return None
                
            self.sf.cachePut(cache_key, content)
            return content
            
        except requests.exceptions.RequestException as e:
            self.error(f"Error fetching Zone-H feed: {e}")
            self.errorState = True
            return None
        except Exception as e:
            self.error(f"Unexpected error fetching Zone-H feed: {e}")
            self.errorState = True
            return None

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if eventName == 'CO_HOSTED_SITE' and not self.opts['checkcohosts']:
            return

        if eventName.startswith("AFFILIATE") and not self.opts['checkaffiliates']:
            return

        if eventName == 'INTERNET_NAME':
            evtType = 'DEFACED_INTERNET_NAME'
        elif eventName in ['IP_ADDRESS', 'IPV6_ADDRESS']:
            evtType = 'DEFACED_IPADDR'
        elif eventName == 'CO_HOSTED_SITE':
            evtType = 'DEFACED_COHOST'
        elif eventName == 'AFFILIATE_INTERNET_NAME':
            evtType = 'DEFACED_AFFILIATE_INTERNET_NAME'
        elif eventName in ['AFFILIATE_IPADDR', 'AFFILIATE_IPV6_ADDRESS']:
            evtType = 'DEFACED_AFFILIATE_IPADDR'
        else:
            self.debug(f"Unexpected event type {eventName}, skipping")
            return

        if self.checkForStop():
            return

        found = False
        
        # Check each configured feed
        for feed in self.opts['feeds']:
            if self.checkForStop():
                return
                
            content = self.fetchFeed(feed)
            if not content:
                self.info(f"No content found for feed {feed}")
                continue
                
            ret = self.lookupItem(eventData, content)
            if ret:
                found = True
                evt = SpiderFootEvent(evtType, ret, self.__name__, event)
                self.notifyListeners(evt)
        
        if not found:
            self.debug(f"No Zone-H defacements found for {eventData}")

# End of sfp_zoneh class
