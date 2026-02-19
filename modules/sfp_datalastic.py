from __future__ import annotations

"""SpiderFoot plug-in module: datalastic."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_datalastic
# Purpose:     Query Datalastic Maritime API for vessel tracking, specs,
#              port intelligence, casualties, ownership and inspections.
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


class sfp_datalastic(SpiderFootModernPlugin):

    """Query Datalastic for maritime vessel tracking, specs, ports and intelligence."""

    meta = {
        'name': "Datalastic Maritime",
        'summary': (
            "Query Datalastic API for real-time vessel tracking, vessel specs, "
            "port intelligence, ship casualties, ownership and inspections."
        ),
        'flags': ["apikey"],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://datalastic.com/",
            'model': "COMMERCIAL_ONLY",
            'references': [
                "https://datalastic.com/api-reference/",
            ],
            'favIcon': "https://datalastic.com/favicon.ico",
            'logo': "https://datalastic.com/wp-content/uploads/2021/11/logo.svg",
            'description': (
                "Datalastic provides a comprehensive maritime API covering "
                "1,000,000+ vessels and 22,000+ ports globally. Endpoints "
                "include real-time vessel tracking, vessel finder, ship specs, "
                "port data, historical positions, casualty reports, ownership, "
                "inspections, and classification data."
            ),
        }
    }

    opts = {
        'api_key': "",
        'max_results': 25,
        'enable_vessel_find': True,
        'enable_vessel_info': True,
        'enable_port_find': True,
        'enable_casualty': True,
        'enable_ownership': True,
        'pause': 1.0,
    }

    optdescs = {
        'api_key': "Datalastic API key.",
        'max_results': "Maximum number of results to process per query.",
        'enable_vessel_find': "Search for vessels by name?",
        'enable_vessel_info': "Retrieve detailed vessel specifications?",
        'enable_port_find': "Search for maritime ports?",
        'enable_casualty': "Retrieve ship casualty reports?",
        'enable_ownership': "Retrieve vessel ownership data?",
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
            "COUNTRY_NAME",
        ]

    # ── Helpers ───────────────────────────────────────────────────
    def _api_get(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Call Datalastic REST API and return parsed JSON or None."""
        if self.errorState:
            return None

        api_key = self.opts.get('api_key', '')
        if not api_key:
            self.error("Datalastic API key is not set.")
            self.errorState = True
            return None

        base = "https://api.datalastic.com/api/v0"
        qparams = f"api-key={api_key}"
        if params:
            for k, v in params.items():
                qparams += f"&{k}={v}"

        url = f"{base}/{endpoint}?{qparams}"
        res = self.fetch_url(url, timeout=30)

        if not res:
            self.error(f"Datalastic: No response from {endpoint}")
            return None

        if res['code'] not in ['200', 200]:
            self.error(f"Datalastic: HTTP {res['code']} from {endpoint}")
            if res['code'] in ['401', 401, '403', 403]:
                self.errorState = True
            if res['code'] in ['429', 429]:
                self.error("Datalastic: Rate limit exceeded (600 req/min).")
            return None

        try:
            data = json.loads(res['content'])
        except (json.JSONDecodeError, TypeError):
            self.error(f"Datalastic: Invalid JSON from {endpoint}")
            return None

        meta = data.get('meta', {})
        if not meta.get('success', True):
            self.error(f"Datalastic: API error on {endpoint}")
            return None

        return data

    # ── Query methods ─────────────────────────────────────────────
    def _query_vessel_find(self, search_name: str, event: SpiderFootEvent) -> list[dict]:
        """Search vessels by name using the vessel_find endpoint. Returns found vessels."""
        params = {
            'name': search_name,
            'fuzzy': '1',
        }
        data = self._api_get("vessel_find", params)
        if not data:
            return []

        vessels = data.get('data', [])
        if not isinstance(vessels, list):
            return []

        max_results = self.opts.get('max_results', 25)
        found = []

        for vessel in vessels[:max_results]:
            if self.checkForStop():
                break

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(vessel, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

            # Extract key fields
            name = vessel.get('name', '')
            mmsi = vessel.get('mmsi', '')
            imo = vessel.get('imo', '')
            country = vessel.get('country_name', '')
            vtype = vessel.get('type', '')
            vsubtype = vessel.get('type_specific', '')
            home_port = vessel.get('home_port', '')
            length = vessel.get('length', '')
            breadth = vessel.get('breadth', '')
            year = vessel.get('year_built', '')

            # GeoInfo: vessel summary
            parts = []
            if name:
                parts.append(name)
            if vtype:
                t = vtype
                if vsubtype:
                    t += f" / {vsubtype}"
                parts.append(t)
            if country:
                parts.append(f"Flag: {country}")
            if home_port:
                parts.append(f"Port: {home_port}")

            if parts:
                geo = " | ".join(parts)
                if geo not in self.results:
                    self.results[geo] = True
                    g_evt = SpiderFootEvent(
                        "GEOINFO", geo, self.__name__, event)
                    self.notifyListeners(g_evt)

            if country and country not in self.results:
                self.results[country] = True
                c_evt = SpiderFootEvent(
                    "COUNTRY_NAME", country, self.__name__, event)
                self.notifyListeners(c_evt)

            found.append(vessel)

        return found

    def _query_vessel_tracking(self, vessel_id: dict, event: SpiderFootEvent) -> None:
        """Get live tracking for a single vessel by MMSI or IMO."""
        mmsi = vessel_id.get('mmsi', '')
        imo = vessel_id.get('imo', '')

        params = {}
        if mmsi:
            params['mmsi'] = mmsi
        elif imo:
            params['imo'] = imo
        else:
            return

        data = self._api_get("vessel", params)
        if not data or 'data' not in data:
            return

        vessel = data['data']

        evt = SpiderFootEvent(
            "RAW_RIR_DATA", json.dumps(vessel, indent=2),
            self.__name__, event)
        self.notifyListeners(evt)

        lat = vessel.get('lat')
        lon = vessel.get('lon')
        if lat is not None and lon is not None:
            coords = f"{lat},{lon}"
            if coords not in self.results:
                self.results[coords] = True
                evt = SpiderFootEvent(
                    "PHYSICAL_COORDINATES", coords,
                    self.__name__, event)
                self.notifyListeners(evt)

        dest = vessel.get('destination', '')
        name = vessel.get('name', '')
        speed = vessel.get('speed', '')
        nav = vessel.get('navigational_status', '')

        parts = []
        if name:
            parts.append(name)
        if dest:
            parts.append(f"→ {dest}")
        if speed:
            parts.append(f"{speed} kts")
        if nav:
            parts.append(nav)
        if parts:
            geo = " | ".join(parts)
            if geo not in self.results:
                self.results[geo] = True
                evt = SpiderFootEvent(
                    "GEOINFO", geo, self.__name__, event)
                self.notifyListeners(evt)

    def _query_vessel_info(self, vessel_id: dict, event: SpiderFootEvent) -> None:
        """Get detailed vessel specifications by MMSI or IMO."""
        mmsi = vessel_id.get('mmsi', '')
        imo = vessel_id.get('imo', '')

        params = {}
        if mmsi:
            params['mmsi'] = mmsi
        elif imo:
            params['imo'] = imo
        else:
            return

        data = self._api_get("vessel_info", params)
        if not data or 'data' not in data:
            return

        info = data['data']

        evt = SpiderFootEvent(
            "RAW_RIR_DATA", json.dumps(info, indent=2),
            self.__name__, event)
        self.notifyListeners(evt)

    def _query_port_find(self, search_name: str, event: SpiderFootEvent) -> None:
        """Search maritime ports by name."""
        params = {
            'name': search_name,
            'fuzzy': '1',
        }
        data = self._api_get("port_find", params)
        if not data:
            return

        ports = data.get('data', [])
        if not isinstance(ports, list):
            return

        for port in ports[:self.opts.get('max_results', 25)]:
            if self.checkForStop():
                return

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(port, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

            name = port.get('name', '')
            country = port.get('country_name', '')
            lat = port.get('lat')
            lon = port.get('lon')
            port_type = port.get('port_type', '')

            if lat is not None and lon is not None:
                coords = f"{lat},{lon}"
                if coords not in self.results:
                    self.results[coords] = True
                    evt = SpiderFootEvent(
                        "PHYSICAL_COORDINATES", coords,
                        self.__name__, event)
                    self.notifyListeners(evt)

            parts = [p for p in (name, port_type, country) if p]
            if parts:
                geo = ", ".join(parts)
                if geo not in self.results:
                    self.results[geo] = True
                    evt = SpiderFootEvent(
                        "GEOINFO", geo, self.__name__, event)
                    self.notifyListeners(evt)

    def _query_casualty(self, search_name: str, event: SpiderFootEvent) -> None:
        """Search ship casualty records by vessel name."""
        data = self._api_get("maritime_reports/casualty", {'name': search_name})
        if not data:
            return

        records = data.get('data', [])
        if not isinstance(records, list):
            return

        for rec in records[:self.opts.get('max_results', 25)]:
            if self.checkForStop():
                return

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(rec, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

    def _query_ownership(self, search_name: str, event: SpiderFootEvent) -> None:
        """Search vessel ownership records."""
        data = self._api_get("maritime_reports/ownership", {'beneficial_owner': search_name})
        if not data:
            return

        records = data.get('data', [])
        if not isinstance(records, list):
            return

        for rec in records[:self.opts.get('max_results', 25)]:
            if self.checkForStop():
                return

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(rec, indent=2),
                self.__name__, event)
            self.notifyListeners(evt)

            owner = rec.get('beneficial_owner', '')
            if owner and owner not in self.results:
                self.results[owner] = True
                evt = SpiderFootEvent(
                    "COMPANY_NAME", owner, self.__name__, event)
                self.notifyListeners(evt)

            operator = rec.get('operator', '')
            if operator and operator not in self.results:
                self.results[operator] = True
                evt = SpiderFootEvent(
                    "COMPANY_NAME", operator, self.__name__, event)
                self.notifyListeners(evt)

            country = rec.get('beneficial_owner_country', '')
            if country and country not in self.results:
                self.results[country] = True
                evt = SpiderFootEvent(
                    "COUNTRY_NAME", country, self.__name__, event)
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
            self.error("Datalastic API key is not set.")
            self.errorState = True
            return

        search = val.strip()
        pause = self.opts.get('pause', 1.0)

        # ── Vessel search ─────────────────────────────────────────
        if self.opts.get('enable_vessel_find') and src in (
            "COMPANY_NAME", "INTERNET_NAME", "DOMAIN_NAME"
        ):
            vessels = self._query_vessel_find(search, event)
            if self.errorState:
                return
            time.sleep(pause)

            # For the first found vessel, get live tracking + specs
            if vessels:
                first = vessels[0]
                vid = {
                    'mmsi': first.get('mmsi', ''),
                    'imo': first.get('imo', ''),
                }

                self._query_vessel_tracking(vid, event)
                if self.errorState:
                    return
                time.sleep(pause)

                if self.opts.get('enable_vessel_info'):
                    self._query_vessel_info(vid, event)
                    if self.errorState:
                        return
                    time.sleep(pause)

            if self.checkForStop():
                return

        # ── Port search ───────────────────────────────────────────
        if self.opts.get('enable_port_find') and src in (
            "GEOINFO", "COUNTRY_NAME"
        ):
            self._query_port_find(search, event)
            if self.errorState:
                return
            time.sleep(pause)

        if self.checkForStop():
            return

        # ── Casualty search ───────────────────────────────────────
        if self.opts.get('enable_casualty') and src == "COMPANY_NAME":
            self._query_casualty(search, event)
            if self.errorState:
                return
            time.sleep(pause)

        if self.checkForStop():
            return

        # ── Ownership search ──────────────────────────────────────
        if self.opts.get('enable_ownership') and src == "COMPANY_NAME":
            self._query_ownership(search, event)
