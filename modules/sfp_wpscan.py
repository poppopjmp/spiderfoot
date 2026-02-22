from __future__ import annotations

"""SpiderFoot plug-in module: wpscan."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_wpscan
# Purpose:     Query WPScan Vulnerability Database API for known WordPress
#              core, plugin and theme vulnerabilities.
#
# Author:      Agostino Panico <van1sh@van1shland.io>
#
# Created:     18/02/2026
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import re
import time

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_wpscan(SpiderFootAsyncPlugin):

    """Query WPScan Vulnerability Database for known WordPress core, plugin and theme vulnerabilities."""

    meta = {
        'name': "WPScan",
        'summary': "Query the WPScan WordPress Vulnerability Database API for known CVEs in WordPress core, plugins and themes.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://wpscan.com/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://wpscan.com/api/",
                "https://wpscan.com/docs/api",
            ],
            'apiKeyInstructions': [
                "Visit https://wpscan.com/register",
                "Register a free account",
                "Navigate to your profile to find your API token",
                "Free tier provides limited daily API requests",
            ],
            'favIcon': "https://wpscan.com/favicon.ico",
            'logo': "https://wpscan.com/assets/wpscan-logo.png",
            'description': (
                "WPScan maintains the largest WordPress vulnerability database. "
                "The API provides CVE information for WordPress core versions, "
                "plugins and themes. Free tier available with registration."
            ),
        }
    }

    opts = {
        'api_key': "",
    }

    optdescs = {
        'api_key': "WPScan API token.",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return [
            "URL_WEB_FRAMEWORK",
            "SOFTWARE_USED",
            "WEBSERVER_TECHNOLOGY",
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "VULNERABILITY_CVE_CRITICAL",
            "VULNERABILITY_CVE_HIGH",
            "VULNERABILITY_CVE_MEDIUM",
            "VULNERABILITY_CVE_LOW",
            "VULNERABILITY_GENERAL",
            "RAW_RIR_DATA",
        ]

    # ---- WordPress detection helpers ----

    @staticmethod
    def _parseWordPressVersion(data: str) -> str | None:
        """Try to extract a WordPress version from event data.

        Examples of data we might receive:
         - "WordPress 6.4.2"
         - "WordPress/6.4"
         - "/wp-content/ (WordPress)"
         - "wordpress:6.4.2"
        """
        if not data:
            return None

        data_lower = data.lower()
        if 'wordpress' not in data_lower and 'wp-' not in data_lower:
            return None

        # Try version patterns
        patterns = [
            r'wordpress[/ :]+(\d+\.\d+(?:\.\d+)?)',
            r'wordpress\s+(\d+\.\d+(?:\.\d+)?)',
        ]
        for pat in patterns:
            m = re.search(pat, data_lower)
            if m:
                return m.group(1)

        # WordPress detected but no version
        return ""

    @staticmethod
    def _parseWordPressPlugin(data: str) -> str | None:
        """Try to extract a WordPress plugin slug from event data.

        Looks for patterns like:
         - /wp-content/plugins/akismet/
         - plugin:akismet:4.2.1
        """
        if not data:
            return None

        m = re.search(r'/wp-content/plugins/([a-zA-Z0-9_-]+)', data)
        if m:
            return m.group(1).lower()

        return None

    @staticmethod
    def _parseWordPressTheme(data: str) -> str | None:
        """Try to extract a WordPress theme slug from event data.

        Looks for:
         - /wp-content/themes/flavor/
        """
        if not data:
            return None

        m = re.search(r'/wp-content/themes/([a-zA-Z0-9_-]+)', data)
        if m:
            return m.group(1).lower()

        return None

    # ---- API helpers ----

    def _apiGet(self, path: str) -> dict | None:
        """Make a GET request to the WPScan API v3."""
        url = f"https://wpscan.com/api/v3/{path}"

        res = self.fetch_url(
            url,
            timeout=self.opts.get('_fetchtimeout', 30),
            useragent="SpiderFoot",
            headers={"Authorization": f"Token token={self.opts['api_key']}"},
        )

        if not res:
            self.error(f"No response from WPScan API ({path})")
            return None

        if res['code'] in ["401", "403"]:
            self.error("WPScan API token is invalid or rate limit exceeded.")
            self.errorState = True
            return None

        if res['code'] == "429":
            self.error("WPScan API rate limit exceeded.")
            return None

        if res['code'] == "404":
            self.debug(f"WPScan API: no data for {path}")
            return None

        if res['code'] not in ["200"]:
            self.error(f"Unexpected HTTP {res['code']} from WPScan API")
            return None

        if not res.get('content'):
            self.debug(f"Empty response from WPScan API ({path})")
            return None

        try:
            return json.loads(res['content'])
        except (ValueError, TypeError) as e:
            self.error(f"Error parsing WPScan response: {e}")
            return None

    def queryWordPressCore(self, version: str) -> dict | None:
        """Query the WPScan API for WordPress core vulnerabilities.

        GET /api/v3/wordpresses/{version_without_dots}
        """
        version_key = version.replace('.', '')
        return self._apiGet(f"wordpresses/{version_key}")

    def queryPlugin(self, slug: str) -> dict | None:
        """Query the WPScan API for plugin vulnerabilities.

        GET /api/v3/plugins/{slug}
        """
        return self._apiGet(f"plugins/{slug}")

    def queryTheme(self, slug: str) -> dict | None:
        """Query the WPScan API for theme vulnerabilities.

        GET /api/v3/themes/{slug}
        """
        return self._apiGet(f"themes/{slug}")

    # ---- Event handler ----

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        if not self.opts.get('api_key'):
            self.error("You enabled sfp_wpscan but did not set an API token!")
            self.errorState = True
            return

        # Deduplicate on the lookup key (version/plugin/theme)
        check_key = f"{eventName}:{eventData}"
        if check_key in self.results:
            return
        self.results[check_key] = True

        self.debug(f"Received event, {eventName}, from {event.module}")

        # Determine what WordPress component to look up
        wp_version = self._parseWordPressVersion(eventData)
        plugin_slug = self._parseWordPressPlugin(eventData)
        theme_slug = self._parseWordPressTheme(eventData)

        if wp_version is not None and wp_version != "":
            lookup_key = f"wp_core:{wp_version}"
            if lookup_key not in self.results:
                self.results[lookup_key] = True
                self._lookupCore(event, wp_version)
                time.sleep(1)

        if plugin_slug:
            lookup_key = f"wp_plugin:{plugin_slug}"
            if lookup_key not in self.results:
                self.results[lookup_key] = True
                self._lookupPlugin(event, plugin_slug)
                time.sleep(1)

        if theme_slug:
            lookup_key = f"wp_theme:{theme_slug}"
            if lookup_key not in self.results:
                self.results[lookup_key] = True
                self._lookupTheme(event, theme_slug)

    def _emitVulnerabilities(self, event: SpiderFootEvent, vulns: list, component: str) -> None:
        """Emit vulnerability events from a WPScan vulnerability list."""
        if not vulns:
            return

        for vuln in vulns:
            if self.checkForStop():
                return

            title = vuln.get('title', 'Unknown vulnerability')
            vuln_type = vuln.get('vuln_type', '')
            fixed_in = vuln.get('fixed_in', '')

            # Extract CVE references
            cve_ids = []
            for ref in vuln.get('references', {}).get('cve', []):
                cve_ids.append(f"CVE-{ref}")

            # Build description
            desc_parts = [f"WPScan: {title}"]
            desc_parts.append(f"Component: {component}")
            if vuln_type:
                desc_parts.append(f"Type: {vuln_type}")
            if fixed_in:
                desc_parts.append(f"Fixed in: {fixed_in}")
            if cve_ids:
                desc_parts.append(f"CVE(s): {', '.join(cve_ids)}")

            description = "\n".join(desc_parts)

            # Determine severity from CVSS if available
            cvss = vuln.get('cvss', {})
            score = cvss.get('score')

            if score is not None:
                try:
                    score = float(score)
                except (ValueError, TypeError):
                    score = None

            if score is not None:
                if score >= 9.0:
                    etype = "VULNERABILITY_CVE_CRITICAL"
                elif score >= 7.0:
                    etype = "VULNERABILITY_CVE_HIGH"
                elif score >= 4.0:
                    etype = "VULNERABILITY_CVE_MEDIUM"
                else:
                    etype = "VULNERABILITY_CVE_LOW"
            else:
                etype = "VULNERABILITY_GENERAL"

            evt = SpiderFootEvent(etype, description, self.__name__, event)
            self.notifyListeners(evt)

    def _lookupCore(self, event: SpiderFootEvent, version: str) -> None:
        """Look up WordPress core vulnerabilities."""
        data = self.queryWordPressCore(version)
        if not data:
            return

        # WPScan API returns { "version_key": { ... } }
        for version_key, info in data.items():
            vulns = info.get('vulnerabilities', [])
            if vulns:
                evt = SpiderFootEvent(
                    "RAW_RIR_DATA", json.dumps(info, indent=2),
                    self.__name__, event)
                self.notifyListeners(evt)
                self._emitVulnerabilities(event, vulns, f"WordPress {version}")

    def _lookupPlugin(self, event: SpiderFootEvent, slug: str) -> None:
        """Look up WordPress plugin vulnerabilities."""
        data = self.queryPlugin(slug)
        if not data:
            return

        for plugin_key, info in data.items():
            vulns = info.get('vulnerabilities', [])
            if vulns:
                evt = SpiderFootEvent(
                    "RAW_RIR_DATA", json.dumps(info, indent=2),
                    self.__name__, event)
                self.notifyListeners(evt)
                self._emitVulnerabilities(event, vulns, f"Plugin: {slug}")

    def _lookupTheme(self, event: SpiderFootEvent, slug: str) -> None:
        """Look up WordPress theme vulnerabilities."""
        data = self.queryTheme(slug)
        if not data:
            return

        for theme_key, info in data.items():
            vulns = info.get('vulnerabilities', [])
            if vulns:
                evt = SpiderFootEvent(
                    "RAW_RIR_DATA", json.dumps(info, indent=2),
                    self.__name__, event)
                self.notifyListeners(evt)
                self._emitVulnerabilities(event, vulns, f"Theme: {slug}")

# End of sfp_wpscan class
