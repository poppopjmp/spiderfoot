from __future__ import annotations

"""SpiderFoot plug-in module: Bug Bounty scope and target importer.

Fetches in-scope targets from bug bounty platforms (HackerOne, Bugcrowd,
Intigriti) so SpiderFoot can automatically limit scans to valid scope.

Produces INTERNET_NAME, DOMAIN_NAME, IP_ADDRESS, and NETBLOCK_OWNER
events based on the program's asset scope definitions. Also produces
RAW_RIR_DATA with the full scope JSON from the bounty platform.

Event flow:
  IN:  ROOT (scan start — one-shot enrichment)
  OUT: INTERNET_NAME, DOMAIN_NAME, IP_ADDRESS, NETBLOCK_OWNER, RAW_RIR_DATA
"""

import json
import re
import time
from ipaddress import ip_network

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_bugbounty(SpiderFootAsyncPlugin):
    """Bug Bounty Scope — Import in-scope targets from HackerOne, Bugcrowd, and Intigriti."""

    meta = {
        'name': "Bug Bounty Scope Importer",
        'summary': "Import in-scope targets from bug bounty platforms (HackerOne, Bugcrowd, Intigriti) to validate scan scope.",
        'flags': ["apikey"],
        'useCases': ["Passive", "Footprint"],
        'categories': ["Public Registries"],
        'dataSource': {
            'website': "https://www.hackerone.com/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://api.hackerone.com/",
                "https://docs.bugcrowd.com/",
                "https://kb.intigriti.com/",
            ],
            'description': "Import targets from bug bounty platforms to ensure your scans "
            "stay within the defined program scope. Supports HackerOne, Bugcrowd, "
            "and Intigriti public/private programs.",
            'apiKeyInstructions': [
                "For HackerOne: create an API token at https://hackerone.com/settings/api_token/edit",
                "For Bugcrowd: create an API token in account settings",
                "For Intigriti: create an API token in account settings",
                "Enter the relevant token in the corresponding option",
            ],
        },
    }

    opts = {
        'platform': 'hackerone',          # hackerone, bugcrowd, intigriti
        'program_handle': '',
        'hackerone_api_user': '',
        'hackerone_api_token': '',
        'bugcrowd_api_token': '',
        'intigriti_api_token': '',
        'include_out_of_scope': False,
        'import_wildcards': True,
    }

    optdescs = {
        'platform': "Bug bounty platform: 'hackerone', 'bugcrowd', or 'intigriti'.",
        'program_handle': "Program handle/slug on the bug bounty platform.",
        'hackerone_api_user': "HackerOne API username.",
        'hackerone_api_token': "HackerOne API token.",
        'bugcrowd_api_token': "Bugcrowd API token.",
        'intigriti_api_token': "Intigriti API token (Bearer).",
        'include_out_of_scope': "Include out-of-scope assets for awareness.",
        'import_wildcards': "Expand wildcard domains (e.g. *.example.com → example.com).",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return [
            "INTERNET_NAME",
            "DOMAIN_NAME",
            "IP_ADDRESS",
            "NETBLOCK_OWNER",
            "RAW_RIR_DATA",
        ]

    # ---------------------------------------------------------------
    # Platform API methods
    # ---------------------------------------------------------------

    def _fetch_hackerone_scope(self) -> list[dict]:
        """Fetch scope from HackerOne API v1."""
        handle = self.opts.get('program_handle', '')
        api_user = self.opts.get('hackerone_api_user', '')
        api_token = self.opts.get('hackerone_api_token', '')

        if not all([handle, api_user, api_token]):
            self.error("HackerOne requires program_handle, api_user, and api_token")
            return []

        import base64
        auth = base64.b64encode(f"{api_user}:{api_token}".encode()).decode()

        url = f"https://api.hackerone.com/v1/hackers/programs/{handle}"
        res = self.fetch_url(
            url,
            timeout=30,
            useragent="SpiderFoot",
            headers={
                "Authorization": f"Basic {auth}",
                "Accept": "application/json",
            },
        )

        if not res or not res.get('content'):
            self.error(f"HackerOne API returned empty response for '{handle}'")
            return []

        try:
            data = json.loads(res['content'])
        except json.JSONDecodeError:
            self.error("Failed to parse HackerOne response")
            return []

        assets = []
        relationships = data.get('relationships', {})
        structured_scopes = relationships.get('structured_scopes', {}).get('data', [])

        for scope in structured_scopes:
            attrs = scope.get('attributes', {})
            assets.append({
                'identifier': attrs.get('asset_identifier', ''),
                'type': attrs.get('asset_type', ''),
                'eligible': attrs.get('eligible_for_bounty', False),
                'eligible_for_submission': attrs.get('eligible_for_submission', True),
                'instruction': attrs.get('instruction', ''),
                'max_severity': attrs.get('max_severity', ''),
            })

        return assets

    def _fetch_bugcrowd_scope(self) -> list[dict]:
        """Fetch scope from Bugcrowd API."""
        handle = self.opts.get('program_handle', '')
        token = self.opts.get('bugcrowd_api_token', '')

        if not all([handle, token]):
            self.error("Bugcrowd requires program_handle and bugcrowd_api_token")
            return []

        url = f"https://api.bugcrowd.com/programs/{handle}/target_groups"
        res = self.fetch_url(
            url,
            timeout=30,
            useragent="SpiderFoot",
            headers={
                "Authorization": f"Token {token}",
                "Accept": "application/vnd.bugcrowd+json",
            },
        )

        if not res or not res.get('content'):
            self.error(f"Bugcrowd API returned empty response for '{handle}'")
            return []

        try:
            data = json.loads(res['content'])
        except json.JSONDecodeError:
            self.error("Failed to parse Bugcrowd response")
            return []

        assets = []
        for group in data.get('data', []):
            targets = group.get('relationships', {}).get('targets', {}).get('data', [])
            for target in targets:
                attrs = target.get('attributes', {})
                assets.append({
                    'identifier': attrs.get('name', attrs.get('uri', '')),
                    'type': attrs.get('category', ''),
                    'eligible': attrs.get('in_scope', True),
                    'eligible_for_submission': True,
                })

        return assets

    def _fetch_intigriti_scope(self) -> list[dict]:
        """Fetch scope from Intigriti API."""
        handle = self.opts.get('program_handle', '')
        token = self.opts.get('intigriti_api_token', '')

        if not all([handle, token]):
            self.error("Intigriti requires program_handle and intigriti_api_token")
            return []

        url = f"https://api.intigriti.com/core/researcher/programs/{handle}"
        res = self.fetch_url(
            url,
            timeout=30,
            useragent="SpiderFoot",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )

        if not res or not res.get('content'):
            self.error(f"Intigriti API returned empty response for '{handle}'")
            return []

        try:
            data = json.loads(res['content'])
        except json.JSONDecodeError:
            self.error("Failed to parse Intigriti response")
            return []

        assets = []
        domains = data.get('domains', [])
        for domain in domains:
            assets.append({
                'identifier': domain.get('endpoint', ''),
                'type': domain.get('type', {}).get('value', 'url'),
                'eligible': domain.get('tier', {}).get('value', 0) > 0,
                'eligible_for_submission': True,
            })

        return assets

    # ---------------------------------------------------------------
    # Asset classification
    # ---------------------------------------------------------------

    def _classify_asset(self, identifier: str) -> tuple[str, str]:
        """Classify an asset identifier into a SpiderFoot event type.

        Returns:
            (event_type, cleaned_value)
        """
        identifier = identifier.strip()

        # Wildcard domain: *.example.com
        if identifier.startswith('*.'):
            base = identifier[2:]
            if self.opts.get('import_wildcards', True):
                return "DOMAIN_NAME", base
            return "", ""

        # IP CIDR: 10.0.0.0/24
        if '/' in identifier:
            try:
                net = ip_network(identifier, strict=False)
                return "NETBLOCK_OWNER", str(net)
            except ValueError:
                pass

        # IP address
        ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
        if ip_pattern.match(identifier):
            return "IP_ADDRESS", identifier

        # URL → extract domain
        url_pattern = re.compile(r'^https?://([^/:]+)')
        url_match = url_pattern.match(identifier)
        if url_match:
            return "INTERNET_NAME", url_match.group(1)

        # Domain/hostname
        domain_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$')
        if domain_pattern.match(identifier):
            # Check if it's a base domain or subdomain
            parts = identifier.split('.')
            if len(parts) == 2:
                return "DOMAIN_NAME", identifier
            return "INTERNET_NAME", identifier

        return "", ""

    # ---------------------------------------------------------------
    # Event handling
    # ---------------------------------------------------------------

    def handleEvent(self, event):
        """Handle ROOT event — import bug bounty scope."""
        if self.errorState:
            return

        program = self.opts.get('program_handle', '')
        if not program:
            self.error("No program_handle configured")
            self.errorState = True
            return

        if program in self.results:
            return
        self.results[program] = True

        platform = self.opts.get('platform', 'hackerone').lower()
        self.info(f"Fetching scope from {platform} program '{program}'")

        # Fetch scope from the selected platform
        if platform == 'hackerone':
            assets = self._fetch_hackerone_scope()
        elif platform == 'bugcrowd':
            assets = self._fetch_bugcrowd_scope()
        elif platform == 'intigriti':
            assets = self._fetch_intigriti_scope()
        else:
            self.error(f"Unsupported platform: {platform}")
            self.errorState = True
            return

        if not assets:
            self.info(f"No assets found for program '{program}'")
            return

        # Emit raw scope data
        raw_event = SpiderFootEvent(
            "RAW_RIR_DATA",
            json.dumps({"platform": platform, "program": program, "assets": assets}, indent=2),
            self.__name__, event,
        )
        self.notifyListeners(raw_event)

        # Process assets
        imported = 0
        for asset in assets:
            if self.checkForStop():
                return

            identifier = asset.get('identifier', '')
            eligible = asset.get('eligible_for_submission', True)

            # Skip out-of-scope unless opted in
            if not eligible and not self.opts.get('include_out_of_scope', False):
                continue

            event_type, value = self._classify_asset(identifier)
            if not event_type or not value:
                self.debug(f"Unrecognized asset: {identifier}")
                continue

            if value in self.results:
                continue
            self.results[value] = True

            evt = SpiderFootEvent(event_type, value, self.__name__, event)
            self.notifyListeners(evt)
            imported += 1

        self.info(f"Imported {imported} assets from {platform} program '{program}'")
