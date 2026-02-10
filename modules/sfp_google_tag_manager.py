# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_google_tag_manager
# Purpose:     Search Google Tag Manager (GTM) for hosts sharing the same GTM code.
#
# Author:      <bcoles@gmail.com>
#
# Created:     2023-10-29
# Copyright:   (c) bcoles 2023
# Licence:     MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""SpiderFoot plug-in module: google_tag_manager."""

import re
import urllib.error
import urllib.parse
import urllib.request

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_google_tag_manager(SpiderFootModernPlugin):
    """SpiderFoot plugin to search Google Tag Manager (GTM) for hosts sharing the same GTM code."""
    __name__ = "sfp_google_tag_manager"
    meta = {
        'name': "Google Tag Manager",
        'summary': "Search Google Tag Manager (GTM) for hosts sharing the same GTM code.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Passive DNS"],
        'dataSource': {
            'website': "https://tagmanager.google.com",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://marketingplatform.google.com/about/tag-manager/",
                "https://developers.google.com/tag-manager/quickstart",
                "https://developers.google.com/tag-manager/devguide"
            ],
            'favIcon': "https://google.com/favicon.ico",
            'logo': "https://google.com/favicon.ico",
            'description': "Manage all your website tags without editing code. Google Tag Manager "
            "delivers simple, reliable, easily integrated tag management solutions for free."
        }
    }

    opts = {
        "verify": True
    }

    optdescs = {
        "verify": "Verify identified hostnames resolve to an IP address."
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ['WEB_ANALYTICS_ID']

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            'DOMAIN_NAME',
            'INTERNET_NAME',
            'AFFILIATE_DOMAIN_NAME',
            'AFFILIATE_INTERNET_NAME',
        ]

    # from: https://stackoverflow.com/a/43211062
    def is_valid_hostname(self, hostname: str = None) -> bool:
        """Check if valid hostname."""
        if not hostname:
            return False
        if len(hostname) > 255:
            return False

        hostname = hostname.rstrip(".")
        allowed = re.compile("(?!-)[A-Z0-9-_]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(x) for x in hostname.split("."))

    def queryGoogleTagId(self, tag_id: str = None) -> set:
        """Query GoogleTagId."""
        if not tag_id:
            return None

        params = urllib.parse.urlencode({
            'id': tag_id,
        })

        res = self.fetch_url(
            f"https://googletagmanager.com/gtm.js?{params}",
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts['_useragent']
        )

        if res['code'] != "200":
            self.debug(f"Invalid GTM tag id: {tag_id}")
            return None

        data = res['content']

        if not data:
            self.debug(f"Invalid GTM tag id: {tag_id}")
            return None

        hosts = list()

        for host in re.findall(r'"map","key","(.+?)"', data):
            if '.' not in host:
                continue
            if self.is_valid_hostname(host):
                hosts.append(host)

        for host in re.findall(r',"arg1":"(.+?)"', data):
            if '.' not in host:
                continue
            if self.is_valid_hostname(host):
                hosts.append(host)

        for url in SpiderFootHelpers.extractUrlsFromText(str(data).replace("\\/", "/")):
            host = self.sf.urlFQDN(url)
            if not host:
                continue
            if '.' not in host:
                continue
            hosts.append(host)

        return set(hosts)

    def handleEvent(self, event) -> None:
        """Handle an event received by this module."""
        self.debug(f"Received event, {event.eventType}, from {event.module}")

        if self.errorState:
            return

        if event.data in self.results:
            return

        self.results[event.data] = True

        try:
            network = event.data.split(": ")[0]
            tag_id = event.data.split(": ")[1]
        except Exception as e:
            self.error(f"Unable to parse WEB_ANALYTICS_ID: {event.data} ({e})")
            return

        if network != 'Google Tag Manager':
            return

        hosts = self.queryGoogleTagId(tag_id)

        if not hosts:
            self.info(f"No hosts found for {tag_id}")
            return

        self.info(f"Retrieved {len(hosts)} results")

        for host in hosts:
            # we ignore unresolved hosts due to large number of false positives
            if self.opts['verify'] and not self.resolve_host(host) and not self.resolve_host6(host):
                self.debug(
                    f"Potential host name '{host}' could not be resolved")
                continue

            if self.getTarget().matches(host, includeChildren=True, includeParents=True):
                evt_type = 'INTERNET_NAME'
            else:
                evt_type = 'AFFILIATE_INTERNET_NAME'

            evt = SpiderFootEvent(evt_type, host, self.__name__, event)
            self.notifyListeners(evt)

            if self.sf.isDomain(host, self.opts['_internettlds']):
                if evt_type.startswith('AFFILIATE'):
                    evt_type = 'AFFILIATE_DOMAIN_NAME'
                else:
                    evt_type = 'DOMAIN_NAME'

                evt = SpiderFootEvent(evt_type, host, self.__name__, event)
                self.notifyListeners(evt)

# End of sfp_google_tag_manager class
