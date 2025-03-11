# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:   sfp_darksearch
# Purpose:  Search the Darksearch.io API for mentions of domain names and emails.
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


class sfp_darksearch(SpiderFootPlugin):
    meta = {
        "name": "Darksearch.io",
        "summary": "Search Darksearch.io for mentions of domain names and emails on the dark web.",
        "flags": ["apikey"],
        "useCases": ["Investigate", "Passive"],
        "categories": ["Search Engines"],
        "dataSource": {
            "website": "https://darksearch.io/",
            "model": "FREE_AUTH_LIMITED",
            "references": [
                "https://darksearch.io/apidocs",
                "https://darksearch.io/docs",
            ],
            "apiKeyInstructions": [
                "Visit https://darksearch.io/",
                "Register for a free account",
                "Navigate to API section",
                "Your API key will be provided after registration",
            ],
            "favIcon": "https://darksearch.io/favicon.ico",
            "logo": "https://darksearch.io/assets/img/logo.png",
            "description": "Darksearch.io is a search engine for Tor Hidden Services (onion sites). "
            "It allows you to find hidden services based on keywords or search terms.",
        },
    }

    # Default options
    opts = {
        "api_key": "",
        "max_pages": 10,
        "per_page": 20,
        "extract_emails": True,
        "extract_urls": True,
        "validate_certificates": False,  # Don't validate .onion SSL certificates
        "include_similar": True,
    }

    # Option descriptions
    optdescs = {
        "api_key": "Darksearch.io API key.",
        "max_pages": "Maximum number of pages of results to fetch.",
        "per_page": "Results per page (maximum 50).",
        "extract_emails": "Extract emails found in search results.",
        "extract_urls": "Extract URLs found in search results.",
        "validate_certificates": "Validate SSL certificates of onion sites (not recommended).",
        "include_similar": "Include similar domain results.",
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
        return ["DOMAIN_NAME", "EMAILADDR", "HUMAN_NAME", "COMPANY_NAME", "USERNAME"]

    # What events this module produces
    def producedEvents(self):
        return [
            "DARKNET_MENTION_URL",
            "DARKNET_MENTION_CONTENT",
            "EMAILADDR",
            "EMAILADDR_GENERIC",
            "DOMAIN_NAME",
            "LINKED_URL_INTERNAL",
            "RAW_RIR_DATA",
        ]

    def queryDarksearch(self, query, page=1):
        """Query the Darksearch.io API."""
        if not self.opts["api_key"]:
            self.error("You enabled sfp_darksearch but did not set an API key!")
            self.errorState = True
            return None

        headers = {
            "Authorization": f"Bearer {self.opts['api_key']}",
            "Content-Type": "application/json",
        }

        params = {"query": query, "page": page,
                  "limit": min(50, self.opts["per_page"])}

        url = f"https://api.darksearch.io/search?{urllib.parse.urlencode(params)}"

        res = self.sf.fetchUrl(
            url, headers=headers, timeout=30, useragent=self.opts["_useragent"]
        )

        if res["code"] == "401":
            self.error("Invalid Darksearch.io API key.")
            self.errorState = True
            return None

        if res["code"] == "429":
            self.error("Darksearch.io API rate limit exceeded.")
            time.sleep(3)  # Wait before next attempt
            return None

        if res["code"] not in ["200", "201"]:
            self.error(
                f"Unexpected HTTP response code {res['code']} from Darksearch.io."
            )
            self.errorState = True
            return None

        if not res["content"]:
            self.debug(f"No results found for {query} on Darksearch.io")
            return None

        try:
            data = json.loads(res["content"])
            return data
        except Exception as e:
            self.error(f"Error processing Darksearch.io response: {e}")
            return None

    def extractEmails(self, content):
        """Extract email addresses from content."""
        emails = self.sf.parseEmails(content)
        return list(set(emails))

    def extractUrls(self, content):
        """Extract URLs from content, including onion URLs."""
        # Use SpiderFoot's URL extraction and add regex for .onion URLs
        urls = self.sf.extractUrls(content)

        # Add additional regex for .onion URLs if needed
        onion_urls = self.sf.parseLinks(content, includeFilter=r"\.onion")

        return list(set(urls + onion_urls))

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if not self.opts["api_key"]:
            self.error("You enabled sfp_darksearch but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # Formulate query based on event type
        if eventName == "DOMAIN_NAME":
            query = f"domain:{eventData}"
        elif eventName == "EMAILADDR":
            query = f"email:{eventData}"
        else:
            # For other types, use as-is with quotes for exact matching
            query = f'"{eventData}"'

        # Include similar results option
        if self.opts["include_similar"] and eventName == "DOMAIN_NAME":
            similar_query = eventData.replace(".", " ")
            query = f"{query} OR {similar_query}"

        # Execute search across multiple pages
        page = 1
        total_results = []

        while page <= self.opts["max_pages"]:
            data = self.queryDarksearch(query, page)

            if not data or "results" not in data:
                break

            current_results = data.get("results", [])
            if not current_results:
                if page == 1:
                    self.debug(
                        f"No results found for {query} on Darksearch.io")
                break

            total_results.extend(current_results)

            # Check if this is the last page
            if len(current_results) < self.opts["per_page"]:
                break

            page += 1
            time.sleep(1)  # Be nice to the API

        if not total_results:
            return

        # Create raw RIR data event with all results
        evt = SpiderFootEvent(
            "RAW_RIR_DATA",
            json.dumps({"query": query, "results": total_results}),
            self.__name__,
            event,
        )
        self.notifyListeners(evt)

        # Process each result
        for result in total_results:
            onion_url = result.get("link")
            title = result.get("title", "No Title")
            snippet = result.get("snippet", "No snippet available")

            if not onion_url:
                continue

            # Report darknet mention URL
            url_evt = SpiderFootEvent(
                "DARKNET_MENTION_URL", f"{onion_url} [{title}]", self.__name__, event
            )
            self.notifyListeners(url_evt)

            # Report content snippet
            content_evt = SpiderFootEvent(
                "DARKNET_MENTION_CONTENT",
                f"Title: {title}\nURL: {onion_url}\nSnippet: {snippet}",
                self.__name__,
                event,
            )
            self.notifyListeners(content_evt)

            # Extract emails from title and snippet if configured
            if self.opts["extract_emails"]:
                content_to_check = f"{title} {snippet}"
                emails = self.extractEmails(content_to_check)

                for email in emails:
                    if self.sf.validEmail(email):
                        mail_domain = email.split("@")[1]
                        if mail_domain == eventData or self.getTarget().matches(
                            mail_domain
                        ):
                            evt_type = "EMAILADDR"
                        else:
                            evt_type = "EMAILADDR_GENERIC"

                        mail_evt = SpiderFootEvent(
                            evt_type, email, self.__name__, event
                        )
                        self.notifyListeners(mail_evt)

            # Extract URLs from snippet if configured
            if self.opts["extract_urls"]:
                urls = self.extractUrls(snippet)

                for url in urls:
                    if ".onion" not in url:  # Only interested in clearnet URLs
                        netloc = self.sf.urlFQDN(url)

                        # Report domain
                        if self.getTarget().matches(netloc):
                            dom_evt = SpiderFootEvent(
                                "LINKED_URL_INTERNAL", url, self.__name__, event
                            )
                            self.notifyListeners(dom_evt)

                        # Report discovered domain
                        if self.sf.isDomain(netloc, self.opts.get("_internettlds")):
                            dom_evt = SpiderFootEvent(
                                "DOMAIN_NAME", netloc, self.__name__, event
                            )
                            self.notifyListeners(dom_evt)
