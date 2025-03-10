# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:   sfp_hibp
# Purpose:  Query the Have I Been Pwned (HIBP) API to see if an email has been compromised.
#
# Author:   Agostino Panico <van1sh@van1shland.io>
#
# Created:  01/02/2025
# Copyright:  (c) poppopjmp
# Licence:  MIT
# -------------------------------------------------------------------------------

import json
import time
from datetime import datetime

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_hibp(SpiderFootPlugin):

    meta = {
        'name': "Have I Been Pwned",
        'summary': "Check Have I Been Pwned for email address breaches.",
        'flags': ["apikey"],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Leaks, Dumps and Breaches"],
        'dataSource': {
            'website': "https://haveibeenpwned.com/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://haveibeenpwned.com/API/v3",
                "https://haveibeenpwned.com/FAQs"
            ],
            'apiKeyInstructions': [
                "Visit https://haveibeenpwned.com/API/Key",
                "Purchase an API key",
                "The API key will be provided after purchase"
            ],
            'favIcon': "https://haveibeenpwned.com/favicon.ico",
            'logo': "https://haveibeenpwned.com/Content/Images/SocialLogo.png",
            'description': "Check if your email or phone is in a data breach. "
                          "Have I Been Pwned allows you to search across multiple data breaches "
                          "to see if your email address or phone number has been compromised."
        }
    }

    # Default options
    opts = {
        'api_key': '',
        'check_breaches': True,
        'check_pastes': True,
        'max_age_days': 0,  # 0 = no limit
        'sleep': 5,
        'check_domain': True,
        'max_domain_breaches': 100
    }

    # Option descriptions
    optdescs = {
        'api_key': "Have I Been Pwned API key.",
        'check_breaches': "Check email breach database.",
        'check_pastes': "Check pastes for emails.",
        'max_age_days': "Maximum age of breaches to consider (0 = unlimited).",
        'sleep': "Seconds to sleep between API requests.",
        'check_domain': "Check entire domain breach data.",
        'max_domain_breaches': "Maximum number of breaches to retrieve for a domain."
    }

    # Be sure to completely clear any class variables in setup()
    # or you risk data persisting between scan runs.
    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.errorState = False

        # Clear / reset any other class member variables here
        # or you risk them persisting between threads.

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["EMAILADDR", "DOMAIN_NAME"]

    # What events this module produces
    def producedEvents(self):
        return [
            "RAW_RIR_DATA", 
            "EMAILADDR_COMPROMISED",
            "DOMAIN_COMPROMISED", 
            "LEAKSITE_CONTENT", 
            "LEAKSITE_URL",
            "PASSWORD_COMPROMISED"
        ]

    def queryHibp(self, email, check_type="breachedaccount"):
        """Query the Have I Been Pwned API."""
        if not self.opts['api_key']:
            self.error("You enabled sfp_hibp but did not set an API key!")
            self.errorState = True
            return None

        headers = {
            'hibp-api-key': self.opts['api_key'],
            'user-agent': self.opts.get('_useragent', "SpiderFoot")
        }

        url = f"https://haveibeenpwned.com/api/v3/{check_type}/{email}"
        
        # Add truncate query parameter to get all results
        if check_type == "breachedaccount":
            url += "?truncateResponse=false"
        
        res = self.sf.fetchUrl(
            url,
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts.get('_useragent', "SpiderFoot"),
            headers=headers
        )
        
        # Handle rate limiting
        if res['code'] == "429":
            self.error("Have I Been Pwned rate limit exceeded")
            time.sleep(self.opts['sleep'])  # Sleep and don't retry on rate limit
            return None
            
        # Handle errors
        if res['code'] in ["401", "403"]:
            self.error("Invalid Have I Been Pwned API key or permission denied")
            self.errorState = True
            return None
            
        # If not found
        if res['code'] == "404":
            self.debug(f"No {check_type} results found for {email}")
            return []
            
        # If unexpected response
        if res['code'] != "200":
            self.error(f"Unexpected HTTP response code {res['code']} from Have I Been Pwned")
            self.errorState = True
            return None

        # Parse the response
        if not res['content']:
            self.debug(f"No {check_type} data received from Have I Been Pwned")
            return []
            
        try:
            data = json.loads(res['content'])
            return data
        except Exception as e:
            self.error(f"Error processing JSON response from Have I Been Pwned: {e}")
            return None

    def queryDomainBreaches(self, domain):
        """Query the Have I Been Pwned domain breach API."""
        if not self.opts['api_key']:
            self.error("You enabled sfp_hibp but did not set an API key!")
            self.errorState = True
            return None
            
        headers = {
            'hibp-api-key': self.opts['api_key'],
            'user-agent': self.opts.get('_useragent', "SpiderFoot")
        }

        url = f"https://haveibeenpwned.com/api/v3/breacheddomain/{domain}"
        
        res = self.sf.fetchUrl(
            url,
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts.get('_useragent', "SpiderFoot"),
            headers=headers
        )
        
        # Handle rate limiting
        if res['code'] == "429":
            self.error("Have I Been Pwned rate limit exceeded")
            time.sleep(self.opts['sleep'])
            return None
            
        # Handle errors
        if res['code'] in ["401", "403"]:
            self.error("Invalid Have I Been Pwned API key or permission denied")
            self.errorState = True
            return None
            
        # If not found
        if res['code'] == "404":
            self.debug(f"No domain breach results found for {domain}")
            return []
            
        # If unexpected response
        if res['code'] != "200":
            self.error(f"Unexpected HTTP response code {res['code']} from Have I Been Pwned")
            self.errorState = True
            return None

        # Parse the response
        if not res['content']:
            self.debug(f"No domain breach data received from Have I Been Pwned")
            return []
            
        try:
            data = json.loads(res['content'])
            return data
        except Exception as e:
            self.error(f"Error processing JSON response from Have I Been Pwned: {e}")
            return None

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        # Don't check the same email/domain twice
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return
            
        self.results[eventData] = True

        # Handle email addresses
        if eventName == "EMAILADDR" and self.opts['check_breaches']:
            self.debug(f"Checking email address {eventData} against HIBP")
            
            # Check breaches for the email
            if self.opts['check_breaches']:
                breaches = self.queryHibp(eventData, 'breachedaccount')
                
                if breaches is None:
                    return
                    
                if len(breaches) > 0:
                    # Create raw RIR data event
                    evt = SpiderFootEvent(
                        "RAW_RIR_DATA",
                        json.dumps({'type': 'breaches', 'data': breaches}),
                        self.__name__,
                        event
                    )
                    self.notifyListeners(evt)
                    
                    # Process each breach
                    for breach in breaches:
                        breach_name = breach.get('Name', 'Unknown')
                        breach_date = breach.get('BreachDate', 'Unknown')
                        breach_domain = breach.get('Domain', 'Unknown')
                        
                        # Skip old breaches if configured
                        if self.opts['max_age_days'] > 0 and breach_date != 'Unknown':
                            try:
                                breach_date_obj = datetime.strptime(breach_date, '%Y-%m-%d')
                                age_days = (datetime.now() - breach_date_obj).days
                                if age_days > self.opts['max_age_days']:
                                    self.debug(f"Skipping breach {breach_name} due to age ({age_days} days)")
                                    continue
                            except Exception:
                                pass  # If date parsing fails, include the breach anyway
                        
                        # Check for password compromise
                        if breach.get('DataClasses') and 'Passwords' in breach.get('DataClasses'):
                            evt = SpiderFootEvent(
                                "PASSWORD_COMPROMISED",
                                f"Password potentially compromised in {breach_name} breach ({breach_date})",
                                self.__name__,
                                event
                            )
                            self.notifyListeners(evt)
                        
                        # Create compromised email event
                        evt = SpiderFootEvent(
                            "EMAILADDR_COMPROMISED",
                            f"HIBP: {eventData} compromised in {breach_name} breach ({breach_date})",
                            self.__name__,
                            event
                        )
                        self.notifyListeners(evt)
                        
                        # Create leak site URL event if available
                        if breach.get('Domain'):
                            evt = SpiderFootEvent(
                                "LEAKSITE_URL",
                                f"https://{breach.get('Domain')}",
                                self.__name__,
                                event
                            )
                            self.notifyListeners(evt)
                        
                        # Create leak site content event with breach details
                        content = f"Breach Name: {breach_name}\n"
                        content += f"Breach Date: {breach_date}\n"
                        content += f"Domain: {breach_domain}\n"
                        
                        if breach.get('Description'):
                            content += f"Description: {breach.get('Description')}\n"
                            
                        if breach.get('DataClasses'):
                            content += f"Data Classes: {', '.join(breach.get('DataClasses'))}\n"
                            
                        evt = SpiderFootEvent(
                            "LEAKSITE_CONTENT",
                            content,
                            self.__name__,
                            event
                        )
                        self.notifyListeners(evt)
            
            # Check pastes for the email
            if self.opts['check_pastes']:
                pastes = self.queryHibp(eventData, 'pasteaccount')
                
                if pastes is None:
                    return
                    
                if len(pastes) > 0:
                    # Create raw RIR data event for pastes
                    evt = SpiderFootEvent(
                        "RAW_RIR_DATA",
                        json.dumps({'type': 'pastes', 'data': pastes}),
                        self.__name__,
                        event
                    )
                    self.notifyListeners(evt)
                    
                    # Process each paste
                    for paste in pastes:
                        paste_id = paste.get('Id', 'Unknown')
                        paste_source = paste.get('Source', 'Unknown')
                        paste_date = paste.get('Date', 'Unknown')
                        
                        # Create compromised email event for paste
                        evt = SpiderFootEvent(
                            "EMAILADDR_COMPROMISED",
                            f"HIBP: {eventData} found in paste {paste_id} from {paste_source} ({paste_date})",
                            self.__name__,
                            event
                        )
                        self.notifyListeners(evt)
                        
                        # Create leak site URL event if available
                        if paste.get('Source') and paste.get('Id'):
                            if paste['Source'] == 'Pastebin':
                                url = f"https://pastebin.com/{paste['Id']}"
                            else:
                                url = f"{paste['Source']}/{paste['Id']}"
                                
                            evt = SpiderFootEvent(
                                "LEAKSITE_URL",
                                url,
                                self.__name__,
                                event
                            )
                            self.notifyListeners(evt)
            
            # Be nice to the HIBP API
            time.sleep(self.opts['sleep'])
                
        # Handle domain names
        elif eventName == "DOMAIN_NAME" and self.opts['check_domain']:
            self.debug(f"Checking domain {eventData} against HIBP")
            
            domain_breaches = self.queryDomainBreaches(eventData)
            
            if domain_breaches is None:
                return
                
            breach_count = len(domain_breaches)
                
            if breach_count > 0:
                # Limit the number of breaches if needed
                if self.opts['max_domain_breaches'] > 0 and breach_count > self.opts['max_domain_breaches']:
                    domain_breaches = domain_breaches[:self.opts['max_domain_breaches']]
                
                # Create raw RIR data event for domain breaches
                evt = SpiderFootEvent(
                    "RAW_RIR_DATA",
                    json.dumps({'type': 'domain_breaches', 'data': domain_breaches}),
                    self.__name__,
                    event
                )
                self.notifyListeners(evt)
                
                # Create domain compromised event with summary
                evt = SpiderFootEvent(
                    "DOMAIN_COMPROMISED",
                    f"HIBP: {eventData} found in {breach_count} breach(es)",
                    self.__name__,
                    event
                )
                self.notifyListeners(evt)
                
                # Process breach details if available
                for breach in domain_breaches[:self.opts['max_domain_breaches']]:
                    breach_name = breach.get('Name', 'Unknown')
                    breach_date = breach.get('BreachDate', 'Unknown')
                    
                    # Create leak site content event with breach details
                    content = f"Domain Breach: {eventData}\n"
                    content += f"Breach Name: {breach_name}\n"
                    content += f"Breach Date: {breach_date}\n"
                    
                    if breach.get('Description'):
                        content += f"Description: {breach.get('Description')}\n"
                        
                    if breach.get('DataClasses'):
                        content += f"Data Compromised: {', '.join(breach.get('DataClasses'))}\n"
                        
                    evt = SpiderFootEvent(
                        "LEAKSITE_CONTENT",
                        content,
                        self.__name__,
                        event
                    )
                    self.notifyListeners(evt)
                    
            # Be nice to the HIBP API
            time.sleep(self.opts['sleep'])
