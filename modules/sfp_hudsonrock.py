from __future__ import annotations

"""SpiderFoot plug-in module: hudsonrock."""

# -------------------------------------------------------------------------------
# Name:         sfp_hudsonrock
# Purpose:      Query Hudson Rock's Cavalier OSINT API for infostealer
#               intelligence on domains, emails, usernames, and phone numbers.
#
# Author:       SpiderFoot Contributors
#
# Created:      15/02/2026
# Copyright:    (c) SpiderFoot Contributors
# Licence:      MIT
# -------------------------------------------------------------------------------

import json
import time
import urllib.parse

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_hudsonrock(SpiderFootModernPlugin):

    """Query Hudson Rock Cavalier API for infostealer compromise intelligence on domains, emails, usernames and phone numbers."""

    meta = {
        'name': "Hudson Rock",
        'summary': "Query Hudson Rock's Cavalier OSINT API for infostealer intelligence. "
                   "Searches for compromised credentials, infected machines, and stealer "
                   "malware data associated with domains, emails, usernames and phone numbers.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Leaks, Dumps and Breaches"],
        'dataSource': {
            'website': "https://www.hudsonrock.com/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://cavalier.hudsonrock.com/docs",
                "https://www.hudsonrock.com/free-tools",
            ],
            'favIcon': "https://www.hudsonrock.com/favicon.ico",
            'logo': "https://www.hudsonrock.com/favicon.ico",
            'description': "Hudson Rock provides access to infostealer intelligence via "
                           "the Cavalier OSINT API. It aggregates data from millions of "
                           "computers compromised by infostealer malware worldwide, surfacing "
                           "compromised credentials, employee exposures, and third-party risks.",
        }
    }

    # Default options
    opts = {
        'delay': 1,
        'max_stealers': 50,
    }

    # Option descriptions
    optdescs = {
        'delay': "Delay (in seconds) between API requests to avoid rate-limiting.",
        'max_stealers': "Maximum number of stealer records to process per query (0 = unlimited).",
    }

    # Class variables — cleared in setup()
    results = None
    errorState = False

    BASE_URL = "https://cavalier.hudsonrock.com/api/json/v2/osint-tools"

    def setup(self, sfc, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return [
            "EMAILADDR",
            "DOMAIN_NAME",
            "INTERNET_NAME",
            "USERNAME",
            "PHONE_NUMBER",
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "EMAILADDR_COMPROMISED",
            "PHONE_NUMBER_COMPROMISED",
            "RAW_RIR_DATA",
            "MALICIOUS_INTERNET_NAME",
        ]

    # ------------------------------------------------------------------ #
    #  API query helpers
    # ------------------------------------------------------------------ #

    def _query_domain(self, domain: str) -> dict | None:
        """Search Hudson Rock Cavalier for an entire domain."""
        url = f"{self.BASE_URL}/search-by-domain?domain={urllib.parse.quote(domain, safe='')}"
        return self._fetch(url, domain)

    def _query_email(self, email: str) -> dict | None:
        """Search Hudson Rock Cavalier for a specific e-mail address."""
        url = f"{self.BASE_URL}/search-by-email?email={urllib.parse.quote(email, safe='')}"
        return self._fetch(url, email)

    def _query_username(self, username: str) -> dict | None:
        """Search Hudson Rock Cavalier by username (also used for phone numbers)."""
        url = f"{self.BASE_URL}/search-by-username?username={urllib.parse.quote(username, safe='')}"
        return self._fetch(url, username)

    def _fetch(self, url: str, qry: str) -> dict | None:
        """Execute an HTTP GET against the Cavalier API and return parsed JSON."""
        time.sleep(self.opts.get('delay', 1))

        res = self.fetch_url(
            url,
            timeout=self.opts.get('_fetchtimeout', 15),
            useragent="SpiderFoot",
        )

        if res is None:
            self.info(f"No response from Hudson Rock for {qry}")
            return None

        code = str(res.get('code', ''))

        if code == '404':
            self.debug(f"No Hudson Rock data for {qry}")
            return None

        if code in ('429',):
            self.error("Hudson Rock API rate-limited — consider increasing the delay option.")
            return None

        if code not in ('200',):
            self.error(f"Unexpected HTTP {code} from Hudson Rock for {qry}")
            return None

        content = res.get('content')
        if not content:
            return None

        try:
            return json.loads(content)
        except Exception as e:
            self.error(f"Error parsing Hudson Rock JSON for {qry}: {e}")

        return None

    # ------------------------------------------------------------------ #
    #  Event processing helpers
    # ------------------------------------------------------------------ #

    def _format_stealer_summary(self, s: dict) -> str:
        """Produce a human-readable line for a single stealer record."""
        parts = []
        if s.get('date_compromised'):
            parts.append(f"Date: {s['date_compromised']}")
        if s.get('computer_name') and s['computer_name'] != 'Not Found':
            parts.append(f"Host: {s['computer_name']}")
        if s.get('operating_system'):
            parts.append(f"OS: {s['operating_system']}")
        if s.get('stealer_family'):
            parts.append(f"Stealer: {s['stealer_family']}")
        if s.get('malware_path') and s['malware_path'] != 'Not Found':
            parts.append(f"Malware: {s['malware_path']}")
        if s.get('ip') and s['ip'] != 'Not Found':
            parts.append(f"IP: {s['ip']}")
        avs = s.get('antiviruses')
        if avs and isinstance(avs, list):
            parts.append(f"AV: {', '.join(avs)}")
        return " | ".join(parts) if parts else "Compromised (details redacted)"

    def _process_stealers(self, stealers: list, source_label: str,
                          source_event: SpiderFootEvent) -> None:
        """Emit RAW_RIR_DATA for each stealer record (capped by max_stealers)."""
        limit = self.opts.get('max_stealers', 50) or len(stealers)
        for idx, s in enumerate(stealers[:limit]):
            if self.checkForStop():
                return
            summary = self._format_stealer_summary(s)
            text = f"Hudson Rock [{source_label}]: {summary}"
            evt = SpiderFootEvent("RAW_RIR_DATA", text, self.__name__, source_event)
            self.notifyListeners(evt)

    # ------------------------------------------------------------------ #
    #  Main event handler
    # ------------------------------------------------------------------ #

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        # De-duplicate
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return
        self.results[eventData] = True

        # ----- DOMAIN / INTERNET_NAME ----- #
        if eventName in ("DOMAIN_NAME", "INTERNET_NAME"):
            data = self._query_domain(eventData)
            if data is None:
                return

            total = data.get('total', 0)
            employees = data.get('employees', 0)
            users = data.get('users', 0)
            third_parties = data.get('third_parties', 0)

            if total <= 0:
                self.info(f"No infostealer data for domain {eventData}")
                return

            # Emit a domain-level summary as RAW_RIR_DATA
            stealer_families = data.get('data', {}).get('stealerFamilies', {})
            family_summary = ""
            if isinstance(stealer_families, dict):
                families = {k: v for k, v in stealer_families.items()
                            if k != 'total' and isinstance(v, int) and v > 0}
                top = sorted(families.items(), key=lambda x: x[1], reverse=True)[:10]
                family_summary = ", ".join(f"{k}: {v}" for k, v in top)

            summary = (
                f"Hudson Rock Infostealer Intelligence for {eventData}\n"
                f"Total compromised credentials: {total}\n"
                f"Employees: {employees} | Users: {users} | Third-parties: {third_parties}\n"
            )
            if family_summary:
                summary += f"Top stealer families: {family_summary}\n"

            # Password strength stats
            for pw_key, pw_label in [('employeePasswords', 'Employee'),
                                      ('userPasswords', 'User')]:
                pw_data = data.get('data', {}).get(pw_key, {})
                if pw_data and pw_data.get('has_stats'):
                    total_pw = pw_data.get('totalPass', 0)
                    weak_pct = pw_data.get('too_weak', {}).get('perc', 0) + pw_data.get('weak', {}).get('perc', 0)
                    strong_pct = pw_data.get('strong', {}).get('perc', 0)
                    summary += f"{pw_label} passwords: {total_pw} total, {weak_pct:.1f}% weak, {strong_pct:.1f}% strong\n"

            evt = SpiderFootEvent("RAW_RIR_DATA", summary.strip(), self.__name__, event)
            self.notifyListeners(evt)

            # If employees compromised, flag the domain
            if employees > 0:
                desc = f"Hudson Rock: {employees} employee credential(s) compromised by infostealers [{eventData}]"
                evt = SpiderFootEvent("MALICIOUS_INTERNET_NAME", desc, self.__name__, event)
                self.notifyListeners(evt)

        # ----- EMAIL ----- #
        elif eventName == "EMAILADDR":
            data = self._query_email(eventData)
            if data is None:
                return

            stealers = data.get('stealers', [])
            if not stealers:
                self.info(f"No infostealer data for e-mail {eventData}")
                return

            # Emit compromised marker
            evt = SpiderFootEvent(
                "EMAILADDR_COMPROMISED",
                f"{eventData} [Hudson Rock - Infostealer]",
                self.__name__, event,
            )
            self.notifyListeners(evt)

            # Emit individual stealer records
            self._process_stealers(stealers, eventData, event)

        # ----- USERNAME ----- #
        elif eventName == "USERNAME":
            data = self._query_username(eventData)
            if data is None:
                return

            stealers = data.get('stealers', [])
            if not stealers:
                self.info(f"No infostealer data for username {eventData}")
                return

            # Emit stealer records as RAW_RIR_DATA
            self._process_stealers(stealers, eventData, event)

        # ----- PHONE NUMBER ----- #
        elif eventName == "PHONE_NUMBER":
            # Hudson Rock uses the username endpoint for phone numbers
            data = self._query_username(eventData)
            if data is None:
                return

            stealers = data.get('stealers', [])
            if not stealers:
                self.info(f"No infostealer data for phone {eventData}")
                return

            evt = SpiderFootEvent(
                "PHONE_NUMBER_COMPROMISED",
                f"{eventData} [Hudson Rock - Infostealer]",
                self.__name__, event,
            )
            self.notifyListeners(evt)

            self._process_stealers(stealers, eventData, event)

# End of sfp_hudsonrock class
