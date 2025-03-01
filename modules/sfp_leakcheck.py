# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_leakcheck
# Purpose:     Gather breach data from LeakCheck API v2.
#
# Author:      <the@leakcheck.net>
#
# Created:     05-10-2024
# Copyright:   (c) LeakCheck Security Services LTD
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin

class sfp_leakcheck(SpiderFootPlugin):

    meta = {
        'name': "LeakCheck.io",
        'summary': "Gather breach data from LeakCheck API.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Leaks, Dumps and Breaches"],
        'dataSource': {
            'website': "https://leakcheck.io/",
            'model': "COMMERCIAL_ONLY",
            'references': [
                "https://wiki.leakcheck.io/en/api"
            ],
            'apiKeyInstructions': [
                "Visit https://leakcheck.io",
                "Register for an account",
                "Visit https://leakcheck.io/settings",
                "Create your API key there"
            ],
            'favIcon': "https://leakcheck.io/favicon.ico",
            'logo': "https://wiki.leakcheck.io/wiki.png",
            'description': "LeakCheck offers a search engine with a database of more than 9 billion leaked records. Users can search for leaked information using email addresses, usernames, phone numbers, keywords, and domain names. Our goal is to safeguard the data of people and companies."
        }
    }

    # Default options
    opts = {
        'api_key': '',
        'pause': 1
    }

    # Option descriptions
    optdescs = {
        'api_key': 'LeakCheck API key.',
        'pause': 'Number of seconds to wait between each API call.'
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return [
            "DOMAIN_NAME",
            "EMAILADDR",
            "PHONE_NUMBER",
        ]

    # What events this module produces
    def producedEvents(self):
        return [
            'EMAILADDR',
            'EMAILADDR_COMPROMISED',
            'USERNAME',
            'ACCOUNT_EXTERNAL_OWNED_COMPROMISED',
            'PHONE_NUMBER_COMPROMISED',
            'IP_ADDRESS',
            'DATE_HUMAN_DOB',
            'COUNTRY_NAME',
            'PASSWORD_COMPROMISED',
            'HUMAN_NAME',
            'GEOINFO',
            'RAW_RIR_DATA'
        ]

    # Query LeakCheck
    def query(self, event):
        if event.eventType == "EMAILADDR":
            queryString = f"https://leakcheck.io/api/v2/query/{event.data}?type=email"
        elif event.eventType == "DOMAIN_NAME":
            queryString = f"https://leakcheck.io/api/v2/query/{event.data}?type=domain"
        elif event.eventType == "PHONE_NUMBER":
            queryString = f"https://leakcheck.io/api/v2/query/{event.data.replace('+', '')}?type=phone"
        else:
            return None

        headers = {
            'Accept': 'application/json',
            'X-API-Key': self.opts['api_key']
        }

        res = self.sf.fetchUrl(queryString,
                               headers=headers,
                               timeout=15,
                               useragent=self.opts['_useragent'],
                               verify=True)

        time.sleep(self.opts['pause'])

        if res['code'] == "400":
            self.error("Invalid API credentials or request.")
            self.errorState = True
            return None

        if res['code'] == "401":
            self.error("Missing or incorrect API key.")
            self.errorState = True
            return None

        if res['code'] == "429":
            self.error("Too many requests performed in a short time. Please wait before trying again.")
            time.sleep(5)
            res = self.sf.fetchUrl(queryString, headers=headers, timeout=15, useragent=self.opts['_useragent'], verify=True)

        if res['code'] != "200":
            self.error("Unable to fetch data from LeakCheck.")
            self.errorState = True
            return None

        if res['content'] is None:
            self.debug('No response from LeakCheck')
            return None

        try:
            return json.loads(res['content'])
        except Exception as e:
            self.debug(f"Error processing JSON response: {e}")
            return None

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if srcModuleName == self.__name__:
            return

        if eventData in self.results:
            return

        if self.errorState:
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.opts['api_key'] == "":
            self.error("You enabled sfp_leakcheck but did not set an API key!")
            self.errorState = True
            return

        data = self.query(event)

        if not data:
            return

        if not data.get('found'):
            self.debug('No breach data found.')
            return

        for entry in data.get('result', []):
            email = entry.get('email')
            username = entry.get('username')
            phone = entry.get('phone')
            leakSource = entry.get('source', {}).get('name', 'N/A')
            breachDate = entry.get('source', {}).get('breach_date', 'Unknown Date')
            country = entry.get('country', None)
            ip_address = entry.get('ip', None)
            dob = entry.get('dob', None)
            password = entry.get('password', None)

            # Check for human name fields
            first_name = entry.get('first_name')
            last_name = entry.get('last_name')
            middle_name = entry.get('middle_name')
            name = entry.get('name')

            # Check for geoinfo fields
            zip_code = entry.get('zip')
            address = entry.get('address')
            location = entry.get('location')
            area = entry.get('area')
            city = entry.get('city')

            if email:
                if eventName == "EMAILADDR" and email == eventData:
                    evt = SpiderFootEvent('EMAILADDR_COMPROMISED', f"{email} [{leakSource} - {breachDate}]", self.__name__, event)
                    self.notifyListeners(evt)
                elif eventName == "DOMAIN_NAME":
                    pevent = SpiderFootEvent("EMAILADDR", email, self.__name__, event)
                    self.notifyListeners(pevent)

                    evt = SpiderFootEvent('EMAILADDR_COMPROMISED', f"{email} [{leakSource} - {breachDate}]", self.__name__, pevent)
                    self.notifyListeners(evt)

            if username:
                evt = SpiderFootEvent('ACCOUNT_EXTERNAL_OWNED_COMPROMISED', f"{username} [{leakSource} - {breachDate}]", self.__name__, event)
                self.notifyListeners(evt)

            if phone:
                evt = SpiderFootEvent('PHONE_NUMBER_COMPROMISED', f"{phone} [{leakSource} - {breachDate}]", self.__name__, event)
                self.notifyListeners(evt)

            if ip_address:
                evt = SpiderFootEvent('IP_ADDRESS', f"{ip_address} [{leakSource} - {breachDate}]", self.__name__, event)
                self.notifyListeners(evt)

            if dob:
                evt = SpiderFootEvent('DATE_HUMAN_DOB', f"{dob} [{leakSource} - {breachDate}]", self.__name__, event)
                self.notifyListeners(evt)

            if country:
                evt = SpiderFootEvent('COUNTRY_NAME', f"{country} [{leakSource} - {breachDate}]", self.__name__, event)
                self.notifyListeners(evt)

            if password:
                evt = SpiderFootEvent('PASSWORD_COMPROMISED', f"{password} [{leakSource} - {breachDate}]", self.__name__, event)
                self.notifyListeners(evt)

            # Produce HUMAN_NAME event if name-related fields are found
            if name or first_name or last_name or middle_name:
                full_name = ' '.join(filter(None, [name, first_name, middle_name, last_name]))
                evt = SpiderFootEvent('HUMAN_NAME', f"{full_name} [{leakSource} - {breachDate}]", self.__name__, event)
                self.notifyListeners(evt)

            # Produce GEOINFO event if geolocation-related fields are found
            geo_info = ', '.join(filter(None, [address, location, area, city, country, zip_code]))
            if geo_info:
                evt = SpiderFootEvent('GEOINFO', f"{geo_info} [{leakSource} - {breachDate}]", self.__name__, event)
                self.notifyListeners(evt)

            evt = SpiderFootEvent('RAW_RIR_DATA', str(entry), self.__name__, event)
            self.notifyListeners(evt)

# End of sfp_leakcheck class
