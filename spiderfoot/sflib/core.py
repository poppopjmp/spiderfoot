# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot SFLib Module
# Purpose:      Common functions for working with the database back-end.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
# Will import from .config, .network, .logging, .helpers as needed

from copy import deepcopy
import logging
import ssl
import dns.resolver
from typing import Tuple
from .config import configSerialize, configUnserialize
from .network import (
    resolveHost, resolveIP, resolveHost6, validateIP, safeSocket, safeSSLSocket, parseCert, getSession, useProxyForUrl, fetchUrl, checkDnsWildcard
)
from .helpers import (
    hashstring, cachePut, cacheGet, removeUrlCreds, isValidLocalOrLoopbackIp, domainKeyword, domainKeywords, hostDomain, validHost, isDomain, validIP, validIP6, validIpNetwork, isPublicIpAddress, normalizeDNS
)

class SpiderFoot:
    _dbh = None
    _scanId = None
    _socksProxy = None
    opts = dict()

    def __init__(self, options: dict) -> None:
        if not isinstance(options, dict):
            raise TypeError(f"options is {type(options)}; expected dict()")
        self.opts = deepcopy(options)
        self.log = logging.getLogger(f"spiderfoot.{__name__}")
        ssl._create_default_https_context = ssl._create_unverified_context
        if self.opts.get('_dnsserver', "") != "":
            res = dns.resolver.Resolver()
            res.nameservers = [self.opts['_dnsserver']]
            dns.resolver.override_system_resolver(res)

    @property
    def dbh(self):
        return self._dbh

    @property
    def scanId(self) -> str:
        return self._scanId

    @property
    def socksProxy(self) -> str:
        return self._socksProxy

    @dbh.setter
    def dbh(self, dbh):
        self._dbh = dbh

    @scanId.setter
    def scanId(self, scanId: str) -> str:
        self._scanId = scanId

    @socksProxy.setter
    def socksProxy(self, socksProxy: str) -> str:
        self._socksProxy = socksProxy

    def optValueToData(self, val: str) -> str:
        if not isinstance(val, str):
            self.error(f"Invalid option value {val}")
            return None
        if val.startswith('@'):
            fname = val.split('@')[1]
            self.info(f"Loading configuration data from: {fname}")
            try:
                with open(fname, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                self.error(f"Unable to open option file, {fname}: {e}")
                return None
        if val.lower().startswith('http://') or val.lower().startswith('https://'):
            try:
                self.info(f"Downloading configuration data from: {val}")
                from .network import getSession  # Import here for patching
                session = getSession()
                res = session.get(val)
                return res.content.decode('utf-8')
            except Exception as e:
                self.error(f"Unable to open option URL, {val}: {e}")
                return None
        return val

    def error(self, message: str) -> None:
        if not self.opts.get('__logging', False):
            return
        self.log.error(message, extra={'scanId': self._scanId})

    def fatal(self, error: str) -> None:
        self.log.critical(error, extra={'scanId': self._scanId})
        import inspect
        print(str(inspect.stack()))
        import sys
        sys.exit(-1)

    def status(self, message: str) -> None:
        if not self.opts.get('__logging', False):
            return
        self.log.info(message, extra={'scanId': self._scanId})

    def info(self, message: str) -> None:
        if not self.opts.get('__logging', False):
            return
        self.log.info(message, extra={'scanId': self._scanId})

    def debug(self, message: str) -> None:
        if not self.opts.get('_debug', False):
            return
        if not self.opts.get('__logging', False):
            return
        self.log.debug(message, extra={'scanId': self._scanId})

    # The following methods are now thin wrappers or use helpers directly
    def hashstring(self, string: str) -> str:
        return hashstring(string)
    def cachePut(self, label: str, data: str) -> None:
        return cachePut(label, data)
    def cacheGet(self, label: str, timeoutHrs: int) -> str:
        return cacheGet(label, timeoutHrs)
    def removeUrlCreds(self, url: str) -> str:
        return removeUrlCreds(url)
    def isValidLocalOrLoopbackIp(self, ip: str) -> bool:
        return isValidLocalOrLoopbackIp(ip)
    def domainKeyword(self, domain: str, tldList: list) -> str:
        return domainKeyword(domain, tldList)
    def domainKeywords(self, domainList: list, tldList: list) -> set:
        return domainKeywords(domainList, tldList)
    def hostDomain(self, hostname: str, tldList: list) -> str:
        return hostDomain(hostname, tldList)
    def validHost(self, hostname: str, tldList: str) -> bool:
        return validHost(hostname, tldList)
    def isDomain(self, hostname: str, tldList: list) -> bool:
        return isDomain(hostname, tldList)
    def validIP(self, address: str) -> bool:
        return validIP(address)
    def validIP6(self, address: str) -> bool:
        return validIP6(address)
    def validIpNetwork(self, cidr: str) -> bool:
        return validIpNetwork(cidr)
    def isPublicIpAddress(self, ip: str) -> bool:
        return isPublicIpAddress(ip)
    def normalizeDNS(self, res: list) -> list:
        return normalizeDNS(res)
    def resolveHost(self, host: str) -> list:
        return resolveHost(host)
    def resolveIP(self, ipaddr: str) -> list:
        return resolveIP(ipaddr)
    def resolveHost6(self, hostname: str) -> list:
        return resolveHost6(hostname)
    def validateIP(self, host: str, ip: str) -> bool:
        return validateIP(host, ip)
    def safeSocket(self, host: str, port: int, timeout: int):
        return safeSocket(host, port, timeout)
    def safeSSLSocket(self, host: str, port: int, timeout: int):
        return safeSSLSocket(host, port, timeout)
    def parseCert(self, rawcert: str, fqdn: str = None, expiringdays: int = 30) -> dict:
        return parseCert(rawcert, fqdn, expiringdays)
    def getSession(self):
        return getSession()
    def useProxyForUrl(self, url: str) -> bool:
        # Patch: pass self for urlFQDN resolution and improve local IP detection
        from .network import useProxyForUrl
        return useProxyForUrl(url, self.opts, urlFQDN=self.urlFQDN, isValidLocalOrLoopbackIp=self.isValidLocalOrLoopbackIp)
    def fetchUrl(self, url: str, cookies: str = None, timeout: int = 30, useragent: str = "SpiderFoot", headers: dict = None, noLog: bool = False, postData: str = None, disableContentEncoding: bool = False, sizeLimit: int = None, headOnly: bool = False, verify: bool = True) -> dict:
        return fetchUrl(url, cookies, timeout, useragent, headers, noLog, postData, disableContentEncoding, sizeLimit, headOnly, verify)
    def checkDnsWildcard(self, target: str) -> bool:
        return checkDnsWildcard(target)
    def modulesProducing(self, events: list) -> list:
        modlist = list()
        if not events:
            return modlist
        loaded_modules = self.opts.get('__modules__')
        if not loaded_modules:
            return modlist
        for mod in list(loaded_modules.keys()):
            provides = loaded_modules[mod].get('provides')
            if not provides:
                continue
            if "*" in events:
                modlist.append(mod)
            for evtype in provides:
                if evtype in events:
                    modlist.append(mod)
        return list(set(modlist))

    def modulesConsuming(self, events: list) -> list:
        modlist = list()
        if not events:
            return modlist
        loaded_modules = self.opts.get('__modules__')
        if not loaded_modules:
            return modlist
        for mod in list(loaded_modules.keys()):
            consumes = loaded_modules[mod].get('consumes')
            if not consumes:
                continue
            if "*" in consumes:
                modlist.append(mod)
                continue
            for evtype in consumes:
                if evtype in events:
                    modlist.append(mod)
        return list(set(modlist))

    def eventsFromModules(self, modules: list) -> list:
        evtlist = list()
        if not modules:
            return evtlist
        loaded_modules = self.opts.get('__modules__')
        if not loaded_modules:
            return evtlist
        for mod in modules:
            if mod in list(loaded_modules.keys()):
                provides = loaded_modules[mod].get('provides')
                if provides:
                    for evt in provides:
                        evtlist.append(evt)
        return evtlist

    def eventsToModules(self, modules: list) -> list:
        evtlist = list()
        if not modules:
            return evtlist
        loaded_modules = self.opts.get('__modules__')
        if not loaded_modules:
            return evtlist
        for mod in modules:
            if mod in list(loaded_modules.keys()):
                consumes = loaded_modules[mod].get('consumes')
                if consumes:
                    for evt in consumes:
                        evtlist.append(evt)
        return evtlist

    def urlFQDN(self, url: str) -> str:
        if not url:
            self.error(f"Invalid URL: {url}")
            return None
        from spiderfoot import SpiderFootHelpers
        baseurl = SpiderFootHelpers.urlBaseUrl(url)
        if '://' in baseurl:
            count = 2
        else:
            count = 0
        return baseurl.split('/')[count].lower()

    def googleIterate(self, searchString: str, opts: dict = None) -> dict:
        """Request search results from the Google API.

        Will return a dict:
        {
          "urls": a list of urls that match the query string,
          "webSearchUrl": url for Google results page,
        }

        Options accepted:
            useragent: User-Agent string to use
            timeout: API call timeout

        Args:
            searchString (str): Google search query
            opts (dict): TBD

        Returns:
            dict: Search results as {"webSearchUrl": "URL", "urls": [results]}
        """
        if not searchString:
            return None

        if opts is None:
            opts = {}

        search_string = searchString.replace(" ", "%20")
        import urllib.parse
        params = urllib.parse.urlencode({
            "cx": opts.get("cse_id", ""),
            "key": opts.get("api_key", ""),
        })

        response = self.fetchUrl(
            f"https://www.googleapis.com/customsearch/v1?q={search_string}&{params}",
            timeout=opts.get("timeout", 30),
        )

        if response['code'] != '200':
            self.error("Failed to get a valid response from the Google API")
            return None

        try:
            response_json = response['content']
            if isinstance(response_json, str):
                import json
                response_json = json.loads(response_json)
        except Exception:
            self.error(
                "The key 'content' in the Google API response doesn't contain valid JSON.")
            return None

        if "items" not in response_json:
            return None

        params = urllib.parse.urlencode({
            "ie": "utf-8",
            "oe": "utf-8",
            "aq": "t",
            "rls": "org.mozilla:en-US:official",
            "client": "firefox-a",
        })

        return {
            "urls": [str(k['link']) for k in response_json['items']],
            "webSearchUrl": f"https://www.google.com/search?q={search_string}&{params}"
        }

    def bingIterate(self, searchString: str, opts: dict = None) -> dict:
        """Request search results from the Bing API.

        Will return a dict:
        {
          "urls": a list of urls that match the query string,
          "webSearchUrl": url for bing results page,
        }

        Options accepted:
            count: number of search results to request from the API
            useragent: User-Agent string to use
            timeout: API call timeout

        Args:
            searchString (str): Bing search query
            opts (dict): TBD

        Returns:
            dict: Search results as {"webSearchUrl": "URL", "urls": [results]}
        """
        if not searchString:
            return None

        if opts is None:
            opts = {}

        search_string = searchString.replace(" ", "%20")
        import urllib.parse
        params = urllib.parse.urlencode({
            "responseFilter": "Webpages",
            "count": opts.get("count", 10),
        })

        response = self.fetchUrl(
            f"https://api.cognitive.microsoft.com/bing/v7.0/search?q={search_string}&{params}",
            timeout=opts.get("timeout", 30),
            useragent=opts.get("useragent", "SpiderFoot"),
            headers={"Ocp-Apim-Subscription-Key": opts.get("api_key", "")},
        )

        if response['code'] != '200':
            self.error("Failed to get a valid response from the Bing API")
            return None

        try:
            import json
            response_json = response['content']
            if isinstance(response_json, str):
                response_json = json.loads(response_json)
        except Exception:
            self.error(
                "The key 'content' in the bing API response doesn't contain valid JSON.")
            return None

        if ("webPages" in response_json and "value" in response_json["webPages"]):
            urls = [str(k['url']) for k in response_json["webPages"]["value"]]
            webSearchUrl = response_json["webPages"].get("webSearchUrl", "")
            return {
                "urls": urls,
                "webSearchUrl": webSearchUrl
            }
        return None

    def loadModules(self):
        """Load SpiderFoot modules from the modules directory."""
        import os
        from spiderfoot import SpiderFootHelpers
        script_dir = os.path.dirname(os.path.abspath(__file__))
        modpath = os.path.join(script_dir, 'modules')
        if not os.path.isdir(modpath):
            self.error(f"Modules directory not found: {modpath}")
            return
        self.info(f"Loading modules from: {modpath}")
        try:
            module_files = [f for f in os.listdir(modpath) if f.endswith('.py') and not f.startswith('__')]
        except OSError as e:
            self.error(f"Error reading modules directory: {e}")
            return
        if not module_files:
            self.info("No module files found.")
            return
        self.info(f"Found {len(module_files)} module files")
        # Actual module loading logic would go here
        # For now, just log the module names
        for mod in module_files:
            self.debug(f"Module found: {mod}")

    def cveInfo(self, cveId: str, sources: str = "circl,nist") -> tuple[str, str]:
        """Look up a CVE ID for more information in the first available source.

        Args:
            cveId (str): CVE ID, e.g. CVE-2018-15473
            sources (str): Comma-separated list of sources to query. Options available are circl and nist

        Returns:
            tuple[str, str]: Appropriate event type and descriptive text
        """
        sources = sources.split(",")
        eventType = "VULNERABILITY_GENERAL"
        def cveRating(score: int) -> str:
            if score == "Unknown":
                return None
            if score >= 0 and score <= 3.9:
                return "LOW"
            if score >= 4.0 and score <= 6.9:
                return "MEDIUM"
            if score >= 7.0 and score <= 8.9:
                return "HIGH"
            if score >= 9.0:
                return "CRITICAL"
            return None
        for source in sources:
            # Placeholder: actual CVE lookup logic would go here
            pass
        return (eventType, f"{cveId}\nScore: Unknown\nDescription: Unknown")

    def configSerialize(self, opts: dict, filterSystem: bool = True):
        """Delegate to config.configSerialize."""
        from .config import configSerialize
        return configSerialize(opts, filterSystem)

    def configUnserialize(self, opts: dict, referencePoint: dict, filterSystem: bool = True):
        """Delegate to config.configUnserialize."""
        from .config import configUnserialize
        return configUnserialize(opts, referencePoint, filterSystem)
