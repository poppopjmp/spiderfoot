# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:   sfp_checkphish
# Purpose:  Check URLs against CheckPhish API for phishing detection.
#
# Author:   Agostino Panico <van1sh@van1shland.io>
#
# Created:  01/02/2025
# Copyright:  (c) poppopjmp
# Licence:  MIT
# -------------------------------------------------------------------------------

import json
import time
import urllib.parse

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_checkphish(SpiderFootPlugin):

    meta = {
        'name': "CheckPhish",
        'summary': "Check URLs against the CheckPhish API for phishing detection.",
        'flags': ["apikey"],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://checkphish.ai/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://checkphish.ai/docs/checkphish-api/"
            ],
            'apiKeyInstructions': [
                "Visit https://checkphish.ai/",
                "Register for a free account",
                "Navigate to Dashboard > API",
                "Your API key is listed under 'API Key'"
            ],
            'favIcon': "https://checkphish.ai/assets/favicon-32x32.png",
            'logo': "https://checkphish.ai/assets/brand/logo-full-black.svg",
            'description': "CheckPhish is a deep learning-powered API for real-time phishing "
                          "detection and protection."
        }
    }

    # Default options
    opts = {
        'api_key': '',
        'wait_time': 10,
        'verify_ssl': True,
        'include_subdomains': True,
        'max_retry': 3
    }

    # Option descriptions
    optdescs = {
        'api_key': "CheckPhish API key.",
        'wait_time': "Seconds to wait between scan submission and result retrieval.",
        'verify_ssl': "Verify SSL certificates of target websites.",
        'include_subdomains': "Include subdomains in scans.",
        'max_retry': "Maximum number of retries for a scan result."
    }

    # Be sure to completely clear any class variables in setup()
    # or you risk data persisting between scan runs.
    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        
        # Override the options configurable by the user
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return [
            "DOMAIN_NAME",
            "INTERNET_NAME",
            "URL_UNSCOPED",
            "URL_MALICIOUS"
        ]

    # What events this module produces
    def producedEvents(self):
        return [
            "MALICIOUS_URL",
            "PHISHING_URL",
            "DOMAIN_REPUTATION",
            "RAW_RIR_DATA"
        ]

    def submitScan(self, url):
        """Submit a URL scan request to CheckPhish API."""
        if not self.opts['api_key']:
            self.error("You enabled sfp_checkphish but did not set an API key!")
            self.errorState = True
            return None

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.opts['api_key']
        }

        data = {
            "urlInfo": {
                "url": url
            },
            "scanType": "full"
        }
        
        if not self.opts['include_subdomains']:
            data["urlInfo"]["considerSubdomains"] = False

        res = self.sf.fetchUrl(
            "https://developers.checkphish.ai/api/neo/scan",
            timeout=30,
            useragent=self.opts.get('_useragent', "SpiderFoot"),
            headers=headers,
            postData=json.dumps(data)
        )

        if not res['content']:
            self.error("Empty response from CheckPhish API on submission.")
            return None

        try:
            submission_data = json.loads(res['content'])
            return submission_data
        except Exception as e:
            self.error(f"Error processing CheckPhish submission response: {e}")
            return None

    def getScanResults(self, job_id):
        """Get scan results from CheckPhish API."""
        if not self.opts['api_key']:
            return None

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.opts['api_key']
        }

        data = {
            "jobID": job_id,
            "insights": True
        }

        res = self.sf.fetchUrl(
            "https://developers.checkphish.ai/api/neo/scan/status",
            timeout=30,
            useragent=self.opts.get('_useragent', "SpiderFoot"),
            headers=headers,
            postData=json.dumps(data)
        )

        if not res['content']:
            self.error("Empty response from CheckPhish API on status check.")
            return None

        try:
            result_data = json.loads(res['content'])
            return result_data
        except Exception as e:
            self.error(f"Error processing CheckPhish status response: {e}")
            return None

    def normalizeDomain(self, domain):
        """Normalize domain name for URL creation."""
        if domain.lower().startswith('http://') or domain.lower().startswith('https://'):
            return domain
        return f"https://{domain}"

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        
        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if not self.opts['api_key']:
            self.error("You enabled sfp_checkphish but did not set an API key!")
            self.errorState = True
            return

        # Don't check the same URL twice
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return
            
        self.results[eventData] = True
        
        # Format URL based on event type
        scan_url = eventData
        if eventName in ["DOMAIN_NAME", "INTERNET_NAME"]:
            scan_url = self.normalizeDomain(eventData)
            
        # Submit the scan request to CheckPhish
        self.debug(f"Submitting scan for: {scan_url}")
        submission = self.submitScan(scan_url)
        
        if not submission:
            self.error(f"Failed to submit CheckPhish scan for {scan_url}")
            return
            
        if 'jobID' not in submission:
            self.error(f"No jobID received from CheckPhish for {scan_url}")
            self.debug(f"Response was: {submission}")
            return
            
        job_id = submission['jobID']
        self.debug(f"Scan submitted successfully with job ID: {job_id}")
        
        # Wait for the specified time before checking results
        time.sleep(self.opts['wait_time'])
        
        # Retrieve scan results
        retry_count = 0
        result = None
        
        while retry_count < self.opts['max_retry']:
            result = self.getScanResults(job_id)
            
            if not result:
                self.error(f"Failed to get CheckPhish results for {scan_url}")
                return
                
            status = result.get('status', 'UNKNOWN')
            
            # If the scan is complete, process the results
            if status == 'DONE':
                break
                
            # If the scan is still running, wait and retry
            if status == 'RUNNING':
                retry_count += 1
                self.debug(f"Scan still running. Retrying in {self.opts['wait_time']} seconds (attempt {retry_count}/{self.opts['max_retry']})")
                time.sleep(self.opts['wait_time'])
                continue
                
            # If the scan failed, log and return
            self.error(f"Scan failed with status: {status}")
            return
            
        # If we exhausted all retries and the scan is still running
        if not result or result.get('status') != 'DONE':
            self.error(f"Timed out waiting for CheckPhish results for {scan_url}")
            return
            
        # Output raw data for debugging and future use
        evt = SpiderFootEvent("RAW_RIR_DATA", json.dumps(result), self.__name__, event)
        self.notifyListeners(evt)
        
        # Process the results
        disposition = result.get('disposition', '')
        confidence = result.get('confidence', 0)
        brand = result.get('brand', 'unknown')
        
        # Generate events based on scan results
        if disposition == 'phishing':
            confidence_str = f"({confidence}% confidence)" if confidence else ""
            
            # Report as phishing URL
            phish_desc = f"CheckPhish identified {scan_url} as a phishing site {confidence_str}"
            if brand and brand != 'unknown':
                phish_desc += f" targeting {brand}"
                
            evt = SpiderFootEvent("PHISHING_URL", phish_desc, self.__name__, event)
            self.notifyListeners(evt)
            
            # Also report as generally malicious
            evt = SpiderFootEvent("MALICIOUS_URL", phish_desc, self.__name__, event)
            self.notifyListeners(evt)
            
        # For domain reputation (applies to domain events only)
        if eventName in ["DOMAIN_NAME", "INTERNET_NAME"]:
            rep_desc = f"CheckPhish disposition: {disposition.upper()}"
            if confidence:
                rep_desc += f" (confidence: {confidence}%)"
                
            evt = SpiderFootEvent("DOMAIN_REPUTATION", rep_desc, self.__name__, event)
            self.notifyListeners(evt)
