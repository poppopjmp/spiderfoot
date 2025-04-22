# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_wayback
# Purpose:     Query the Internet Archive's Wayback Machine for historic versions
#              of websites.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     10/08/2013
# Copyright:   (c) Steve Micallef 2013
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import re
import urllib.parse

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_wayback(SpiderFootPlugin):

    meta = {
        'name': "Wayback Machine",
        'summary': "Queries the Internet Archive's Wayback Machine for historic versions of websites.",
        'flags': [],
        'useCases': ["Passive", "Footprint"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://archive.org/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://archive.org/help/",
                "https://archive.org/about/",
            ],
            'favIcon': "https://archive.org/images/glogo.jpg",
            'logo': "https://archive.org/images/glogo.jpg",
            'description': "The Internet Archive's Wayback Machine allows you to view historic versions of websites."
        }
    }

    opts = {
        'farback': 30,  # Number of days back to look for wayback URLs
        'timeout': 15,
        'maxpages': 20  # num of pages to visit
    }

    optdescs = {
        'farback': "Number of days back to look for historic version of pages.",
        'timeout': "Query timeout, in seconds.",
        'maxpages': "Maximum number of pages of results to download."
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ["DOMAIN_NAME", "INTERNET_NAME", "AFFILIATE_DOMAIN_NAME"]

    def producedEvents(self):
        return ["WAYBACK_URL", "LINKED_URL_INTERNAL"]

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked")
            return

        self.results[eventData] = True

        if self.opts['farback'] <= 0:
            self.info("farback option <= 0, using default of 30 days")
            self.opts['farback'] = 30

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        data = self.queryArchive(eventData, self.opts['farback'])
        if not data:
            self.info(f"No Wayback data found for {eventData}")
            return

        ret = self.processData(data, event)
        self.info(f"Found {len(ret)} Wayback URLs for {eventData}")

    def queryArchive(self, domain, timeBack):
        """Query the Wayback Machine

        Args:
            domain: Domain to look for historic URLs for
            timeBack: Number of days back to look for historic URLs

        Returns:
            dict: JSON response from the API
        """
        headers = {
            'User-Agent': 'SpiderFoot',
        }

        ret = None
        url = f"https://web.archive.org/cdx/search/cdx?url={domain}/*&collapse=urlkey&fl=original&filter=statuscode:200&filter=mimetype:text/html&output=json"

        res = self.sf.fetchUrl(
            url,
            timeout=self.opts['timeout'],
            useragent=self.opts['_useragent'],
            headers=headers
        )

        if res['code'] != "200":
            self.error(f"Error retrieving Wayback data: {res['code']}")
            self.errorState = True
            return None

        try:
            ret = json.loads(res['content'])
        except Exception as e:
            self.error(f"Error processing Wayback data: {e}")
            self.errorState = True
            return None

        if len(ret) <= 1:
            return None

        return ret

    def processData(self, data, event):
        """Process data from the Wayback Machine query.

        Args:
            data: JSON response from the API
            event: SpiderFoot event

        Returns:
            list: Wayback URLs discovered
        """
        ret = list()

        # The first row is the header fields
        for row in data[1:]:
            url = row[0]
            if not url:
                continue

            # Don't process wildcard domains
            if (
                self.getTarget().matches(url) or
                event.data.lower() in url.lower()
            ):
                if url not in ret:
                    ret.append(url)
                    evt = SpiderFootEvent("WAYBACK_URL", url, self.__name__, event)
                    self.notifyListeners(evt)

            # Resolve the URL to find common URLs internally linked
            if len(ret) >= self.opts['maxpages']:
                break

            res = self.sf.fetchUrl(
                "https://web.archive.org/web/" + urllib.parse.quote(url),
                useragent=self.opts['_useragent'],
                timeout=self.opts['timeout']
            )

            if not res['content']:
                continue

            proto = "https" if "://" not in url and event.data.lower() in url.lower() else urllib.parse.urlparse(url).scheme
            links = re.findall(r'href=[\'"]?([^\'"\s>]+)', str(res['content']))

            if links:
                for link in links:
                    if len(ret) >= self.opts['maxpages']:
                        break

                    if (
                        link in self.results or
                        link in ["#", "/", "javascript:"] or
                        link.startswith("mailto:")
                    ):
                        continue

                    # Need to consider page as relative to the URL
                    if '://' not in link:
                        if link.startswith('/'):
                            link = proto + "://" + event.data + link
                        else:
                            link = proto + "://" + event.data + "/" + link

                    self.debug(f"Found a link: {link}")
                    if (
                        self.getTarget().matches(link) or
                        event.data.lower() in link.lower()
                    ):
                        ret.append(link)
                        evt = SpiderFootEvent("LINKED_URL_INTERNAL", link, self.__name__, event)
                        self.notifyListeners(evt)

        return ret