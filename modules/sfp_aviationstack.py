from __future__ import annotations

"""SpiderFoot plug-in module: aviationstack."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_aviationstack
# Purpose:     Query AviationStack API for real-time & historical flight,
#              airline, airport and aircraft data.
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
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_aviationstack(SpiderFootModernPlugin):

    """Query AviationStack for flight tracking, airline, airport and aircraft intelligence."""

    meta = {
        'name': "AviationStack",
        'summary': (
            "Query AviationStack API for real-time and historical flight data, "
            "airline details, airport information and aircraft registrations."
        ),
        'flags': ["apikey"],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://aviationstack.com/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://aviationstack.com/documentation",
            ],
            'favIcon': "https://aviationstack.com/site_images/aviationstack_shortcut_icon.ico",
            'logo': "https://aviationstack.com/site_images/aviationstack_logo.svg",
            'description': (
                "AviationStack provides a comprehensive REST API for real-time "
                "and historical flight tracking data, airport timetables, airline "
                "routes, and aircraft registrations. Free tier: 100 requests/month."
            ),
        }
    }

    # Default options
    opts = {
        'api_key': "",
        'max_results': 50,
        'enable_flights': True,
        'enable_airports': True,
        'enable_airlines': True,
        'enable_aircraft': True,
        'pause': 1.5,
    }

    optdescs = {
        'api_key': "AviationStack API access key.",
        'max_results': "Maximum number of results to retrieve per query (max 100 on free plan).",
        'enable_flights': "Query the flights endpoint for real-time flight data?",
        'enable_airports': "Query the airports endpoint for airport information?",
        'enable_airlines': "Query the airlines endpoint for airline details?",
        'enable_aircraft': "Query the airplanes endpoint for aircraft registration data?",
        'pause': "Seconds to wait between API requests.",
    }

    # ── Module wiring ─────────────────────────────────────────────
    def setup(self) -> None:
        self.results = self.tempStorage()
        self.errorState = False

    def watchedEvents(self) -> list[str]:
        return [
            "COMPANY_NAME",
            "INTERNET_NAME",
            "DOMAIN_NAME",
            "GEOINFO",
            "COUNTRY_NAME",
        ]

    def producedEvents(self) -> list[str]:
        return [
            "RAW_RIR_DATA",
            "GEOINFO",
            "PHYSICAL_COORDINATES",
            "COMPANY_NAME",
        ]

    # ── Helpers ───────────────────────────────────────────────────
    def _api_get(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Call AviationStack REST API and return parsed JSON or None."""
        if self.errorState:
            return None

        api_key = self.opts.get('api_key', '')
        if not api_key:
            self.error("AviationStack API key is not set.")
            self.errorState = True
            return None

        base = "http://api.aviationstack.com/v1"
        qparams = f"access_key={api_key}"
        if params:
            for k, v in params.items():
                qparams += f"&{k}={v}"

        url = f"{base}/{endpoint}?{qparams}"
        res = self.fetch_url(url, timeout=30)

        if not res:
            self.error(f"AviationStack: No response from {endpoint}")
            return None

        if res['code'] not in ['200', 200]:
            self.error(f"AviationStack: HTTP {res['code']} from {endpoint}")
            if res['code'] in ['401', 401, '403', 403]:
                self.errorState = True
            return None

        try:
            data = json.loads(res['content'])
        except (json.JSONDecodeError, TypeError):
            self.error(f"AviationStack: Invalid JSON from {endpoint}")
            return None

        if 'error' in data:
            err = data['error']
            self.error(
                f"AviationStack API error: {err.get('message', err.get('code', 'unknown'))}"
            )
            if err.get('code') in ('invalid_access_key', 'usage_limit_reached'):
                self.errorState = True
            return None

        return data

    # ── Query methods ─────────────────────────────────────────────
    def _query_flights(self, search_term: str, event: SpiderFootEvent) -> None:
        """Search flights by airline name or IATA code."""
        params = {
            'airline_name': search_term,
            'limit': min(self.opts.get('max_results', 50), 100),
        }
        data = self._api_get("flights", params)
        if not data or 'data' not in data:
            return

        flights = data['data']
        if not flights:
            return

        for flight in flights:
            if self.checkForStop():
                return

            # Emit raw data
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(flight, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

            # Extract geo from departure
            dep = flight.get('departure', {})
            if dep:
                lat = dep.get('latitude')
                lon = dep.get('longitude')
                airport_name = dep.get('airport')
                if lat and lon:
                    coords = f"{lat},{lon}"
                    if coords not in self.results:
                        self.results[coords] = True
                        evt = SpiderFootEvent(
                            "PHYSICAL_COORDINATES", coords,
                            self.__name__, event)
                        self.notifyListeners(evt)
                if airport_name:
                    tz = dep.get('timezone', '')
                    geo = f"{airport_name}"
                    if tz:
                        geo += f" ({tz})"
                    if geo not in self.results:
                        self.results[geo] = True
                        evt = SpiderFootEvent(
                            "GEOINFO", geo, self.__name__, event)
                        self.notifyListeners(evt)

            # Extract geo from arrival
            arr = flight.get('arrival', {})
            if arr:
                lat = arr.get('latitude')
                lon = arr.get('longitude')
                airport_name = arr.get('airport')
                if lat and lon:
                    coords = f"{lat},{lon}"
                    if coords not in self.results:
                        self.results[coords] = True
                        evt = SpiderFootEvent(
                            "PHYSICAL_COORDINATES", coords,
                            self.__name__, event)
                        self.notifyListeners(evt)
                if airport_name:
                    tz = arr.get('timezone', '')
                    geo = f"{airport_name}"
                    if tz:
                        geo += f" ({tz})"
                    if geo not in self.results:
                        self.results[geo] = True
                        evt = SpiderFootEvent(
                            "GEOINFO", geo, self.__name__, event)
                        self.notifyListeners(evt)

            # Airline as COMPANY_NAME
            airline = flight.get('airline', {})
            if airline:
                name = airline.get('name')
                if name and name not in self.results:
                    self.results[name] = True
                    evt = SpiderFootEvent(
                        "COMPANY_NAME", name, self.__name__, event)
                    self.notifyListeners(evt)

    def _query_airports(self, search_term: str, event: SpiderFootEvent) -> None:
        """Search airports by name or country."""
        params = {
            'search': search_term,
            'limit': min(self.opts.get('max_results', 50), 100),
        }
        data = self._api_get("airports", params)
        if not data or 'data' not in data:
            return

        for airport in data['data']:
            if self.checkForStop():
                return

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(airport, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

            lat = airport.get('latitude')
            lon = airport.get('longitude')
            name = airport.get('airport_name', '')
            country = airport.get('country_name', '')
            city = airport.get('city_iata_code', '')

            if lat and lon:
                coords = f"{lat},{lon}"
                if coords not in self.results:
                    self.results[coords] = True
                    evt = SpiderFootEvent(
                        "PHYSICAL_COORDINATES", coords,
                        self.__name__, event)
                    self.notifyListeners(evt)

            parts = [p for p in (name, city, country) if p]
            if parts:
                geo = ", ".join(parts)
                if geo not in self.results:
                    self.results[geo] = True
                    evt = SpiderFootEvent(
                        "GEOINFO", geo, self.__name__, event)
                    self.notifyListeners(evt)

    def _query_airlines(self, search_term: str, event: SpiderFootEvent) -> None:
        """Search airlines by name."""
        params = {
            'search': search_term,
            'limit': min(self.opts.get('max_results', 50), 100),
        }
        data = self._api_get("airlines", params)
        if not data or 'data' not in data:
            return

        for airline in data['data']:
            if self.checkForStop():
                return

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(airline, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

            name = airline.get('airline_name')
            if name and name not in self.results:
                self.results[name] = True
                evt = SpiderFootEvent(
                    "COMPANY_NAME", name, self.__name__, event)
                self.notifyListeners(evt)

            country = airline.get('country_name')
            if country and country not in self.results:
                self.results[country] = True
                evt = SpiderFootEvent(
                    "GEOINFO", country, self.__name__, event)
                self.notifyListeners(evt)

    def _query_aircraft(self, search_term: str, event: SpiderFootEvent) -> None:
        """Search aircraft/airplanes by airline or registration."""
        params = {
            'search': search_term,
            'limit': min(self.opts.get('max_results', 50), 100),
        }
        data = self._api_get("airplanes", params)
        if not data or 'data' not in data:
            return

        for plane in data['data']:
            if self.checkForStop():
                return

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(plane, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

            owner = plane.get('airline_iata_code', '')
            model = plane.get('model_name', '')
            reg = plane.get('registration_number', '')
            info_parts = [p for p in (owner, model, reg) if p]
            if info_parts:
                info = "Aircraft: " + " | ".join(info_parts)
                if info not in self.results:
                    self.results[info] = True

    # ── Main handler ──────────────────────────────────────────────
    def handleEvent(self, event: SpiderFootEvent) -> None:
        if self.errorState:
            return

        src = event.eventType
        val = event.data

        if not val:
            return

        # Dedup
        cache_key = f"{src}:{val}"
        if cache_key in self.results:
            return
        self.results[cache_key] = True

        api_key = self.opts.get('api_key', '')
        if not api_key:
            self.error("AviationStack API key is not set.")
            self.errorState = True
            return

        search_term = val.strip()

        # Query flights
        if self.opts.get('enable_flights'):
            self._query_flights(search_term, event)
            if self.errorState:
                return
            time.sleep(self.opts.get('pause', 1.5))

        if self.checkForStop():
            return

        # Query airports
        if self.opts.get('enable_airports') and src in (
            "GEOINFO", "COUNTRY_NAME", "INTERNET_NAME", "DOMAIN_NAME"
        ):
            self._query_airports(search_term, event)
            if self.errorState:
                return
            time.sleep(self.opts.get('pause', 1.5))

        if self.checkForStop():
            return

        # Query airlines
        if self.opts.get('enable_airlines') and src in (
            "COMPANY_NAME", "INTERNET_NAME", "DOMAIN_NAME"
        ):
            self._query_airlines(search_term, event)
            if self.errorState:
                return
            time.sleep(self.opts.get('pause', 1.5))

        if self.checkForStop():
            return

        # Query aircraft registrations
        if self.opts.get('enable_aircraft') and src in (
            "COMPANY_NAME", "INTERNET_NAME", "DOMAIN_NAME"
        ):
            self._query_aircraft(search_term, event)
