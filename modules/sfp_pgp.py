from __future__ import annotations

"""SpiderFoot plug-in module: pgp."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_pgp
# Purpose:      SpiderFoot plug-in for looking up e-mail addresses in PGP
#               key servers as well as finding e-mail addresses belonging to
#               your target.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     17/02/2015
# Copyright:   (c) Steve Micallef 2015
# Licence:     MIT
# -------------------------------------------------------------------------------

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_pgp(SpiderFootModernPlugin):

    """Look up domains and e-mail addresses in PGP public key servers."""

    meta = {
        'name': "PGP Key Servers",
        'summary': "Look up domains and e-mail addresses in PGP public key servers.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Public Registries"]
    }

    results = None
    errorState = False

    # Sample key servers:
    # https://pgp.key-server.io
    # http://the.earth.li:11371
    # https://keyserver.ubuntu.com
    # https://sks-keyservers.net

    opts = {
        'retrieve_keys': True,
        'keyserver_search1': "https://keyserver.ubuntu.com/pks/lookup?fingerprint=on&op=vindex&search=",
        'keyserver_fetch1': "https://keyserver.ubuntu.com/pks/lookup?op=get&search=",
        'keyserver_search2': "http://the.earth.li:11371/pks/lookup?fingerprint=on&op=vindex&search=",
        'keyserver_fetch2': "http://the.earth.li:11371/pks/lookup?op=get&search="
    }

    optdescs = {
        'retrieve_keys': "Retrieve PGP keys.",
        'keyserver_search1': "PGP public key server URL to find e-mail addresses on a domain. Domain will get appended.",
        'keyserver_fetch1': "PGP public key server URL to find the public key for an e-mail address. Email address will get appended.",
        'keyserver_search2': "Backup PGP public key server URL to find e-mail addresses on a domain. Domain will get appended.",
        'keyserver_fetch2': "Backup PGP public key server URL to find the public key for an e-mail address. Email address will get appended."
    }

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ['INTERNET_NAME', "EMAILADDR", "DOMAIN_NAME"]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["EMAILADDR", "EMAILADDR_GENERIC", "AFFILIATE_EMAILADDR", "PGP_KEY"]

    def queryDomain(self, keyserver_search_url: str, qry: str) -> dict | None:
        """Query Domain."""
        res = self.fetch_url(
            keyserver_search_url + qry,
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts['_useragent']
        )

        if not res:
            return None

        if res['content'] is None:
            return None

        if res['code'] == "503":
            return None

        return res

    def queryEmail(self, keyserver_fetch_url: str, qry: str) -> dict | None:
        """Query Email."""
        res = self.fetch_url(
            keyserver_fetch_url + qry,
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts['_useragent']
        )

        if not res:
            return None

        if res['content'] is None:
            return None

        if res['code'] == "503":
            return None

        return res

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        if eventData in self.results:
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {event.module}")

        if not self.opts['keyserver_search1'] and not self.opts['keyserver_search2']:
            self.error(
                f"You enabled {self.__class__.__name__} but did not set key server URLs")
            self.errorState = True
            return

        # Get e-mail addresses on this domain
        if eventName in ["DOMAIN_NAME", "INTERNET_NAME"]:
            res = self.queryDomain(self.opts['keyserver_search1'], eventData)

            if not res:
                res = self.queryDomain(
                    self.opts['keyserver_search2'], eventData)

            if not res:
                return

            emails = SpiderFootHelpers.extractEmailsFromText(res['content'])
            self.info(f"Found {len(emails)} email addresses")

            for email in emails:
                if email.split("@")[0] in self.opts['_genericusers'].split(","):
                    evttype = "EMAILADDR_GENERIC"
                else:
                    evttype = "EMAILADDR"

                mailDom = email.lower().split('@')[1]
                if not self.getTarget().matches(mailDom):
                    evttype = "AFFILIATE_EMAILADDR"

                self.debug(f"Found e-mail address: {email}")
                evt = SpiderFootEvent(evttype, email, self.__name__, event)
                self.notifyListeners(evt)

        if eventName == "EMAILADDR" and self.opts['retrieve_keys']:
            res = self.queryEmail(self.opts['keyserver_fetch1'], eventData)

            if not res:
                res = self.queryEmail(self.opts['keyserver_fetch2'], eventData)

            if not res:
                return

            keys = SpiderFootHelpers.extractPgpKeysFromText(res['content'])
            self.info(f"Found {len(keys)} public PGP keys")

            for key in keys:
                self.debug(f"Found public key: {key}")
                evt = SpiderFootEvent("PGP_KEY", key, self.__name__, event)
                self.notifyListeners(evt)

# End of sfp_pgp class
