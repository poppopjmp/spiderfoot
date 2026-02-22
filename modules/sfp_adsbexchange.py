from __future__ import annotations

"""SpiderFoot plug-in module: adsbexchange."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_adsbexchange
# Purpose:     Query ADS-B Exchange via RapidAPI for unfiltered flight
#              tracking data including military and blocked aircraft.
#
# Author:      Agostino Panico <van1sh@van1shland.io>
#
# Created:     18/02/2026
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_adsbexchange(SpiderFootAsyncPlugin):

    """Query ADS-B Exchange for unfiltered real-time aircraft tracking data."""

    meta = {
        'name': "ADS-B Exchange",
        'summary': (
            "Query the ADS-B Exchange API (via RapidAPI) for unfiltered "
            "real-time aircraft positions, including military and FAA-blocked aircraft."
        ),
        'flags': ["apikey"],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://www.adsbexchange.com/",
            'model': "COMMERCIAL_ONLY",
            'references': [
                "https://www.adsbexchange.com/data/",
                "https://rapidapi.com/adsbx/api/adsbexchange-com1",
            ],
            'favIcon': "https://www.adsbexchange.com/favicon.ico",
            'logo': "https://www.adsbexchange.com/wp-content/uploads/cropped-ADSBx-Logo-v2.png",
            'description': (
                "ADS-B Exchange is the world's largest source of unfiltered "
                "flight data. Unlike other trackers, it does not censor military, "
                "government or FAA-blocked aircraft. Access via RapidAPI ($10/mo basic)."
            ),
        }
    }

    opts = {
        'api_key': "",
        'max_results': 25,
        'pause': 1.0,
    }

    optdescs = {
        'api_key': "RapidAPI key for ADS-B Exchange (adsbexchange-com1).",
        'max_results': "Maximum number of aircraft results to process per query.",
        'pause': "Seconds to wait between API requests.",
    }

    # ── Module wiring ─────────────────────────────────────────────
    def setup(self) -> None:
        self.results = self.tempStorage()
        self.errorState = False

    def watchedEvents(self) -> list[str]:
        return [
            "COMPANY_NAME",
            "GEOINFO",
            "COUNTRY_NAME",
        ]

    def producedEvents(self) -> list[str]:
        return [
            "RAW_RIR_DATA",
            "GEOINFO",
            "PHYSICAL_COORDINATES",
        ]

    # ── Helpers ───────────────────────────────────────────────────
    def _api_get(self, endpoint: str) -> dict | None:
        """Call ADS-B Exchange RapidAPI endpoint and return parsed JSON."""
        if self.errorState:
            return None

        api_key = self.opts.get('api_key', '')
        if not api_key:
            self.error("ADS-B Exchange RapidAPI key is not set.")
            self.errorState = True
            return None

        host = "adsbexchange-com1.p.rapidapi.com"
        url = f"https://{host}/{endpoint}"

        headers = {
            'x-rapidapi-key': api_key,
            'x-rapidapi-host': host,
        }

        res = self.fetch_url(url, timeout=30, headers=headers)

        if not res:
            self.error(f"ADS-B Exchange: No response from {endpoint}")
            return None

        if res['code'] not in ['200', 200]:
            self.error(f"ADS-B Exchange: HTTP {res['code']} for {endpoint}")
            if res['code'] in ['401', 401, '403', 403, '429', 429]:
                self.errorState = True
            return None

        try:
            data = json.loads(res['content'])
        except (json.JSONDecodeError, TypeError):
            self.error(f"ADS-B Exchange: Invalid JSON from {endpoint}")
            return None

        return data

    def _process_aircraft(self, ac_list: list[dict], event: SpiderFootEvent) -> None:
        """Process a list of aircraft records and emit events."""
        max_results = self.opts.get('max_results', 25)
        count = 0

        for ac in ac_list:
            if self.checkForStop():
                return
            if count >= max_results:
                break
            count += 1

            # Emit raw data
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(ac, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

            # Extract position
            lat = ac.get('lat')
            lon = ac.get('lon')
            if lat is not None and lon is not None:
                coords = f"{lat},{lon}"
                if coords not in self.results:
                    self.results[coords] = True
                    evt = SpiderFootEvent(
                        "PHYSICAL_COORDINATES", coords,
                        self.__name__, event)
                    self.notifyListeners(evt)

            # Build GeoInfo summary
            flight = ac.get('flight', '').strip()
            reg = ac.get('r', '')  # registration
            ac_type = ac.get('t', '')  # aircraft type
            alt = ac.get('alt_baro', '')
            spd = ac.get('gs', '')  # ground speed

            parts = []
            if flight:
                parts.append(f"Flight: {flight}")
            if reg:
                parts.append(f"Reg: {reg}")
            if ac_type:
                parts.append(f"Type: {ac_type}")
            if alt:
                parts.append(f"Alt: {alt}ft")
            if spd:
                parts.append(f"Speed: {spd}kts")

            if parts:
                geo = " | ".join(parts)
                if geo not in self.results:
                    self.results[geo] = True
                    evt = SpiderFootEvent(
                        "GEOINFO", geo, self.__name__, event)
                    self.notifyListeners(evt)

    # ── Query methods ─────────────────────────────────────────────
    def _query_by_callsign(self, callsign: str, event: SpiderFootEvent) -> None:
        """Search aircraft by callsign/flight number."""
        data = self._api_get(f"v2/callsign/{callsign}/")
        if not data:
            return

        ac_list = data.get('ac', [])
        if not ac_list:
            return

        self._process_aircraft(ac_list, event)

    def _query_by_registration(self, reg: str, event: SpiderFootEvent) -> None:
        """Search aircraft by registration number."""
        data = self._api_get(f"v2/registration/{reg}/")
        if not data:
            return

        ac_list = data.get('ac', [])
        if not ac_list:
            return

        self._process_aircraft(ac_list, event)

    def _query_by_type(self, ac_type: str, event: SpiderFootEvent) -> None:
        """Search aircraft by ICAO type designator."""
        data = self._api_get(f"v2/type/{ac_type}/")
        if not data:
            return

        ac_list = data.get('ac', [])
        if not ac_list:
            return

        self._process_aircraft(ac_list, event)

    # ── Main handler ──────────────────────────────────────────────
    def handleEvent(self, event: SpiderFootEvent) -> None:
        if self.errorState:
            return

        src = event.eventType
        val = event.data

        if not val:
            return

        cache_key = f"{src}:{val}"
        if cache_key in self.results:
            return
        self.results[cache_key] = True

        api_key = self.opts.get('api_key', '')
        if not api_key:
            self.error("ADS-B Exchange RapidAPI key is not set.")
            self.errorState = True
            return

        search = val.strip()

        # Use the value as a potential callsign or registration
        # Company names could be airline names → search as callsign prefix
        if src == "COMPANY_NAME":
            # Airline names: try as callsign  (e.g., "UNITED" → callsign)
            # Limit to alphanumeric tokens for valid callsign search
            token = ''.join(c for c in search if c.isalnum())[:8]
            if len(token) >= 2:
                self._query_by_callsign(token, event)
                if self.errorState:
                    return
                time.sleep(self.opts.get('pause', 1.0))

        elif src in ("GEOINFO", "COUNTRY_NAME"):
            # For geo events, we can't search by location via RapidAPI
            # endpoints easily. Log and skip.
            self.debug(
                f"ADS-B Exchange: Skipping geo-based search for '{search}' "
                "(use callsign or registration for targeted queries)."
            )
