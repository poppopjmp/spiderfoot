from __future__ import annotations

"""SpiderFoot plug-in module: aprsfi."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_aprsfi
# Purpose:     Query aprs.fi API for APRS station and AIS vessel tracking,
#              position data, weather stations and messaging.
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


class sfp_aprsfi(SpiderFootModernPlugin):

    """Query aprs.fi for APRS station locations and AIS vessel tracking data."""

    meta = {
        'name': "aprs.fi",
        'summary': (
            "Query the aprs.fi API for APRS station locations, "
            "AIS vessel tracking data, weather reports and messaging."
        ),
        'flags': ["apikey"],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://aprs.fi/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://aprs.fi/page/api",
            ],
            'favIcon': "https://aprs.fi/favicon.ico",
            'logo': "https://aprs.fi/img/aprsfi_logo.png",
            'description': (
                "aprs.fi provides a free API for querying APRS (Automatic Packet "
                "Reporting System) station locations, AIS vessel positions, weather "
                "data and APRS messages. Supports up to 20 targets per request. "
                "Includes AIS vessel tracking with MMSI, IMO, course, speed, heading, "
                "length, width and draught data."
            ),
        }
    }

    opts = {
        'api_key': "",
        'query_location': True,
        'query_weather': True,
        'pause': 1.5,
    }

    optdescs = {
        'api_key': "aprs.fi API key (get from account settings at aprs.fi).",
        'query_location': "Query location/position data for callsigns?",
        'query_weather': "Query weather data for weather stations?",
        'pause': "Seconds to wait between API requests.",
    }

    # ── Module wiring ─────────────────────────────────────────────
    def setup(self) -> None:
        self.results = self.tempStorage()
        self.errorState = False

    def watchedEvents(self) -> list[str]:
        return [
            "COMPANY_NAME",
            "USERNAME",
            "INTERNET_NAME",
        ]

    def producedEvents(self) -> list[str]:
        return [
            "RAW_RIR_DATA",
            "GEOINFO",
            "PHYSICAL_COORDINATES",
            "COUNTRY_NAME",
        ]

    # ── Helpers ───────────────────────────────────────────────────
    def _api_get(self, what: str, params: dict) -> dict | None:
        """Call aprs.fi REST API and return parsed JSON or None."""
        if self.errorState:
            return None

        api_key = self.opts.get('api_key', '')
        if not api_key:
            self.error("aprs.fi API key is not set.")
            self.errorState = True
            return None

        base = "https://api.aprs.fi/api/get"
        qparams = f"what={what}&apikey={api_key}&format=json"
        for k, v in params.items():
            qparams += f"&{k}={v}"

        url = f"{base}?{qparams}"
        res = self.fetch_url(url, timeout=30)

        if not res:
            self.error(f"aprs.fi: No response for {what} query")
            return None

        if res['code'] not in ['200', 200]:
            self.error(f"aprs.fi: HTTP {res['code']}")
            if res['code'] in ['401', 401, '403', 403]:
                self.errorState = True
            return None

        try:
            data = json.loads(res['content'])
        except (json.JSONDecodeError, TypeError):
            self.error("aprs.fi: Invalid JSON response")
            return None

        if data.get('result') != 'ok':
            desc = data.get('description', 'unknown error')
            self.error(f"aprs.fi API error: {desc}")
            if 'authentication' in desc.lower() or 'api key' in desc.lower():
                self.errorState = True
            return None

        return data

    # ── Query methods ─────────────────────────────────────────────
    def _query_location(self, name: str, event: SpiderFootEvent) -> None:
        """Query location data for one or more callsigns/names."""
        data = self._api_get("loc", {'name': name})
        if not data:
            return

        found = data.get('found', 0)
        if not found:
            return

        entries = data.get('entries', [])
        for entry in entries:
            if self.checkForStop():
                return

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(entry, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

            lat = entry.get('lat')
            lng = entry.get('lng')
            if lat and lng:
                coords = f"{lat},{lng}"
                if coords not in self.results:
                    self.results[coords] = True
                    evt = SpiderFootEvent(
                        "PHYSICAL_COORDINATES", coords,
                        self.__name__, event)
                    self.notifyListeners(evt)

            # Build geo info
            station_name = entry.get('name', '')
            target_type = entry.get('type', '')
            comment = entry.get('comment', '')
            speed = entry.get('speed', '')
            course = entry.get('course', '')
            altitude = entry.get('altitude', '')

            # AIS specific fields
            mmsi = entry.get('mmsi', '')
            imo = entry.get('imo', '')
            heading = entry.get('heading', '')
            length = entry.get('length', '')
            width = entry.get('width', '')
            draught = entry.get('draught', '')
            navstat = entry.get('navstat', '')

            parts = []
            if station_name:
                parts.append(station_name)

            # Classify target type
            type_labels = {
                'a': 'AIS vessel',
                'l': 'APRS station',
                'i': 'APRS item',
                'o': 'APRS object',
                'w': 'Weather station',
            }
            type_label = type_labels.get(target_type, '')
            if type_label:
                parts.append(type_label)

            # AIS vessel details
            if mmsi:
                parts.append(f"MMSI: {mmsi}")
            if imo:
                parts.append(f"IMO: {imo}")
            if length and width:
                parts.append(f"{length}x{width}m")
            if draught:
                parts.append(f"Draft: {draught}m")
            if speed:
                parts.append(f"{speed} km/h")
            if heading:
                parts.append(f"Hdg: {heading}°")
            if altitude:
                parts.append(f"Alt: {altitude}m")
            if comment:
                parts.append(comment[:100])

            if parts:
                geo = " | ".join(parts)
                if geo not in self.results:
                    self.results[geo] = True
                    evt = SpiderFootEvent(
                        "GEOINFO", geo, self.__name__, event)
                    self.notifyListeners(evt)

    def _query_weather(self, name: str, event: SpiderFootEvent) -> None:
        """Query weather data for a station."""
        data = self._api_get("wx", {'name': name})
        if not data:
            return

        found = data.get('found', 0)
        if not found:
            return

        entries = data.get('entries', [])
        for entry in entries:
            if self.checkForStop():
                return

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(entry, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

            # Weather summary
            station = entry.get('name', '')
            temp = entry.get('temp', '')
            humidity = entry.get('humidity', '')
            pressure = entry.get('pressure', '')
            wind_dir = entry.get('wind_direction', '')
            wind_speed = entry.get('wind_speed', '')

            parts = []
            if station:
                parts.append(f"WX: {station}")
            if temp:
                parts.append(f"{temp}°C")
            if humidity:
                parts.append(f"Humidity: {humidity}%")
            if pressure:
                parts.append(f"{pressure} mbar")
            if wind_dir and wind_speed:
                parts.append(f"Wind: {wind_speed} m/s @ {wind_dir}°")

            if parts:
                geo = " | ".join(parts)
                if geo not in self.results:
                    self.results[geo] = True
                    evt = SpiderFootEvent(
                        "GEOINFO", geo, self.__name__, event)
                    self.notifyListeners(evt)

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
            self.error("aprs.fi API key is not set.")
            self.errorState = True
            return

        search = val.strip()
        pause = self.opts.get('pause', 1.5)

        # aprs.fi only supports exact callsign/name lookups (no wildcard)
        # Use the value directly as a station name or callsign
        if self.opts.get('query_location', True):
            self._query_location(search, event)
            if self.errorState:
                return
            time.sleep(pause)

        if self.checkForStop():
            return

        if self.opts.get('query_weather', True):
            self._query_weather(search, event)
