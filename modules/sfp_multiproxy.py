from __future__ import annotations

"""SpiderFoot plug-in module: multiproxy."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_multiproxy
# Purpose:     Check if an IP arress is an open proxy according to multiproxy.org
#              open proxy list.
#
# Author:       steve@binarypool.com
#
# Created:     14/12/2013
# Copyright:   (c) Steve Micallef, 2013
# Licence:     MIT
# -------------------------------------------------------------------------------

from netaddr import IPAddress, IPNetwork

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_multiproxy(SpiderFootModernPlugin):

    """Check if an IP address is an open proxy according to multiproxy.org open proxy list."""

    meta = {
        'name': "multiproxy.org Open Proxies",
        'summary': "Check if an IP address is an open proxy according to multiproxy.org open proxy list.",
        'flags': [],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Secondary Networks"],
        'dataSource': {
            'website': "https://multiproxy.org/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://multiproxy.org/faq.htm",
                "https://multiproxy.org/env_check.htm",
                "https://multiproxy.org/anon_proxy.htm",
                "https://multiproxy.org/help.htm"
            ],
            'favIcon': "https://www.google.com/s2/favicons?domain=https://multiproxy.org/",
            'logo': "https://multiproxy.org/images/mproxy_title.png",
            'description': "MultiProxy is a multifunctional personal proxy server that protects your privacy "
            "while on the Internet as well as speeds up your downloads, "
            "especially if you are trying to get several files form overseas or from otherwise rather slow server. "
            "It can also completely hide your IP address by dynamically connecting to "
            "non-transparent anonymizing public proxy servers. "
            "You can also test a list of proxy servers and sort them by connection speed and level of anonimity.",
        }
    }

    opts = {
        'checkaffiliates': True,
        'cacheperiod': 18
    }

    optdescs = {
        'checkaffiliates': "Apply checks to affiliates?",
        'cacheperiod': "Hours to cache list data before re-fetching."
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return [
            'IP_ADDRESS',
            'AFFILIATE_IPADDR',
            'NETBLOCK_OWNER',
            'NETBLOCK_MEMBER',
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "BLACKLISTED_IPADDR",
            "BLACKLISTED_AFFILIATE_IPADDR",
            "BLACKLISTED_SUBNET",
            "BLACKLISTED_NETBLOCK",
            "MALICIOUS_IPADDR",
            "MALICIOUS_AFFILIATE_IPADDR",
            "MALICIOUS_NETBLOCK",
            "MALICIOUS_SUBNET",
        ]

    def queryProxyList(self, target, targetType) -> bool:
        """Query ProxyList."""
        proxy_list = self.retrieveProxyList()

        if not proxy_list:
            self.errorState = True
            return False

        if targetType == "ip":
            if target in proxy_list:
                self.debug(
                    f"IP address {target} found in multiproxy.org open proxy list.")
                return True
        elif targetType == "netblock":
            netblock = IPNetwork(target)
            for ip in proxy_list:
                if IPAddress(ip) in netblock:
                    self.debug(
                        f"IP address {ip} found within netblock/subnet {target} in multiproxy.org open proxy list.")
                    return True

        return False

    def retrieveProxyList(self):
        """RetrieveProxyList."""
        proxy_list = self.cache_get('multiproxyopenproxies', 24)

        if proxy_list is not None:
            return self.parseProxyList(proxy_list)

        res = self.fetch_url(
            "http://multiproxy.org/txt_all/proxy.txt",
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts['_useragent'],
        )

        if res['code'] != "200":
            self.error(
                f"Unexpected HTTP response code {res['code']} from multiproxy.org.")
            self.errorState = True
            return None

        if res['content'] is None:
            self.error("Received no content from multiproxy.org")
            self.errorState = True
            return None

        self.cache_put("multiproxyopenproxies", res['content'])

        return self.parseProxyList(res['content'])

    def parseProxyList(self, proxy_list):
        """Parse plaintext open proxy list.

        Args:
            proxy_list (str): plaintext open proxy list from multiproxy.org

        Returns:
            list: list of open proxy IP addresses
        """
        ips = list()

        if not proxy_list:
            return ips

        for ip in proxy_list.split('\n'):
            ip = ip.strip().split(":")[0]
            if ip.startswith('#'):
                continue
            if not self.sf.validIP(ip):
                continue
            ips.append(ip)

        return ips

    def handleEvent(self, event) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        if self.errorState:
            return

        self.results[eventData] = True

        if eventName == 'IP_ADDRESS':
            targetType = 'ip'
            malicious_type = "MALICIOUS_IPADDR"
            blacklist_type = "BLACKLISTED_IPADDR"
        elif eventName == 'AFFILIATE_IPADDR':
            if not self.opts.get('checkaffiliates', False):
                return
            targetType = 'ip'
            malicious_type = "MALICIOUS_AFFILIATE_IPADDR"
            blacklist_type = "BLACKLISTED_AFFILIATE_IPADDR"
        elif eventName == 'NETBLOCK_OWNER':
            if not self.opts.get('checknetblocks', False):
                return
            targetType = 'netblock'
            malicious_type = "MALICIOUS_NETBLOCK"
            blacklist_type = "BLACKLISTED_NETBLOCK"
        elif eventName == 'NETBLOCK_MEMBER':
            if not self.opts.get('checksubnets', False):
                return
            targetType = 'netblock'
            malicious_type = "MALICIOUS_SUBNET"
            blacklist_type = "BLACKLISTED_SUBNET"
        else:
            self.debug(f"Unexpected event type {eventName}, skipping")
            return

        self.debug(
            f"Checking maliciousness of {eventData} ({eventName}) with multiproxy.org open proxy list")

        if not self.queryProxyList(eventData, targetType):
            return

        url = "http://multiproxy.org/txt_all/proxy.txt"
        text = f"multiproxy.org Open Proxies [{eventData}]\n<SFURL>{url}</SFURL>"

        evt = SpiderFootEvent(malicious_type, text, self.__name__, event)
        self.notifyListeners(evt)

        evt = SpiderFootEvent(blacklist_type, text, self.__name__, event)
        self.notifyListeners(evt)

# End of sfp_multiproxy class
