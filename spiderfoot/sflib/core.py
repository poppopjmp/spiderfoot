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
"""Core SpiderFoot engine object.

Contains the :class:`SpiderFoot` "god object" that holds scan
configuration, provides DNS resolution, HTTP fetching, content analysis,
and various domain / IP / URL helper methods used by every module.
"""

from __future__ import annotations

# Will import from .config, .network, .logging, .helpers as needed

from copy import deepcopy
import logging
import ssl
import dns.resolver
from .network import (
    resolveHost, resolveIP, resolveHost6, validateIP,
    safeSocket, safeSSLSocket, parseCert, getSession,
    fetchUrl, checkDnsWildcard,
)
from .helpers import (
    hashstring, cachePut, cacheGet, removeUrlCreds,
    isValidLocalOrLoopbackIp, domainKeyword, domainKeywords,
    hostDomain, validHost, isDomain, validIP, validIP6,
    validIpNetwork, isPublicIpAddress, normalizeDNS,
)

class SpiderFoot:
    """Central facade for SpiderFoot scan operations.

    Provides module loading, configuration management, DNS resolution,
    HTTP session handling, and utility methods used throughout scans.
    Every scan instantiates one :class:`SpiderFoot` object that modules
    interact with via their ``sf`` attribute.
    """

    _dbh = None
    _scanId = None
    _socksProxy = None
    opts = dict()

    def __init__(self, options: dict) -> None:
        """Initialize a SpiderFoot instance with the given options."""
        if not isinstance(options, dict):
            raise TypeError(f"options is {type(options)}; expected dict()")
        self.opts = deepcopy(options)
        self.log = logging.getLogger(f"spiderfoot.{__name__}")

        # SSL context for SCAN connections to external targets only.
        # Verification is intentionally disabled because scan targets often
        # present self-signed, expired, or otherwise invalid certificates
        # and we still need to connect to inspect them.
        # IMPORTANT: Do NOT use this context for internal service calls
        # (LiteLLM, MinIO, Qdrant, PostgreSQL, Redis).  Use
        # _internal_ssl_context instead.
        self._scan_ssl_context = ssl.create_default_context()
        self._scan_ssl_context.check_hostname = False
        self._scan_ssl_context.verify_mode = ssl.CERT_NONE

        # SSL context for INTERNAL service calls (LiteLLM, MinIO, Qdrant,
        # etc.) — uses default system CA bundle and enforces verification.
        self._internal_ssl_context = ssl.create_default_context()

        # Backward-compat alias (modules may reference self._ssl_context)
        self._ssl_context = self._scan_ssl_context

        if self.opts.get('_dnsserver', "") != "":
            res = dns.resolver.Resolver()
            res.nameservers = [self.opts['_dnsserver']]
            dns.resolver.override_system_resolver(res)

    @property
    def dbh(self) -> SpiderFootDb | None:
        """Database handle for this scan instance."""
        return self._dbh

    @property
    def scanId(self) -> str:
        """Unique identifier for the current scan."""
        return self._scanId

    @property
    def socksProxy(self) -> str:
        """SOCKS proxy address for network requests."""
        return self._socksProxy

    @dbh.setter
    def dbh(self, dbh: SpiderFootDb | None) -> None:
        """Set the database handle for this scan instance."""
        self._dbh = dbh

    @scanId.setter
    def scanId(self, scanId: str) -> str:
        """Set the unique identifier for the current scan."""
        self._scanId = scanId

    @socksProxy.setter
    def socksProxy(self, socksProxy: str) -> str:
        """Set the SOCKS proxy address for network requests."""
        self._socksProxy = socksProxy

    def optValueToData(self, val: str) -> str:
        """Resolve an option value that may reference a file (@path) or URL."""
        if not isinstance(val, str):
            self.error(f"Invalid option value {val}")
            return None
        if val.startswith('@'):
            fname = val.split('@')[1]
            self.info(f"Loading configuration data from: {fname}")
            try:
                with open(fname, encoding="utf-8") as f:
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
        """Log an error message for the current scan."""
        if not self.opts.get('__logging', False):
            return
        self.log.error(message, extra={'scanId': self._scanId})

    def fatal(self, error: str) -> None:
        """Log a critical error and terminate the process."""
        self.log.critical(error, extra={'scanId': self._scanId})
        import sys
        sys.exit(-1)

    def status(self, message: str) -> None:
        """Log a status/info message for the current scan."""
        if not self.opts.get('__logging', False):
            return
        self.log.info(message, extra={'scanId': self._scanId})

    def info(self, message: str) -> None:
        """Log an informational message for the current scan."""
        if not self.opts.get('__logging', False):
            return
        self.log.info(message, extra={'scanId': self._scanId})

    def debug(self, message: str) -> None:
        """Log a debug message if debug mode is enabled."""
        if not self.opts.get('_debug', False):
            return
        if not self.opts.get('__logging', False):
            return
        self.log.debug(message, extra={'scanId': self._scanId})

    # The following methods are now thin wrappers or use helpers directly
    def hashstring(self, string: str) -> str:
        """Hash a string using MD5 and return the hex digest."""
        return hashstring(string)
    def cachePut(self, label: str, data: str) -> None:
        """Store data in the cache under the given label."""
        return cachePut(label, data)
    def cacheGet(self, label: str, timeoutHrs: int) -> str:
        """Retrieve cached data by label within the given timeout."""
        return cacheGet(label, timeoutHrs)
    def removeUrlCreds(self, url: str) -> str:
        """Remove credentials from a URL."""
        return removeUrlCreds(url)
    def isValidLocalOrLoopbackIp(self, ip: str) -> bool:
        """Check if an IP address is local or loopback."""
        return isValidLocalOrLoopbackIp(ip)
    def domainKeyword(self, domain: str, tldList: list) -> str:
        """Extract the primary keyword from a domain name."""
        return domainKeyword(domain, tldList)
    def domainKeywords(self, domainList: list, tldList: list) -> set:
        """Extract keywords from a list of domain names."""
        return domainKeywords(domainList, tldList)
    def hostDomain(self, hostname: str, tldList: list) -> str:
        """Return the registered domain for a hostname."""
        return hostDomain(hostname, tldList)
    def validHost(self, hostname: str, tldList: str) -> bool:
        """Check if a hostname is valid against the TLD list."""
        return validHost(hostname, tldList)
    def isDomain(self, hostname: str, tldList: list) -> bool:
        """Check if a hostname is a registered domain."""
        return isDomain(hostname, tldList)
    def validIP(self, address: str) -> bool:
        """Check if a string is a valid IPv4 address."""
        return validIP(address)
    def validIP6(self, address: str) -> bool:
        """Check if a string is a valid IPv6 address."""
        return validIP6(address)
    def validIpNetwork(self, cidr: str) -> bool:
        """Check if a string is a valid IP network in CIDR notation."""
        return validIpNetwork(cidr)
    def isPublicIpAddress(self, ip: str) -> bool:
        """Check if an IP address is publicly routable."""
        return isPublicIpAddress(ip)
    def normalizeDNS(self, res: list) -> list:
        """Normalize DNS results by removing trailing dots."""
        return normalizeDNS(res)
    def resolveHost(self, host: str) -> list:
        """Resolve a hostname to its IPv4 addresses."""
        return resolveHost(host)
    def resolveIP(self, ipaddr: str) -> list:
        """Resolve an IP address to its hostnames via reverse DNS."""
        return resolveIP(ipaddr)
    def resolveHost6(self, hostname: str) -> list:
        """Resolve a hostname to its IPv6 addresses."""
        return resolveHost6(hostname)
    def validateIP(self, host: str, ip: str) -> bool:
        """Validate that an IP address resolves to the given host."""
        return validateIP(host, ip)
    def safeSocket(self, host: str, port: int, timeout: int) -> 'ssl.SSLSocket':
        """Create a safe TCP socket connection to a host and port."""
        return safeSocket(host, port, timeout)
    def safeSSLSocket(self, host: str, port: int, timeout: int) -> 'ssl.SSLSocket':
        """Create a safe SSL socket connection to a host and port."""
        return safeSSLSocket(host, port, timeout)
    def parseCert(self, rawcert: str, fqdn: str | None = None, expiringdays: int = 30) -> dict:
        """Parse an SSL certificate and return its details."""
        return parseCert(rawcert, fqdn, expiringdays)
    def getSession(self) -> 'requests.sessions.Session':
        """Return a configured requests session for HTTP operations."""
        return getSession()
    def useProxyForUrl(self, url: str) -> bool:
        """Determine whether to use the configured proxy for a URL."""
        # Patch: pass self for urlFQDN resolution and improve local IP detection
        from .network import useProxyForUrl
        return useProxyForUrl(
            url, self.opts,
            urlFQDN=self.urlFQDN,
            isValidLocalOrLoopbackIp=self.isValidLocalOrLoopbackIp,
        )
    def fetchUrl(
        self, url: str, cookies: str | None = None, timeout: int = 30,
        useragent: str = "SpiderFoot", headers: dict | None = None,
        noLog: bool = False, postData: str | None = None,
        disableContentEncoding: bool = False,
        sizeLimit: int | None = None, headOnly: bool = False,
        verify: bool = True,
        stealth_engine: object | None = None,
    ) -> dict:
        """Fetch the contents of a URL and return the response.

        When the scan config contains ``_stealth_level`` (set by the API
        from the user's stealth selection), a :class:`StealthScanContext`
        and :class:`StealthFetchMiddleware` are created lazily and cached
        on ``self`` so all modules share the same instance.  The middleware
        adds domain throttling, detection/block handling with automatic
        retries, proxy chain rotation, metrics collection, and all the
        per-request stealth features (UA rotation, header randomisation,
        TLS diversification, jitter).

        When an explicit *stealth_engine* is provided (e.g. from tests),
        it is passed directly to the low-level ``fetchUrl`` for backward
        compatibility.
        """
        # If an explicit stealth_engine was supplied, use the simple path
        if stealth_engine is not None:
            return fetchUrl(
                url, cookies, timeout, useragent, headers, noLog,
                postData, disableContentEncoding, sizeLimit,
                headOnly, verify,
                stealth_engine=stealth_engine,
            )

        # Auto-create the full stealth middleware from scan config
        middleware = self._get_or_create_stealth_middleware()
        if middleware is not None:
            return middleware.fetch(
                url,
                cookies=cookies,
                timeout=timeout,
                useragent=useragent,
                headers=headers,
                noLog=noLog,
                postData=postData,
                disableContentEncoding=disableContentEncoding,
                sizeLimit=sizeLimit,
                headOnly=headOnly,
                verify=verify,
                _original_fetch=fetchUrl,
            )

        # No stealth — plain fetch
        return fetchUrl(
            url, cookies, timeout, useragent, headers, noLog,
            postData, disableContentEncoding, sizeLimit,
            headOnly, verify,
        )

    # ── Stealth context management ────────────────────────────────────

    def _get_or_create_stealth_context(self) -> object | None:
        """Lazily create and cache a :class:`StealthScanContext`.

        Uses the full integration layer (proxy chains, domain throttling,
        metrics) rather than a bare :class:`StealthEngine`.
        """
        if hasattr(self, '_stealth_context') and self._stealth_context is not None:
            return self._stealth_context
        if not (hasattr(self, 'opts') and self.opts):
            return None
        level = self.opts.get("_stealth_level")
        if not level or level == "none":
            return None
        try:
            from spiderfoot.recon.stealth_integration import create_stealth_context
            self._stealth_context = create_stealth_context(
                sf_options=self.opts,
            )
            return self._stealth_context
        except Exception:
            return None

    def _get_or_create_stealth_middleware(self) -> object | None:
        """Lazily create and cache a :class:`StealthFetchMiddleware`."""
        if hasattr(self, '_stealth_middleware') and self._stealth_middleware is not None:
            return self._stealth_middleware
        ctx = self._get_or_create_stealth_context()
        if ctx is None:
            return None
        try:
            from spiderfoot.recon.stealth_integration import StealthFetchMiddleware
            self._stealth_middleware = StealthFetchMiddleware(ctx)
            return self._stealth_middleware
        except Exception:
            return None

    @property
    def stealth_context(self) -> object | None:
        """Public accessor for the per-scan stealth context (if active)."""
        return getattr(self, '_stealth_context', None)

    def _get_or_create_stealth_engine(self, level: str) -> object | None:
        """Lazily create and cache a StealthEngine for the given level.

        .. deprecated::
            Prefer :meth:`_get_or_create_stealth_context` which uses the
            full integration layer.  Kept for backward compatibility with
            tests that pass ``stealth_engine`` explicitly.
        """
        if hasattr(self, '_stealth_engine') and self._stealth_engine is not None:
            return self._stealth_engine
        try:
            from spiderfoot.recon.stealth_engine import StealthEngine, StealthProfileConfig
            config = StealthProfileConfig.from_level(level)
            self._stealth_engine = StealthEngine(config)
            return self._stealth_engine
        except Exception:
            return None
    def checkDnsWildcard(self, target: str) -> bool:
        """Check if a target domain has a DNS wildcard entry."""
        return checkDnsWildcard(target)
    def modulesProducing(self, events: list) -> list:
        """Return the list of modules that produce the given event types."""
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
        """Return the list of modules that consume the given event types."""
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
        """Return event types produced by the given modules."""
        if not modules:
            return []
        loaded_modules = self.opts.get('__modules__')
        if not loaded_modules:
            return []
        return [
            evt
            for mod in modules
            if mod in loaded_modules
            for evt in (loaded_modules[mod].get('provides') or [])
        ]

    def eventsToModules(self, modules: list) -> list:
        """Return event types consumed by the given modules."""
        if not modules:
            return []
        loaded_modules = self.opts.get('__modules__')
        if not loaded_modules:
            return []
        return [
            evt
            for mod in modules
            if mod in loaded_modules
            for evt in (loaded_modules[mod].get('consumes') or [])
        ]

    def urlFQDN(self, url: str) -> str:
        """Extract the fully qualified domain name from a URL."""
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

    def googleIterate(self, searchString: str, opts: dict | None = None) -> dict:
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
        except (json.JSONDecodeError, TypeError):
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

    def bingIterate(self, searchString: str, opts: dict | None = None) -> dict:
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
        except (json.JSONDecodeError, TypeError):
            self.error(
                "The key 'content' in the bing API response doesn't contain valid JSON.")
            return None

        if "webPages" in response_json and "value" in response_json["webPages"]:
            urls = [str(k['url']) for k in response_json["webPages"]["value"]]
            webSearchUrl = response_json["webPages"].get("webSearchUrl", "")
            return {
                "urls": urls,
                "webSearchUrl": webSearchUrl
            }
        return None

    def loadModules(self) -> None:
        """Load SpiderFoot modules from the modules directory.

        Discovers all sfp_*.py files, imports them via importlib,
        introspects producedEvents/watchedEvents/meta, and registers
        them in self.opts['__modules__'].
        """
        import os
        import sys
        import importlib
        import importlib.util

        # Modules live at the repository root under modules/
        script_dir = os.path.dirname(os.path.abspath(__file__))
        modpath = os.path.normpath(os.path.join(script_dir, '..', '..', 'modules'))

        if not os.path.isdir(modpath):
            self.error(f"Modules directory not found: {modpath}")
            return

        self.info(f"Loading modules from: {modpath}")

        try:
            module_files = [
                f for f in os.listdir(modpath)
                if f.endswith('.py') and f.startswith('sfp_') and not f.startswith('__')
            ]
        except OSError as e:
            self.error(f"Error reading modules directory: {e}")
            return

        if not module_files:
            self.info("No module files found.")
            return

        self.info(f"Found {len(module_files)} module files")

        # Ensure the modules directory is importable
        if modpath not in sys.path:
            sys.path.insert(0, modpath)

        modules_dict = {}
        loaded = 0
        failed = 0

        for mod_file in sorted(module_files):
            mod_name = mod_file[:-3]  # strip .py
            try:
                spec = importlib.util.spec_from_file_location(
                    mod_name,
                    os.path.join(modpath, mod_file)
                )
                if spec is None or spec.loader is None:
                    self.error(f"Cannot create import spec for {mod_name}")
                    failed += 1
                    continue

                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                # The module class has the same name as the file
                if not hasattr(mod, mod_name):
                    self.debug(f"Module {mod_name} has no class named {mod_name}, skipping")
                    failed += 1
                    continue

                mod_class = getattr(mod, mod_name)

                # Extract metadata by inspecting the class (not instantiating)
                meta = getattr(mod_class, 'meta', {})

                # producedEvents/watchedEvents are instance methods, so create
                # a bare instance without calling setup() for introspection.
                try:
                    tmp = object.__new__(mod_class)
                    provides = tmp.producedEvents() if hasattr(tmp, 'producedEvents') else []
                    consumes = tmp.watchedEvents() if hasattr(tmp, 'watchedEvents') else []
                except Exception:
                    provides = []
                    consumes = []

                modules_dict[mod_name] = {
                    'module': mod_class,
                    'provides': provides,
                    'consumes': consumes,
                    'meta': meta,
                    'cats': meta.get('categories', []),
                    'group': meta.get('useCases', []),
                    'labels': meta.get('flags', []),
                    'descr': meta.get('summary', ''),
                    'dataSource': meta.get('dataSource', {}),
                }
                loaded += 1
                self.debug(f"Loaded module: {mod_name} "
                           f"(provides={len(provides)}, consumes={len(consumes)})")

            except Exception as e:
                self.error(f"Failed to load module {mod_name}: {e}")
                failed += 1
                continue

        if '__modules__' not in self.opts:
            self.opts['__modules__'] = {}
        self.opts['__modules__'].update(modules_dict)

        self.info(f"Module loading complete: {loaded} loaded, {failed} failed")

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
            """Return the severity rating string for a CVE score."""
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
        for source in [s.strip() for s in sources]:
            if source == "circl":
                try:
                    res = self.fetchUrl(
                        f"https://cve.circl.lu/api/cve/{cveId}",
                        timeout=self.opts.get('_fetchtimeout', 15),
                        useragent=self.opts.get('_useragent', 'SpiderFoot')
                    )
                    if res and res.get('code') == '200' and res.get('content'):
                        import json
                        data = json.loads(res['content']) if isinstance(res['content'], str) else res['content']
                        cvss = data.get('cvss')
                        if cvss is None:
                            cvss = data.get('cvss3', 'Unknown')
                        try:
                            score = float(cvss)
                        except (ValueError, TypeError):
                            score = None
                        rating = cveRating(score) if score is not None else None
                        if rating:
                            eventType = f"VULNERABILITY_CVE_{rating}"
                        summary = data.get('summary', 'No description available')
                        return (eventType, f"{cveId}\nScore: {cvss}\nDescription: {summary}")
                except Exception as e:
                    self.debug(f"CIRCL CVE lookup failed for {cveId}: {e}")

            elif source == "nist":
                try:
                    res = self.fetchUrl(
                        f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cveId}",
                        timeout=self.opts.get('_fetchtimeout', 15),
                        useragent=self.opts.get('_useragent', 'SpiderFoot')
                    )
                    if res and res.get('code') == '200' and res.get('content'):
                        import json
                        data = json.loads(res['content']) if isinstance(res['content'], str) else res['content']
                        vulns = data.get('vulnerabilities', [])
                        if vulns:
                            cve_data = vulns[0].get('cve', {})
                            metrics = cve_data.get('metrics', {})
                            score = None
                            for key in ('cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2'):
                                metric_list = metrics.get(key, [])
                                if metric_list:
                                    score = metric_list[0].get('cvssData', {}).get('baseScore')
                                    if score is not None:
                                        break
                            if score is not None:
                                rating = cveRating(float(score))
                                if rating:
                                    eventType = f"VULNERABILITY_CVE_{rating}"
                            descriptions = cve_data.get('descriptions', [])
                            summary = next((d['value'] for d in descriptions if d.get('lang') == 'en'), 'No description')
                            return (eventType, f"{cveId}\nScore: {score or 'Unknown'}\nDescription: {summary}")
                except Exception as e:
                    self.debug(f"NIST CVE lookup failed for {cveId}: {e}")

            else:
                self.debug(f"Unknown CVE source: {source}")

        # All sources failed — return generic
        return (eventType, f"{cveId}\nScore: Unknown\nDescription: Unknown")

    def configSerialize(self, opts: dict, filterSystem: bool = True) -> dict:
        """Delegate to config.configSerialize."""
        from .config import configSerialize
        return configSerialize(opts, filterSystem)

    def configUnserialize(self, opts: dict, referencePoint: dict, filterSystem: bool = True) -> dict:
        """Delegate to config.configUnserialize."""
        from .config import configUnserialize
        return configUnserialize(opts, referencePoint, filterSystem)

    def getEventTypes(self) -> list:
        """Return the list of event types known to this scan."""
        return self.opts.get('__eventtypes__', [])

    def getModules(self) -> dict:
        """Return the dictionary of loaded modules."""
        return self.opts.get('__modules__', {})
